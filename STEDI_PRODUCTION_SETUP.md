# Production Stedi Validation Setup

## Architecture

```
Invoice PDF → BigQuery (yusen_invoices)
                  ↓
Supporting Excel → Parse → Extract Order IDs → JSON
                  ↓
        validate-stedi-production.py
                  ↓
            Stedi API 945
                  ↓
        Validation Results (JSON)
                  ↓
        Store in validation_results table
```

## Setup (One Time)

### 1. Install Dependencies
```bash
pip3 install google-cloud-bigquery requests
```

### 2. Set Stedi API Key
```bash
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
```

### 3. Verify GCloud Authentication
```bash
gcloud auth application-default login
# Or use service account:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
```

## Per-Invoice Workflow

### Step 1: Parse Invoice Excel
```bash
python3 scripts/parse_invoice_excel.py /path/to/invoice.xlsx INVOICE_NUMBER --output orders.json
```

**Supports both formats:**
- Yusen (Small Parcel + LTL sheets) → 47 orders/invoice
- Taylored Services (TSI PO# format) → 3,979+ orders/invoice

### Step 2: Validate Against Stedi 945
```bash
python3 validate-stedi-production.py 752319 --json-file 752319_orders.json
```

**Output:**
```
================================================================================
Stedi Order Validation: Invoice 752319
================================================================================

📋 Validating 3979 orders against Stedi 945...
  ✓ [    1/3979] '102003276483843               SHIP_20260501_001
  ✓ [    2/3979] '102003326671937               SHIP_20260501_002
  🚨 [    3/3979] '102003340942336               N/A
  ...

================================================================================
STEDI ORDER VALIDATION SUMMARY
================================================================================
Invoice:       752319
Warehouse:     FONTANA
Total Orders:  3979
Found:         3950 ✓
Missing:       29 🚨
Success Rate:  99.3%
================================================================================

🚨 29 MISSING ORDERS (not found in Stedi 945):
  • 102003340942336 - Stedi API error: Not found in 945
  • 102003417641042 - Stedi API error: Not found in 945
  ...
```

### Step 3: Export JSON for Further Processing
```bash
python3 validate-stedi-production.py 752319 --json-file 752319_orders.json --output 752319_validation.json
```

## Freight Invoice Formats Supported

The parser auto-detects invoice formats (same vendor, company renamed):

| Format | Detection | Example | Status |
|--------|-----------|---------|--------|
| **Yusen** (old company name) | Sheet names: "Small Parcel", "LTL" | 751996 | ✅ |
| **Taylored Services** (new company name) | TSI PO# header, Sheet1/Sheet2 | 752319 | ✅ |

Both formats are from the same vendor (company rebranded from Yusen → Taylored). The parser auto-detects and handles both.

**To add new vendors:**
1. Update `detect_format()` in `scripts/parse_invoice_excel.py`
2. Create `parse_<vendor>_excel()` function
3. Test with sample file

## Batch Processing

Validate multiple invoices:

```bash
#!/bin/bash
INVOICES=(752319 751996 752325)

for inv in "${INVOICES[@]}"; do
  echo "Processing invoice $inv..."
  python3 scripts/parse_invoice_excel.py "invoices/${inv}.xlsx" $inv --output "${inv}_orders.json"
  python3 validate-stedi-production.py $inv --json-file "${inv}_orders.json" --output "${inv}_results.json"
  
  # Parse results and upload to BigQuery
  # bq load americanflat.finance.validation_results "${inv}_results.json" --autodetect
done
```

## JSON Output Structure

```json
{
  "invoice_number": "752319",
  "warehouse": "FONTANA",
  "validated_at": "2026-06-24T14:30:00.123456",
  "stedi_validation": {
    "total_orders": 3979,
    "found": 3950,
    "missing": 29,
    "orders": [
      {
        "found": true,
        "order_id": "102003276483843",
        "transaction_type": "945",
        "shipment_tracking": "SHIP_20260501_001",
        "ship_date": "2026-05-01T10:30:00Z",
        "carrier": "AMAZON_FREIGHT",
        "shipment_quantity": 50,
        "service_type": "Small Parcel",
        "quantity": 1
      },
      {
        "found": false,
        "order_id": "102003340942336",
        "error": "Not found in Stedi 945",
        "service_type": "LTL",
        "quantity": 1
      }
    ]
  }
}
```

## Troubleshooting

### "Stedi API error: Failed to resolve api.stedi.com"
- Network issue: Verify internet connectivity
- Firewall: Ensure api.stedi.com is accessible
- Try: `curl https://api.stedi.com/health`

### "STEDI_API_KEY is not set"
```bash
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
echo $STEDI_API_KEY  # Verify
```

### "All orders missing from Stedi"
1. **Check order format** — Strip leading/trailing quotes
2. **Verify warehouse** — Order may be from different location
3. **Contact Stedi** — Check API key permissions
4. **Check 945 documents** — May not be ingested yet

### "Parser extracted 0 orders"
- Excel format not recognized
- Update `detect_format()` to handle new vendor format
- Verify Excel has data in expected columns

## Next Steps

1. **Automation**: Cloud Function to run nightly
2. **Results Storage**: Create `validation_results` table in BigQuery
3. **Dashboard**: Query validation trends
4. **Alerts**: Slack/email when missing orders detected

---

**Ready to validate!** 🚀

## Understanding EDI Transaction Types (945 vs 940)

The validator checks two Stedi EDI document types:

### **945 - Warehouse Shipping Advice** ✓ Shipped
- Order has been picked, packed, and shipped from warehouse
- Contains shipment tracking information
- Indicates successful fulfillment

### **940 - Warehouse Order** (Fallback) ⏳ In Warehouse  
- Order has been received by warehouse but not yet shipped
- Checked if 945 not found
- Indicates order is in system but still being processed

**Validation Flow:**
1. Search for 945 documents (shipped orders)
2. If not found, search for 940 documents (in warehouse)
3. If neither found, mark as missing

**Example Summary:**
```
✓ Found: 3,921 (98.5%)
  ├─ 945 (Shipped):      3,890
  └─ 940 (In Warehouse):    31
🚨 Missing: 58
```

**Missing Orders Investigation:**
If orders show as missing, check:
1. Order ID matches exactly (case-sensitive, no extra spaces)
2. Order has been submitted to warehouse
3. Order isn't in a different transaction type
4. Check for typos in Excel invoice file

