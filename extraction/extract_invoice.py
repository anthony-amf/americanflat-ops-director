#!/usr/bin/env python3
"""
Invoice Extraction CLI for Americanflat Invoice Audit System

This script reads a PDF invoice, uses Claude to extract structured data,
maps charges to canonical codes, and outputs JSON ready for BigQuery ingest.

Usage:
    python extraction/extract_invoice.py path/to/invoice.pdf
    python extraction/extract_invoice.py path/to/invoice.pdf --output output.json
    python extraction/extract_invoice.py path/to/invoice.pdf --validate

Environment:
    ANTHROPIC_API_KEY - Your Claude API key
"""

import sys
import json
import argparse
import base64
from pathlib import Path
from typing import Any

import anthropic


def read_pdf(pdf_path: str) -> bytes:
    """Read PDF file and return as bytes."""
    with open(pdf_path, "rb") as f:
        return f.read()


def load_charge_code_map(map_path: str = "extraction/charge_code_map.json") -> list[dict]:
    """Load charge code mapping from JSON file."""
    try:
        with open(map_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: charge_code_map.json not found at {map_path}")
        return []


def extract_invoice(pdf_bytes: bytes, charge_code_map: list[dict]) -> dict[str, Any]:
    """
    Use Claude to extract invoice data from PDF.

    Args:
        pdf_bytes: PDF file content as bytes
        charge_code_map: List of charge code mapping objects

    Returns:
        Extracted invoice data as dictionary
    """
    client = anthropic.Anthropic()

    # Encode PDF as base64
    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    # Load system prompt
    try:
        with open("extraction/system_prompt.md", "r") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print("Error: system_prompt.md not found")
        sys.exit(1)

    # Prepare charge code map for inclusion in prompt
    map_json = json.dumps(charge_code_map, indent=2)

    # Create message with PDF and charge code map
    user_message = f"""Please extract the invoice data from this PDF and return a JSON object.

Use this charge_code_map to normalize the charge descriptions to canonical codes:

{map_json}

Return ONLY valid JSON (no markdown, no code blocks). The JSON should match the structure described in the system prompt."""

    # Call Claude with vision
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": user_message,
                    }
                ],
            }
        ],
    )

    # Parse response JSON
    response_text = message.content[0].text

    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()

    try:
        extracted_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing Claude response as JSON: {e}")
        print(f"Response: {response_text[:500]}")
        sys.exit(1)

    return extracted_data


def validate_extraction(data: dict[str, Any]) -> list[str]:
    """
    Validate extracted data for required fields and format.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required top-level fields
    required = ["invoice_number", "invoice_date", "invoice_type", "carrier", "warehouse_location"]
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check line items
    if "line_items" not in data:
        errors.append("Missing required field: line_items")
    elif not isinstance(data["line_items"], list):
        errors.append("line_items must be a list")
    elif len(data["line_items"]) == 0:
        errors.append("line_items is empty")
    else:
        required_line_fields = ["charge_description", "quantity", "unit_price", "billed_amount", "canonical_charge_code"]
        for i, item in enumerate(data["line_items"]):
            for field in required_line_fields:
                if field not in item:
                    errors.append(f"Line item {i} missing field: {field}")

    return errors


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract invoice data from PDF using Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extraction/extract_invoice.py samples/751996.pdf
  python extraction/extract_invoice.py samples/751996.pdf --output output.json
  python extraction/extract_invoice.py samples/751996.pdf --validate
        """
    )
    parser.add_argument("pdf_path", help="Path to invoice PDF")
    parser.add_argument(
        "--output",
        help="Output JSON file (default: <invoice_name>.json in current dir)",
        default=None
    )
    parser.add_argument(
        "--validate",
        help="Validate extraction and report errors",
        action="store_true"
    )

    args = parser.parse_args()

    # Verify PDF exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {args.pdf_path}")
        sys.exit(1)

    print(f"Extracting invoice from {args.pdf_path}...")

    # Read PDF
    pdf_bytes = read_pdf(args.pdf_path)

    # Load charge code map
    charge_code_map = load_charge_code_map()

    # Extract using Claude
    extracted = extract_invoice(pdf_bytes, charge_code_map)

    # Validate
    if args.validate:
        errors = validate_extraction(extracted)
        if errors:
            print("\nValidation errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("✓ Validation passed")

    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        invoice_num = extracted.get("invoice_number", pdf_path.stem)
        output_file = f"{invoice_num}.json"

    # Write output
    with open(output_file, "w") as f:
        json.dump(extracted, f, indent=2)

    print(f"✓ Extracted to {output_file}")
    print(f"  Invoice #: {extracted.get('invoice_number')}")
    print(f"  Type: {extracted.get('invoice_type')}")
    print(f"  Warehouse: {extracted.get('warehouse_location')}")
    print(f"  Line items: {len(extracted.get('line_items', []))}")
    print(f"  Total: {extracted.get('total_billed', 'N/A')}")
    print(f"  Confidence: {extracted.get('extraction_confidence', 'N/A')}")


if __name__ == "__main__":
    main()
