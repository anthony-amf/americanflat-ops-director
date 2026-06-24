#!/usr/bin/env python3
"""
Production Stedi Validator for Americanflat Invoices

Validates invoices against Stedi 945 EDI documents.
Supports: Yusen (modern and legacy/Taylored formats)

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
STEDI_URL = "https://api.stedi.com/executions/execute"
PROJECT = "americanflat"
DATASET = "finance"


def query_stedi_for_order(order_id: str) -> dict:
    """Query Stedi API for order via stedi-po-lookup workflow."""
    if not order_id:
        return {"found": False, "order_id": order_id, "error": "Empty order ID"}

    try:
        headers = {"Authorization": f"Key {STEDI_API_KEY}"}
        payload = {
            "workflowName": "stedi-po-lookup",
            "input": {
                "businessIdentifier": str(order_id).strip("'").strip()
            }
        }

        response = requests.post(STEDI_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        result = response.json()

        if result.get("status") == "SUCCEEDED":
            output = result.get("output", {})
            return {
                "found": True,
                "order_id": order_id,
                "transaction_type": output.get("transactionType", "945"),
                "shipment_tracking": output.get("shipmentId") or output.get("shipmentTrackingNumber"),
                "ship_date": output.get("shipDate"),
                "carrier": output.get("carrier"),
                "shipment_quantity": output.get("shipmentQuantity"),
            }
        else:
            return {
                "found": False,
                "order_id": order_id,
                "stedi_status": result.get("status")
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

    print(f"\n{'='*80}")
    print(f"STEDI ORDER VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Invoice:       {result['invoice_number']}")
    print(f"Warehouse:     {result['warehouse']}")
    print(f"Total Orders:  {stedi['total_orders']}")
    print(f"Found:         {stedi['found']} ✓")
    print(f"Missing:       {stedi['missing']} 🚨")
    print(f"Success Rate:  {success_rate:.1f}%")
    print(f"{'='*80}\n")

    # Show missing orders
    missing = [o for o in stedi["orders"] if not o.get("found")]
    if missing:
        print(f"🚨 {len(missing)} MISSING ORDERS (not found in Stedi 945):\n")
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
