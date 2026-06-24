#!/usr/bin/env python3
"""
Demo: Complete Invoice Validation for 751596

Shows what the validator outputs with real data from invoice 751996.
No BigQuery connection needed - uses sample data.
"""

import json


# Sample data from invoice 751996 (New Jersey Small Parcel/LTL)
INVOICE_751996 = {
    "invoice_id": "751996",
    "invoice_date": "2026-05-19",
    "vendor": "Yusen Logistics",
    "warehouse": "NEW JERSEY",
    "total_billed": 13445.58,
    "total_expected": 13445.58,
    "rate_variance": {
        "delta": 0.0,
        "delta_percent": 0.0,
        "flagged": False,
        "flagged_line_count": 0,
        "line_items": [
            {
                "description": "E-COMMERCE",
                "canonical_code": "SMALL_PARCEL_ECOM_ORDER",
                "quantity": 3201,
                "billed_rate": 2.42,
                "expected_rate": 2.42,
                "billed_amount": 7746.42,
                "expected_amount": 7746.42,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "SHIP CARTONS",
                "canonical_code": "SMALL_PARCEL_SHIP_CARTONS",
                "quantity": 114,
                "billed_rate": 1.9425,
                "expected_rate": 1.9425,
                "billed_amount": 221.45,
                "expected_amount": 221.45,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "ORDERS",
                "canonical_code": "SMALL_PARCEL_ORDERS",
                "quantity": 28,
                "billed_rate": 2.3625,
                "expected_rate": 2.3625,
                "billed_amount": 66.15,
                "expected_amount": 66.15,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "SMALL PARCELS",
                "canonical_code": "SMALL_PARCEL_EXTRA_PICKS",
                "quantity": 114,
                "billed_rate": 0.71,
                "expected_rate": 0.71,
                "billed_amount": 80.94,
                "expected_amount": 80.94,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "SHIP CARTONS",
                "canonical_code": "SMALL_PARCEL_SHIP_CARTONS",
                "quantity": 2031,
                "billed_rate": 1.9425,
                "expected_rate": 1.9425,
                "billed_amount": 3945.22,
                "expected_amount": 3945.22,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "STANDARD PALLETS",
                "canonical_code": "LTL_STANDARD_PALLETS",
                "quantity": 84,
                "billed_rate": 5.6235,
                "expected_rate": 5.6235,
                "billed_amount": 472.37,
                "expected_amount": 472.37,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "STRETCHWRAP PALLETS",
                "canonical_code": "LTL_STRETCHWRAP_PALLETS",
                "quantity": 84,
                "billed_rate": 4.725,
                "expected_rate": 4.725,
                "billed_amount": 396.9,
                "expected_amount": 396.9,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "PACK CARTONS",
                "canonical_code": "LTL_PACK_CARTONS",
                "quantity": 167,
                "billed_rate": 1.0,
                "expected_rate": 1.0,
                "billed_amount": 167.0,
                "expected_amount": 167.0,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "ORDERS",
                "canonical_code": "SMALL_PARCEL_ORDERS",
                "quantity": 38,
                "billed_rate": 2.3625,
                "expected_rate": 2.3625,
                "billed_amount": 89.78,
                "expected_amount": 89.78,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
            {
                "description": "BOLS",
                "canonical_code": "LTL_BOL_FEE",
                "quantity": 38,
                "billed_rate": 6.825,
                "expected_rate": 6.825,
                "billed_amount": 259.35,
                "expected_amount": 259.35,
                "variance": 0.0,
                "variance_percent": 0.0,
                "flagged": False,
            },
        ],
    },
    "stedi_validation": {
        "total_orders": 47,
        "found": 45,
        "missing": 2,
        "orders": [
            {
                "order_id": "AMF-751996-001",
                "found": True,
                "transaction_type": "945",
                "shipment_tracking": "SHIP_20260519_00001",
                "ship_date": "2026-05-19T10:30:00Z",
                "invoice_line_items": [
                    {"service_type": "Small Parcel", "quantity": 50, "amount": 242.00}
                ],
                "total_amount": 242.00,
            },
            {
                "order_id": "AMF-751996-002",
                "found": True,
                "transaction_type": "945",
                "shipment_tracking": "SHIP_20260519_00002",
                "ship_date": "2026-05-19T11:15:00Z",
                "invoice_line_items": [
                    {"service_type": "Small Parcel", "quantity": 75, "amount": 181.50}
                ],
                "total_amount": 181.50,
            },
            {
                "order_id": "AMF-751996-003",
                "found": True,
                "transaction_type": "945",
                "shipment_tracking": "SHIP_20260519_00003",
                "ship_date": "2026-05-19T14:45:00Z",
                "invoice_line_items": [
                    {"service_type": "Small Parcel", "quantity": 100, "amount": 242.00}
                ],
                "total_amount": 242.00,
            },
            {
                "order_id": "1Z999AA10999999999",
                "found": False,
                "invoice_line_items": [
                    {"service_type": "Small Parcel", "quantity": 25, "amount": 60.50},
                    {"service_type": "Small Parcel", "quantity": 30, "amount": 72.60}
                ],
                "total_amount": 133.10,
            },
            {
                "order_id": "1Z999AA10888888888",
                "found": False,
                "invoice_line_items": [
                    {"service_type": "LTL", "quantity": 2, "amount": 151.47}
                ],
                "total_amount": 151.47,
            },
        ]
    }
}


def format_report(result):
    """Format validation report."""
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
        f"RATE CARD VALIDATION",
        f"{'-'*80}",
        f"Total Billed:    ${result['total_billed']:,.2f}",
        f"Total Expected:  ${result['total_expected']:,.2f}",
        f"Variance:        ${rate_variance.get('delta', 0):,.2f} ({rate_variance.get('delta_percent', 0):+.2f}%)",
        f"Status:          {'🚨 FLAGGED' if rate_variance.get('flagged') else '✓ OK'}",
        f"",
        f"Line Items ({len(rate_variance.get('line_items', []))} total, {rate_variance.get('flagged_line_count', 0)} flagged):",
    ]

    # Flagged first
    line_items = rate_variance.get("line_items", [])
    sorted_items = sorted(line_items, key=lambda x: (not x['flagged'], x['description']))

    for item in sorted_items:
        flag = "🚨" if item['flagged'] else "✓"
        lines.append(
            f"  {flag} {item['description']:<25} "
            f"Qty: {item['quantity']:>6.0f}  "
            f"Billed: ${item['billed_amount']:>10,.2f}  "
            f"Expected: ${item['expected_amount']:>10,.2f}  "
            f"Var: ${item['variance']:>+8,.2f}"
        )

    # Stedi
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

        orders = stedi.get("orders", [])
        flagged = [o for o in orders if not o.get("found")]
        found = [o for o in orders if o.get("found")]

        # Show flagged orders with details
        if flagged:
            lines.append("DISCREPANCIES - Missing from Stedi 945:")
            lines.append(f"{'-'*80}")

            for order in flagged:
                lines.append(f"🚨 Order ID (Excel):  {order['order_id']}")
                lines.append(f"   Stedi Status:       NOT FOUND")
                line_items = order.get("invoice_line_items", [])
                if line_items:
                    total_amount = order.get("total_amount", 0)
                    service_types = set(item.get('service_type', 'Unknown') for item in line_items)
                    lines.append(f"   Service Type(s):    {', '.join(service_types)}")
                    lines.append(f"   Invoice Total:      ${total_amount:,.2f}")
                    lines.append(f"")
                    for item in line_items:
                        lines.append(
                            f"     • {item.get('service_type', 'Unknown'):<18} "
                            f"Qty: {item.get('quantity', 0):<6} Amount: ${item.get('amount', 0):>10,.2f}"
                        )
                lines.append("")

        # Show found orders with tracking
        if found:
            lines.append("")
            lines.append("VALIDATED - Found in Stedi 945:")
            lines.append(f"{'-'*80}")
            for order in found[:10]:  # Show first 10
                txn_type = order.get("transaction_type", "?")
                tracking = order.get("shipment_tracking", "N/A")
                ship_date = order.get("ship_date", "N/A")
                lines.append(f"✓ Order ID (Excel):   {order['order_id']}")
                lines.append(f"  Shipment Tracking:  {tracking}")
                if ship_date and ship_date != "N/A":
                    # Format ship date nicely
                    if "T" in str(ship_date):
                        ship_date = str(ship_date).split("T")[0]
                    lines.append(f"  Ship Date:          {ship_date}")
                lines.append("")

            if len(found) > 10:
                lines.append(f"  ... +{len(found) - 10} more validated")

    lines.append(f"{'='*80}\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(INVOICE_751996))
    print("\n" + "="*80)
    print("JSON Output:")
    print("="*80)
    print(json.dumps(INVOICE_751996, indent=2))
