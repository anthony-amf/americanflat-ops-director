#!/usr/bin/env python3
"""
Invoice + Stedi Validator for Americanflat

Complete validation workflow:
1. Fetch invoice from BigQuery
2. Compare charges vs. rate card (variance analysis)
3. Fetch order IDs from yusen_invoice_line_items
4. Validate each order against Stedi EDI documents
5. Report rate variances + missing orders

Usage:
    python invoice-stedi-validator.py 751596
    python invoice-stedi-validator.py 751596 --output json
    python invoice-stedi-validator.py 751596 --skip-stedi
"""

import sys
import json
import argparse
import os
import subprocess
from typing import Any
from datetime import datetime

from google.cloud import bigquery


# BigQuery config
PROJECT = "americanflat"
DATASET = "finance"
INVOICES_TABLE = "yusen_invoices"
LINE_ITEMS_TABLE = "yusen_invoice_line_items"

# Stedi API
STEDI_BASE = "https://core.us.stedi.com/2023-08-01/transactions"
TOLERANCE = 5.00  # Flag if variance > ±$5

# Charge code mappings
CHARGE_CODE_MAP = {
    ("Yusen", "SMALL_PARCEL_LTL", "E-COMMERCE", "NEW JERSEY"): "SMALL_PARCEL_ECOM_ORDER",
    ("Yusen", "SMALL_PARCEL_LTL", "E-COMMERCE", "FONTANA"): "SMALL_PARCEL_ECOM_ORDER",
    ("Yusen", "SMALL_PARCEL_LTL", "E-COMMERCE", "SOUTH CAROLINA"): "SMALL_PARCEL_ECOM_ORDER",
    ("Yusen", "SMALL_PARCEL_LTL", "SHIP CARTONS", "NEW JERSEY"): "SMALL_PARCEL_SHIP_CARTONS",
    ("Yusen", "SMALL_PARCEL_LTL", "SHIP CARTONS", "FONTANA"): "SMALL_PARCEL_SHIP_CARTONS",
    ("Yusen", "SMALL_PARCEL_LTL", "ORDERS", "NEW JERSEY"): "SMALL_PARCEL_ORDERS",
    ("Yusen", "SMALL_PARCEL_LTL", "SMALL PARCELS", "NEW JERSEY"): "SMALL_PARCEL_EXTRA_PICKS",
    ("Yusen", "SMALL_PARCEL_LTL", "STANDARD PALLETS", "NEW JERSEY"): "LTL_STANDARD_PALLETS",
    ("Yusen", "SMALL_PARCEL_LTL", "STRETCHWRAP PALLETS", "NEW JERSEY"): "LTL_STRETCHWRAP_PALLETS",
    ("Yusen", "SMALL_PARCEL_LTL", "PACK CARTONS", "NEW JERSEY"): "LTL_PACK_CARTONS",
    ("Yusen", "SMALL_PARCEL_LTL", "BOLS", "NEW JERSEY"): "LTL_BOL_FEE",
    ("Yusen", "SMALL_PARCEL_LTL", "STANDARD PALLETS", "FONTANA"): "LTL_STANDARD_PALLETS",
    ("Yusen", "SMALL_PARCEL_LTL", "STRETCHWRAP PALLETS", "FONTANA"): "LTL_STRETCHWRAP_PALLETS",
    ("Yusen", "SMALL_PARCEL_LTL", "BOLS", "FONTANA"): "LTL_BOL_FEE",
}

# Rate card (2026 rates from Notion)
RATE_CARD = {
    ("NEW JERSEY", "SMALL_PARCEL_ECOM_ORDER"): 2.42,
    ("NEW JERSEY", "SMALL_PARCEL_SHIP_CARTONS"): 1.9425,
    ("NEW JERSEY", "SMALL_PARCEL_ORDERS"): 2.3625,
    ("NEW JERSEY", "SMALL_PARCEL_EXTRA_PICKS"): 0.71,
    ("NEW JERSEY", "LTL_STANDARD_PALLETS"): 5.6235,
    ("NEW JERSEY", "LTL_STRETCHWRAP_PALLETS"): 4.7250,
    ("NEW JERSEY", "LTL_PACK_CARTONS"): 1.0000,
    ("NEW JERSEY", "LTL_BOL_FEE"): 6.8250,
    ("FONTANA", "SMALL_PARCEL_ECOM_ORDER"): 2.42,
    ("FONTANA", "SMALL_PARCEL_SHIP_CARTONS"): 1.9425,
    ("FONTANA", "SMALL_PARCEL_ORDERS"): 2.35,
    ("FONTANA", "SMALL_PARCEL_EXTRA_PICKS"): 0.7478,
    ("FONTANA", "LTL_STANDARD_PALLETS"): 6.14,
    ("FONTANA", "LTL_STRETCHWRAP_PALLETS"): 4.69,
    ("FONTANA", "LTL_BOL_FEE"): 7.63,
    ("SOUTH CAROLINA", "SMALL_PARCEL_ECOM_ORDER"): 2.99,
    ("SOUTH CAROLINA", "SMALL_PARCEL_SHIP_CARTONS"): 0.63,
    ("SOUTH CAROLINA", "SMALL_PARCEL_EXTRA_PICKS"): 0.84,
    ("SOUTH CAROLINA", "LTL_STANDARD_PALLETS"): 5.87,
    ("SOUTH CAROLINA", "LTL_STRETCHWRAP_PALLETS"): 5.88,
    ("SOUTH CAROLINA", "LTL_BOL_FEE"): 6.83,
}


