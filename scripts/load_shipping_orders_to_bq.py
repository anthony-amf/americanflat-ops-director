#!/usr/bin/env python3
"""
Load a week of shipped orders into americanflat.finance.shipping_orders.

Reads the same five files the weekly Cost Per SKU report reads (the dated
staging folder the download-weekly-shipping-reports skill produces), matches
each shipped package to its FedEx or Stamps.com charge, keeps only the four
marketplaces where we cover the shipping — Target, Michaels, Shopify, Macy's —
and writes one row per package to BigQuery.

Runs from the Mac: writing to BigQuery needs gcloud ADC. A cloud session can
still run --dry-run to check a folder parses.

Usage
-----
    # one week (the folder the Thursday job stages)
    python3 scripts/load_shipping_orders_to_bq.py \
        --week-dir "~/Documents/Claude/Projects/Weekly Shipping Reports/2026-06-08_to_2026-06-15"

    # every week folder under the project root, oldest first
    python3 scripts/load_shipping_orders_to_bq.py \
        --backfill-root "~/Documents/Claude/Projects/Weekly Shipping Reports"

    # parse and summarize without touching BigQuery
    python3 scripts/load_shipping_orders_to_bq.py --week-dir <dir> --dry-run \
        --out-json /tmp/shipping_orders.json

Re-running a week is safe. Before inserting, the loader removes the rows that
week previously wrote plus any row whose shipment key it is about to re-insert,
so a late FedEx invoice that lands in a later week's file upgrades the shipment
from unmatched to matched instead of adding a second row.

The matching itself is the shipping-cost-report skill's code, imported rather
than copied — that skill stays the single source of truth for how invoices tie
to orders.
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_write import safe_write_text  # noqa: E402

# Present in every JSON dump this script writes, so a write to an existing file
# that lacks it is refused rather than clobbering something real.
JSON_MARKER = '"_written_by": "load_shipping_orders_to_bq.py"'

PROJECT = "americanflat"
DATASET = "finance"
TABLE = "shipping_orders"

# The channels where Americanflat pays the freight. Everything else in the 3PL
# reports (Amazon, Wayfair, Walmart, Kohl's, Faire, wholesale, ShipStation) is
# dropped: the marketplace covers shipping there, so it has no place here.
COVERED_MARKETPLACES = {"Target", "Michaels", "Shopify", "Macy's"}

# Where the shipping-cost-report skill might live, most-specific first. Entries
# may contain * — plugin-managed skills land under a generated folder name, so
# the exact path differs per machine and install.
SKILL_LIB_CANDIDATES = [
    "~/.claude/skills/shipping-cost-report/scripts",
    "~/.claude/skills/synced/shipping-cost-report/scripts",
    "/root/.claude/skills/synced/shipping-cost-report/scripts",
    "~/.claude/plugins/*/skills/shipping-cost-report/scripts",
    "~/.claude/plugins/*/*/skills/shipping-cost-report/scripts",
    "~/Library/Application Support/Claude/*/skills-plugin/*/*/skills/shipping-cost-report/scripts",
    "~/Library/Application Support/Claude/*/*/*/skills/shipping-cost-report/scripts",
]

# Last resort: sweep the home folder for the file itself. Read-only, and skipped
# unless every candidate path above came up empty.
SKILL_LIB_SWEEP_ROOTS = ["~/.claude", "~/Library/Application Support/Claude"]

WEEK_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$")

FILE_PATTERNS = {
    "fedex": ["FedEx_Invoice_*.csv", "FEDEX_INVOICE_*.csv"],
    "stamps": ["Stamps_PrintHistory_*.csv"],
    "fontana": ["Fontana_ShippedOrders_*.csv", "Fontana_ShippedOrders_*.xlsx"],
    "newjersey": ["NewJersey_ShippedOrders_*.csv", "NewJersey_ShippedOrders_*.xlsx"],
    "sc": ["SouthCarolina_OrderDetails_*.xlsx"],
}

BQ_SCHEMA_FIELDS = [
    ("shipment_key", "STRING", "REQUIRED"),
    ("ship_date", "DATE", "NULLABLE"),
    ("week_start", "DATE", "NULLABLE"),
    ("week_label", "STRING", "NULLABLE"),
    ("marketplace", "STRING", "NULLABLE"),
    ("marketplace_raw", "STRING", "NULLABLE"),
    ("warehouse", "STRING", "NULLABLE"),
    ("order_number", "STRING", "NULLABLE"),
    ("po_number", "STRING", "NULLABLE"),
    ("tracking", "STRING", "NULLABLE"),
    ("consignee", "STRING", "NULLABLE"),
    ("carrier", "STRING", "NULLABLE"),
    ("units", "INT64", "NULLABLE"),
    ("is_additional_package", "BOOL", "NULLABLE"),
    ("cost_status", "STRING", "NULLABLE"),
    ("carrier_source", "STRING", "NULLABLE"),
    ("shipping_cost", "NUMERIC", "NULLABLE"),
    ("cost_per_unit", "NUMERIC", "NULLABLE"),
    ("billed_weight", "NUMERIC", "NULLABLE"),
    ("match_method", "STRING", "NULLABLE"),
    ("source_week", "STRING", "NULLABLE"),
    ("loaded_at", "TIMESTAMP", "NULLABLE"),
]


# ── the shipping-cost-report skill's matching code ─────────────────────────


def _expand(candidate: str) -> list[Path]:
    """Turn one candidate into concrete paths to process_shipments.py."""
    raw = str(Path(candidate).expanduser())
    hits = sorted(glob.glob(raw)) if "*" in raw else [raw]
    out = []
    for hit in hits:
        path = Path(hit)
        out.append(path / "process_shipments.py" if path.is_dir() else path)
    return out


def load_shipping_lib(explicit: str | None = None):
    """Import process_shipments.py from the shipping-cost-report skill."""
    candidates = [explicit] if explicit else []
    candidates += [os.environ.get("SHIPPING_COST_REPORT_SCRIPTS", "")]
    candidates += SKILL_LIB_CANDIDATES

    for cand in candidates:
        if not cand:
            continue
        for path in _expand(cand):
            if path.is_file():
                return _import_lib(path)

    # Nothing matched a known layout — go looking for it.
    for root in SKILL_LIB_SWEEP_ROOTS:
        base = Path(root).expanduser()
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("shipping-cost-report/scripts/process_shipments.py")):
            return _import_lib(path)

    sys.exit(
        "Could not find the shipping-cost-report skill's process_shipments.py.\n"
        "Looked in:\n  "
        + "\n  ".join(str(Path(c).expanduser()) for c in candidates if c)
        + "\nand swept "
        + ", ".join(str(Path(r).expanduser()) for r in SKILL_LIB_SWEEP_ROOTS)
        + ".\nFind it with:  find ~ -name process_shipments.py 2>/dev/null\n"
        "then pass --shipping-lib <the folder it is in>."
    )


def _import_lib(path: Path):
    spec = importlib.util.spec_from_file_location("process_shipments", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(f"Matching logic: {path}")
    return module


# ── file discovery ────────────────────────────────────────────────────────


def find_files(week_dir: Path) -> dict:
    """Locate the five staged source files inside a week folder."""
    found = {}
    for key, patterns in FILE_PATTERNS.items():
        hits: list[str] = []
        for pattern in patterns:
            hits.extend(sorted(glob.glob(str(week_dir / pattern))))
        found[key] = hits
    return found


def describe_files(found: dict) -> str:
    parts = []
    for key, hits in found.items():
        parts.append(f"{key}={len(hits)}")
    return ", ".join(parts)


# ── row building ──────────────────────────────────────────────────────────


def shipment_key(order: dict) -> str:
    """Stable identity for a package: warehouse + order + PO + tracking.

    Deliberately excludes cost fields and carrier_source so that reloading a
    shipment after its invoice arrives replaces the unmatched row rather than
    creating a second one.
    """
    raw = "|".join(
        (order.get(f) or "").strip().upper()
        for f in ("warehouse", "order_number", "po_number", "tracking")
    )
    return hashlib.sha1(raw.encode()).hexdigest()


def week_fields(ship_date: str) -> tuple[str | None, str | None]:
    """Monday of the ship week, and the ISO week label."""
    if not ship_date:
        return None, None
    try:
        d = datetime.strptime(ship_date, "%Y-%m-%d").date()
    except ValueError:
        return None, None
    monday = date.fromordinal(d.toordinal() - d.weekday())
    iso = d.isocalendar()
    return monday.isoformat(), f"{iso[0]}-W{iso[1]:02d}"


def money(value) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def build_rows(matched: list, unmatched: list, source_week: str, loaded_at: str) -> tuple[list, dict]:
    """Turn matched/unmatched orders into BigQuery rows for the four marketplaces."""
    stats = {
        "matched_in": len(matched),
        "unmatched_in": len(unmatched),
        "dropped_marketplace": 0,
        "no_ship_date": 0,
        "duplicate_keys": 0,
        "additional_packages": 0,
    }
    rows: dict[str, dict] = {}

    def add(order: dict, is_matched: bool):
        marketplace = order.get("marketplace") or ""
        if marketplace not in COVERED_MARKETPLACES:
            stats["dropped_marketplace"] += 1
            return

        ship_date = order.get("ship_date") or ""
        week_start, week_label = week_fields(ship_date)
        if not week_start:
            stats["no_ship_date"] += 1
            ship_date = None

        method = order.get("match_method") or ""
        # A "(multi-pkg)" row is the 2nd+ package of an order that the skill
        # matched by PO reference. It carries the whole order's units, which
        # would double-count them, so the units live on the primary row only.
        additional = "multi-pkg" in method
        if additional:
            stats["additional_packages"] += 1
        units = 0 if additional else int(order.get("units") or 0)
        cost = money(order.get("shipping_cost")) if is_matched else None

        row = {
            "shipment_key": shipment_key(order),
            "ship_date": ship_date,
            "week_start": week_start,
            "week_label": week_label,
            "marketplace": marketplace,
            "marketplace_raw": (order.get("marketplace_raw") or "") or None,
            "warehouse": order.get("warehouse") or None,
            "order_number": (order.get("order_number") or "") or None,
            "po_number": (order.get("po_number") or "") or None,
            "tracking": (order.get("tracking") or "") or None,
            "consignee": (order.get("consignee") or "") or None,
            "carrier": (order.get("carrier") or "") or None,
            "units": units,
            "is_additional_package": additional,
            "cost_status": "matched" if is_matched else "unmatched",
            "carrier_source": order.get("carrier_source") if is_matched else None,
            "shipping_cost": cost,
            "cost_per_unit": money(cost / units) if cost is not None and units > 0 else None,
            "billed_weight": money(order.get("weight")) if is_matched else None,
            "match_method": method or None,
            "source_week": source_week,
            "loaded_at": loaded_at,
        }
        if row["shipment_key"] in rows:
            stats["duplicate_keys"] += 1
            # Prefer a matched row over an unmatched one for the same package.
            if rows[row["shipment_key"]]["cost_status"] == "matched":
                return
        rows[row["shipment_key"]] = row

    for order in matched:
        add(order, True)
    for order in unmatched:
        add(order, False)

    return list(rows.values()), stats


def process_week(week_dir: Path, lib, source_week: str) -> tuple[list, dict]:
    """Parse one week folder and return (rows, stats)."""
    return process_sources(find_files(week_dir), lib, source_week)


def process_sources(found: dict, lib, source_week: str) -> tuple[list, dict]:
    """Parse a set of source files and return (rows, stats)."""
    print(f"  files: {describe_files(found)}")

    missing = [k for k, v in found.items() if not v]
    if missing:
        print(f"  ⚠ missing source files: {', '.join(missing)}")
    if not (found["fontana"] or found["newjersey"] or found["sc"]):
        print("  ⚠ no 3PL shipped-order report in this folder — skipping")
        return [], {}

    fedex_data: dict = {}
    for f in found["fedex"]:
        fedex_data.update(lib.parse_fedex_invoice(f))
    stamps_data: dict = {}
    for f in found["stamps"]:
        stamps_data.update(lib.parse_stamps_history(f))

    orders: list = []
    for f in found["fontana"]:
        orders.extend(lib.parse_3pl_nj_fontana(f, warehouse_override="Fontana"))
    for f in found["newjersey"]:
        orders.extend(lib.parse_3pl_nj_fontana(f, warehouse_override="New Jersey"))
    for f in found["sc"]:
        orders.extend(lib.parse_3pl_sc(f))

    matched, unmatched, _, _ = lib.match_shipments(orders, fedex_data, stamps_data)
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows, stats = build_rows(matched, unmatched, source_week, loaded_at)

    stats["orders_parsed"] = len(orders)
    stats["fedex_records"] = len(fedex_data)
    stats["stamps_records"] = len(stamps_data)
    print(
        f"  parsed {len(orders)} 3PL orders, {len(fedex_data)} FedEx + "
        f"{len(stamps_data)} Stamps charges → {len(rows)} rows for our four marketplaces"
    )
    if stats["no_ship_date"]:
        print(f"  ⚠ {stats['no_ship_date']} rows had no usable ship date (kept, date left blank)")
    if stats["duplicate_keys"]:
        print(f"  ⚠ {stats['duplicate_keys']} duplicate shipments collapsed")
    return rows, stats


# ── BigQuery write ────────────────────────────────────────────────────────


def write_rows(rows: list, source_week: str, project: str, dataset: str, table: str):
    """Replace this week's rows in BigQuery with the freshly built ones."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{table}"

    # 1. Clear what this folder wrote last time.
    job = client.query(
        f"DELETE FROM `{table_id}` WHERE source_week = @week",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("week", "STRING", source_week)]
        ),
    )
    job.result()
    print(f"  cleared {job.num_dml_affected_rows or 0} existing rows for {source_week}")

    # 2. Clear the same shipments if an earlier week already recorded them
    #    (a late invoice moves a shipment from unmatched to matched).
    keys = [r["shipment_key"] for r in rows]
    cleared = 0
    for i in range(0, len(keys), 4000):
        chunk = keys[i : i + 4000]
        job = client.query(
            f"DELETE FROM `{table_id}` "
            f"WHERE shipment_key IN UNNEST(@keys) AND source_week != @week",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("keys", "STRING", chunk),
                    bigquery.ScalarQueryParameter("week", "STRING", source_week),
                ]
            ),
        )
        job.result()
        cleared += job.num_dml_affected_rows or 0
    if cleared:
        print(f"  superseded {cleared} rows loaded under an earlier week")

    # 3. Append via a load job (not the streaming API — streamed rows would be
    #    un-editable for ~90 minutes, which breaks the next re-run).
    schema = [
        bigquery.SchemaField(name, field_type, mode=mode)
        for name, field_type, mode in BQ_SCHEMA_FIELDS
    ]
    load = client.load_table_from_json(
        rows,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        ),
    )
    load.result()
    print(f"  ✓ loaded {len(rows)} rows into {table_id}")


