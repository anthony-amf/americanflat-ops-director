#!/usr/bin/env python3
"""Load a week of staged carrier invoices into BigQuery.

Meant to run as the last step of the `download-weekly-shipping-reports` skill,
on the Mac, right after it stages the five files and runs the cost report. That
is the only moment where the raw exports, gcloud's write credentials and a known
week window all exist at once — a cloud session has the credentials but not the
files, and this repo's portal has neither.

    python3 scripts/load_shipping_costs_to_bq.py \
        --dir "~/Documents/Claude/Projects/Weekly Shipping Reports/2026-09-01_to_2026-09-08"

That reports what it would load and changes nothing. Add --write to merge.

Scope note (2026-09-10): `americanflat/Ops` owns loading the Stamps table via
tools/stamps_shipping_costs_load.py, so this script skips Stamps files unless
told otherwise. FedEx is what it is for — no other tool loads that. Two tools
writing one table is how the Stamps table got to 25,948 rows and $297,557.98
against a true 20,528 and $239,109.04.

Two tables, two different grains, because the carriers bill differently:

  finance.stamps_shipping_costs   one row per shipment. Stamps states a final
                                  figure per label (quoted + adjusted = paid),
                                  so tracking is the key.
  finance.fedex_shipping_costs    one row per invoice line. FedEx bills a
                                  shipment again on a later invoice when it
                                  re-rates, and both lines are money paid, so
                                  the key is (tracking, invoice date, amount).

Getting those the wrong way round fails silently in opposite directions: keying
FedEx on tracking drops re-rates and understates cost; letting Stamps carry
several rows per shipment double-counts it. The MERGE statements in
sql/stamps_weekly_load.sql and sql/fedex_shipping_costs_setup.sql are the
authority on both; this script stages the rows they consume.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

# One parser, not two. The portal builder already reads these exact exports and
# already knows their traps; importing keeps a fix in one place.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from refresh_marketplace_shipments import (  # noqa: E402
    norm_carrier, norm_tracking, parse_amount, iso_date, _read_xlsx,
)

PROJECT = "americanflat"
STAMPS_TABLE = "%s.finance.stamps_shipping_costs" % PROJECT
FEDEX_TABLE = "%s.finance.fedex_shipping_costs" % PROJECT

# The canonical staged names the downloader writes. Anything else in the folder
# is ignored rather than guessed at.
STAMPS_HINTS = ("stamps", "printhistory", "print_history")
FEDEX_HINTS = ("fedex",)


def read_rows(path):
    """Raw rows with every column kept — unlike the builder's _cost_rows, which
    reduces to five fields because the page needs no more."""
    if path.lower().endswith((".xlsx", ".xls")):
        return _read_xlsx(path)
    import csv
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        return list(csv.DictReader(fh))


def is_refund(r):
    """A refunded label cost us nothing. Stamps keeps the row with its original
    Amount Paid, so loading it would bill a shipment that was credited back."""
    return (str(r.get("Refund Status", "")).strip().lower() == "approved"
            or str(r.get("Shipment Status", "")).strip().lower() == "refunded")


def col(r, *names):
    for n in names:
        if n in r and r[n] not in (None, ""):
            return r[n]
    return None


def stamps_records(path):
    """Stamps.com print history -> finance.stamps_shipping_costs rows."""
    out, skipped = [], 0
    for r in read_rows(path):
        if is_refund(r):
            skipped += 1
            continue
        trk = norm_tracking(col(r, "Tracking #", "Tracking Number"))
        paid = parse_amount(col(r, "Amount Paid"))
        # A non-numeric amount is a repeated header row from stacked exports,
        # not a charge.
        if not trk or paid is None:
            skipped += 1
            continue
        adj = parse_amount(col(r, "Adjusted Amount")) or 0.0
        out.append({
            "tracking_number": trk,
            "ship_date": iso_date(col(r, "Ship Date")) or None,
            "carrier": norm_carrier(col(r, "Carrier")) or "Other",
            "service": col(r, "Service", "Service Type"),
            "weight_lb": parse_amount(col(r, "Weight", "Weight (lbs)")),
            "amount_paid": round(paid, 2),
            "adjusted_amount": round(adj, 2),
            "order_id": col(r, "Order ID"),
            "reference_1": col(r, "Reference 1"),
            "cost_code": col(r, "Cost Code"),
            "to_name": col(r, "To Name", "Ship To Name"),
            "to_zip": col(r, "To Zip", "To Postal Code"),
            "source_file": os.path.basename(path),
        })
    return out, skipped


def fedex_records(path):
    """FedEx invoice export -> finance.fedex_shipping_costs rows."""
    out, skipped = [], 0
    for r in read_rows(path):
        trk = norm_tracking(col(r, "Express or Ground Tracking ID", "Tracking Number"))
        amt = parse_amount(col(r, "Net Charge Amount", "Net Charge"))
        if not trk or amt is None:
            skipped += 1
            continue
        out.append({
            "tracking_number": trk,
            "invoice_date": iso_date(col(r, "Invoice Date")) or None,
            "ship_date": iso_date(col(r, "Shipment Date")) or None,
            "net_charge": round(amt, 2),
            "service_type": col(r, "Service Type"),
            "package_weight": parse_amount(col(r, "Rated Weight Amount", "Package Weight")),
            "zone": col(r, "Zone"),
            "source_file": os.path.basename(path),
        })
    return out, skipped


def dedupe(records, keys):
    """Collapse rows identical on `keys`. The weekly exports overlap, so the same
    line arrives two or three times — 7,965 rows in the FedEx sheet carry 3,697
    distinct charges. Anything differing on those keys is kept: for FedEx that is
    a genuine re-rate, and dropping it would understate what we paid."""
    seen, out, dropped = set(), [], 0
    for r in records:
        k = tuple(r.get(x) for x in keys)
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        out.append(r)
    return out, dropped


def load_sql(path, stage):
    """The executable part of a spec file, pointed at this run's staging table.

    The .sql files are the authority on how a merge works and carry the reasoning
    with them, so the script reads them rather than holding a second copy that
    could drift. Only the marked section runs: the rest is commentary and DDL
    meant for a human to run once.
    """
    text = open(path, encoding="utf-8").read()
    start = text.index(">>>\n") + len(">>>\n")
    end = text.index("-- <<< END EXECUTABLE")
    body = text[start:end].replace("@@STAGE@@", stage.replace(":", "."))
    # Strip line comments BEFORE splitting on ';'. These files explain
    # themselves at length and that prose contains semicolons, which would
    # otherwise split a comment in half and leave English at the head of the
    # next statement. (Safe here because no string literal in these files
    # contains a double dash; check that before pasting one in.)
    code = "\n".join(line.split("--")[0].rstrip() for line in body.splitlines())
    return [st.strip() for st in code.split(";") if st.strip()]


def bq(args, dry):
    cmd = ["bq", "--project_id=" + PROJECT] + args
    if dry:
        # A whole MERGE is not worth reading in a dry run; its first line says
        # which table it touches, which is the part worth checking.
        shown = [a if len(a) < 90 else a.splitlines()[0].strip() + " …" for a in args]
        print("    would run: bq " + " ".join(shown))
        return ""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("bq failed:\n%s\n%s" % (" ".join(cmd), r.stderr.strip()))
    return r.stdout


def stage_and_merge(records, table, stage, schema, sql_path, dry, workdir):
    """Load to a fresh dated staging table, then merge. A new staging table per
    run rather than replacing one: nothing is overwritten, and BigQuery expires
    them on its own after a week."""
    # Name the file after the table, not its bq spec — the spec has a colon in it.
    path = os.path.join(workdir, stage.split(".")[-1] + ".ndjson")
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps({k: v for k, v in r.items() if v is not None}) + "\n")
    print("    staged %d rows -> %s" % (len(records), path))
    bq(["load", "--source_format=NEWLINE_DELIMITED_JSON",
        "--expiration=604800", stage, path, schema], dry)
    for statement in load_sql(sql_path, stage):
        bq(["query", "--use_legacy_sql=false", "--max_rows=200", statement], dry)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", help="the week's staging folder")
    ap.add_argument("--stamps", nargs="*", default=[], help="Stamps print history export(s)")
    ap.add_argument("--fedex", nargs="*", default=[], help="FedEx invoice export(s)")
    ap.add_argument("--stamps-anyway", action="store_true",
                    help="load Stamps too. Off by default: americanflat/Ops owns "
                         "that table now, and two tools writing one table is how "
                         "it got double-counted once already")
    ap.add_argument("--write", action="store_true",
                    help="actually merge. Without it, report only and change nothing")
    args = ap.parse_args()

    stamps, fedex = list(args.stamps), list(args.fedex)
    if args.dir:
        d = os.path.expanduser(args.dir)
        if not os.path.isdir(d):
            sys.exit("no such folder: %s" % d)
        for f in sorted(os.listdir(d)):
            low, full = f.lower(), os.path.join(d, f)
            if not low.endswith((".csv", ".xlsx", ".xls")):
                continue
            if any(h in low for h in STAMPS_HINTS):
                stamps.append(full)
            elif any(h in low for h in FEDEX_HINTS):
                fedex.append(full)
    if stamps and not args.stamps_anyway:
        print("Skipping %d Stamps file(s): americanflat/Ops owns that table now.\n"
              "  Load them with tools/stamps_shipping_costs_load.py in that repo —\n"
              "  it orders overlapping exports properly and refuses to run while\n"
              "  the target holds escaped tracking numbers. Pass --stamps-anyway to\n"
              "  override, but do not run both tools against one table.\n"
              % len(stamps))
        stamps = []
    if not stamps and not fedex:
        sys.exit("nothing to load — pass --dir with the week's folder, or --stamps/--fedex")

    dry = not args.write
    if dry:
        print("DRY RUN — reporting only. Add --write to merge.\n")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    workdir = os.path.join(os.path.expanduser("~"), "Documents", "Claude",
                           "bq-staging", stamp)
    os.makedirs(workdir, exist_ok=True)

    if stamps:
        print("Stamps.com -> %s" % STAMPS_TABLE)
        recs, skipped = [], 0
        for p in stamps:
            got, sk = stamps_records(p)
            print("  %-52s %6d rows  (%d skipped)" % (os.path.basename(p)[:52], len(got), sk))
            recs += got
            skipped += sk
        # One row per shipment: Amount Paid is already final.
        recs, dropped = dedupe(recs, ["tracking_number"])
        print("  %d shipments after collapsing %d repeated lines" % (len(recs), dropped))
        stage_and_merge(recs, STAMPS_TABLE,
                        "%s:finance._stage_stamps_%s" % (PROJECT, stamp),
                        "tracking_number:STRING,ship_date:DATE,carrier:STRING,"
                        "service:STRING,weight_lb:NUMERIC,amount_paid:NUMERIC,"
                        "adjusted_amount:NUMERIC,order_id:STRING,reference_1:STRING,"
                        "cost_code:STRING,to_name:STRING,to_zip:STRING,source_file:STRING",
                        "sql/stamps_weekly_load.sql", dry, workdir)

    if fedex:
        print("\nFedEx -> %s" % FEDEX_TABLE)
        recs, skipped = [], 0
        for p in fedex:
            got, sk = fedex_records(p)
            print("  %-52s %6d rows  (%d skipped)" % (os.path.basename(p)[:52], len(got), sk))
            recs += got
            skipped += sk
        # One row per invoice LINE: a second line on a later invoice is a re-rate.
        recs, dropped = dedupe(recs, ["tracking_number", "invoice_date", "net_charge"])
        shipments = len({r["tracking_number"] for r in recs})
        print("  %d charge lines across %d shipments, after collapsing %d repeats"
              % (len(recs), shipments, dropped))
        stage_and_merge(recs, FEDEX_TABLE,
                        "%s:finance._stage_fedex_%s" % (PROJECT, stamp),
                        "tracking_number:STRING,invoice_date:DATE,ship_date:DATE,"
                        "net_charge:NUMERIC,service_type:STRING,package_weight:NUMERIC,"
                        "zone:STRING,source_file:STRING",
                        "sql/fedex_shipping_costs_setup.sql", dry, workdir)

    print("\n%s" % ("Nothing was written. Re-run with --write to load."
                    if dry else "Loaded. The checks at the end of each SQL file "
                                "print above — read them before trusting the week."))


if __name__ == "__main__":
    main()
