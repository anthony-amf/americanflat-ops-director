# Changelog

## 1.5.0 — 2026-08-13

Hourly labor is now validated **per warehouse**. Until now every hourly rate in
the MSA sat in one flat table, so a rate valid at one DC passed everywhere — a
South Carolina $63.00 physical-inventory rate billed on a New Jersey work order
verified clean. The MSA prices the same role differently by site, so the check
has to know which site billed the hour.

- **`MSA_HOURLY_RATES`, keyed by warehouse.** Fontana: $35 material handler, $42
  clerical, $47.1232 QA, $59.8278 general labor / physical inventory / stock
  consolidation, $82.1166 supervisor. New Jersey: $35 / $42 / $53.55 / $77.70.
  South Carolina: $32 / $40, $53.55 general labor, **$63.00 physical inventory
  and stock consolidation**, $77.70 supervisor. National lines ($185 IT, and the
  legacy $56.82 returns rate verified against real invoices) apply everywhere.
- **Off-card labor rates are named, not waved through.** A line billed at another
  site's hourly rate is labelled `off-card hourly (...)` and held at
  `needs_detail`, with that warehouse's own hourly schedule printed in the report
  card. It is deliberately **not** `disputed` — a wrong-site rate is a rebill
  request, not one of the enumerated AF-7/AF-9 MSA conflicts.
- **The VAS ad-hoc job-rate escape no longer hides it.** Both the parsed-line path
  and the scanned/OCR fallback check the off-card table first, so a mis-keyed
  labor rate can no longer be accepted as "job rate 63.0" and stamped `valid`.
- **Unknown warehouses keep 1.4.0 behaviour** — a row whose warehouse text doesn't
  normalize is matched against every site's rates, so it is never flagged on a guess.
- Added the missing **SC dray admin fee $51.45** to the flat rate table (Fontana
  $52.8831 and NJ $47.334 were already there as container admin).
- **Rate snapshot:** SC `vas_hourly` corrected **51.00 → 53.55** — 51.00 was the
  pre-June card rate, superseded by the MSA hourly table. Added a `hourly_labor`
  block mirroring the MSA's per-site role table, so the fallback snapshot carries
  the same rates as the code.

Rate source: AMERICANFLAT Yusen MSA hourly labor table (draft 7.15.2026, rates
final per Anthony 8/5/26), mirrored on the Notion rate card.

## 1.4.0 — 2026-08-06

Adds a **PDF line-level pass** on top of 1.3.0's stickiness rules. Until now the
sweep could only see the invoice header, which is why VAS, Storage, Receiving and
SP/LTL invoices parked on `needs_detail` and needed a person to supply the detail.
The validator now opens the invoice PDF itself and checks every charge line.

- **Line-level verification.** For US invoices the sweep fetches the PDF (local
  cache → Drive API via ADC `drive.readonly` → public link), extracts the text
  (tesseract/pdftoppm OCR fallback for the scanned SC VAS scans), parses the
  charge lines and verifies qty × full-precision MSA rate = line amount.
- **Truncated-rate matching** — the rule that makes it work. Yusen prints page-1
  rates truncated to 2dp (1.7871 → "1.78", 4.347 → "4.34", 0.7312 → "0.73") while
  the line amounts use full precision. A printed rate is matched to every
  full-precision MSA rate it could represent and the line math picks the winner —
  which also disambiguates NJ storage 4.34 from stretchwrap 4.347. Matching
  printed rates against card values directly is what produced the false
  `needs_detail` stamps cleared in the 2026-08-06 revalidation.
- **Disputes from real line evidence** complement `apply_msa_conflicts`' notes-based
  detection: AF-9 wrap/14.317 pallet+wrap, AF-7 pack-out on SP/LTL. A dispute found
  by either route survives the other coming back clean.
- **VAS documentation policy** (Anthony, 2026-08-05): verified line math — MSA rate,
  ad-hoc job rate, or an OCR line reconciling to the invoice total — plus supporting
  documentation pages in the PDF stamps `valid`. `needs_detail` is reserved for no
  documentation, or an error (unreadable/scanned-without-OCR).
- **SP/LTL is never stamped `valid` by the sweep** — the Stedi order-level payment
  gate stands. A clean SP/LTL header records an "MSA header pass complete" note and
  stays `needs_detail`.
