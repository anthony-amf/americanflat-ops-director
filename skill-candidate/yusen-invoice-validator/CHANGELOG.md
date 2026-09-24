# Changelog

## 1.6.0 — 2026-08-14

Teaches the validator to judge two kinds of VAS work that had no way to resolve, and
corrects three rate-card errors that were producing false disputes. Only
`validate_rate_card.py`, `references/rate-card-snapshot.json` and `skill.toml`
(version bump) differ from 1.5.0.

### Savannah VAS pallet work orders

Savannah bills pallets as VAS jobs rather than on the SP/LTL invoice. The generic VAS
logic has no per-unit basis for those, so they parked at `needs_detail` indefinitely —
including invoices billed exactly right. New `apply_vas_pallet_check` reads the
quantity and rate from `notes` (no PDF and no OCR needed, which matters because SC VAS
PDFs are scanned images), then:

1. Recomputes pallets x printed rate against the invoice total. A mismatch is a
   `discrepancy` and the rate question is not asked.
2. Judges the rate against AF-9's $10.00 all-in, pallet and stretch wrap included:
   $10.00 is `valid`, above it is `disputed` for the excess, below it is a
   `discrepancy` needing a human.

Stage 2 is what protects money. 48 x $14.317 = $687.22 recomputes perfectly, so a
recompute-only rule would have stamped an AF-9 overcharge `valid` and dropped a live
claim.

Bounded by `ltl._af9_effective_from` (2026-06-01), so a pre-June invoice billed at the
documented pre-June rate is `valid` with a note, not disputed — the pre-June rate is
the correct rate for a pre-June invoice. Without that bound the rule would have
flipped three settled April invoices to `disputed` on every nightly sweep.

Two interference guards: `apply_msa_conflicts` stands aside when the pallet rule has
already judged the charge, and `_line_pass_keeping_disputes` skips these rows rather
than let a scanned PDF demote a sound `valid`.

### Hourly VAS projects vs the MSA hourly table

New `apply_vas_labor_check` divides the total by the hours in `notes`, works out which
row of the MSA table the work belongs to, and compares. The rate depends on both site
and kind of work, which is why one figure per warehouse was never enough. Matching
against the whole site column rather than only the guessed role means a wording
mismatch cannot turn a contracted rate into a dispute. Overtime at 1.5x any contracted
role rate reads as `valid` — agreed, so it is a contracted rate like any other, and a
multiplier on whichever row applies rather than a rate of its own. Above every rate in
the column is `disputed` for the excess over the highest contracted rate; below the
role rate is `valid`, noted as in Americanflat's favour.

It also clears validate()'s "provide hours from the invoice detail" placeholder once it
has supplied them, so a resolved row cannot read `valid` and "needs more detail" at
once.

### Three rate-card corrections

- **South Carolina hourly held $51.00**, which appears nowhere in the MSA — the
  superseded card value, as the live Notion card's own footnote says. Judged against
  it, five correctly-billed Savannah invoices read as overbilled, including a
  stock-consolidation project at the contracted $63.00. The card now carries the full
  role x site table, and `vas_hourly` defaults to general labour.
- **No `receiving` section at all**, so receiving invoices had nothing to check
  against. Now mirrored from the Notion card, including the pre-June rates that the
  card's own history table lacked — every observed line sits at exactly 1.087x the
  June rate, confirmed to the cent against the PDFs of 749279 and 752320.
- **AF-9 had no effective date**, covered above.

Also recorded: the 1.5x overtime multiplier, the IT and supplies/equipment rows, and
the New Jersey 5% labour tax appearing on receiving invoices as "NJ BILL OF RIGHTS
SURCHARGE" — the same charge under different wording, which a match on "labor tax"
misses.

### Effect on the ledger

Nineteen invoices resolved. All eleven hourly VAS jobs now read `valid` ($15,984, none
disputed) — the six already-valid Savannah and NJ labour invoices were right all
along. Net dispute movement is negative: $1,766 of claims raised against the stale
card were withdrawn once it was corrected. Every one was our own reference being
wrong, not Yusen's billing.

