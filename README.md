# Invoice Audit System

A carrier-agnostic invoice audit system for Americanflat. Ingest invoices, extract structured line items via Claude, load into BigQuery, and automatically flag charges that don't match negotiated rate cards.

**Design principle:** Claude does the messy work (PDF → structured line items); SQL does the math (expected vs. billed).

---

## Overview

### Goal
Drop invoice PDFs into a folder → extract structured line items → load into BigQuery → compare each charge against the rate card → produce an auditable `discrepancies` table on a regular cadence.

### Data Flow
```
invoice PDF  →  extraction (Claude)  →  invoice_line_items (BigQuery)
                                              │
                          join on lane + canonical charge code + date
                                              │
rate_card ───────────────────────────────────┤
charge_code_map ──────────────────────────────┘
                                              ▼
                                        discrepancies
```

---

## Invoice Types

The system handles **5 invoice types**, each with distinct validation logic:

### 1. Small Parcel / LTL Shipments
- **Structure:** Multiple line items (qty @ unit price per charge type)
- **Example charges:** E-commerce orders, Ship cartons, Pallets, BOLs, etc.
- **Validation:** Rate card + Stedi 940/945 EDI documents
- **Supporting docs:** Excel files with order numbers, carton counts, BOL numbers
- **Carriers:** Yusen Logistics (US locations)
- **Cadence:** Monthly

### 2. Value Added Services (VAS)
- **Structure:** Labor-based (hours @ hourly rate) OR material-based (units @ unit price)
- **Examples:** Back office support, labeling, repackaging, overtime
- **Validation:** Rate card only
- **Supporting docs:** Email or attached documentation
- **Cadence:** Variable (as needed)

### 3. Storage
- **Structure:** Pallets @ per-pallet per-week rate
- **Validation:** Rate card + warehouse inventory count (weekly snapshot)
- **Supporting docs:** Excel with pallet inventory details
- **Cadence:** Weekly

### 4. Administrative
- **Structure:** Fixed weekly fee per location
- **Validation:** Contract rate (no variance expected)
- **Supporting docs:** None (contract terms only)
- **Cadence:** Weekly

### 5. Canada
- **Structure:** Mixed (similar to US but with HST + currency conversion)
- **Unique aspects:** 
  - Harmonized Sales Tax (HST) applied to non-shipping items
  - Currency conversion CAD → USD
- **Validation:** Rate card (in CAD) converted to USD, HST verified
- **Cadence:** Monthly

---

## BigQuery Schema

### `invoice_line_items`
One row per charge extracted from an invoice.

```sql
invoice_number (STRING, NOT NULL)
invoice_date (DATE, NOT NULL)
invoice_type (STRING) -- SMALL_PARCEL_LTL, VAS, STORAGE, ADMIN, CANADA
carrier (STRING) -- Yusen, Taylored, etc.
warehouse_location (STRING) -- Fontana, New Jersey, South Carolina, Brampton
canonical_charge_code (STRING) -- normalized code
charge_description (STRING) -- carrier's original language
quantity (DECIMAL)
unit_price (DECIMAL)
billed_amount (DECIMAL)
currency (STRING) -- USD, CAD
hst_amount (DECIMAL) -- Canada only
supporting_doc_url (STRING) -- link to Excel/supporting documentation
line_hash (STRING) -- FARM_FINGERPRINT for idempotency
created_at (TIMESTAMP)

PRIMARY KEY: (invoice_number, line_hash)
```

### `rate_card`
Negotiated rates, effective-dated. Rates change rarely; when they do, add a new row with a new `effective_date`.

```sql
warehouse_location (STRING)
canonical_charge_code (STRING)
effective_date (DATE, NOT NULL)
end_date (DATE) -- NULL = current; used to handle rate version transitions
unit_price (DECIMAL)
currency (STRING) -- USD, CAD
notes (STRING) -- e.g., "Updated per contract renewal 2026"
created_at (TIMESTAMP)

PRIMARY KEY: (warehouse_location, canonical_charge_code, effective_date)
```

### `charge_code_map`
Maps each carrier's charge descriptions to canonical codes. **This is the tuning surface** — you'll update this most often as you discover new charge descriptions.

```sql
carrier (STRING)
invoice_type (STRING)
carrier_charge_description (STRING) -- e.g., "E-commerce orders - Count of DTC orders"
warehouse_location (STRING)
canonical_charge_code (STRING) -- e.g., SMALL_PARCEL_ECOM_ORDER
notes (STRING) -- why this mapping, any caveats
created_at (TIMESTAMP)
updated_at (TIMESTAMP)

PRIMARY KEY: (carrier, invoice_type, carrier_charge_description, warehouse_location)
```

### `discrepancies` (view)
Audit output: billed vs. expected, with deltas. Computed nightly by the comparison SQL.

