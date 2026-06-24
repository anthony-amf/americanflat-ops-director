#!/usr/bin/env python3
"""
Invoice Variance Validator for Americanflat

Fetches an invoice from BigQuery, compares charges against Notion rate card,
validates order IDs against Stedi EDI documents, and reports variances.

Usage:
    python invoice-variance-validator.py 751596
    python invoice-variance-validator.py 751596 --verbose
    python invoice-variance-validator.py 751596 --output json
    python invoice-variance-validator.py 751596 --skip-stedi
"""

import sys
import json
import argparse
import os
import subprocess
from typing import Any
from decimal import Decimal
from datetime import datetime

from google.cloud import bigquery
import anthropic


# BigQuery config (from your setup)
PROJECT = "americanflat"
DATASET = "finance"
TABLE = "yusen_invoices"

# Charge code mappings (from extraction/charge_code_map.json)
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
}

# Notion rate card (hardcoded from the Notion page we reviewed)
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

TOLERANCE = 5.00  # Flag if variance > ±$5

# Stedi API config
STEDI_BASE = "https://core.us.stedi.com/2023-08-01/transactions"


def fetch_invoice_from_bigquery(invoice_id: str) -> dict[str, Any]:
    """Fetch invoice from BigQuery."""
    client = bigquery.Client(project=PROJECT)

    query = f"""
    SELECT invoice_id, invoice_date, vendor_name, line_items, total_amount
    FROM `{PROJECT}.{DATASET}.{TABLE}`
    WHERE invoice_id = @invoice_id
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        rows = list(results)
        if not rows:
            raise ValueError(f"Invoice {invoice_id} not found in BigQuery")
        return rows[0]
    except Exception as e:
        print(f"Error querying BigQuery: {e}")
        raise


def infer_warehouse_from_vendor(vendor_name: str, invoice_data: dict) -> str:
    """Infer warehouse location from vendor or invoice data."""
    # Try to extract from raw_extraction or bill_to
    if "ship_to" in invoice_data:
        if "FONTANA" in invoice_data["ship_to"].upper():
            return "FONTANA"
        elif "NEW JERSEY" in invoice_data["ship_to"].upper():
            return "NEW JERSEY"
        elif "SAVANNAH" in invoice_data["ship_to"].upper() or "SOUTH CAROLINA" in invoice_data["ship_to"].upper():
            return "SOUTH CAROLINA"

    # Default based on vendor
    if "Fontana" in invoice_data.get("bill_to", ""):
        return "FONTANA"

    return "NEW JERSEY"  # Default


def map_charge_to_canonical(vendor: str, description: str, warehouse: str, invoice_type: str = "SMALL_PARCEL_LTL") -> str:
    """Map charge description to canonical code."""
    key = (vendor, invoice_type, description.upper(), warehouse.upper())
    return CHARGE_CODE_MAP.get(key, f"UNMAPPED_{description.upper()}")


def get_expected_rate(warehouse: str, canonical_code: str) -> float | None:
    """Look up expected rate from rate card."""
    return RATE_CARD.get((warehouse.upper(), canonical_code))


def query_stedi_for_order(order_id: str) -> dict[str, Any] | None:
    """
    Query Stedi for a specific order ID.

    Returns shipment info if found, None if not found.
    """
    try:
        api_key = os.environ.get("STEDI_API_KEY", "").strip()
        if not api_key:
            return None  # Skip if no API key

        # Query Stedi transactions by businessIdentifier (order ID)
        url = f"{STEDI_BASE}?businessIdentifier={order_id}&limit=100"

        cmd = [
            "curl", "-sS", "-m", "60",
            "-H", f"Authorization: {api_key}",
            url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        transactions = data.get("transactions", [])

        # Look for 945 (Warehouse Shipping Advice)
        for txn in transactions:
            if txn.get("transactionType") == "945":
                return {
                    "order_id": order_id,
                    "found": True,
                    "transaction_type": "945",
                    "shipment_id": txn.get("transactionId"),
                    "ship_date": txn.get("sentAt"),
                    "warehouse": txn.get("senderName", "Unknown"),
                }

        # Fall back to 940 (Warehouse Order)
        for txn in transactions:
            if txn.get("transactionType") == "940":
                return {
                    "order_id": order_id,
                    "found": True,
                    "transaction_type": "940",
                    "transaction_id": txn.get("transactionId"),
                    "warehouse": txn.get("senderName", "Unknown"),
                }

        # Not found in Stedi
        return {"order_id": order_id, "found": False}

    except Exception as e:
        return {"order_id": order_id, "found": False, "error": str(e)}


def validate_orders_with_stedi(order_ids: list[str]) -> dict[str, Any]:
    """
    Validate a list of order IDs against Stedi.

    Returns summary of found/missing orders.
    """
    if not order_ids:
        return {"total": 0, "found": 0, "missing": 0, "orders": []}

    results = []
    for order_id in order_ids:
        result = query_stedi_for_order(order_id)
        if result:
            results.append(result)

    found_count = sum(1 for r in results if r.get("found"))
    missing_count = len(order_ids) - found_count

    return {
        "total": len(order_ids),
        "found": found_count,
        "missing": missing_count,
        "orders": results,
    }


def validate_invoice(invoice_id: str, verbose: bool = False, skip_stedi: bool = False) -> dict[str, Any]:
    """Validate invoice by comparing billed vs. expected rates and validating orders with Stedi."""

    # Fetch from BigQuery
    invoice_data = fetch_invoice_from_bigquery(invoice_id)

    # Extract basic info
    invoice_id = invoice_data["invoice_id"]
    invoice_date = invoice_data["invoice_date"]
    vendor = invoice_data.get("vendor_name", "Unknown")
    warehouse = infer_warehouse_from_vendor(vendor, invoice_data)
    line_items_raw = invoice_data.get("line_items", [])
    total_billed = float(invoice_data.get("total_amount", 0))

    # Detect invoice type (for now, assume SMALL_PARCEL_LTL if has line items)
    invoice_type = "SMALL_PARCEL_LTL" if line_items_raw else "UNKNOWN"

    # Process line items
    validated_lines = []
    total_expected = 0.0
    total_variance = 0.0
    flagged_count = 0

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
            flagged = True  # Flag unmapped charges
        else:
            expected_amount = expected_rate * quantity
            variance = billed_amount - expected_amount
            variance_pct = (variance / expected_amount * 100) if expected_amount != 0 else 0
            flagged = abs(variance) > TOLERANCE
            total_expected += expected_amount
            total_variance += variance

        if flagged:
            flagged_count += 1

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
            "flagged": flagged,
        })

    # Compute overall variance
    overall_variance = total_billed - total_expected
    overall_variance_pct = (overall_variance / total_expected * 100) if total_expected != 0 else 0
    overall_flagged = abs(overall_variance) > TOLERANCE

    # Extract and validate order IDs (for Small Parcel/LTL invoices)
    order_ids = []
    stedi_validation = None

    if invoice_type == "SMALL_PARCEL_LTL" and not skip_stedi:
        # Extract order IDs from line descriptions that contain order info
        # (This is a simplification; in practice, order IDs would come from supporting docs)
        for line in validated_lines:
            if "ORDER" in line["description"].upper():
                # For now, we'd need the supporting Excel file to get actual order IDs
                # This is a placeholder for future enhancement
                pass

        # For now, skip Stedi validation if no explicit order IDs in the invoice
        # In production, you'd read order IDs from the supporting Excel file
        stedi_validation = {
            "status": "skipped",
            "reason": "Order IDs not found in invoice line items (would come from supporting docs Excel)"
        }

    result = {
        "invoice_id": invoice_id,
        "invoice_date": str(invoice_date),
        "vendor": vendor,
        "warehouse": warehouse,
        "invoice_type": invoice_type,
        "total_billed": round(total_billed, 2),
        "total_expected": round(total_expected, 2),
        "variance": round(overall_variance, 2),
        "variance_percent": round(overall_variance_pct, 2),
        "flagged": overall_flagged,
        "flagged_line_count": flagged_count,
        "line_items": validated_lines,
    }

    if stedi_validation:
        result["stedi_validation"] = stedi_validation

    return result


def format_report(result: dict[str, Any], output_format: str = "text") -> str:
    """Format validation result for display."""
    if output_format == "json":
        return json.dumps(result, indent=2)

    # Text format
    lines = [
        f"\n{'='*70}",
        f"Invoice Variance Report",
        f"{'='*70}",
        f"Invoice ID:      {result['invoice_id']}",
        f"Date:            {result['invoice_date']}",
        f"Vendor:          {result['vendor']}",
        f"Warehouse:       {result['warehouse']}",
        f"",
        f"Billed Total:    ${result['total_billed']:,.2f}",
        f"Expected Total:  ${result['total_expected']:,.2f}",
        f"Variance:        ${result['variance']:,.2f} ({result['variance_percent']:+.2f}%)",
        f"Status:          {'🚨 FLAGGED' if result['flagged'] else '✓ OK'}",
        f"",
        f"Line Items ({len(result['line_items'])} total, {result['flagged_line_count']} flagged):",
        f"{'-'*70}",
    ]

    # Sort: flagged first
    sorted_items = sorted(result['line_items'], key=lambda x: (not x['flagged'], x['description']))

    for item in sorted_items:
        flag = "🚨" if item['flagged'] else "✓"
        lines.append(
            f"{flag} {item['description']:<25} "
            f"Qty: {item['quantity']:>6.0f}  "
            f"Billed: ${item['billed_amount']:>10,.2f}  "
            f"Expected: ${item['expected_amount']:>10,.2f}  "
            f"Variance: ${item['variance']:>+8,.2f}"
        )

    lines.append(f"{'='*70}")

    # Stedi validation if present
    if "stedi_validation" in result:
        stedi = result["stedi_validation"]
        lines.append("")
        lines.append("Stedi Order Validation:")
        lines.append(f"{'-'*70}")
        if stedi.get("status") == "skipped":
            lines.append(f"⚠ {stedi.get('reason')}")
        else:
            lines.append(f"Total Orders: {stedi.get('total')}")
            lines.append(f"Found in Stedi: {stedi.get('found')}")
            lines.append(f"Missing: {stedi.get('missing')}")
            if stedi.get("orders"):
                lines.append("")
                for order in stedi["orders"]:
                    status = "✓" if order.get("found") else "✗"
                    txn_type = order.get("transaction_type", "Unknown")
                    lines.append(f"  {status} {order['order_id']:<20} [{txn_type}]")
        lines.append(f"{'='*70}\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check invoice against rate card and Stedi orders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python invoice-variance-validator.py 751596
  python invoice-variance-validator.py 751596 --verbose
  python invoice-variance-validator.py 751596 --output json
  python invoice-variance-validator.py 751596 --skip-stedi

Environment:
  STEDI_API_KEY - Your Stedi API key (required for order validation)
        """
    )
    parser.add_argument("invoice_id", help="Invoice ID to validate")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--skip-stedi", action="store_true", help="Skip Stedi order validation")

    args = parser.parse_args()

    try:
        result = validate_invoice(args.invoice_id, verbose=args.verbose, skip_stedi=args.skip_stedi)
        report = format_report(result, output_format=args.output)
        print(report)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