- **Settled rows skip the PDF fetch entirely** (disputed, or any `valid` stamp
  including human-set ones), which is what keeps a several-times-daily sweep cheap
  and preserves 1.3.0's guarantee that a human verdict is not re-judged.
- New flags `--no-pdf` and `--pdf-dir` (default `~/.yusen-pdf-cache`, env
  `YUSEN_PDF_CACHE`); new deps `pypdf`, `cryptography`.
- Bundled rate snapshot refreshed to the MSA schedule (storage SC 3.35 / NJ 4.34 /
  Fontana 4.47, ecom order 2.2264, additional picks 0.506 / SC 0.5796, ship cartons
  1.6422–1.8887, BOL 6.50, $10.00 all-in pallet with wrap included) plus Fontana
  "storage per bin" 0.7312.

Verified against the 108 cached post-May US invoice PDFs: every verdict matches the
hand-checked 2026-08-06 revalidation.

## 1.3.0 — 2026-08-05

Human verdicts outrank the automated header pass. A stamp recorded by a person is
now as sticky as a `disputed` stamp, so supplying the itemized detail once makes it
stick instead of being reverted by the next sweep.

- **A human stamp is preserved against re-sweeps.** `write_result` treats any prior
  stamp whose `validated_by` is not `yusen-invoice-validator` as human-set: an
  automated pass returning `valid` or `needs_detail` refreshes `validated_at` and the
  `[AUTO]` report block but leaves the status, variance and provenance alone. This
  generalises the previous rule, which only protected a *paid* row's explicit `valid`
  — it now covers unpaid rows too, which is the common case for an invoice whose
  hours or unit counts were entered by hand.
- **Escalations still win.** Preservation applies only when the sweep comes back
  `valid`/`needs_detail`. A pass that finds `disputed` or a discrepancy overrides a
  human `valid`, because that is new information rather than missing information.
- **`fetch_invoice` now selects `validated_by`.** Without it the guard above could
  never see who set the prior stamp and would silently never fire.
- **Why now.** A header-level pass cannot see hours or itemized counts, so VAS,
  Storage and SP/LTL invoices land on `needs_detail` by default. When those details
  are supplied by hand and the row is marked `valid`, the 15:30 MT sweep was set to
  overwrite it the next day — a treadmill that would have reverted invoice 755879 and
  the 226 rows bulk-marked valid on 2026-08-05.

## 1.2.0 — 2026-08-05

Validate-on-ingest hook: every sweep now stamps a finance-visible status and a
stored report card, and invoices carrying known MSA-conflict charges surface as
`disputed` automatically instead of waiting for a manual review.

- **New `disputed` status** (⚑, short-pay/hold): emitted when a validated
  invoice contains any known 2026-MSA conflict line — AF-9 wrap billed
  separately (NJ STRETCHWRAP at 4.34–4.35) or embedded (Fontana/SC 14.317
  pallet rate → wrap component × 4.317) against the $10.00 all-in national
  pallet rate; AF-7 PACK CARTON pack-out at 0.92 (removed per Yusen 4/28);
  Fontana PICK & PACK ECOM billed on every pick where the MSA line is "Per
  Additional Ecom Pick" (flagged for additional-only recompute). The disputed
  dollar total goes to `validation_variance`, so both dashboards render
  "⚑ Disputed $X".
- **Disputed stamps are sticky**: a re-sweep whose header-level pass comes back
  `valid`/`needs_detail` refreshes `validated_at` and the report but never
  downgrades a `disputed` row — the conflict lives in line items a header pass
  can't see. Clears only on re-bill/credit or manual clearing.
- **Paid-valid stamps are sticky too**: a paid row explicitly stamped `valid`
  (the mark-paid user policy) is settled — a later header-level sweep coming
  back `needs_detail` refreshes the report but never un-checks it; real
  escalations (`discrepancy`/`disputed`) still overwrite.
- **Report card stored on every `--write`**, not only on `--mark-paid`: the
  per-invoice verdict is written to `validation_report` as a dated
  `[AUTO YYYY-MM-DD]` block that replaces only its own previous block —
  payment report cards, `[MSA DISPUTE …]` specs, and human notes are preserved.
- Sweep rollup now counts and lists MSA disputes alongside discrepancies.

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