```sql
invoice_number (STRING)
invoice_date (DATE)
invoice_type (STRING)
warehouse_location (STRING)
carrier (STRING)
canonical_charge_code (STRING)
billed_quantity (DECIMAL)
billed_unit_price (DECIMAL)
billed_amount (DECIMAL)
expected_unit_price (DECIMAL)
expected_amount (DECIMAL)
delta (DECIMAL) -- billed - expected
delta_percent (FLOAT)
flagged (BOOL) -- TRUE if abs(delta) > tolerance_threshold
tolerance_threshold (DECIMAL) -- configurable parameter
created_at (TIMESTAMP)
```

---

## Design Decisions

### Effective-date the rate card
Rates change over a contract's life. The system matches each invoice line to the rate version **in effect on the invoice date**, not today's rate. Use `effective_date` and `end_date` to model rate transitions.

### The charge-code map is the hard part
Carriers describe the same accessorial many different ways. A version-controlled dictionary mapping their language to yours is what makes the audit reliable — and it's the piece you'll tune most over time.

### Idempotent loads
Re-running extraction on the same invoice must not create duplicate rows. Dedupe on `invoice_number + line_hash` (where `line_hash = FARM_FINGERPRINT(invoice_number || line_sequence)`).

### Configurable tolerance
Don't flag two cents of rounding. Make the flag threshold a parameter in the discrepancies query.

### Separate responsibilities
- **Claude:** Extracts messy PDF data, normalizes charge descriptions to canonical codes using `charge_code_map`
- **SQL:** Joins extracted data to rate card, computes deltas, flags discrepancies
- **Never** have Claude decide if $4,200 equals $3,800 — that's a SQL join.

---

## Repo Structure

```
invoice-audit/
├── README.md                          # This file
├── .gitignore                         # Exclude credentials, PDFs, data
├── schema/
│   ├── 00_init.sql                    # DDL for all 4 tables
│   └── 01_views.sql                   # Discrepancies view + helpers
├── extraction/
│   ├── extract_invoice.py             # CLI: reads PDF, calls Claude, outputs JSON
│   ├── system_prompt.md               # Claude system prompt (the intelligence)
│   └── charge_code_map.json           # Carrier → canonical code mappings
├── sql/
│   ├── load_invoice_lines.sql         # Idempotent insert with dedup
│   ├── rate_card_snapshot.sql         # View: rate_card as of invoice_date
│   └── discrepancies.sql              # Main audit query
├── samples/
│   ├── README.md                      # Instructions for testing
│   ├── 751996_NJ_SmallParcelLTL.pdf  # Test invoice 1
│   ├── 752325_Fontana_VAS.pdf         # Test invoice 2
│   ├── 752734_NJ_Admin.pdf            # Test invoice 3
│   ├── 751542_NJ_Storage.pdf          # Test invoice 4
│   └── 16v_cJBaViconkw0yx4meyIjmBySxwnV7_Canada.xlsx # Test invoice 5
└── orchestration/
    ├── ingest.py                      # (Future) Email → PDF → extraction → BQ
    └── validate.py                    # Run discrepancy scan on samples
```

### What goes in the repo (version-controlled)
- Schema DDL
- Extraction prompt
- Charge-code map
- Comparison SQL
- Orchestration script
- README

### What does NOT go in the repo
- Credentials / BigQuery service-account key
- Invoice PDFs (except samples/)
- Actual invoice data in BigQuery

---

## Build Sequence

### Phase 1: Proof of Concept (Local)

1. **Stand up the BigQuery schema**
   - Run `schema/00_init.sql` to create tables

2. **Seed the rate card**
   - Load 2026 rates from Notion into `rate_card` table
   - Rates effective 2026-01-01, no end_date (= current)

3. **Seed the charge-code map**
   - Map carrier descriptions from all 5 invoice types to canonical codes
   - Example:
     - Carrier: "Yusen", Type: "SMALL_PARCEL_LTL", Description: "E-COMMERCE", Location: "NEW JERSEY" → Code: "SMALL_PARCEL_ECOM_ORDER"

4. **Extract → `invoice_line_items`**
   - Run `extraction/extract_invoice.py` on 1 sample of each type (5 PDFs)
   - Verify extracted JSON matches invoice PDF
   - Load to BigQuery via `sql/load_invoice_lines.sql`

5. **Run comparison SQL**
   - Execute `sql/discrepancies.sql`
   - Validate against known-good invoices (should have ~0 delta)
   - Validate against known-bad invoices (should flag discrepancies)

6. **Iterate on charge-code map**
   - If extraction misses a charge type, update `charge_code_map.json` and re-run

### Phase 2: Production (Email Ingestion + Scheduling)

1. **Email ingestion**
   - Script watches `submitinvoice@americanflat.com` for PDFs
   - Downloads PDFs + supporting docs to a staging folder

2. **Scheduled extraction**
   - Nightly or weekly: run `extraction/extract_invoice.py` on all new PDFs
   - Load to `invoice_line_items`

3. **Scheduled discrepancy scan**
   - BigQuery scheduled query runs `sql/discrepancies.sql` nightly
   - Outputs to `discrepancies` table
   - Alert on flagged items (via email or dashboard)

---

## Setup Instructions

### Prerequisites
- `gcloud` CLI authenticated to your BigQuery project
- Python 3.9+
- Claude API key (via `ANTHROPIC_API_KEY` env var)