# ── summary ───────────────────────────────────────────────────────────────


def summarize(rows: list):
    """Print the per-marketplace picture, the way the weekly report does."""
    if not rows:
        return
    by_mp: dict[str, dict] = {}
    for r in rows:
        agg = by_mp.setdefault(
            r["marketplace"],
            {"shipments": 0, "units": 0, "cost": 0.0, "matched": 0, "matched_units": 0},
        )
        agg["shipments"] += 1
        agg["units"] += r["units"] or 0
        if r["cost_status"] == "matched":
            agg["matched"] += 1
            agg["cost"] += r["shipping_cost"] or 0.0
            agg["matched_units"] += r["units"] or 0

    print()
    print(f"{'Marketplace':<12} {'Shipments':>10} {'Units':>8} {'Cost':>12} {'CPU':>8} {'Matched':>9}")
    print("-" * 64)
    tot = {"shipments": 0, "units": 0, "cost": 0.0, "matched": 0, "matched_units": 0}
    for mp, agg in sorted(by_mp.items()):
        cpu = agg["cost"] / agg["matched_units"] if agg["matched_units"] else 0.0
        rate = 100 * agg["matched"] / agg["shipments"] if agg["shipments"] else 0.0
        print(
            f"{mp:<12} {agg['shipments']:>10,} {agg['units']:>8,} "
            f"${agg['cost']:>11,.2f} ${cpu:>7,.2f} {rate:>8.1f}%"
        )
        for k in tot:
            tot[k] += agg[k]
    cpu = tot["cost"] / tot["matched_units"] if tot["matched_units"] else 0.0
    rate = 100 * tot["matched"] / tot["shipments"] if tot["shipments"] else 0.0
    print("-" * 64)
    print(
        f"{'TOTAL':<12} {tot['shipments']:>10,} {tot['units']:>8,} "
        f"${tot['cost']:>11,.2f} ${cpu:>7,.2f} {rate:>8.1f}%"
    )
    if rate < 80:
        print("\n⚠ match rate under 80% — check that the FedEx invoice in this folder covers this week.")


