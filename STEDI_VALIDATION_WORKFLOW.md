# Stedi Order Validation Workflow

End-to-end guide for validating invoices against Stedi EDI documents.

## Architecture

```
Invoice PDF → BigQuery (yusen_invoices)
                  ↓
Supporting Excel → Extract Order IDs → BigQuery (yusen_invoice_line_items)
                  ↓
            Validate Against Stedi
                  ↓
         Report: Found ✓ / Missing 🚨
```

## Setup

### 1. Create BigQuery Tables

```bash
bq query --use_legacy_sql=false < schema/02_line_items.sql
```

This creates `finance.yusen_invoice_line_items`:
```
invoice_number | line_item_id | order_number | service_type | warehouse_location
751996         | 1            | 1Z999AA10... | Small Parcel | NEW JERSEY
751996         | 2            | 1Z999AA11... | Small Parcel | NEW JERSEY
751996         | 1000         | SSCC_12345   | LTL          | NEW JERSEY
```

### 2. Install Dependencies

```bash
pip install openpyxl google-cloud-bigquery
```

## Workflow

### Step 1: Parse Supporting Excel Files

Each invoice comes with an Excel file containing order numbers. Extract them:

```bash
python scripts/parse_invoice_excel.py path/to/751996.xlsx 751996
```

Output:
```json
{
  "invoice_number": "751996",
  "warehouse_location": "NEW JERSEY",
  "total_line_items": 47,
  "line_items": [
    {
      "line_item_id": 1,
      "order_number": "1Z999AA10123456789",
      "service_type": "Small Parcel",
      "quantity": 1
    },
    ...
  ]
}
```

### Step 2: Load to BigQuery

```bash
python scripts/parse_invoice_excel.py path/to/751996.xlsx 751996 --output orders.json
python scripts/load_line_items_to_bq.py orders.json
```

This inserts rows into `yusen_invoice_line_items`.

### Step 3: Validate with Stedi

Query Stedi for each order:

```bash
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
python invoice-stedi-validator.py 751996
```

Output:
```
======================================================================
Invoice: 751996 (2026-05-19)
Vendor: Yusen Logistics
======================================================================

Stedi Order Validation:
----------------------------------------------------------------------
Total Orders:    47
Found in Stedi:  45 ✓
Missing:         2 🚨

  ✓ 1Z999AA10123456789              [945]
  ✓ 1Z999AA10123456790              [945]
  ✓ 1Z999AA10123456791              [945]
  🚨 1Z999AA10999999999              [NOT FOUND]
  🚨 1Z999AA10888888888              [NOT FOUND]
  ...
======================================================================
```

## Interpreting Results

### ✓ Found (Transaction Type = 945)
- Order exists in Stedi as a **Warehouse Shipping Advice (945)**
- This means the warehouse reported it shipped
- **Status:** Valid

### ✓ Found (Transaction Type = 940)
- Order exists as a **Warehouse Order (940)**
- Order was received but may not have shipped yet
- **Status:** Valid (order is in system)

### 🚨 Missing (NOT FOUND)
- Order number does **not** appear in any Stedi EDI document
- Either:
  - Typo in the order number
  - Order was never sent to the warehouse
  - Invoice includes orders outside your system
- **Action:** Investigate and flag to operations

## Batch Processing

To validate multiple invoices:

```bash
for invoice in 751996 752325 752734 751542; do
  echo "Processing $invoice..."
  python scripts/parse_invoice_excel.py samples/${invoice}.xlsx $invoice --output ${invoice}_orders.json
  python scripts/load_line_items_to_bq.py ${invoice}_orders.json
done

# Then validate all
for invoice in 751996 752325 752734 751542; do
  python invoice-stedi-validator.py $invoice
done
```

## JSON Output (for programmatic use)

```bash
python invoice-stedi-validator.py 751996 --output json
```

```json
{
  "invoice_id": "751996",
  "invoice_date": "2026-05-19",
  "vendor": "Yusen Logistics",
  "stedi_validation": {
    "total_orders": 47,
    "found": 45,
    "missing": 2,
    "orders": [
      {
        "order_id": "1Z999AA10123456789",
        "found": true,
        "transaction_type": "945",
        "shipment_id": "...",
        "ship_date": "2026-05-19T10:30:00Z"
      },
      {
        "order_id": "1Z999AA10999999999",
        "found": false
      }
    ]
  }
}
```

## Troubleshooting

### "STEDI_API_KEY is not set"
```bash
export STEDI_API_KEY=22R7W4M.3KmGqoJdae1EebTmnXB9fAAc
python invoice-stedi-validator.py 751596
```

### "Invoice not found in BigQuery"
Verify invoice was loaded:
```bash
bq query --use_legacy_sql=false "SELECT invoice_id FROM americanflat.finance.yusen_invoices WHERE invoice_id = '751996'"
```

### "No orders in line_items table"
Verify data was loaded:
```bash
bq query --use_legacy_sql=false "SELECT * FROM americanflat.finance.yusen_invoice_line_items WHERE invoice_number = '751996'"
```

### Orders are "NOT FOUND" in Stedi
- Check order number format (case sensitivity, extra spaces)
- Verify with Yusen that order was sent to warehouse
- Check if order was shipped from a different warehouse (Fontana vs. New Jersey)

## Next Steps

### Automation
- Set up Cloud Scheduler to run validation nightly
- Flag missing orders to Slack/email
- Create a dashboard showing validation status

### Integration
- Add Stedi validation to the invoice-to-bigquery skill
- Auto-parse Excel files as part of upload workflow
- Create a reconciliation report for finance

### Enhancements
- Match orders to shipments (945) and extract carton/unit counts
- Validate product SKUs and quantities shipped
- Compare invoice carton counts vs. Stedi shipment records
