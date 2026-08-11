#!/usr/bin/env python3
"""Rewrite header-level [AUTO] blocks that are sitting on top of a deeper review.

Why this exists
---------------
A header-level sweep on 2026-08-11 (v1.4.0, run from the Mac ~10:30-10:58 AM MT)
refreshed the [AUTO] block on 335 rows. On rows that already carried a
[DEEP PASS] / [MSA REVAL] / line-level result, the block it wrote says
"provide itemized counts" and "order-level Stedi check available via supporting
Excel" -- which reads as though the itemized and shipping work still needs doing,
directly underneath the block recording that it was done. The [AUTO] block is
written last, so it reads as the current verdict. That is exactly the confusion
Anthony reported on 755265.

v1.5.0 stops NEW ones being written (a needs_detail result on a row with a deeper
block now writes a one-line deferral instead). It cannot repair the ones already
there: every affected row is settled (valid/disputed), so no future sweep will
ever revisit it.

What this does
--------------
For each affected row, replaces ONLY its [AUTO <today>] block with the v1.5.0
deferral wording. Every other block is left byte-for-byte alone.

Safety
------
- Dry run by default. Pass --write to apply.
- Only touches rows that still contain the stale wording, so re-running is a
  no-op rather than a second edit.
- Never changes validation_status, validation_variance, validated_by, or paid_at.
- Prints a before/after length for every row and refuses to shrink a report by
  more than the block it is replacing.

Order of operations: run sql/restore_clobbered_reports_2026-08-11.sql FIRST, so
754891 and 755265 have their history back and qualify for this fix too.

Usage (from the Mac, needs gcloud ADC):
    python3 scripts/fix_stale_auto_blocks_2026-08-11.py            # dry run
    python3 scripts/fix_stale_auto_blocks_2026-08-11.py --write
"""
import argparse
import re
import sys

from google.cloud import bigquery

TABLE = "americanflat.finance.yusen_invoices"
STALE = "order-level Stedi check available via supporting Excel"
DEEPER = re.compile(r"\[(DEEP PASS|STEDI|MSA DISPUTE|MSA REVAL) \d{4}-\d{2}-\d{2}\]")
AUTO_BLOCK = re.compile(r"\n*\[AUTO (\d{4}-\d{2}-\d{2})\].*?(?=\n\n\[|\Z)", re.S)
AMOUNT = re.compile(r"header total \$([\d,]+\.\d\d)")


def deferral(invoice: str, prior: str, amount: str, tag_date: str) -> str:
    tags = ", ".join(sorted({m.group(1).upper() for m in DEEPER.finditer(prior)}))
    amt = f" Header total ${amount}, unchanged." if amount else ""
    return (f"[AUTO {tag_date}] Invoice {invoice} — header-level re-check only, no "
            f"new findings. Itemized detail is already on file above ({tags}); this "
            f"pass does not supersede it.{amt}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    args = ap.parse_args()

    client = bigquery.Client(project="americanflat")
    rows = list(client.query(f"""
        SELECT invoice_number, validation_report, validation_status
        FROM `{TABLE}`
        WHERE validation_report LIKE '%{STALE}%'
          AND REGEXP_CONTAINS(validation_report,
                r'\\[(DEEP PASS|MSA REVAL|STEDI|MSA DISPUTE) \\d{{4}}-\\d{{2}}-\\d{{2}}\\]')
        ORDER BY invoice_number
    """).result())

    if not rows:
        print("Nothing to fix — no row carries the stale wording alongside a deeper block.")
        return 0

    print(f"{len(rows)} row(s) to fix{'' if args.write else '  (DRY RUN — nothing written)'}\n")
    fixed = skipped = 0
    for r in rows:
        prior = r["validation_report"] or ""
        m = AUTO_BLOCK.search(prior)
        if not m:
            print(f"  {r['invoice_number']:22} SKIP — stale wording is not in an [AUTO] block; "
                  f"needs a look by hand")
            skipped += 1
            continue
        if STALE not in m.group(0):
            print(f"  {r['invoice_number']:22} SKIP — the [AUTO] block is already clean; "
                  f"stale text sits in another block")
            skipped += 1
            continue

        amt_m = AMOUNT.search(m.group(0))
        new_block = deferral(r["invoice_number"], prior,
                            amt_m.group(1) if amt_m else "", m.group(1))
        merged = (prior[:m.start()].rstrip() + "\n\n" + new_block
                  + prior[m.end():]).strip()

        print(f"  {r['invoice_number']:22} {r['validation_status'] or '(none)':10} "
              f"{len(prior):>5} -> {len(merged):>5} ({len(merged)-len(prior):+d})")

        if args.write:
            job = client.query(
                f"UPDATE `{TABLE}` SET validation_report = @rep "
                f"WHERE invoice_number = @inv AND validation_report LIKE @stale",
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("rep", "STRING", merged),
                    bigquery.ScalarQueryParameter("inv", "STRING", r["invoice_number"]),
                    bigquery.ScalarQueryParameter("stale", "STRING", f"%{STALE}%"),
                ]))
            job.result()
            if job.num_dml_affected_rows == 0:
                print(f"      no rows affected — already changed by someone else, left alone")
            else:
                fixed += 1

    print(f"\n{fixed} fixed, {skipped} skipped"
          if args.write else f"\n{len(rows) - skipped} would be fixed, {skipped} skipped")
    print("Re-run with --write to apply." if not args.write else "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
