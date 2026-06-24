#!/usr/bin/env python3
"""
Standalone Stedi validator for invoice 752319 (Taylored Services).
Reads order IDs from JSON file and validates against Stedi 945 EDI documents.
"""

import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

STEDI_API_KEY = os.getenv("STEDI_API_KEY", "22R7W4M.3KmGqoJdae1EebTmnXB9fAAc")
STEDI_URL = "https://api.stedi.com/executions/execute"


def query_stedi_for_order(order_id: str) -> dict:
    """Query Stedi for order via 945 EDI document."""
    try:
        headers = {"Authorization": f"Key {STEDI_API_KEY}"}
        payload = {
            "workflowName": "stedi-po-lookup",
            "input": {
                "businessIdentifier": str(order_id).strip("'")
            }
        }

        response = requests.post(STEDI_URL, json=payload, headers=headers, timeout=10)
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
            }
        else:
            return {"found": False, "order_id": order_id}

    except Exception as e:
        print(f"⚠️  Stedi query error for {order_id}: {e}", file=sys.stderr)
        return {"found": False, "order_id": order_id, "error": str(e)}


def validate_invoice(json_file: str, invoice_number: str) -> dict:
    """Validate invoice against Stedi."""
    with open(json_file) as f:
        data = json.load(f)

    line_items = data.get("line_items", [])
    total_orders = len(line_items)

    # Query each order against Stedi
    stedi_results = {
        "total_orders": total_orders,
        "found": 0,
        "missing": 0,
        "orders": []
    }

    print(f"\n📋 Validating {total_orders} orders against Stedi 945...")
    for idx, item in enumerate(line_items, 1):
        order_id = item.get("order_number")
        result = query_stedi_for_order(order_id)

        if result.get("found"):
            stedi_results["found"] += 1
            status = "✓"
        else:
            stedi_results["missing"] += 1
            status = "🚨"

        if idx <= 20 or not result.get("found"):  # Show first 20 + all missing
            tracking = result.get("shipment_tracking", "N/A")
            print(f"  {status} [{idx:4d}/{total_orders}] {order_id:<25} {tracking}")

        stedi_results["orders"].append(result)

        if idx % 100 == 0:
            print(f"  ... {idx}/{total_orders} processed", file=sys.stderr)

    return {
        "invoice_number": invoice_number,
        "invoice_date": datetime.now().isoformat(),
        "warehouse": data.get("warehouse_location"),
        "source_file": json_file,
        "stedi_validation": stedi_results
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate-752319.py <json_file> [invoice_number]")
        sys.exit(1)

    json_file = sys.argv[1]
    invoice_number = sys.argv[2] if len(sys.argv) > 2 else Path(json_file).stem

    if not Path(json_file).exists():
        print(f"❌ File not found: {json_file}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"Stedi Validation: Invoice {invoice_number}")
    print(f"{'='*80}")

    result = validate_invoice(json_file, invoice_number)

    # Print summary
    stedi = result["stedi_validation"]
    print(f"\n{'='*80}")
    print(f"STEDI ORDER VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total Orders:  {stedi['total_orders']}")
    print(f"Found:         {stedi['found']} ✓")
    print(f"Missing:       {stedi['missing']} 🚨")
    print(f"Success Rate:  {100 * stedi['found'] / stedi['total_orders']:.1f}%")
    print(f"{'='*80}\n")

    # Show missing orders
    missing = [o for o in stedi['orders'] if not o.get('found')]
    if missing:
        print(f"🚨 {len(missing)} MISSING ORDERS (not found in Stedi 945):\n")
        for order in missing[:20]:
            print(f"  • {order['order_id']}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        print()

    # Save JSON output
    output_file = f"{invoice_number}_validation.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"✓ Results saved to {output_file}\n")
