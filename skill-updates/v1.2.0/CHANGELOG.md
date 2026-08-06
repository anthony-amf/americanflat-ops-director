# Changelog

## 1.2.0 — 2026-08-06

### Validate-on-ingest: PDF line-level pass (`validate_rate_card.py`)
- New line-level engine: fetches the invoice PDF (local cache → Drive API via
  ADC `drive.readonly` scope → public link), extracts text (OCR fallback via
  tesseract/pdftoppm for scanned SC VAS invoices), parses the charge lines,
  and verifies qty × full-precision MSA rate = line amount. Key rule learned
  from the 2026-08-06 revalidation: Yusen prints page-1 rates **truncated**
  to 2dp (1.7871 → "1.78", 4.347 → "4.34") while amounts use full precision —
  a printed rate maps to candidate full-precision rates and the line math
  picks the winner (also disambiguating NJ storage 4.34 vs stretchwrap 4.347).
- New status **`disputed`**: known MSA-conflict charges (AF-9 stretchwrap
  beside a $10 all-in pallet, 14.317 combined pallet+wrap, AF-7 pack-out at
  0.92/0.966 on SP/LTL) stamp `disputed` with the disputed $ in
  `validation_variance` and the line detail in the report.
- **VAS documentation policy** (Anthony, 2026-08-05): verified line math plus
  supporting documentation pages in the PDF → `valid`; `needs_detail` only
  when there is no documentation for the invoiced amount or the validation
  errored (unreadable/scanned-without-OCR PDF).
- **Report cards on every `--write`**: the sweep refreshes a dated
  `[AUTO-SWEEP]` section of `validation_report` (replaced in place, so daily
  runs don't bloat the report; manual/dispute/payment text is preserved).
- **Status protection**: a `disputed` stamp is never downgraded by a re-sweep;
  an existing `valid` is never downgraded to `needs_detail` by a shallower
  pass (a `discrepancy` finding still overwrites); rows already settled
  (valid/disputed) skip the PDF fetch entirely, keeping the daily sweep cheap.
- SP/LTL is never stamped `valid` by the script alone — the Stedi order-level
  payment gate stands; full-coverage SP/LTL headers record an "MSA header
  pass complete" note and stay `needs_detail` until the deep pass runs.
- New flags: `--no-pdf` (header-only), `--pdf-dir` (cache location, default
  `~/.yusen-pdf-cache`, env `YUSEN_PDF_CACHE`).
- Bundled rate snapshot refreshed to the MSA schedule (storage SC 3.35 / NJ
  4.34 / Fontana 4.47, ecom order 2.2264, picks 0.506/0.5796 "additional
  only", ship cartons 1.6422–1.8887, BOL 6.50, pallet $10.00 all-in wrap
  included); added Fontana "storage per bin" 0.7312 to the line table.
- New deps: `pypdf`, `cryptography` (PDF text extraction).

## 1.1.0 — 2026-07-13

### Validation
- Three-axis reporting is now the standard: every report gives explicit verdicts on
  invoice math, rate-card alignment, and (for SP/LTL) Stedi shipment evidence.
- US Storage/SP-LTL invoices close the rate-card axis from the PDF worksheet
  (qty × full-precision rate); billing bases documented per site (SC peak-day
  pallets, NJ flat count, Fontana locations + bulk).
- Fixed: the intl (NL/Canada) breakdown sum-check never received the `notes`
  column in the live pipeline — one-line fetch fix; the check now genuinely runs.
- NL warehousing invoices (FTI series) are VAT **zero-rated** (art. 44 export
  service) — no longer false-flagged; NL 2026 rates carry ~+4.7% Panteia indexation.
- Recorded the verified 2026 Taylored rate transition (effective billing weeks
  ~May 4–10): storage SC 3.35 / NJ 4.34 / Fontana 4.47; per-fee cuts ~8%; pallet
  restructured to $10.00 + wrap; snapshot annotated pending the Notion card update.
- NJ admin labor tax modeled as on/off date-intervals with the verified cutover
  2026-04-27 (was: flat effective date).
- Warehouse mapping: SAVANNAH / TS South → south_carolina; token-safe matching for
  short codes (stops "Schiphol" → SC substring hits).

### Stedi (SP/LTL)
- Order-level Stedi verification is **automatic** when validating an SP/LTL
  invoice — supporting doc fetched from Drive, parsed, swept 945-then-940; a
  header-only SP/LTL report is labeled incomplete.
- **Payment gate:** SP/LTL invoices cannot be marked paid until the Stedi match
  rate has been run and reviewed.
- Parser supports all three supporting-doc layouts: modern Yusen, Taylored
  (header-driven — variable sheet names/columns/offsets), and the per-carton
  SHIPPED report (ORDER# dedupe + AME*/AMF*/AMS* prefix strip). BOL numbers are
  excluded from the Stedi denominator (verified by worksheet count instead).

### Payment tracking & audit
- New tracking columns (provisioned by `--init`): `paid_at`, `paid_marked_by`,
  `validation_report`.
- `--mark-paid` / `--unmark-paid`: payment marked only on explicit user
  confirmation; approval stores the full report card on the row
  (`--report-file` for document-level reports); reports shown on the dashboard.
- Unpaid invoices no longer print a "not marked paid" line — the ask-if-paid
  step covers it.

### Docs
- README rewritten as the comprehensive system doc (families, hard rules, data
  model, gotchas, rate history); `references/netherlands.md` expanded.

## 1.0.0 — 2026-06-30
- Initial release.
- Rate-card validation against the live Notion Yusen / Taylored 2026 rate card for Admin, Storage, VAS, Small Parcel, and LTL across Fontana, New Jersey, South Carolina, Canada, and Netherlands.
- Stedi EDI order validation (945 shipped / 940 in-warehouse) for Small Parcel / LTL order numbers.
- Netherlands (Yusen Benelux) support: EUR + 21% VAT; transport-invoice checks (Amazon Delivery flat €100, fuel = pct × transport, subtotal/VAT/total) and warehousing rates.
- International breakdown sum-check for NL (EUR) and Canada (USD) one-row-per-charge-type invoices.
- NJ admin labor tax modeled as on/off date-intervals (5% before 2026-04-27).
- Write-back tracking: `--write` persists validation status to BigQuery; `--init` self-provisions the tracking columns.
