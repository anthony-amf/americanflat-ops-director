#!/usr/bin/env python3
"""
Rate Card Validator for Yusen/Taylored Service Invoices

Validates invoice line items against the 2026 rate card.
Supports: Small Parcel (DTC/Vendor Central), LTL, Storage, Admin & VAS
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional
from google.cloud import bigquery

# Rate Card 2026 (as of Mar 30, 2026)
RATE_CARD = {
    "small_parcel_dtc": {
        "fontana": {
            "e_commerce_orders": 2.42,
            "additional_picks": 0.455,
            "tax_labor": 0.0,
        },
        "new_jersey": {
            "e_commerce_orders": 2.42,
            "additional_picks": 0.55,
            "tax_labor": 0.05,
        },
        "south_carolina": {
            "e_commerce_orders": 2.99,
            "additional_picks": 0.63,
            "tax_labor": 0.0,
        },
        "canada": {"e_commerce_orders": None, "additional_picks": None, "tax_labor": None},
    },
    "small_parcel_vendor": {
        "fontana": {
            "ship_carton": 2.05,
            "pick_unit": 1.05,
            "order_fee": 2.35,
            "manual_order": 2.35,
            "small_parcel_addl": 0.7478,
        },
        "new_jersey": {
            "ship_carton": 1.94,
            "pick_unit": 1.00,
            "order_fee": 2.36,
            "manual_order": None,
            "small_parcel_addl": 0.71,
        },
        "south_carolina": {
            "ship_carton": 1.79,
            "pick_unit": None,
            "order_fee": None,
            "manual_order": None,
            "small_parcel_addl": 0.84,
        },
        "canada": {
            "ship_carton": None,
            "pick_unit": None,
            "order_fee": None,
            "manual_order": None,
            "small_parcel_addl": 0.85,
        },
    },
    "ltl": {
        "fontana": {
            "ship_carton": 2.05,
            "pallet": 6.14,
            "stretchwrap": 4.69,
            "pick_unit": 1.05,
            "order_fee": 2.35,
            "bol_fee": 7.63,
            "manual_order": 2.35,
        },
        "new_jersey": {
            "ship_carton": 1.94,
            "pallet": 6.13,
            "stretchwrap": 4.72,
            "pick_unit": None,
            "order_fee": 2.36,
            "bol_fee": 6.83,
            "manual_order": None,
        },
        "south_carolina": {
            "ship_carton": 1.79,
            "pallet": 5.87,
            "stretchwrap": 5.88,
            "pick_unit": None,
            "order_fee": None,
            "bol_fee": 6.83,
            "manual_order": None,
        },
        "canada": {
            "ship_carton": 2.60,
            "pallet": 16.00,
            "stretchwrap": 6.00,
            "pick_unit": 1.95,
            "order_fee": None,
            "bol_fee": 8.00,
            "manual_order": 15.00,
        },
    },
    "storage": {
        "fontana": 5.90,
        "new_jersey": 5.98,
        "south_carolina": 5.09,
        "canada": 5.75,
    },
    "admin_vas": {
        "fontana": {"weekly": 2393.11, "vas_hourly": 59.82, "disposal": 13.68, "label": 0.45},
        "new_jersey": {"weekly": 1124.55, "vas_hourly": 53.55, "disposal": None, "label": 0.45},
        "south_carolina": {"weekly": 1092.00, "vas_hourly": 51.00, "disposal": None, "label": None},
        "canada": {"weekly": 1100.00, "vas_hourly": 50.00, "disposal": None, "label": None},
    },
}

WAREHOUSE_MAP = {
    "fontana": ["fontana", "fontana ca", "ts west (ca)"],
    "new_jersey": ["new jersey", "nj", "new jersey (nj)"],
    "south_carolina": ["south carolina", "sc"],
    "canada": ["canada", "ca warehouse"],
}


def normalize_warehouse(warehouse_name: str) -> Optional[str]:
    """Normalize warehouse name to rate card key."""
    if not warehouse_name:
        return None

    normalized = warehouse_name.lower().strip()
    for key, aliases in WAREHOUSE_MAP.items():
        if any(alias in normalized for alias in aliases):
            return key
    return None


def validate_invoice(invoice_number: str, invoice_type: str, warehouse: str,
                     line_items: List[Dict], amount: float, period_days: int = 7) -> Dict[str, Any]:
    """Validate invoice against rate card."""

    warehouse_key = normalize_warehouse(warehouse)
    if not warehouse_key:
        return {
            "invoice_number": invoice_number,
            "status": "error",
            "error": f"Unknown warehouse: {warehouse}"
        }

    result = {
        "invoice_number": invoice_number,
        "invoice_type": invoice_type,
        "warehouse": warehouse_key,
        "billed_amount": amount,
        "expected_amount": 0.0,
        "variance": 0.0,
        "variance_percent": 0.0,
        "items_validated": 0,
        "discrepancies": [],
        "status": "valid"
    }

    # Admin invoices
    if invoice_type.lower() == "admin":
        rates = RATE_CARD["admin_vas"].get(warehouse_key, {})
        weekly_fee = rates.get("weekly")
        if not weekly_fee:
            return {"invoice_number": invoice_number, "status": "error", "error": f"No admin rate for {warehouse}"}

        # Calculate expected: pro-rate for non-full weeks
        if period_days < 7:
            expected = (weekly_fee / 5) * period_days
        else:
            expected = weekly_fee

        result["expected_amount"] = round(expected, 2)
        result["variance"] = round(amount - expected, 2)
        result["variance_percent"] = round((result["variance"] / expected) * 100, 1)

        if abs(result["variance"]) > 0.01:
            result["status"] = "discrepancy"
            result["discrepancies"].append(
                f"Admin fee variance: charged ${amount}, expected ${expected} ({period_days} days)"
            )

        return result

    # Storage invoices
    if invoice_type.lower() == "storage":
        rate_per_pallet = RATE_CARD["storage"].get(warehouse_key)
        if not rate_per_pallet:
            return {"invoice_number": invoice_number, "status": "error", "error": f"No storage rate for {warehouse}"}

        total_pallets = sum(item.get("quantity", 0) for item in line_items if item.get("service_type") == "Storage")
        expected = round(total_pallets * rate_per_pallet, 2)

        result["expected_amount"] = expected
        result["items_validated"] = len(line_items)
        result["variance"] = round(amount - expected, 2)
        result["variance_percent"] = round((result["variance"] / expected) * 100, 1) if expected > 0 else 0

        if abs(result["variance"]) > 0.01:
            result["status"] = "discrepancy"
            result["discrepancies"].append(
                f"Storage: {total_pallets} pallets × ${rate_per_pallet} = ${expected}, charged ${amount}"
            )

        return result

    # Small Parcel / LTL validation (simplified - would need more detail from line items)
    result["expected_amount"] = amount  # Placeholder
    result["items_validated"] = len(line_items)
    result["status"] = "pending_detail"
    result["note"] = "Detailed line item validation requires itemized invoice data"

    return result


def validate_from_bigquery(invoice_number: str, project: str = "americanflat") -> Dict[str, Any]:
    """Fetch invoice from BigQuery and validate."""

    client = bigquery.Client(project=project)

    # Get invoice header
    query = f"""
    SELECT
      invoice_number, type_of_invoice, warehouse, amount, date, bill_period
    FROM americanflat.finance.yusen_invoices
    WHERE invoice_number = '{invoice_number}'
    LIMIT 1
    """

    result = client.query(query).result()
    rows = list(result)

    if not rows:
        return {"invoice_number": invoice_number, "status": "error", "error": "Invoice not found"}

    invoice = rows[0]

    # Calculate period days
    period_text = invoice.get("bill_period", "")
    # Try to parse from period text (e.g., "May 25-29" = 5 days)
    period_days = 7  # Default to weekly
    if "-" in period_text:
        try:
            parts = period_text.split("-")
            if len(parts) == 2:
                start_day = int(parts[0].split()[-1])
                end_day = int(parts[1])
                period_days = end_day - start_day + 1
        except:
            pass

    result = validate_invoice(
        invoice_number=invoice_number,
        invoice_type=invoice.get("type_of_invoice", ""),
        warehouse=invoice.get("warehouse", ""),
        line_items=[],
        amount=float(invoice.get("amount", 0)),
        period_days=period_days
    )

    result["date"] = str(invoice.get("date"))
    result["period"] = period_text

    return result


def print_report(result: Dict[str, Any]) -> None:
    """Print validation report."""
    print(f"\n{'='*80}")
    print(f"RATE CARD VALIDATION: Invoice {result['invoice_number']}")
    print(f"{'='*80}")

    if result.get("status") == "error":
        print(f"❌ ERROR: {result.get('error')}")
        return

    print(f"Type:           {result.get('invoice_type')}")
    print(f"Warehouse:      {result.get('warehouse')}")
    print(f"Period:         {result.get('period', 'N/A')}")
    print(f"{'─'*80}")
    print(f"Billed:         ${result.get('billed_amount', 0):,.2f}")
    print(f"Expected:       ${result.get('expected_amount', 0):,.2f}")
    print(f"Variance:       ${result.get('variance', 0):,.2f} ({result.get('variance_percent', 0):+.1f}%)")
    print(f"Status:         {result.get('status').upper()}")
    print(f"{'='*80}\n")

    if result.get("discrepancies"):
        print("⚠️  DISCREPANCIES:\n")
        for i, disc in enumerate(result["discrepancies"], 1):
            print(f"  {i}. {disc}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate invoices against Yusen/Taylored rate card",
        epilog="""
Examples:
  python rate-card-validator.py 752857
  python rate-card-validator.py 752319
  python rate-card-validator.py 751996 --list-all
        """
    )
    parser.add_argument("invoice_number", help="Invoice number to validate")
    parser.add_argument("--list-all", action="store_true", help="Validate all invoices in BigQuery")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    if args.list_all:
        # Validate all invoices
        client = bigquery.Client(project="americanflat")
        query = "SELECT DISTINCT invoice_number FROM americanflat.finance.yusen_invoices ORDER BY invoice_number DESC LIMIT 20"

        results = []
        for row in client.query(query).result():
            result = validate_from_bigquery(row['invoice_number'])
            results.append(result)
            if not args.json:
                print_report(result)

        if args.json:
            print(json.dumps(results, indent=2))
    else:
        result = validate_from_bigquery(args.invoice_number)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_report(result)


if __name__ == "__main__":
    main()
