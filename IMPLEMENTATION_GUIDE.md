# Complete Invoice Validation System - Implementation Guide

**End-to-end validation:** Rate Card + Stedi Order Tracking

---

## Architecture

```
Invoice PDF (Yusen)
    ↓
BigQuery: yusen_invoices
    ├─ invoice_number, invoice_date, vendor_name
    ├─ line_items (charges)
    └─ total_amount

Supporting Excel (Order IDs)
    ↓
Parse with: parse_invoice_excel.py
    ↓
BigQuery: yusen_invoice_line_items
    ├─ invoice_number
    ├─ order_number (from Excel)
    ├─ service_type, quantity, amount
    └─ warehouse_location

Validation Layer
    ├─ Rate Card Check (Notion)
    │   └─ Billed vs Expected rates
    │
    └─ Stedi Order Check (945 EDI)
        ├─ Order ID (Excel) → Stedi query
        ├─ Returns: Shipment Tracking
        └─ Reports: Found ✓ or Missing 🚨
```

---

## One-Time Setup (15 minutes)

### 1. Install Dependencies

```bash
pip3 install google-cloud-bigquery openpyxl
```

### 2. Create BigQuery Tables

```bash
# Navigate to repo directory
cd /path/to/invoice-audit

# Create invoice_line_items table for storing order IDs
bq query --use_legacy_sql=false < schema/02_line_items.sql

# Verify
bq ls americanflat.finance
# Should show: yusen_invoices, yusen_invoice_line_items
```

### 3. Set Stedi API Key

```bash
# Add to ~/.zshrc or ~/.bashrc
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc

# Verify
echo $STEDI_API_KEY  # Should print the key
```

---

## Per-Invoice Workflow

### Step 1: Parse Supporting Excel File

Your skill uploads the invoice PDF. You separately get the supporting Excel file with order numbers.

```bash
python3 scripts/parse_invoice_excel.py path/to/invoice.xlsx INVOICE_NUMBER
```

**Example:**
```bash
python3 scripts/parse_invoice_excel.py ~/Downloads/751996.xlsx 751996
```

**Output:** `751996_orders.json`
```json
{
  "invoice_number": "751996",
  "warehouse_location": "NEW JERSEY",
  "total_line_items": 47,
  "line_items": [
    {
      "line_item_id": 1,
      "order_number": "AMF-751996-001",
      "service_type": "Small Parcel",
      "quantity": 50,
      "warehouse_location": "NEW JERSEY"
    }
  ]
}
```

### Step 2: Load Order IDs to BigQuery

```bash
python3 scripts/load_line_items_to_bq.py 751996_orders.json
```

**Verify:**
```bash
bq query "SELECT COUNT(*) FROM americanflat.finance.yusen_invoice_line_items WHERE invoice_number = '751996'"
# Should return: 47
```

### Step 3: Run Complete Validation

```bash
python3 invoice-stedi-validator.py 751996
```

**Output Example:**
```
================================================================================
Invoice Validation Report
================================================================================
Invoice ID:      751996
Date:            2026-05-19
Vendor:          Yusen Logistics
Warehouse:       NEW JERSEY

RATE CARD VALIDATION
Total Billed:    $13,445.58
Total Expected:  $13,445.58
Variance:        $0.00 (+0.00%)
Status:          ✓ OK

STEDI ORDER VALIDATION
Total Orders:    47
Found:           45 ✓
Missing:         2 🚨

DISCREPANCIES - Missing from Stedi 945:
🚨 Order ID (Excel):  AMF-751996-045
   Stedi Status:       NOT FOUND
   Service Type(s):    Small Parcel
   Invoice Total:      $133.10

VALIDATED - Found in Stedi 945:
✓ Order ID (Excel):   AMF-751996-001
  Shipment Tracking:  SHIP_20260519_00001
  Ship Date:          2026-05-19
```

### Step 4 (Optional): Export as JSON for Automation

```bash
python3 invoice-stedi-validator.py 751996 --output json > 751996_validation.json
```

Use this JSON to:
- Feed to accounting system
- Create Slack alerts
- Update a dashboard
- Trigger follow-up workflows

---

## Batch Processing

To validate multiple invoices at once:

```bash
#!/bin/bash
# validate_batch.sh

INVOICES=(751996 752325 751542)

for inv in "${INVOICES[@]}"; do
  echo "Processing $inv..."
  
  # Parse Excel
  python3 scripts/parse_invoice_excel.py samples/${inv}.xlsx $inv --output ${inv}_orders.json
  
  # Load to BigQuery
  python3 scripts/load_line_items_to_bq.py ${inv}_orders.json
  
  # Validate
  python3 invoice-stedi-validator.py $inv | tee ${inv}_validation.txt
done
```

Run:
```bash
chmod +x validate_batch.sh
./validate_batch.sh
```