### 1. Create BigQuery tables
```bash
bq query --use_legacy_sql=false < schema/00_init.sql
bq query --use_legacy_sql=false < schema/01_views.sql
```

### 2. Seed rate card and charge-code map
```bash
# Load rates from Notion (manually or via script)
bq load --source_format=CSV rate_card rates_2026.csv

# Load charge-code mappings
bq load --source_format=NEWLINE_DELIMITED_JSON charge_code_map charge_code_map.json
```

### 3. Test extraction on samples
```bash
python extraction/extract_invoice.py samples/751996_NJ_SmallParcelLTL.pdf
# Outputs: 751996_NJ_SmallParcelLTL.json

# Validate JSON output, then load to BigQuery
bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items 751996_NJ_SmallParcelLTL.json
```

### 4. Run discrepancy scan
```bash
bq query --use_legacy_sql=false < sql/discrepancies.sql
```

---

## Key Files

### `extraction/system_prompt.md`
The Claude system prompt that drives invoice extraction. It:
- Identifies invoice type (SMALL_PARCEL_LTL, VAS, STORAGE, ADMIN, CANADA)
- Extracts header info: invoice number, date, warehouse location, carrier
- Extracts line items: charge description, quantity, unit price, total
- Maps each charge to a canonical code using `charge_code_map.json`
- Handles currency conversion for Canada invoices
- Outputs structured JSON

### `extraction/charge_code_map.json`
Example structure:
```json
[
  {
    "carrier": "Yusen",
    "invoice_type": "SMALL_PARCEL_LTL",
    "carrier_charge_description": "E-COMMERCE",
    "warehouse_location": "NEW JERSEY",
    "canonical_charge_code": "SMALL_PARCEL_ECOM_ORDER",
    "notes": "Count of DTC e-commerce orders shipped via small parcel"
  },
  {
    "carrier": "Yusen",
    "invoice_type": "SMALL_PARCEL_LTL",
    "carrier_charge_description": "SHIP CARTONS",
    "warehouse_location": "NEW JERSEY",
    "canonical_charge_code": "SMALL_PARCEL_SHIP_CARTONS",
    "notes": "Carton picks for small parcel shipments"
  }
]
```

### `sql/discrepancies.sql`
Joins extracted invoices to rate card, computes deltas, flags anomalies.

Key logic:
- For each line in `invoice_line_items`:
  - Look up rate in `rate_card` on (warehouse_location, canonical_charge_code, effective_date)
  - Compute expected_amount = quantity × expected_unit_price
  - Compute delta = billed_amount - expected_amount
  - Flag if abs(delta) > tolerance_threshold

---

## Validation Rules by Invoice Type

### Small Parcel / LTL
- **Rate card match:** ✓ (billed vs. contract rate)
- **Stedi EDI match:** ✓ (order numbers appear in 940/945 documents)
- **Supporting docs:** ✓ (Excel with order counts, carton counts, BOLs)

### VAS
- **Rate card match:** ✓ (hours/units vs. contract rate)
- **Supporting docs:** ✓ (email, attached notes)

### Storage
- **Rate card match:** ✓ (pallet count vs. contract rate)
- **Inventory match:** ✓ (weekly pallet count from warehouse system)

### Admin
- **Contract match:** ✓ (fixed fee, no variance expected)

### Canada
- **Rate card match:** ✓ (CAD rate converted to USD)
- **HST calculation:** ✓ (tax applied correctly to non-shipping items)
- **Currency conversion:** ✓ (exchange rate on invoice date)

---

## Tolerance Thresholds

Define in `sql/discrepancies.sql`:
- **Small Parcel / LTL:** ±$5 or ±2%
- **VAS:** ±$1 or ±5%
- **Storage:** ±5 pallets or ±10%
- **Admin:** $0 (exact match expected)
- **Canada:** ±CAD$5 or ±2%

Adjust based on historical variance and rounding patterns.

---

## Troubleshooting

### Extraction fails on a specific invoice
1. Check invoice type detection (is the header recognized?)
2. Verify charge descriptions exist in `charge_code_map.json`
3. Look at the extracted JSON — are line items present?
4. Add the missing mapping to `charge_code_map.json` and retry

### Discrepancies are flagged but look correct
1. Check the rate card — is the effective date right?
2. Verify currency (USD vs. CAD)
3. Check tolerance threshold — is it too tight?
4. Review the delta — is it rounding or a real error?

### BigQuery queries time out
1. Partition `invoice_line_items` by `invoice_date` for faster joins
2. Index `rate_card` on (warehouse_location, canonical_charge_code, effective_date)

---

## Future Enhancements

- [ ] Email ingestion (submitinvoice@americanflat.com)
- [ ] Scheduled queries (nightly discrepancy scan)
- [ ] Dashboard (Looker/Datazoom showing trends)
- [ ] Alerts (Slack/email on flagged items)
- [ ] Stedi API integration (validate EDI documents)
- [ ] Multi-currency support (EUR, etc.)
- [ ] Version history (audit trail for rate changes)

---

## Contact

Questions or issues? Reach out to the Operations team or open an issue in this repo.
