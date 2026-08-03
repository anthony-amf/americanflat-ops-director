# Changelog

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
