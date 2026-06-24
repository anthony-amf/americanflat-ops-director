# Invoice Variance Checker Skill

## Overview
Validates an invoice against the Notion rate card by:
1. Fetching the invoice from BigQuery (by invoice_id)
2. Extracting line items (description, quantity, rate)
3. Looking up the Notion rate card for expected rates
4. Comparing billed vs. expected and reporting variances

## Input
- **invoice_id** — invoice number (e.g., "751996")
- **warehouse_location** (optional) — if not in BigQuery, user provides it

## Output
```json
{
  "invoice_id": "751996",
  "invoice_date": "2026-05-19",
  "vendor": "Yusen Logistics",
  "warehouse": "NEW JERSEY",
  "total_billed": 13445.58,
  "total_expected": 13445.58,
  "variance": 0.00,
  "variance_percent": 0.0,
  "flagged": false,
  "line_items": [
    {
      "description": "E-COMMERCE",
      "canonical_code": "SMALL_PARCEL_ECOM_ORDER",
      "quantity": 3201,
      "billed_rate": 2.42,
      "expected_rate": 2.42,
      "billed_amount": 7746.42,
      "expected_amount": 7746.42,
      "variance": 0.00,
      "variance_percent": 0.0,
      "flagged": false
    },
    {
      "description": "SHIP CARTONS",
      "canonical_code": "SMALL_PARCEL_SHIP_CARTONS",
      "quantity": 114,
      "billed_rate": 1.9425,
      "expected_rate": 1.9425,
      "billed_amount": 221.45,
      "expected_amount": 221.45,
      "variance": 0.00,
      "variance_percent": 0.0,
      "flagged": false
    }
  ]
}
```

## Implementation Steps

### Step 1: Query BigQuery for Invoice
```bash
bq query --use_legacy_sql=false \
  "SELECT invoice_id, invoice_date, vendor_name, line_items, total_amount FROM {PROJECT}.{DATASET}.invoices WHERE invoice_id = '{invoice_id}'"
```

### Step 2: Fetch Notion Rate Card
Use the existing Notion API to query the rate card table we reviewed earlier.

### Step 3: Map & Compare
For each line item:
1. Extract: description, quantity, rate (billed_rate), amount
2. Map description → canonical_code using charge_code_map
3. Look up expected_rate from Notion rate card
4. Compute: variance = (billed_rate - expected_rate) × quantity
5. Flag if variance > tolerance (default ±$5)

### Step 4: Return Report
Format as JSON or human-readable text showing:
- Total billed vs. total expected
- Each line item with variance highlighted
- Flagged items at the top

## Questions to Clarify

1. **BigQuery table name** — what's the exact table name your skill writes to?
2. **Notion rate card** — can we query it via Notion API, or should I read it as a cached JSON?
3. **Charge mapping** — should I use the charge_code_map.json I created, or does your skill have one?
4. **Tolerance threshold** — default to ±$5, or different per invoice type?
