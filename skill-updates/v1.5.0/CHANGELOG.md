# Changelog

## 1.5.0 — 2026-10-19

Adds a **receiving check**. Until now a US receiving invoice went through the
same flat MSA rate table as everything else, which had two blind spots:

- **No pre-June rates.** Receiving was billed at 1.087× the June rates until the
  June 2026 billing weeks. The table only knew the June rates, so all twelve
  pre-June receiving invoices (749279 → 752504, ≈$55.9K) parked on
  `needs_detail` with "no charge lines verified". The Notion card gained the
  pre-June receiving rates on 2026-08-12, but the validator never did.
- **No warehouse check.** A rate matched whichever warehouse it belonged to, so
  Fontana's 0.9173 on a New Jersey invoice would have passed.

New `scripts/receiving.py` (stdlib only, runnable on saved invoice text) checks
each line — cartons handled in, container admin, sortation per SKU, LTL/air
cartons and minimum, container storage — against the **invoice's own warehouse**
and the **rate period of its service dates** (read from "INBOUND PROCESSING
BETWEEN … AND …"; invoice date as the fallback, with a two-week grace either
side of the June cutover). It also checks the NJ 5% "Bill of Rights" labor
surcharge: its base must equal the receiving lines, and it may only appear on
invoices dated before 2026-04-27 (the snapshot's `labor_tax` periods).

Outcomes:
- every line at its own warehouse's rate for the right period, lines + surcharge
  = billed → `valid`;
- an old rate after the cut, another warehouse's *higher* rate, a surcharge
  outside its window or off its base → `discrepancy`, overcharge in
  `validation_variance`, payable amount in the report;
- a line at another warehouse's *lower* rate (likely mis-filed), an
  unrecognised rate, an unexplained remainder, or a line that only matches a
  derived, never-confirmed rate (all SC pre-June; pre-June LTL/minimum/storage)
  → `needs_detail`.

The report lists each line in plain words ("Handling in: 9,664 cartons ×
$1.029 = $9,944.26"), cartons per container, and the reason for any flag.

Layout quirks it handles, all seen on real invoices:
- **Supporting pages repeat the charges per container** ("NUMBER OF ADDITIONAL
  SKUS 19 $34.02 $646.37" under a page-1 total of 113 SKUs). Lines are read in
  layers — invoice face first, then page-1 columns, then the per-container
  worksheet, then the charge summary — and the first layer that adds up to the
  billed total is used, so detail is never counted twice.
- **Rates printed as "99.9999"** (752504): the amount is matched to the card
  rate that reproduces it exactly, and the report says so.
- **A surcharge shown only on the worksheet** (750725, 751036, 751984, 752032,
  752504 — dated after the NJ labor tax ended): the report notes it was shown
  but not billed; the total confirms it.
- **Fontana sortation is $34.0197, not the card's $34.0198.** Yusen's own
  charge summary prints 34.0197 and only that reproduces every line to the
  cent (17 SKUs = $578.33 on 750792). The Notion card should be corrected.
- Two-digit-year service periods ("BETWEEN 08/16/26 TO 08/22/26").

Line amounts must now reproduce to the cent (tolerance $0.011, was $0.02).

Verified on 15 real receiving invoices (the 12 pre-June ones plus 754676,
757874, 758385): all `valid` to the cent. `test_receiving.py` replays them from
`receiving_fixtures.jsonl` (Drive's text extraction, Yusen's bank lines removed)
plus nine planted mistakes, each caught.

`validate_rate_card.py` hands receiving rows to it from the PDF line pass;
nothing else in the line pass changes.

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