---

## Interpreting Results

### Rate Card Validation

| Status | Meaning | Action |
|--------|---------|--------|
| ✓ OK | All charges match Notion rate card | Invoice approved |
| 🚨 FLAGGED | Variance > ±$5 | Investigate with vendor |
| [UNMAPPED] | Charge not in rate card | Update charge_code_map.json |

**Example Variance:** If billed $100 but expected $95, delta = +$5 (flagged)

### Stedi Order Validation

| Status | Meaning | Action |
|--------|---------|--------|
| ✓ Found [945] | Order in Stedi Warehouse Shipping Advice | Order confirmed shipped ✓ |
| ✓ Found [940] | Order in Stedi Warehouse Order | Order received, pending shipment |
| 🚨 NOT FOUND | Order not in any Stedi EDI doc | Contact Yusen; verify order number |

**Shipment Tracking:** The ID from the 945 document (e.g., "SHIP_20260519_00001")

---

## Common Issues & Fixes

### "Order not found in BigQuery"
```bash
# Verify order was loaded
bq query "SELECT * FROM americanflat.finance.yusen_invoice_line_items WHERE order_number = 'AMF-751996-001'"
```

### "STEDI_API_KEY is not set"
```bash
# Check environment
echo $STEDI_API_KEY

# If empty, set it
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
```

### "Order ID format mismatch"
Excel might have formats like:
- `1Z999AA10123456789` (tracking number)
- `AMF-751996-001` (order ID)
- `PO-12345` (purchase order)

The validator uses whatever is in the Excel file. Ensure Stedi queries are consistent with your order ID format.

### "Missing orders" investigation
When an order is not found in Stedi:

1. **Verify order number** — check Excel file for typos
2. **Check Stedi directly** — log into Stedi portal and search by order ID
3. **Contact Yusen** — order may not have been sent to warehouse
4. **Check timing** — Stedi may need 24-48 hours to reflect shipments

---

## Automation (Next Phase)

### Cloud Scheduler + Cloud Function

Create a Cloud Function that runs nightly:

```python
def validate_invoice(request):
    """Cloud Function: validate invoices nightly"""
    import subprocess
    import os
    
    invoices = get_pending_invoices()  # From BigQuery
    
    for inv in invoices:
        # Parse & load
        subprocess.run([
            'python3', 'scripts/parse_invoice_excel.py',
            f'gs://bucket/{inv}.xlsx', inv
        ])
        subprocess.run(['python3', 'scripts/load_line_items_to_bq.py', f'{inv}_orders.json'])
        
        # Validate
        result = subprocess.run([
            'python3', 'invoice-stedi-validator.py', inv, '--output', 'json'
        ], capture_output=True, text=True)
        
        # Store result
        store_validation_result(inv, result)
        
        # Alert if issues
        if json.loads(result)['stedi_validation']['missing'] > 0:
            send_slack_alert(inv, result)
```

Deploy:
```bash
gcloud functions deploy validate-invoices \
  --runtime python39 \
  --trigger-topic validate-invoices-daily \
  --env-vars-file .env.yaml
```

### Dashboard

Connect validation results to a BI tool:

```sql
SELECT
  invoice_id,
  invoice_date,
  vendor,
  warehouse,
  rate_variance.delta as rate_delta,
  stedi_validation.total_orders,
  stedi_validation.found,
  stedi_validation.missing
FROM validation_results
WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY created_at DESC
```

---

## File Checklist

Before deployment, verify these files exist:

```
✓ schema/
  ├─ 00_init.sql           (original schema)
  └─ 02_line_items.sql     (order IDs table)

✓ scripts/
  ├─ parse_invoice_excel.py
  └─ load_line_items_to_bq.py

✓ invoice-stedi-validator.py (production)
✓ invoice-validator-demo.py   (demo/testing)

✓ Documentation/
  ├─ README.md
  ├─ STEDI_VALIDATION_WORKFLOW.md
  ├─ COMPLETE_VALIDATION_GUIDE.md
  └─ IMPLEMENTATION_GUIDE.md (this file)
```

---

## Ready to Deploy?

1. ✅ Dependencies installed (`pip3 install google-cloud-bigquery openpyxl`)
2. ✅ BigQuery tables created (`bq query < schema/02_line_items.sql`)
3. ✅ Stedi API key set (`export STEDI_API_KEY=...`)
4. ✅ First invoice validated (tested with sample)

**Next:** Push to GitHub and set up nightly automation.

---

## Support

- **Rate card questions:** See `charge_code_map.json`
- **Stedi questions:** See `STEDI_VALIDATION_WORKFLOW.md`
- **BigQuery questions:** See table schemas in `schema/`
- **Command help:** Run `python3 invoice-stedi-validator.py --help`

---

**Congrats!** You now have an auditable, repeatable invoice validation system. 🎉
