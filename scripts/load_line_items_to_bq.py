#!/usr/bin/env python3
"""
Load parsed invoice line items into BigQuery.

Takes JSON output from parse_invoice_excel.py and loads it into
finance.yusen_invoice_line_items.

Usage:
    python scripts/load_line_items_to_bq.py orders.json
    python scripts/load_line_items_to_bq.py orders.json --project americanflat --dataset finance
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Any

from google.cloud import bigquery


def load_to_bigquery(json_file: str, project: str = "americanflat", dataset: str = "finance", table: str = "yusen_invoice_line_items"):
    """Load line items JSON to BigQuery."""

    # Read JSON
    with open(json_file, "r") as f:
        data = json.load(f)

    invoice_number = data.get("invoice_number")
    line_items = data.get("line_items", [])

    if not line_items:
        print(f"No line items to load from {json_file}")
        return

    # Prepare rows for BigQuery
    rows = []
    for item in line_items:
        rows.append({
            "invoice_number": invoice_number,
            "line_item_id": item.get("line_item_id"),
            "order_number": item.get("order_number"),
            "quantity": item.get("quantity"),
            "service_type": item.get("service_type"),
            "amount": None,  # Would come from invoice line item amount
            "warehouse_location": item.get("warehouse_location"),
            "notes": item.get("notes"),
            "ingested_at": None,  # BigQuery will auto-populate with DEFAULT
        })

    # Load to BigQuery
    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{table}"

    try:
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            print(f"❌ Errors loading to BigQuery:")
            for error in errors:
                print(f"  {error}")
            return False
        else:
            print(f"✓ Loaded {len(rows)} line items to {table_id}")
            return True
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Load invoice line items to BigQuery"
    )
    parser.add_argument("json_file", help="JSON file from parse_invoice_excel.py")
    parser.add_argument("--project", default="americanflat", help="GCP project")
    parser.add_argument("--dataset", default="finance", help="BigQuery dataset")
    parser.add_argument("--table", default="yusen_invoice_line_items", help="BigQuery table")

    args = parser.parse_args()

    # Verify file exists
    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"Error: File not found: {args.json_file}", file=sys.stderr)
        sys.exit(1)

    success = load_to_bigquery(
        args.json_file,
        project=args.project,
        dataset=args.dataset,
        table=args.table
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
