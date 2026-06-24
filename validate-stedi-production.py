#!/usr/bin/env python3
"""
Production Stedi Validator for Americanflat Invoices

Validates invoices against Stedi 945 EDI documents.
Supports: Yusen (old) and Taylored Services (new company name) invoice formats

Usage:
    python validate-stedi-production.py 751996 --json-file orders.json
    python validate-stedi-production.py 752319 --json-file orders.json --output results.json
"""

import json
import os
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# BigQuery
from google.cloud import bigquery

STEDI_API_KEY = os.getenv("STEDI_API_KEY", "22R7W4M.3KmGqoJdae1EebTmnXB9fAAc")
STEDI_BASE_URL = "https://core.us.stedi.com"
STEDI_API_VERSION = "2023-08-01"
PROJECT = "americanflat"
DATASET = "finance"


def query_stedi_for_order(order_id: str) -> dict:
    """Query Stedi for order: first check 945 (Shipping Advice), then 940 (Warehouse Order)."""
    if not order_id:
        return {"found": False, "order_id": order_id, "error": "Empty order ID"}

    try:
        clean_id = str(order_id).strip("'").strip()
        headers = {
            "Authorization": STEDI_API_KEY,
            "Content-Type": "application/json"
        }

        url = f"{STEDI_BASE_URL}/{STEDI_API_VERSION}/transactions"

        # First: Try 945 (Warehouse Shipping Advice - order shipped)
        params = {
            "transaction_type": "945",
            "businessIdentifier": clean_id
        }

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        items = result.get("items", [])

        if items:
            # Found in 945 (Shipped)
            doc = items[0]
            return {
                "found": True,
                "order_id": order_id,
                "transaction_type": "945",
                "status": "Shipped",
                "shipment_tracking": doc.get("shipmentId") or doc.get("shipmentTrackingNumber") or doc.get("shipment_id"),
                "ship_date": doc.get("shipDate") or doc.get("ship_date"),
                "carrier": doc.get("carrier"),
                "shipment_quantity": doc.get("quantity"),
                "stedi_document_id": doc.get("id"),
            }

        # Fallback: Try 940 (Warehouse Order - order received, not yet shipped)
        params["transaction_type"] = "940"
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        items = result.get("items", [])

        if items:
            # Found in 940 (Received at warehouse)
            doc = items[0]
            return {
                "found": True,
                "order_id": order_id,
                "transaction_type": "940",
                "status": "In Warehouse (Not Yet Shipped)",
                "shipment_tracking": None,
                "ship_date": None,
                "carrier": None,
                "shipment_quantity": doc.get("quantity"),
                "stedi_document_id": doc.get("id"),
            }

        # Not found in either 945 or 940
        return {"found": False, "order_id": order_id}

    except requests.exceptions.HTTPError as e:
        return {
            "found": False,
            "order_id": order_id,
            "error": f"Stedi API error: {e.response.status_code} {e.response.text[:100]}"
        }
    except requests.exceptions.RequestException as e:
        return {
            "found": False,
            "order_id": order_id,
            "error": f"Stedi API error: {str(e)}"
        }
    except Exception as e:
        return {
            "found": False,
            "order_id": order_id,
            "error": f"Unexpected error: {str(e)}"
        }


def validate_from_json(json_file: str, invoice_number: str) -> dict:
    """Validate orders from JSON file against Stedi."""
    with open(json_file) as f:
        data = json.load(f)

    line_items = data.get("line_items", [])
    return validate_orders(line_items, invoice_number, data.get("warehouse_location"))


def validate_orders(orders: list, invoice_number: str, warehouse: str = "FONTANA") -> dict:
    """Validate a list of orders against Stedi API."""
    total_orders = len(orders)
    stedi_results = {
        "total_orders": total_orders,
        "found": 0,
        "missing": 0,
        "orders": []
    }

    print(f"\n📋 Validating {total_orders} orders against Stedi 945...")

    for idx, order in enumerate(orders, 1):
        order_id = order.get("order_number")
        result = query_stedi_for_order(order_id)

        if result.get("found"):
            stedi_results["found"] += 1
            status = "✓"
        else:
            stedi_results["missing"] += 1
            status = "🚨"

        # Show first 20 + all missing
        if idx <= 20 or not result.get("found"):
            tracking = result.get("shipment_tracking", "N/A")
            error_msg = f" ({result.get('error')})" if result.get("error") else ""
            print(f"  {status} [{idx:5d}/{total_orders}] {str(order_id):<30} {tracking}{error_msg}")

        # Add to results
        stedi_results["orders"].append({
            **result,
            "service_type": order.get("service_type"),
            "quantity": order.get("quantity"),
        })

        if idx % 100 == 0:
            print(f"  ... {idx}/{total_orders} processed", file=sys.stderr)

    return {
        "invoice_number": invoice_number,
        "warehouse": warehouse,
        "validated_at": datetime.now().isoformat(),
        "stedi_validation": stedi_results
    }


def print_summary(result: dict) -> None:
    """Print validation summary."""
    stedi = result["stedi_validation"]
    success_rate = 100 * stedi["found"] / max(1, stedi["total_orders"])

    # Count transaction types
    found_945 = sum(1 for o in stedi["orders"] if o.get("found") and o.get("transaction_type") == "945")
    found_940 = sum(1 for o in stedi["orders"] if o.get("found") and o.get("transaction_type") == "940")

    print(f"\n{'='*80}")
    print(f"STEDI ORDER VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Invoice:       {result['invoice_number']}")
    print(f"Warehouse:     {result['warehouse']}")
    print(f"Total Orders:  {stedi['total_orders']}")
    print(f"{'─'*80}")
    print(f"✓ Found:       {stedi['found']} ({success_rate:.1f}%)")
    print(f"  ├─ 945 (Shipped):           {found_945}")
    print(f"  └─ 940 (In Warehouse):      {found_940}")
    print(f"🚨 Missing:     {stedi['missing']}")
    print(f"{'='*80}\n")

    # Show missing orders
    missing = [o for o in stedi["orders"] if not o.get("found")]
    if missing:
        print(f"🚨 {len(missing)} MISSING ORDERS (not found in Stedi 945 or 940):\n")
        print(f"Tip: Check if orders are still in transit or if data entry matches Stedi IDs\n")
        for order in missing[:30]:
            order_id = order.get("order_id", "N/A")
            error = f" - {order.get('error')}" if order.get("error") else ""
            print(f"  • {order_id}{error}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate invoices against Stedi 945 EDI",
        epilog="""
Examples:
  python validate-stedi-production.py 751996 --json-file orders.json
  python validate-stedi-production.py 752319 --json-file orders.json --output results.json
        """
    )
    parser.add_argument("invoice_number", help="Invoice number")
    parser.add_argument("--json-file", help="Path to parsed JSON file with order IDs")
    parser.add_argument("--warehouse", help="Warehouse location (auto-detected from JSON)")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--verbose", action="store_true", help="Show all orders")

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"Stedi Order Validation: Invoice {args.invoice_number}")
    print(f"{'='*80}")

    # Load from JSON file
    if args.json_file:
        if not Path(args.json_file).exists():
            print(f"❌ File not found: {args.json_file}")
            sys.exit(1)

        result = validate_from_json(args.json_file, args.invoice_number)
        warehouse = result.get("warehouse")
    else:
        print("❌ Must specify --json-file (BigQuery support coming soon)")
        sys.exit(1)

    # Print summary
    print_summary(result)

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"✓ Results saved to {args.output}\n")
    else:
        # Print JSON to stdout
        print("JSON Output:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
