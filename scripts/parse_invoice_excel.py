#!/usr/bin/env python3
"""
Parse supporting Excel files from Yusen invoices.

Extracts order numbers, quantities, and service types from the Excel files
that accompany Small Parcel/LTL invoices.

Usage:
    python scripts/parse_invoice_excel.py path/to/invoice.xlsx 751996
    python scripts/parse_invoice_excel.py path/to/invoice.xlsx 751996 --output orders.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Any

import openpyxl


def parse_yusen_excel(file_path: str, invoice_number: str, warehouse: str = "NEW JERSEY") -> dict[str, Any]:
    """
    Parse Yusen supporting Excel file.

    Expected structure:
    - "Small Parcel" sheet with order numbers in column A
    - "LTL" sheet (if present) with SSCC/BOL numbers

    Returns:
        {
            "invoice_number": "751996",
            "warehouse": "NEW JERSEY",
            "line_items": [
                {"order_number": "1Z...", "service_type": "Small Parcel", "quantity": 1},
                ...
            ]
        }
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    line_items = []

    # Parse Small Parcel sheet
    if "Small Parcel" in wb.sheetnames or "SML PRCL" in wb.sheetnames:
        sheet_name = "Small Parcel" if "Small Parcel" in wb.sheetnames else "SML PRCL"
        ws = wb[sheet_name]

        # Extract order numbers from column A (skip header)
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=5), start=1):
            order_num = row[0].value
            quantity = row[1].value if len(row) > 1 else None
            notes = row[4].value if len(row) > 4 else None

            if order_num:  # Skip empty rows
                line_items.append({
                    "line_item_id": row_idx,
                    "order_number": str(order_num).strip(),
                    "quantity": int(quantity) if quantity else 1,
                    "service_type": "Small Parcel",
                    "warehouse_location": warehouse,
                    "notes": notes,
                })

    # Parse LTL sheet
    if "LTL" in wb.sheetnames:
        ws = wb["LTL"]

        # Extract BOL/SSCC numbers from column A
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=5), start=1000):
            bol_num = row[0].value
            quantity = row[1].value if len(row) > 1 else None

            if bol_num:
                line_items.append({
                    "line_item_id": row_idx,
                    "order_number": str(bol_num).strip(),
                    "quantity": int(quantity) if quantity else 1,
                    "service_type": "LTL",
                    "warehouse_location": warehouse,
                    "notes": "BOL/SSCC number",
                })

    return {
        "invoice_number": invoice_number,
        "warehouse_location": warehouse,
        "total_line_items": len(line_items),
        "line_items": line_items,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parse Yusen supporting Excel files",
        epilog="""
Examples:
  python scripts/parse_invoice_excel.py samples/751996.xlsx 751996
  python scripts/parse_invoice_excel.py samples/751542.xlsx 751542 --warehouse "NEW JERSEY"
  python scripts/parse_invoice_excel.py samples/751542.xlsx 751542 --output orders.json
        """
    )
    parser.add_argument("excel_file", help="Path to Excel file")
    parser.add_argument("invoice_number", help="Invoice number (e.g., 751996)")
    parser.add_argument("--warehouse", default="NEW JERSEY", help="Warehouse location")
    parser.add_argument("--output", help="Output JSON file (default: print to stdout)")

    args = parser.parse_args()

    # Verify file exists
    excel_path = Path(args.excel_file)
    if not excel_path.exists():
        print(f"Error: File not found: {args.excel_file}", file=sys.stderr)
        sys.exit(1)

    try:
        result = parse_yusen_excel(str(excel_path), args.invoice_number, args.warehouse)

        # Output
        output_text = json.dumps(result, indent=2)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output_text)
            print(f"✓ Parsed {result['total_line_items']} line items to {args.output}")
        else:
            print(output_text)

    except Exception as e:
        print(f"Error parsing Excel: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
