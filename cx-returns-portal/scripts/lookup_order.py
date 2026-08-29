#!/usr/bin/env python3
"""Look up a Shopify order in BigQuery so CX doesn't retype it.

    python3 scripts/lookup_order.py 22397
    python3 scripts/lookup_order.py '#22397' --json

Reads `americanflat.shopify.orders` and `.order_line_items`, which track Shopify
within about 20 minutes. Read-only: this never writes anything.

What it CANNOT tell you, and why — see references/data-sources.md:

  * the warehouse   — not held at order level anywhere in BigQuery
  * the tracking #  — the ShipStation shipment feed stopped in Oct 2023
  * partial fulfilment — the pipeline only stores FULFILLED / UNFULFILLED / ON_HOLD

Those still come from the Shopify admin screen or the Zendesk ticket. The lookup
covers the fields that were getting mistyped: order number, SKUs and quantities.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys

PROJECT = "americanflat"
ENDPOINT = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/queries"

ORDER_SQL = """
SELECT name, created_at, financial_status, fulfillment_status,
       total_price, currency_code, total_refunded
FROM `americanflat.shopify.orders`
WHERE name = @name OR CAST(order_id AS STRING) = @bare
LIMIT 1
"""

ITEMS_SQL = """
SELECT li.sku, li.title, li.quantity
FROM `americanflat.shopify.order_line_items` li
JOIN `americanflat.shopify.orders` o USING (order_id)
WHERE o.name = @name OR CAST(o.order_id AS STRING) = @bare
ORDER BY li.sku
"""


def as_date(raw) -> str:
    """BigQuery returns TIMESTAMP as epoch seconds in a JSON string."""
    try:
        return datetime.datetime.utcfromtimestamp(float(raw)).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return str(raw)


def normalise(raw: str) -> tuple:
    """Accept 22397, #22397, AMS*22397 — return the Shopify name and a bare form."""
    bare = re.sub(r"^(AM[ES]\s*\*\s*)", "", raw.strip(), flags=re.I).lstrip("#").strip()
    return f"#{bare}", bare


def run_query(sql: str, name: str, bare: str) -> list:
    body = {
        "query": sql,
        "useLegacySql": False,
        "timeoutMs": 60000,
        "maxResults": 200,
        "parameterMode": "NAMED",
        "queryParameters": [
            {"name": "name", "parameterType": {"type": "STRING"},
             "parameterValue": {"value": name}},
            {"name": "bare", "parameterType": {"type": "STRING"},
             "parameterValue": {"value": bare}},
        ],
    }
    # curl, not urllib: the session's proxy injects BigQuery credentials and its CA
    # is already configured for curl.
    proc = subprocess.run(
        ["curl", "-sS", "-X", "POST", ENDPOINT, "-H", "Content-Type: application/json",
         "-d", json.dumps(body)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise SystemExit(f"BigQuery request failed: {proc.stderr.strip()}")
    payload = json.loads(proc.stdout)
    if "error" in payload:
        raise SystemExit(f"BigQuery error: {payload['error'].get('message')}")
    fields = [f["name"] for f in payload.get("schema", {}).get("fields", [])]
    rows = []
    for row in payload.get("rows", []):
        rows.append({k: c.get("v") for k, c in zip(fields, row["f"])})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Look up a Shopify order for a CX case.")
    ap.add_argument("order", help="Order number: 22397, #22397 or AMS*22397")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a summary")
    args = ap.parse_args()

    name, bare = normalise(args.order)
    order_rows = run_query(ORDER_SQL, name, bare)
    if not order_rows:
        print(f"No Shopify order matching {name}.\n"
              f"Orders reach BigQuery about 20 minutes after they are placed, so a\n"
              f"brand-new order may not be there yet. Check the number, or read it off\n"
              f"the Shopify screen instead.", file=sys.stderr)
        return 1

    order = order_rows[0]
    items = run_query(ITEMS_SQL, name, bare)

    result = {
        "order": order["name"],
        "created_at": as_date(order["created_at"]),
        "financial_status": order["financial_status"],
        "fulfillment_status": order["fulfillment_status"],
        "total_price": order["total_price"],
        "currency": order["currency_code"],
        "total_refunded": order["total_refunded"],
        "line_items": [
            {"sku": i["sku"], "title": i["title"], "quantity": int(i["quantity"] or 0)}
            for i in items
        ],
        "not_available_from_bigquery": ["warehouse", "tracking_number", "partial_fulfilment_detail"],
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Order {result['order']}   {result['financial_status']} / {result['fulfillment_status']}")
    print(f"Placed {result['created_at']}   {result['total_price']} {result['currency']}")
    if result["total_refunded"] and float(result["total_refunded"]) > 0:
        print(f"Refunded so far: {result['total_refunded']}")
    print("\nOrdered:")
    for i in result["line_items"]:
        print(f"  {i['sku'] or '(no SKU)'} x {i['quantity']}   {i['title']}")
    print("\nStill needed before drafting — BigQuery does not hold these:")
    print("  - Warehouse: read the fulfillment Location on the Shopify order screen.")
    print("  - Tracking: the ShipStation shipment feed has been stale since Oct 2023.")
    print("  - How many units are actually wrong: that is in the Zendesk ticket.")
    print("  NOTE: quantities above are AS ORDERED, not the shortfall.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