def infer_warehouse_from_data(invoice_data: dict) -> str:
    """Infer warehouse location from invoice data."""
    if "ship_to" in invoice_data:
        ship_to = invoice_data["ship_to"].upper()
        if "FONTANA" in ship_to:
            return "FONTANA"
        elif "SAVANNAH" in ship_to or "SOUTH CAROLINA" in ship_to:
            return "SOUTH CAROLINA"
    return "NEW JERSEY"  # Default


def map_charge_to_canonical(vendor: str, description: str, warehouse: str, invoice_type: str = "SMALL_PARCEL_LTL") -> str:
    """Map charge description to canonical code."""
    key = (vendor, invoice_type, description.upper(), warehouse.upper())
    return CHARGE_CODE_MAP.get(key, f"UNMAPPED_{description.upper()}")


def get_expected_rate(warehouse: str, canonical_code: str) -> float | None:
    """Look up expected rate from rate card."""
    return RATE_CARD.get((warehouse.upper(), canonical_code))


def fetch_invoice_from_bigquery(invoice_id: str) -> dict[str, Any]:
    """Fetch invoice from yusen_invoices table."""
    client = bigquery.Client(project=PROJECT)

    query = f"""
    SELECT invoice_id, invoice_date, vendor_name, line_items, total_amount, ship_to
    FROM `{PROJECT}.{DATASET}.{INVOICES_TABLE}`
    WHERE invoice_id = @invoice_id
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
        ]
    )

    results = client.query(query, job_config=job_config).result()
    rows = list(results)
    if not rows:
        raise ValueError(f"Invoice {invoice_id} not found")
    return rows[0]


def fetch_order_ids_from_bigquery(invoice_id: str) -> dict[str, list[dict]]:
    """
    Fetch order IDs and their associated line items from BigQuery.

    Returns:
        {
            "1Z999AA10123456789": [
                {"service_type": "Small Parcel", "quantity": 1, "amount": 45.67},
                ...
            ],
            ...
        }
    """
    client = bigquery.Client(project=PROJECT)

    query = f"""
    SELECT order_number, service_type, quantity, amount
    FROM `{PROJECT}.{DATASET}.{LINE_ITEMS_TABLE}`
    WHERE invoice_number = @invoice_id
      AND order_number IS NOT NULL
    ORDER BY order_number, line_item_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
        ]
    )

    results = client.query(query, job_config=job_config).result()

    # Group by order number
    order_map = {}
    for row in results:
        order_num = row[0]
        if order_num not in order_map:
            order_map[order_num] = []
        order_map[order_num].append({
            "service_type": row[1],
            "quantity": row[2],
            "amount": row[3],
        })

    return order_map