# ── entry point ───────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(
        description="Load a week of shipped orders into finance.shipping_orders"
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--week-dir", help="One dated weekly staging folder")
    src.add_argument(
        "--backfill-root",
        help="Folder of dated week folders (YYYY-MM-DD_to_YYYY-MM-DD); loads each, oldest first",
    )
    src.add_argument(
        "--files",
        action="store_true",
        help="Name the source files yourself with the five flags below, instead of using a folder. "
             "Use this for a multi-week archive (e.g. the consolidated sheets in Drive) — the "
             "week of each row still comes from its own ship date. Needs --week-label.",
    )
    for flag, label in [
        ("--fedex", "FedEx invoice CSV"),
        ("--stamps", "Stamps.com print history CSV"),
        ("--fontana", "Fontana shipped orders CSV/XLSX"),
        ("--newjersey", "New Jersey shipped orders CSV/XLSX"),
        ("--sc", "South Carolina order details XLSX"),
    ]:
        ap.add_argument(flag, nargs="*", default=[], help=f"{label} (with --files)")
    ap.add_argument("--week-label", help="Override the source_week label (default: folder name)")
    ap.add_argument("--shipping-lib", help="Path to the shipping-cost-report skill's scripts dir")
    ap.add_argument("--dry-run", action="store_true", help="Parse and summarize, write nothing")
    ap.add_argument("--out-json", help="Also write the rows to this JSON file")
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--table", default=TABLE)
    args = ap.parse_args()

    lib = load_shipping_lib(args.shipping_lib)

    if args.files:
        if not args.week_label:
            sys.exit("--files needs --week-label, e.g. --week-label drive-archive-2026-04-30")
        found = {
            "fedex": [str(Path(f).expanduser()) for f in args.fedex],
            "stamps": [str(Path(f).expanduser()) for f in args.stamps],
            "fontana": [str(Path(f).expanduser()) for f in args.fontana],
            "newjersey": [str(Path(f).expanduser()) for f in args.newjersey],
            "sc": [str(Path(f).expanduser()) for f in args.sc],
        }
        print(f"\n{args.week_label}")
        rows, _ = process_sources(found, lib, args.week_label)
        if rows:
            if args.dry_run:
                print("  dry run — nothing written to BigQuery")
            else:
                write_rows(rows, args.week_label, args.project, args.dataset, args.table)
        finish(rows, args)
        return

    if args.week_dir:
        week_dirs = [Path(args.week_dir).expanduser()]
    else:
        root = Path(args.backfill_root).expanduser()
        week_dirs = sorted(d for d in root.iterdir() if d.is_dir() and WEEK_DIR_RE.match(d.name))
        if not week_dirs:
            sys.exit(f"No YYYY-MM-DD_to_YYYY-MM-DD folders found under {root}")
        print(f"Backfilling {len(week_dirs)} week folders from {root}")

    all_rows = []
    for week_dir in week_dirs:
        if not week_dir.is_dir():
            sys.exit(f"Not a folder: {week_dir}")
        source_week = args.week_label or week_dir.name
        print(f"\n{source_week}")
        rows, _ = process_week(week_dir, lib, source_week)
        if not rows:
            continue
        if args.dry_run:
            print("  dry run — nothing written to BigQuery")
        else:
            write_rows(rows, source_week, args.project, args.dataset, args.table)
        all_rows.extend(rows)

    finish(all_rows, args)


def finish(rows: list, args):
    """Print the summary and write the optional JSON copy."""
    summarize(rows)

    if args.out_json:
        out = Path(args.out_json).expanduser()
        payload = {"_written_by": "load_shipping_orders_to_bq.py", "rows": rows}
        safe_write_text(out, json.dumps(payload, indent=2), JSON_MARKER, "rows file")
        print(f"\nRows written to {out}")

    if not args.dry_run and rows:
        print(
            "\nNext: refresh the dashboard with\n"
            "  python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html"
        )


if __name__ == "__main__":
    main()
