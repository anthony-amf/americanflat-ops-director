# Complete Invoice Validation Guide

End-to-end validation: **Rate Card + Stedi Orders**

## What Gets Validated

### 1. Rate Card Validation
- Compares **billed charges** vs. **expected rates** from Notion
- Flags line items where variance > ±$5
- Validates charge descriptions map to canonical codes
- Reports total variance for the invoice

### 2. Stedi Order Validation
- Fetches **order IDs** from supporting Excel files (already in BigQuery)
- Queries **Stedi EDI documents** (945 = Warehouse Shipping Advice)
- Reports which orders are **found ✓** vs. **missing 🚨** in Stedi

---

## Quick Start

### 1. Setup (One Time)

```bash
# Install dependencies
pip install openpyxl google-cloud-bigquery

# Create BigQuery table for order IDs
bq query --use_legacy_sql=false < schema/02_line_items.sql

# Set Stedi API key
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
```

### 2. Load Order Data (Per Invoice)

```bash
# Parse Excel file to extract order IDs
python scripts/parse_invoice_excel.py samples/751996.xlsx 751996 --output orders.json

# Load order IDs into BigQuery
python scripts/load_line_items_to_bq.py orders.json
```

### 3. Run Complete Validation

```bash
python invoice-stedi-validator.py 751996
```

---

## Example Output

```
================================================================================
Invoice Validation Report
================================================================================
Invoice ID:      751996
Date:            2026-05-19
Vendor:          Yusen Logistics
Warehouse:       NEW JERSEY

RATE CARD VALIDATION
--------------------------------------------------------------------------------
Total Billed:    $13,445.58
Total Expected:  $13,445.58
Variance:        $0.00 (+0.00%)
Status:          ✓ OK

Line Items (10 total, 0 flagged):
  ✓ E-COMMERCE                  Qty:   3201  Billed: $7,746.42  Expected: $7,746.42  Var: $-0.00
  ✓ SHIP CARTONS                Qty:    114  Billed:   $221.45  Expected:   $221.45  Var: $-0.00
  ✓ ORDERS                       Qty:     28  Billed:    $66.15  Expected:    $66.15  Var: $-0.00
  ✓ SMALL PARCELS                Qty:    114  Billed:    $80.94  Expected:    $80.94  Var: $-0.00
  ✓ SHIP CARTONS                 Qty:  2,031  Billed: $3,945.22  Expected: $3,945.22  Var: $-0.00
  ✓ STANDARD PALLETS             Qty:     84  Billed:   $472.37  Expected:   $472.37  Var: $-0.00
  ✓ STRETCHWRAP PALLETS          Qty:     84  Billed:   $396.90  Expected:   $396.90  Var: $-0.00
  ✓ PACK CARTONS                 Qty:    167  Billed:   $167.00  Expected:   $167.00  Var: $-0.00
  ✓ ORDERS                        Qty:     38  Billed:    $89.78  Expected:    $89.78  Var: $-0.00
  ✓ BOLS                          Qty:     38  Billed:   $259.35  Expected:   $259.35  Var: $-0.00

STEDI ORDER VALIDATION
--------------------------------------------------------------------------------
Total Orders:    47
Found:           45 ✓
Missing:         2 🚨

  🚨 1Z999AA10999999999                       [NOT FOUND]
  🚨 1Z999AA10888888888                       [NOT FOUND]
  ✓ 1Z999AA10123456789                       [945]
  ✓ 1Z999AA10123456790                       [945]
  ✓ 1Z999AA10123456791                       [945]
  ✓ 1Z999AA10123456792                       [945]
  ... (41 more)

================================================================================
```

---

## Usage Variations

### Rate Card Only (No Stedi)

```bash
python invoice-stedi-validator.py 751596 --skip-stedi
```

### JSON Output (For Automation)

```bash
python invoice-stedi-validator.py 751596 --output json | jq .
```

Output:
```json
{
  "invoice_id": "751996",
  "invoice_date": "2026-05-19",
  "vendor": "Yusen Logistics",
  "warehouse": "NEW JERSEY",
  "total_billed": 13445.58,
  "total_expected": 13445.58,
  "rate_variance": {
    "delta": 0.0,
    "delta_percent": 0.0,
    "flagged": false,
    "flagged_line_count": 0,
    "line_items": [
      {
        "description": "E-COMMERCE",
        "canonical_code": "SMALL_PARCEL_ECOM_ORDER",
        "quantity": 3201.0,
        "billed_rate": 2.42,
        "expected_rate": 2.42,
        "billed_amount": 7746.42,
        "expected_amount": 7746.42,
        "variance": 0.0,
        "variance_percent": 0.0,
        "flagged": false
      }
    ]
  },
  "stedi_validation": {
    "total_orders": 47,
    "found": 45,
    "missing": 2,
    "orders": [
      {
        "order_id": "1Z999AA10123456789",
        "found": true,
        "transaction_type": "945",
        "shipment_id": "..."
      },
      {
        "order_id": "1Z999AA10999999999",
        "found": false
      }
    ]
  }
}
```

