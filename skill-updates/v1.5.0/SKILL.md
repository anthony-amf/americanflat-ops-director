---
name: skill-yusen-invoice-validator
description: >-
  Audit a Yusen / Taylored Service freight (3PL warehouse) invoice — confirm the
  billed amount matches the contracted rate card and that the orders on it
  actually shipped per Stedi EDI (945/940). Use whenever someone gives an invoice
  number ("validate 752857", "is invoice 752319 correct", "should we pay this
  Yusen bill", "audit the Taylored invoice for May 25-29") or drops a Yusen/
  Taylored invoice PDF + Excel to check before payment. Also fires on "check this
  freight invoice against the rate card", "why is this 3PL invoice so high", or
  any Admin / Storage / VAS / Small Parcel / LTL invoice from Fontana, New
  Jersey, South Carolina, or Canada. Pulls invoice data from BigQuery
  (americanflat.finance.yusen_invoices) and the rate card live from Notion. Use
  this when the task is an invoice's correctness; hand a bare order list or
  single-order Stedi check to the Stedi reconciliation/lookup skills, and
  PDF-to-BigQuery extraction to the invoice-to-bigquery skill (it audits loaded
  invoices, doesn't ingest).
---

# Yusen / Taylored Service Invoice Validator

## What this does

Yusen (newer name: Taylored Services — same vendor) is Americanflat's 3PL. They
bill weekly/monthly across five warehouses for several service types. This skill
audits one invoice along two independent axes:

1. **Rate-card check** — does the billed `amount` match the contracted rate for
   that warehouse and service type?
2. **Stedi order check** — for Small Parcel / LTL invoices, did the orders being
   billed actually ship? Each order number is matched against Stedi EDI 945
   (shipped) / 940 (in warehouse) transactions.

Keep the two separate in the final report: a rate that matches but orders that
are missing is still a problem, and vice-versa.

## Setup (once per environment)

- **BigQuery**: `gcloud auth application-default login` (or a service account).
  Data lives in `americanflat.finance.yusen_invoices`.
- **Tracking columns** (`validated_at`, `validation_status`,
  `validation_variance`, `validated_by`, `paid_at`, `paid_marked_by`): the
  writer needs these on the table.
  They already exist on the `americanflat` table. Pointing at a fresh table?
  Provision them once with `python3 scripts/validate_rate_card.py --init` — it's
  idempotent and non-destructive, and `--write` auto-provisions them if missing.
- **Stedi**: `export STEDI_API_KEY=<key>`. The key is read from the environment,
  never embedded — see `references/stedi-api.md`.
- **Python**: `pip3 install google-cloud-bigquery requests openpyxl`.

## Inputs you'll get

- **An invoice number** (most common) → pull everything from BigQuery.
- **A PDF + supporting Excel** → the invoice may not be in BigQuery yet. The
  header data normally arrives via the `skill-invoice-to-bigquery` skill; the
  Excel carries the order numbers for the Stedi check.

## Workflow

### Step 1 — Pull the live rate card from Notion

The rate card changes (rates last rolled April 2026), so **fetch it live** rather
than trusting a snapshot. Use the Notion connector to fetch the page:

- Page: **"Yusen / Taylored Service — Rate Card 2026"**
- ID/URL: `3898555c-2abc-81ef-ab1d-ecc73a53973a`

Read the tables (Small parcel DTC, Small parcel Vendor Central, LTL, Storage,
Admin & VAS) and write them to a temp JSON file matching the shape of
`references/rate-card-snapshot.json` — same keys, same warehouse names
(`fontana`, `new_jersey`, `south_carolina`, `canada`), `null` for `—`/`TBD`
cells. Save it to e.g. `/tmp/rates.json`.

If the Notion connector is unavailable (headless/scheduled run), skip this step;
the validator falls back to the bundled snapshot and prints a staleness warning.
Tell the user the rates may be stale in that case.

### Step 2 — Rate-card validation

```bash
python3 scripts/validate_rate_card.py <invoice_number> --rates /tmp/rates.json
```
- Add `--list-all` (optionally `--limit N`) to sweep recent invoices instead of one.
- Add `--json` for machine-readable output.
- Omit `--rates` only to fall back to the bundled snapshot.
- Add `--write` to persist the outcome back onto the invoice row (sets
  `validated_at`, `validation_status`, `validation_variance`, `validated_by`,
  and stores the auto-composed report card in `validation_report` — replacing
  only its own previous `[AUTO YYYY-MM-DD]` block; paid report cards, MSA
  dispute specs, and human notes are preserved. When a deeper review is already
  on the row — a `[DEEP PASS]`, `[STEDI]`, `[MSA DISPUTE]` or `[MSA REVAL]` block
  — a header-level result writes a short "no new findings, see above" line
  instead of its usual card, so it cannot read as though the itemized and
  shipping work is still outstanding). This is how an invoice gets
  "checked off" — a dashboard or query can then show what's been validated. A
  plain run never mutates the table; only `--write` does.
  Freshly-ingested rows may still be in BigQuery's streaming buffer, where UPDATE
  is blocked — those are reported and succeed on a re-run once the buffer flushes.

**Line-level pass (v1.4.0).** For US invoices the script opens the invoice PDF
(cache `~/.yusen-pdf-cache` → Drive API via ADC `drive.readonly` → public link;
OCR fallback for the scanned SC VAS files) and verifies each charge line as
qty × full-precision MSA rate. Page-1 rates print **truncated** to 2dp
(1.7871 → "1.78", 4.347 → "4.34") while amounts use full precision, so a printed
rate is matched against every full-precision rate it could be and the line math
picks the winner. `--no-pdf` skips it; `--pdf-dir` moves the cache. Rows already
`valid`/`disputed` skip the fetch entirely. VAS follows the documentation policy
(verified math + supporting pages → `valid`); SP/LTL is never stamped `valid`
here — the Stedi gate stands.

What the statuses mean:
- `valid` ✅ — billed amount matches expected (within 1¢).
- `discrepancy` 🚨 — real variance. The line explains billed vs expected.
- `disputed` ⚑ — validated, but the invoice carries known MSA-conflict charges
  (AF-9 all-in $10.00 pallet vs separate/embedded wrap at 4.317–4.35; AF-7
  PACK CARTON pack-out removed 4/28; Fontana PICK & PACK ECOM billed every-pick
  where the MSA line is "Per **Additional** Ecom Pick"). `validation_variance`
  holds the disputed dollar total → dashboards render "⚑ Disputed $X".
  Short-pay/hold. **Sticky:** a re-sweep that comes back valid/needs_detail
  never clears a disputed stamp — it clears only when the invoice is
  re-billed/credited or manually cleared.
- `needs_detail` ⏳ — header total recorded but the check needs itemized data
  (VAS hours; Small Parcel/LTL per-fee units; Storage pallet count). This is
  expected for those types today, **not** a failure — say so plainly.
- `error` ❌ — unknown warehouse or no rate on contract.

How each type is checked (intentionally header-level for now):
- **Admin** → flat weekly fee, pro-rated if the period is under 5 business days.
  (5 business days = a full week; a Mon–Fri invoice is *not* short.)
- **Storage** → per-pallet rate × pallet count. Needs the pallet count from the
  invoice detail; pass it through or report `needs_detail`.
- **VAS / Small Parcel / LTL** → header total reported as `needs_detail`.

### Step 2b — Netherlands (Yusen Benelux) invoices — EUR, different path

NL invoices are **not** US-style: priced in EUR with 21% VAT, two charge families,
priced per carton. Don't run the USD rate-card check on them — use the dedicated
validator, which works from the invoice's extraction JSON (it carries the
per-order line items the BigQuery header lacks):

```bash
python3 scripts/validate_nl_invoice.py <extraction.json>
```

It auto-detects the family and validates in EUR:
- **Transport** (outbound EU delivery — what arrives today): checks per-order
  charges sum to netto, fuel = pct × transport, Amazon Delivery flat €100,
  subtotal = Σ netto, VAT = 21%, total = subtotal + VAT. Transport Outbound is a
  variable lane rate — surfaced, not rate-card-checked.
- **Warehousing** (Benelux LSA — when it arrives): surfaces contracted rates,
  applies the €6,222/month minimum, checks VAT; per-unit lines are `needs_detail`.

`validate_rate_card.py` recognizes the `netherlands` warehouse and points here
rather than running a meaningless USD check. Full detail: `references/netherlands.md`.
Naming trap: the NL invoice series uses a `CA` prefix (`CA26200110`) that is **not**
Canada — genuine Canada is `Yusen CA` / `CA2WFS…`, USD, no VAT.

### Step 3 — Stedi order validation (AUTOMATIC for Small Parcel / LTL)

Skip for Admin / Storage / VAS — they have no order numbers.

**For SMLPRCL/LTL invoices this step is not optional and must not wait to be
asked for.** Validating an SP/LTL invoice MEANS running the order-level Stedi
check — a header-only pass is an incomplete validation and its report must not
read as done. When the user asks to validate an SP/LTL invoice, do all of this
as one flow:

1. Get the order numbers. The supporting doc lives in Drive
   (`supporting_doc_url` on the BigQuery row) — **download the xlsx binary**
   via the Drive connector (`download_file_content`, base64-decode to disk;
   don't parse the text rendering), then:
   ```bash
   python3 scripts/parse_invoice_excel.py <file.xlsx> <invoice_number> --output /tmp/orders.json
   ```
   The parser auto-detects all three layouts: modern Yusen ("Small Parcel"/
   "LTL" sheets), legacy Taylored (TSI PO# header), and the per-carton
   **SHIPPED report** (`ORDER# / CARRIER / …` header) — for which it dedupes
   ORDER# and strips the `AME*`/`AMF*`/`AMS*` prefix automatically (Stedi
   indexes the bare ID; the prefixed form returns zero matches).
   If no supporting doc exists on the row, say so explicitly — the validation
   is blocked on it, and the invoice cannot clear its payment gate.
2. Validate against Stedi (checks 945, then 940):
   ```bash
   python3 scripts/validate_stedi.py <invoice_number> --json-file /tmp/orders.json --output /tmp/stedi.json
   ```

Expect a high but imperfect match rate (≈98% is normal). Genuinely missing
orders usually mean: not yet shipped, not yet transmitted to Stedi, or an
order-ID mismatch (leading `'`, `_1`/`R` suffixes, casing). See
`references/stedi-api.md`.

### Step 3b — Close the rate-card axis for US Storage (and anything with a PDF worksheet)

US Storage invoices carry a qty × rate worksheet in the PDF (`pdf_url` on the
BigQuery row), e.g. `3097 PALLETS @ 3.3500/PALLET $10,374.95` or
`STORAGE PER PALLET (PALLET LOCATIONS) 3,634 4.47`. Always pull it: it turns a
`needs_detail` into a real two-axis verdict — check (a) qty × rate = billed
(invoice math) and (b) the billed *rate* equals the rate card (rate-card
alignment). The billing basis varies by site (SC bills peak-day pallets, NJ a
flat pallet count, Fontana pallet locations + bulk) — report the basis too.

Known context (July 2026): new Taylored rates arrived 2026-04-06 and the Notion
card may lag them. Observed billed storage rates since then: SC $3.35 (card
$5.09), NJ $4.34 (card $5.98), Fontana $4.47 (card $5.90) — all *below* card. A
below-card rate is not a dispute item; flag it as "card likely stale — confirm
against the current rate sheet" rather than an overbilling discrepancy.

### Step 4 — Report

Lead with the verdict, then the evidence — and always give BOTH axes explicitly:
**invoice math** (do the invoice's own numbers reconcile) and **rate card** (do
the billed rates match the contract). One without the other is not a validation:
an invoice can sum perfectly at the wrong rate, or use the right rate with broken
totals. When an axis can't be closed, say why and what's needed. Suggested shape:

```
Invoice <#> — <type>, <warehouse>, <period>
Invoice math:  ✅ qty × rate = billed; components sum; VAT/GST exact  |  🚨 <mismatch>
Rate card:     ✅ billed rate $R = card rate  |  🚨 billed $R vs card $C  |  ⏳ needs <qty/hours/counts>
Stedi:         3,921 / 3,979 orders found (98.5%) — 58 missing   [SP/LTL only]
Paid:          ✓ <date>   [omit this line entirely when not marked paid — the
                            ask-if-paid step covers the unpaid case; don't print
                            "not marked paid"]
Verdict:       OK to pay  |  Hold — <reason>
```

### Step 5 — Payment tracking

When a validation comes back clean (verdict "OK to pay") and the invoice is not
already marked paid, ask the user: **"Has this invoice been paid?"** If they
confirm it has, mark it:

```bash
python3 scripts/validate_rate_card.py <invoice_number> --mark-paid
```

Rules that matter here:
- Payment is a human fact the validator cannot infer — **never mark an invoice
  paid without the user's explicit confirmation in this conversation.** "OK to
  pay" is a validation verdict, not evidence of payment.
- **SMLPRCL/LTL invoices are payment-gated on Stedi verification** (user rule,
  2026-07-09): don't offer or accept a paid mark until the order-level 945/940
  check has been run and its match rate reviewed. Header-level validation alone
  is not sufficient evidence of shipment for these.
- Ask per invoice for single validations. For batch sweeps, don't interrogate
  invoice-by-invoice — ask once at the end whether any of the validated set have
  been paid, and mark only the ones the user names.
- A mistake is reversible with `--unmark-paid <invoice_number>`.
- Marks land in `paid_at` / `paid_marked_by` on the BigQuery row (provisioned by
  `--init`, same streaming-buffer caveat as validation stamps). Reports show the
  paid status; skip the question when it's already marked.
- **Approval stores the report card.** `--mark-paid` adds the report to
  `validation_report` as its own `[PAID YYYY-MM-DD]` block — the audit artifact of
  what was checked at approval time. Auto-composed by default; when you performed a
  deeper document-level validation in-conversation (PDF worksheet qty×rate, NL
  per-order checks), write that richer block to a file and pass
  `--report-file <path>` so the stored report matches what the approver saw.
  The dashboard shows it as the Validated chip's hover tooltip.
  The payment card is **merged in, never substituted** — every other block on the
  row survives. Through v1.4.0 it replaced the whole field, which discarded the
  itemized and Stedi history on any row it touched (754891/755265, 2026-08-11).
  If the row already carries a deeper review, the auto-composed card cites it
  rather than re-stating what a header pass cannot see.

For a `discrepancy`, name the dollar amount and the likely cause (e.g. "NJ Admin
billed $1,071 base without the 5% labor tax — expected $1,124.55, short $53.55").
For missing Stedi orders, list a sample and the order numbers so they're
traceable. Don't bury a real problem under a wall of valid rows.

## Reference files

- `references/bigquery-schema.md` — table columns, warehouse normalization, how
  order IDs flow from the Excel (not the header).
- `references/stedi-api.md` — endpoint, auth, 945-vs-940 logic, order-ID hygiene.
- `references/netherlands.md` — NL (Benelux) EUR/VAT model, the two charge
  families, NL-only charges, and the `CA`-prefix naming trap.
- `references/rate-card-snapshot.json` — fallback rates (incl. the `netherlands`
  block) + the exact JSON shape to write when you pull Notion live.

## Scope notes

- Netherlands (Yusen Benelux) is handled via `validate_nl_invoice.py` (EUR + VAT;
  see Step 2b and `references/netherlands.md`). Transport invoices are fully
  checked; warehousing per-unit charges are `needs_detail` until itemized counts
  are available. Transport Outbound has no rate-card check (variable lane rate).
- Full line-item validation for US Small Parcel / LTL (per-fee carton/pick/pallet/
  BOL math) is deliberately out of scope for now; only header totals are checked.
  Build this out when itemized invoice data is reliably available.
- For pure "do these order numbers exist in Stedi" questions with no invoice/
  rate-card angle, the `stedi-order-reconciliation` skill is the better fit.
