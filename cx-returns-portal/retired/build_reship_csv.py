#!/usr/bin/env python3
"""Build a ShipStation order-import CSV for a replacement (RS) order.

    python3 scripts/build_reship_csv.py 22397 \
        --sku "MW1114WH57:6" --sku "MW0808WH44:1" \
        --name "Sarah Whitfield" \
        --address1 "1842 Larkin St" --address2 "Apt 4" \
        --city "San Francisco" --state CA --postal 94109 \
        --reason "short shipment" --pick units \
        --out reship-22397RS.csv

SKUs and item names are pulled from BigQuery when the order is found, so only the
quantities being replaced need stating. The address is never in BigQuery — copy it
off the Shopify order screen.

Headers come from references/shipstation-csv.json and are UNVERIFIED against a real
ShipStation import; see references/shipstation-csv.md before production use.
"""

import argparse
import csv
import datetime
import io
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "references" / "shipstation-csv.json"

sys.path.insert(0, str(SKILL_DIR / "scripts"))


def rs_number(order: str) -> str:
    """Replacement orders are the original number with RS appended."""
    bare = order.strip().lstrip("#").strip()
    return bare if bare.upper().endswith("RS") else f"{bare}RS"


def parse_sku(spec: str) -> tuple:
    """'MW1114WH57:6' -> ('MW1114WH57', 6). Bare SKU defaults to 1."""
    if ":" in spec:
        sku, qty = spec.rsplit(":", 1)
        try:
            return sku.strip().upper(), int(qty)
        except ValueError:
            raise SystemExit(f"Bad quantity in --sku {spec!r}; expected SKU:N")
    return spec.strip().upper(), 1


def lookup_titles(order: str) -> dict:
    """Item names from BigQuery, so the CSV matches the catalogue. Best effort."""
    try:
        import lookup_order
        name, bare = lookup_order.normalise(order)
        rows = lookup_order.run_query(lookup_order.ITEMS_SQL, name, bare)
        return {(r["sku"] or "").upper(): r["title"] for r in rows if r.get("sku")}
    except SystemExit:
        raise
    except Exception:
        return {}


def build_rows(cfg: dict, args, items: list, titles: dict) -> list:
    d = cfg["defaults"]
    note_bits = [f"Replacement for #{args.order.lstrip('#')}"]
    if args.reason:
        note_bits.append(args.reason)
    if args.ticket:
        note_bits.append(f"Zendesk {args.ticket}")
    note_bits.append(
        "PICK AS SEALED MASTER CARTON - do not split"
        if args.pick == "carton"
        else "Loose-unit pick - individual units only"
    )
    note_bits.append("No charge - replacement, do not invoice")
    notes = " | ".join(note_bits)

    order_date = args.date or datetime.date.today().isoformat()
    shared = {
        "order_number": rs_number(args.order),
        "order_date": order_date,
        "order_status": d["order_status"],
        "shipping_service": args.service or d["shipping_service"],
        "ship_name": args.name,
        "ship_company": args.company or "",
        "address1": args.address1,
        "address2": args.address2 or "",
        "city": args.city,
        "state": args.state,
        "postal": args.postal,
        "country": args.country or d["country"],
        "phone": args.phone or "",
        "unit_price": d["unit_price"],
        "notes": notes,
    }

    rows = []
    for sku, qty in items:
        row = dict(shared)
        row["sku"] = sku
        row["item_name"] = titles.get(sku, "")
        row["qty"] = str(qty)
        rows.append(row)
    return rows


def to_csv(cfg: dict, rows: list) -> str:
    headers = [c["header"] for c in cfg["columns"]]
    fields = [c["field"] for c in cfg["columns"]]
    buf = io.StringIO()
    # ShipStation reads these on Windows; \r\n keeps Excel from mangling the file.
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(f, "") for f in fields])
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a ShipStation reship CSV.")
    ap.add_argument("order", help="Original order number, e.g. 22397")
    ap.add_argument("--sku", action="append", required=True, metavar="SKU:QTY",
                    help="Replacement unit; repeatable. 'MW1114WH57:6'")
    ap.add_argument("--name", required=True, help="Recipient name")
    ap.add_argument("--address1", required=True, help="Street address (not in BigQuery)")
    ap.add_argument("--city", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--postal", required=True)
    ap.add_argument("--address2", default="")
    ap.add_argument("--company", default="")
    ap.add_argument("--country", default="")
    ap.add_argument("--phone", default="")
    ap.add_argument("--service", default="", help="Requested shipping service")
    ap.add_argument("--pick", choices=["carton", "units"], default="carton",
                    help="Sealed master carton (default) or loose units")
    ap.add_argument("--reason", default="", help="Why, e.g. 'damaged on arrival'")
    ap.add_argument("--ticket", default="", help="Zendesk ticket, for internal notes only")
    ap.add_argument("--date", default="", help="Order date (default today)")
    ap.add_argument("--out", default="", help="Write here instead of stdout")
    ap.add_argument("--no-lookup", action="store_true", help="Skip the BigQuery title lookup")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    items = [parse_sku(s) for s in args.sku]
    titles = {} if args.no_lookup else lookup_titles(args.order)
    rows = build_rows(cfg, args, items, titles)
    text = to_csv(cfg, rows)

    if args.out:
        Path(args.out).write_text(text, newline="")
        print(f"Wrote {args.out} — {len(rows)} line item(s) for order {rows[0]['order_number']}.")
    else:
        sys.stdout.write(text)

    missing = [s for s, _ in items if s not in titles]
    if missing and not args.no_lookup:
        print(f"\nNote: no catalogue name found for {', '.join(missing)} — "
              f"Item Name left blank. Check the SKU is right.", file=sys.stderr)
    if not cfg.get("verified_against_real_import"):
        print("\nHEADERS UNVERIFIED: do one test import before trusting this file. "
              "See references/shipstation-csv.md.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