### Batch Validation (Multiple Invoices)

```bash
for invoice in 751996 752325 751542; do
  echo "=== Invoice $invoice ==="
  python invoice-stedi-validator.py $invoice --output json | jq '.rate_variance, .stedi_validation'
done
```

---

## Interpreting Results

### Rate Card Validation

| Status | Meaning | Action |
|--------|---------|--------|
| ✓ OK | Billed matches expected rate | No action needed |
| 🚨 FLAGGED | Variance > ±$5 | Investigate charge discrepancy |
| [UNMAPPED] | Charge description not in rate card | Add to charge_code_map.json |

### Stedi Order Validation

| Status | Meaning | Action |
|--------|---------|--------|
| ✓ [945] | Found in Warehouse Shipping Advice | Order confirmed shipped |
| ✓ [940] | Found in Warehouse Order | Order received by warehouse |
| 🚨 NOT FOUND | No EDI document for this order | Investigate with Yusen |

---

## Troubleshooting

### "Invoice not found"
```bash
# Verify invoice exists in BigQuery
bq query "SELECT invoice_id FROM americanflat.finance.yusen_invoices WHERE invoice_id = '751996'"
```

### "No orders found" (Stedi shows 0)
```bash
# Verify orders were loaded into BigQuery
bq query "SELECT COUNT(*) FROM americanflat.finance.yusen_invoice_line_items WHERE invoice_number = '751996'"
```

### "STEDI_API_KEY is not set"
```bash
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
echo $STEDI_API_KEY  # Verify it's set
```

### "Orders NOT FOUND in Stedi"

Common causes:
1. **Typo in order number** — Check against the Excel file
2. **Order not sent to warehouse** — Contact Yusen
3. **Wrong warehouse** — Verify invoice is for correct location
4. **Order too old** — Stedi may only retain recent documents

### "Unmapped charge codes"

If you see `[UNMAPPED - Code: UNMAPPED_CUSTOM_CHARGE]`:

1. Add the charge to `charge_code_map.json`:
   ```python
   {
     "carrier": "Yusen",
     "invoice_type": "SMALL_PARCEL_LTL",
     "carrier_charge_description": "CUSTOM CHARGE",
     "warehouse_location": "NEW JERSEY",
     "canonical_charge_code": "YOUR_CODE_HERE",
     "notes": "Description of what this charge is"
   }
   ```

2. Add the rate to `RATE_CARD` dict in the script:
   ```python
   ("NEW JERSEY", "YOUR_CODE_HERE"): 123.45,
   ```

3. Re-run validation

---

## Automation (Next Steps)

### Run Nightly

```bash
# Create a cron job (macOS/Linux)
0 6 * * * cd /path/to/invoice-audit && \
  python invoice-stedi-validator.py 751996 --output json | \
  mail -s "Invoice 751996 Validation" ops@americanflat.com
```

### Integration with Cloud Scheduler

Create a Cloud Function that:
1. Fetches all invoices from BigQuery
2. Runs validation for each
3. Stores results in a `validation_results` table
4. Alerts on flagged items

---

## Rate Card Maintenance

To update rates (e.g., annual renewal):

1. Update the Python `RATE_CARD` dict:
   ```python
   RATE_CARD = {
       ("NEW JERSEY", "SMALL_PARCEL_ECOM_ORDER"): 2.50,  # Updated from 2.42
   }
   ```

2. Or store in BigQuery for dynamic lookup:
   ```sql
   SELECT unit_price FROM finance.rate_card
   WHERE warehouse_location = 'NEW JERSEY'
     AND canonical_charge_code = 'SMALL_PARCEL_ECOM_ORDER'
     AND effective_date <= invoice_date
   ORDER BY effective_date DESC LIMIT 1
   ```

---

## Support

Issues or questions?
- Check `STEDI_VALIDATION_WORKFLOW.md` for parsing/loading steps
- Check `COMPLETE_VALIDATION_GUIDE.md` (this file) for validation details
- Reach out to Operations team