## 1.5.0 — 2026-08-11

Fixes two report-text bugs found on invoice 755265. Nothing about how invoices are
judged changes — status, variance and stamp stickiness behave exactly as in 1.4.0.
What changes is how the stored `validation_report` is assembled, and it fixes real
data loss.

**Only two files differ from 1.4.0:** `validate_rate_card.py` and `skill.toml`
(version bump). `SKILL.md` is included with the two documentation passages
updated. Everything else in the 1.4.0 package is unchanged — copy these over the
canonical source and repackage.

### 1. `--mark-paid` was destroying the row's report history

`mark_paid()` stored the payment card with
`validation_report = COALESCE(@report, validation_report)` — a full replace. Since
the mark-paid path always builds a report (auto-composed when `--report-file` is
omitted), **every payment mark silently discarded every other block on the row.**

Found on 755265: the row went from 1,644 chars to 386, losing its
`[MSA REVAL 2026-08-06]` block and its `[DEEP PASS 2026-08-10]` block — the
itemized five-line math and the 289/289 Stedi order match. 754891 lost the same
way (1,741 → 386, 106/106 Stedi). Both rows are `valid` and paid, so no later
sweep would ever have rebuilt them; the text survived only in BigQuery's 7-day
table history. Older paid rows escaped visible damage only because a later sweep
happened to re-add an `[AUTO]` block.

Now: the payment card goes in as its own `[PAID YYYY-MM-DD]` block via
`merge_report(..., tag="PAID")`, leaving every other block verbatim. A second
payment mark replaces only the `[PAID]` block. If the prior report cannot be read,
the field is left untouched rather than overwritten.

Recovery for the two damaged rows:
`sql/restore_clobbered_reports_2026-08-11.sql` in the ops-director repo.

### 2. A header-level pass could talk over a completed deep review

`write_result()` refreshed the `[AUTO]` block on every write — including writes
where it had just decided to *preserve* the existing status. So on 755265 an
`[AUTO 2026-08-11]` block reading "provide itemized counts" and "order-level Stedi
check available via supporting Excel" was appended directly beneath a
`[DEEP PASS 2026-08-10]` block that had already recorded the itemized math and
289/289 shipped. The AUTO block is written last, so it reads as the current
verdict — the invoice looked unfinished when it was fully checked and paid.

Now: when the result is `needs_detail` **and** the row already carries a
`[DEEP PASS]`, `[STEDI]`, `[MSA DISPUTE]` or `[MSA REVAL]` block, the AUTO block
becomes one line — "header-level re-check only, no new findings; itemized detail
already on file above (…); this pass does not supersede it" — instead of the full
card. Rows with no deeper block are unaffected and still get the normal card.

`--mark-paid`'s auto-composed card follows the same rule: with a deeper review on
the row it cites that review rather than re-stating header-level unknowns.

### 3. Smaller wording fix

`compose_report()`'s Stedi line said "order-level Stedi check available via
supporting Excel" — which reads as a to-do even on an invoice whose check is
finished. It now says "no order-level Stedi result recorded on this row yet", and
prints a completed result when the caller supplies one via `r["stedi_note"]`.

### API notes for callers

- `merge_report(prior, block, tag="AUTO")` gained the `tag` argument. Existing
  two-argument calls are unchanged — the cloud sweep's
  `V.merge_report(prior, V.compose_report(r))` still targets the `[AUTO]` block.
- New module-level helpers: `_block_pattern(tag)`, `_DEEPER_BLOCK`,
  `_deferral_block(r, prior_report)`.
- **Rule for anything that writes report text:** go through `merge_report` with the
  right tag. Never assign `validation_report` directly — that is what caused this.

Verified by `skill-updates/v1.5.0/test_report_merge.py` (31 checks over the real
recovered 755265 text): every other block survives a payment mark, repeat marks
don't stack, `[AUTO]` merge behaviour from 1.4.0 is preserved, the deferral names
the deeper blocks and drops the misleading wording, and clean rows still get the
full card.

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