def query_stedi_for_order(order_id: str) -> dict[str, Any]:
    """
    Query Stedi for a specific order ID.

    Returns shipment/tracking info from 945 (Warehouse Shipping Advice) document.
    """
    try:
        api_key = os.environ.get("STEDI_API_KEY", "").strip()
        if not api_key:
            return {"order_id": order_id, "found": False, "reason": "No STEDI_API_KEY"}

        # Query Stedi by order ID
        url = f"{STEDI_BASE}?businessIdentifier={order_id}&limit=10"

        cmd = ["curl", "-sS", "-m", "60", "-H", f"Authorization: {api_key}", url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return {"order_id": order_id, "found": False, "error": "Stedi API error"}

        data = json.loads(result.stdout)
        transactions = data.get("transactions", [])

        # Look for 945 (Warehouse Shipping Advice) - contains tracking/shipment info
        for txn in transactions:
            if txn.get("transactionType") == "945":
                return {
                    "order_id": order_id,
                    "found": True,
                    "transaction_type": "945",
                    "transaction_id": txn.get("transactionId"),
                    "shipment_tracking": txn.get("transactionId"),  # Shipment ID from 945
                    "ship_date": txn.get("sentAt"),
                    "sender": txn.get("senderName"),
                }

        # Fall back to 940 (Warehouse Order) - order received but not yet shipped
        for txn in transactions:
            if txn.get("transactionType") == "940":
                return {
                    "order_id": order_id,
                    "found": True,
                    "transaction_type": "940",
                    "transaction_id": txn.get("transactionId"),
                    "status": "Order received, not yet shipped",
                }

        # Not found in any EDI document
        return {"order_id": order_id, "found": False}

    except Exception as e:
        return {"order_id": order_id, "found": False, "error": str(e)}


def validate_invoice(invoice_id: str, skip_stedi: bool = False) -> dict[str, Any]:
    """Complete validation: rate card + Stedi orders."""

    # Fetch invoice
    invoice_data = fetch_invoice_from_bigquery(invoice_id)

    # Extract basic info
    invoice_id = invoice_data["invoice_id"]
    invoice_date = invoice_data["invoice_date"]
    vendor = invoice_data.get("vendor_name", "Unknown")
    warehouse = infer_warehouse_from_data(invoice_data)
    line_items_raw = invoice_data.get("line_items", [])
    total_billed = float(invoice_data.get("total_amount", 0))

    # === RATE CARD VALIDATION ===
    validated_lines = []
    total_expected = 0.0
    rate_flagged_count = 0

    for item in line_items_raw:
        description = item.get("description", "")
        quantity = float(item.get("quantity", 0))
        billed_rate = float(item.get("rate", 0))
        billed_amount = float(item.get("amount", 0))

        # Map to canonical code
        canonical_code = map_charge_to_canonical(vendor, description, warehouse)

        # Look up expected rate
        expected_rate = get_expected_rate(warehouse, canonical_code)

        if expected_rate is None:
            expected_amount = None
            variance = None
            variance_pct = None
            rate_flagged = True
        else:
            expected_amount = expected_rate * quantity
            variance = billed_amount - expected_amount
            variance_pct = (variance / expected_amount * 100) if expected_amount != 0 else 0
            rate_flagged = abs(variance) > TOLERANCE
            total_expected += expected_amount

        if rate_flagged:
            rate_flagged_count += 1

        validated_lines.append({
            "description": description,
            "canonical_code": canonical_code,
            "quantity": quantity,
            "billed_rate": billed_rate,
            "expected_rate": expected_rate,
            "billed_amount": billed_amount,
            "expected_amount": expected_amount,
            "variance": round(variance, 2) if variance is not None else None,
            "variance_percent": round(variance_pct, 2) if variance_pct is not None else None,
            "flagged": rate_flagged,
        })

    # Compute overall variance
    overall_variance = total_billed - total_expected
    overall_variance_pct = (overall_variance / total_expected * 100) if total_expected != 0 else 0
    overall_rate_flagged = abs(overall_variance) > TOLERANCE

    # === STEDI VALIDATION ===
    stedi_validation = None
    if not skip_stedi:
        order_map = fetch_order_ids_from_bigquery(invoice_id)
        stedi_results = []

        for order_id, line_items in order_map.items():
            result = query_stedi_for_order(order_id)

            # Enrich with invoice line item details
            result["invoice_line_items"] = line_items
            result["total_amount"] = sum(item.get("amount", 0) for item in line_items)

            stedi_results.append(result)

        found_count = sum(1 for r in stedi_results if r.get("found"))
        missing_count = len(order_map) - found_count

        stedi_validation = {
            "total_orders": len(order_map),
            "found": found_count,
            "missing": missing_count,
            "orders": stedi_results,
        }

    return {
        "invoice_id": invoice_id,
        "invoice_date": str(invoice_date),
        "vendor": vendor,
        "warehouse": warehouse,
        "total_billed": round(total_billed, 2),
        "total_expected": round(total_expected, 2),
        "rate_variance": {
            "delta": round(overall_variance, 2),
            "delta_percent": round(overall_variance_pct, 2),
            "flagged": overall_rate_flagged,
            "flagged_line_count": rate_flagged_count,
            "line_items": validated_lines,
        },
        "stedi_validation": stedi_validation,
    }


def format_report(result: dict[str, Any]) -> str:
    """Format report for display."""
    rate_variance = result.get("rate_variance", {})
    stedi = result.get("stedi_validation")

    lines = [
        f"\n{'='*80}",
        f"Invoice Validation Report",
        f"{'='*80}",
        f"Invoice ID:      {result['invoice_id']}",
        f"Date:            {result['invoice_date']}",
        f"Vendor:          {result['vendor']}",
        f"Warehouse:       {result['warehouse']}",
        f"",
    ]

    # Rate Card Validation
    lines.extend([
        f"RATE CARD VALIDATION",
        f"{'-'*80}",
        f"Total Billed:    ${result['total_billed']:,.2f}",
        f"Total Expected:  ${result['total_expected']:,.2f}",
        f"Variance:        ${rate_variance.get('delta', 0):,.2f} ({rate_variance.get('delta_percent', 0):+.2f}%)",
        f"Status:          {'🚨 FLAGGED' if rate_variance.get('flagged') else '✓ OK'}",
        f"",
        f"Line Items ({len(rate_variance.get('line_items', []))} total, {rate_variance.get('flagged_line_count', 0)} flagged):",
    ])

    # Flagged line items first
    line_items = rate_variance.get("line_items", [])
    sorted_items = sorted(line_items, key=lambda x: (not x['flagged'], x['description']))

    for item in sorted_items:
        flag = "🚨" if item['flagged'] else "✓"
        if item['expected_amount'] is not None:
            lines.append(
                f"  {flag} {item['description']:<25} "
                f"Qty: {item['quantity']:>6.0f}  "
                f"Billed: ${item['billed_amount']:>10,.2f}  "
                f"Expected: ${item['expected_amount']:>10,.2f}  "
                f"Var: ${item['variance']:>+8,.2f}"
            )
        else:
            lines.append(
                f"  {flag} {item['description']:<25} "
                f"[UNMAPPED - Code: {item['canonical_code']}]"
            )

    # Stedi Validation
    if stedi:
        lines.extend([
            f"",
            f"STEDI ORDER VALIDATION",
            f"{'-'*80}",
            f"Total Orders:    {stedi.get('total_orders', 0)}",
            f"Found:           {stedi.get('found', 0)} ✓",
            f"Missing:         {stedi.get('missing', 0)} 🚨",
            f"",
        ])

        if stedi.get("orders"):
            orders = stedi["orders"]
            flagged_orders = [o for o in orders if not o.get("found")]

            # Show flagged orders first with details
            if flagged_orders:
                lines.append("DISCREPANCIES - Missing from Stedi 945:")
                lines.append(f"{'-'*80}")

                for order in flagged_orders:
                    lines.append(f"🚨 Order ID (Excel):  {order['order_id']}")
                    lines.append(f"   Stedi Status:       NOT FOUND")
                    line_items = order.get("invoice_line_items", [])
                    if line_items:
                        total_amount = order.get("total_amount", 0)
                        lines.append(f"   Service Type(s):    {', '.join(set(item.get('service_type', 'Unknown') for item in line_items))}")
                        lines.append(f"   Invoice Total:      ${total_amount:,.2f}")
                        lines.append(f"")
                        for item in line_items:
                            lines.append(
                                f"     • {item.get('service_type', 'Unknown'):<18} "
                                f"Qty: {item.get('quantity', 0):<6} Amount: ${item.get('amount', 0):>10,.2f}"
                            )
                    lines.append("")

            # Show found orders with tracking
            found_orders = [o for o in orders if o.get("found")]
            if found_orders:
                lines.append("")
                lines.append("VALIDATED - Found in Stedi 945:")
                lines.append(f"{'-'*80}")
                for order in found_orders:
                    txn_type = order.get("transaction_type", "?")
                    tracking = order.get("shipment_tracking", "N/A")
                    ship_date = order.get("ship_date", "N/A")
                    lines.append(f"✓ Order ID (Excel):   {order['order_id']}")
                    lines.append(f"  Shipment Tracking:  {tracking}")
                    if ship_date and ship_date != "N/A":
                        lines.append(f"  Ship Date:          {ship_date}")
                    if txn_type == "940":
                        lines.append(f"  Status:             {order.get('status', 'Order received, pending shipment')}")
                    lines.append("")
    else:
        lines.extend([
            f"",
            f"STEDI ORDER VALIDATION",
            f"{'-'*80}",
            f"⚠ Skipped (use --skip-stedi=false or set STEDI_API_KEY)",
        ])

    lines.append(f"{'='*80}\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Invoice + Stedi validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python invoice-stedi-validator.py 751596
  python invoice-stedi-validator.py 751596 --output json
  python invoice-stedi-validator.py 751596 --skip-stedi

Environment:
  STEDI_API_KEY - Your Stedi API key (required for order validation)
        """
    )
    parser.add_argument("invoice_id", help="Invoice ID to validate")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--skip-stedi", action="store_true", help="Skip Stedi order validation")

    args = parser.parse_args()

    try:
        result = validate_invoice(args.invoice_id, skip_stedi=args.skip_stedi)

        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print(format_report(result))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
