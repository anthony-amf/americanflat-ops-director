# Sample Invoices for Testing

This directory contains sample invoices (one of each type) for testing the extraction and validation pipeline.

## Invoices Included

### 1. Small Parcel / LTL (New Jersey)
**File:** `751996_NJ_SmallParcelLTL.pdf`
- **Invoice #:** 751996
- **Date:** 05/19/2026
- **Warehouse:** LOC #31 NEW JERSEY
- **Carrier:** Yusen Logistics
- **Total:** $13,445.58 USD
- **Line items:** 10 charges (E-commerce, Ship Cartons, Orders, Pallets, BOLs, etc.)
- **Supporting docs:** Expected Excel file with order numbers, carton counts, BOL numbers
- **Purpose:** Test extraction of multiple line items, rate card lookup, Stedi EDI validation

### 2. VAS - Back Office Support (Fontana)
**File:** `752325_Fontana_VAS.pdf`
- **Invoice #:** 752325
- **Date:** 05/26/2026
- **Warehouse:** FONTANA
- **Carrier:** Yusen Logistics
- **Service:** Back Office Support (05/04-05/08)
- **Quantity:** 40 hours @ $59.82/hr
- **Total:** $2,393.11 USD
- **Purpose:** Test labor-based VAS extraction and hourly rate validation

### 3. Admin Fee (New Jersey)
**File:** `752734_NJ_Admin.pdf`
- **Invoice #:** 752734
- **Date:** 05/31/2026
- **Warehouse:** LOC #31 NEW JERSEY
- **Service:** Administrative Support (Week of May 11, 2026)
- **Total:** $1,071.00 USD
- **Purpose:** Test fixed-fee invoice (no variance expected)

### 4. Storage (New Jersey)
**File:** `751542_NJ_Storage.pdf`
- **Invoice #:** 751542
- **Date:** 05/11/2026
- **Warehouse:** LOC #31 NEW JERSEY
- **Service:** Weekly Storage (Week of May 4, 2026)
- **Quantity:** 6,025 pallets @ $5.98/pallet
- **Total:** $36,029.50 USD
- **Supporting docs:** Excel file with pallet inventory details
- **Purpose:** Test pallet-based storage charges and inventory validation

### 5. Canada (Brampton)
**File:** `canada_brampton_invoice.xlsx` (or similar)
- **Period:** May 2026
- **Warehouse:** Brampton, Ontario
- **Carrier:** Yusen Logistics
- **Subtotal CAD:** $17,300.25
- **HST (Non-Shipping):** $2,249.03
- **Total CAD:** $19,549.28
- **Exchange Rate:** 1.33959
- **Total USD:** $14,593.48
- **Line items:** Pallet storage, order processing, VAS, labeling
- **Purpose:** Test multi-currency extraction, HST calculation, rate card CAD→USD conversion

## How to Test

### Phase 1: Extraction Testing

1. **Extract each invoice:**
   ```bash
   python extraction/extract_invoice.py samples/751996_NJ_SmallParcelLTL.pdf
   ```

2. **Review the extracted JSON:**
   ```bash
   cat 751996_NJ_SmallParcelLTL.json
   ```
   - Verify invoice_number, invoice_date, warehouse_location
   - Verify all line items are present
   - Verify canonical_charge_code mappings (check against charge_code_map.json)
   - Verify quantities, unit prices, billed amounts match PDF

3. **Check extraction_confidence and issues:**
   - Should be >0.9 for clean invoices
   - `issues` array should be empty or contain only notes about supporting docs

### Phase 2: BigQuery Loading

1. **Create tables:**
   ```bash
   bq query --use_legacy_sql=false < schema/00_init.sql
   bq query --use_legacy_sql=false < schema/01_views.sql
   ```

2. **Seed rate_card:**
   ```bash
   # Create a CSV file with 2026 rates from Notion
   # Then load it:
   bq load --source_format=CSV rate_card rates_2026.csv
   ```

3. **Seed charge_code_map:**
   ```bash
   bq load --source_format=NEWLINE_DELIMITED_JSON charge_code_map extraction/charge_code_map.json
   ```

4. **Load each extracted invoice:**
   ```bash
   bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items 751996_NJ_SmallParcelLTL.json
   bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items 752325_Fontana_VAS.json
   bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items 752734_NJ_Admin.json
   bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items 751542_NJ_Storage.json
   bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items canada_brampton.json
   ```

### Phase 3: Discrepancy Validation

1. **Query discrepancies:**
   ```bash
   bq query --use_legacy_sql=false < sql/discrepancies.sql
   ```

2. **Expected results:**
   - **Small Parcel/LTL (751996):** All rates should match; flagged = FALSE (unless rates have changed)
   - **VAS (752325):** Hourly rate should match $59.82 for Fontana; flagged = FALSE
   - **Admin (752734):** Fixed fee $1,071 should match; flagged = FALSE
   - **Storage (751542):** Pallet rate $5.98 should match; flagged = FALSE
   - **Canada:** CAD rates + HST should match; flagged = FALSE

3. **View flagged discrepancies:**
   ```bash
   bq query --use_legacy_sql=false < sql/flagged_discrepancies.sql
   ```
   - Should be empty if all rates match

### Phase 4: Manual Validation

1. **Print each extracted JSON and compare to PDF:**
   ```bash
   # Example: 751996_NJ_SmallParcelLTL.json vs. 751996_NJ_SmallParcelLTL.pdf
   ```

2. **Verify charge_code_map coverage:**
   - Are all charge descriptions mapped?
   - Are confidences high (>0.9)?
   - Any "not found in map" warnings?

3. **Check supporting docs:**
   - Small Parcel/LTL: Does the Excel file have order numbers matching the invoice?
   - Storage: Does the Excel file have pallet counts matching the invoice?

## Troubleshooting

### Extraction fails
- Check that the PDF is readable (try `pdftotext` or a PDF viewer)
- Verify the invoice type detection (check invoice header against system_prompt.md)
- Check that charge descriptions are in charge_code_map.json
- If missing, add the mapping and retry

### BigQuery load fails
- Verify the JSON format matches the schema (use `jq` to validate)
- Check that all required fields are present
- Verify data types (quantities/prices should be DECIMAL64, dates should be DATE)

### Discrepancies are flagged unexpectedly
- Check that the rate_card is seeded with 2026 rates
- Verify effective_date on rate_card matches invoice_date
- Check if rates have changed (compare to your Notion rate card)
- Review tolerance_threshold (default is ±$5 in the view)

## Next Steps

Once all 5 sample invoices pass validation:
1. Create supporting doc links for Small Parcel/LTL and Storage
2. Integrate Stedi API for EDI validation (Small Parcel/LTL only)
3. Set up email ingestion (submitinvoice@americanflat.com)
4. Create scheduled BigQuery query for nightly discrepancy scan
5. Set up alerts (Slack/email on flagged items)
