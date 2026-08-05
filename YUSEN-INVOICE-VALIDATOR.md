# skill-yusen-invoice-validator

Audit Yusen / Taylored Service (3PL warehouse) freight invoices end-to-end:
confirm the **invoice math** is exact, the billed **rates match the contract**,
and the orders billed **actually shipped** per Stedi EDI — then track approval
and payment with a stored, per-invoice report card.

- **Owner:** Anthony Armstrong <anthony@americanflat.com>
- **Tier:** 2 (writes-with-notify — persists validation/payment status to BigQuery via opt-in flags)
- **Department:** ops
- **Data:** BigQuery `americanflat.finance.yusen_invoices` · Notion rate card (live) · Stedi transactions API · Google Drive (invoice PDFs + supporting docs)

---

## The three-axis validation model

Every invoice is judged on three independent axes — one without the others is
not a validation (an invoice can sum perfectly at the wrong rate, or use the
right rate with broken totals, or bill orders that never shipped):

| Axis | Question | How it's closed |
|---|---|---|
| ① **Invoice math** | Do the invoice's own numbers reconcile? | qty × rate per line (full-precision rates), lines sum to total, VAT/GST/FX exact |
| ② **Rate card** | Do the billed rates match the contract? | PDF worksheet rates vs the rate card; currency-aware (USD / EUR+21% VAT / CAD+13% HST) |
| ③ **Stedi** | Did the billed orders ship? | Every order number checked against EDI 945 (shipped) / 940 (in warehouse) |

**Report shape** (stored on the row at approval; shown on the dashboard):

```
Invoice <#> — <type>, <warehouse>, <period>
Invoice math:  ✅ qty × rate = billed; components sum; VAT/GST exact  |  🚨 <mismatch>
Rate card:     ✅ billed rate = card  |  🚨 billed vs card  |  ⏳ needs <counts>
Stedi:         ✅ N/M orders shipped (%)  |  n/a (no order numbers on this type)
Paid:          ✓ <date>   [omitted entirely when not marked]
Verdict:       OK to pay  |  Hold — <reason>
```

## Invoice families & what gets checked

| Family | Types | Validation |
|---|---|---|
| **US weekly** (Fontana / NJ / SC-Savannah) | Storage, Admin, VAS, SP/LTL, Receiving | Storage: pallets × rate from the PDF worksheet (bases differ: SC = peak-day pallets, NJ = flat count, Fontana = locations + bulk). Admin: flat weekly, pro-rated, effective-dated NJ labor tax. SP/LTL: full per-fee worksheet + **automatic Stedi** (see gate). VAS: hourly-rate multiples where clean. |
| **Canada monthly** (Brampton, `CA2WFS…`) | Storage + Receiving rows | USD amounts incl. 13% GST — every GST line verified; full close via the Brampton billing worksheet (CAD rates × FX). |
| **NL transport** (Benelux, `CA262…`) | SP/LTL | EUR + 21% VAT. Per-order: charges sum to netto, Amazon Delivery flat €100, fuel = pct × transport; invoice: subtotal = Σ netto, VAT exact. `scripts/validate_nl_invoice.py`. |
| **NL warehousing** (`FTI…`) | Admin/Storage/VAS/Outbound/Inbound rows | EUR, **VAT zero-rated** (art. 44 export service — not an error). Components sum; €6,222/mo minimum; 2026 rates carry ~+4.7% Panteia indexation over the card's 2025 figures. |

## Hard rules (non-negotiable behaviors)

1. **SP/LTL validation automatically includes Stedi** — fetch the supporting doc
   from Drive, parse, run the 945/940 sweep as one flow. A header-only SP/LTL
   report must be labeled incomplete, never "done".
2. **SP/LTL payment is gated on Stedi** — no paid mark offered or accepted until
   the order-level match rate has been run and reviewed.
3. **Payment is a human fact** — never marked without the user's explicit
   confirmation in-conversation. "OK to pay" is a verdict, not payment evidence.
4. **Approval stores the report card** — `--mark-paid` writes the two-axis/
   three-axis report to `validation_report` on the row (pass a richer
   document-level report via `--report-file`). Reversible via `--unmark-paid`.
5. **A charge that cannot be verified is `needs_detail`, never a silent pass**
   (e.g. a fuel line with no percent, a storage header with no pallet count).
6. **Below-card billing is not a dispute** — flag as "card likely stale" and
   route to the contract owner; only above-card is a discrepancy.

## Workflow (per SKILL.md)

1. **Rate card** — fetch the Notion page live (`3898555c…`); write to JSON; the
   bundled `references/rate-card-snapshot.json` is fallback-only (warns when used).
2. **Header validation** — `scripts/validate_rate_card.py <invoice> [--rates f]
   [--write]`; `--list-all` sweeps; `--init` provisions tracking columns.
3. **SP/LTL deep pass (automatic)** — Drive-download the supporting xlsx →
   `scripts/parse_invoice_excel.py` (auto-detects all layouts) →
   `scripts/validate_stedi.py` (or a concurrent checker for 1,000+ orders).
4. **NL invoices** — `scripts/validate_nl_invoice.py <extraction.json>` (EUR-native).
5. **Report** — three axes, explicit; then ask-if-paid (skip when already marked).
6. **Payment** — `--mark-paid [--report-file rpt.txt]` / `--unmark-paid`.

## Data model (BigQuery `finance.yusen_invoices`)

Base columns: `date, bill_period, invoice_number, type_of_invoice, warehouse,
amount, notes, ingested_at, pdf_url, supporting_doc_url`. One row per invoice;
international invoices arrive one row per charge type (`-Storage`, `-Receiving`,
…) with a parseable breakdown in `notes` (`"Storage: USD 8,429.00 | X=…, Y=…"`)
that the validator sum-checks.

Tracking columns (provisioned by `--init`, idempotent):
`validated_at, validation_status, validation_variance, validated_by, paid_at,
paid_marked_by, validation_report`.

Gotchas: streaming-buffer rows block UPDATE (~90 min — stamps auto-defer and
catch up on the next `--write` pass); `bq` CLI truncates at 100 rows without
`--max_rows`; warehouse text is free-form — `WAREHOUSE_MAP` normalizes it
(**Savannah = TS South = South Carolina**; Schiphol/Moerdijk/Benelux = NL;
token-matching guards short codes like "SC" from false substring hits).

## Supporting-document layouts (all auto-detected)

| Layout | Signature | Notes |
|---|---|---|
| Modern Yusen | "Small Parcel" / "LTL" sheets | order IDs in col A |
| Taylored | `TSI PO#` in any sheet's A1 | header-driven: finds `Order`/`Bol#` header (cols A–C) and reads that column — sheet names (`Sheet1/2`, `sp/ltl`), offsets, and BOL column vary |
| SHIPPED report | `ORDER# / CARRIER / …` header | one row per carton — dedupe ORDER#, **strip `AME*`/`AMF*`/`AMS*` prefix** (Stedi indexes the bare ID) |

BOL numbers are **not** Stedi identifiers — verify them by count against the
worksheet, and exclude them from the Stedi denominator.

## Verified rate history (as of August 2026)

Current-rate source of truth: the **AMERICANFLAT Yusen MSA** (draft 7.15.2026;
Anthony confirmed 8/5/26 the rates are final — only KPI/insurance language
open). Rate validity April 2026 – March 31, 2027. The rate schedule is an
embedded image in the docx — extract text from `word/media/image2.emf`
(EMR_EXTTEXTOUTW records), don't trust pandoc/text alone. The Notion card was
rebuilt from it 2026-08-05 and is current. New rates hit invoices from the
**June 2026 billing weeks** (NJ/Fontana storage switched earlier, ~May 4–10).

| | Old (billed Mar–May) | MSA / current (June →) |
|---|---|---|
| Storage $/pallet | SC 5.0925 · NJ 5.98 · Fontana 5.9055 | **SC 3.35 · NJ 4.34 · Fontana 4.47** (−24–34%) |
| Handling out / ship carton | 2.05 / 1.94 / 1.79 | 1.8887 (CA) / 1.7871 (NJ) / 1.6422 (SC) (−8%) |
| Order fee | 2.35 / 2.36 | 2.1585 (CA) / 2.1735 (NJ) |
| BOL | 7.63 / 6.83 / 6.83 | 6.50 (all sites) |
| Pallet | Fontana 10.3274 combined · NJ 4.91→5.6235 + 4.725 wrap · SC 11.74 via VAS | **10.00 national all-in (AF-9)** — separate wrap ($4.317–4.347) billed June–mid-July is **disputed**, not a rate |
| E-com order | 2.42 | 2.2264 (all) |
| E-com picks | 0.55 billed (old card said 0.455–0.63), additional-only | 0.506 / SC 0.5796 — **"Per Additional Ecom Pick"**: first pick never billable; Fontana's June every-pick billing is disputed |
| Small parcels (UPS/FedEx per ctn) | 0.7478 / 0.71 / 0.84 | 0.6879 / 0.6532 / 0.84 |
| Pack out | NJ 1.00 ("PACK CARTONS") | **removed per Yusen 4/28 (AF-7)** — 0.92/0.966 billings are disputed |
| UCC label | 0.45 | 0.30 |
| Handling in per ctn | — | 0.9173 (CA) / 0.9467 (NJ) / 0.7728 (SC) |
| Container admin | — | 52.8831 / 47.334 / 47.288 |
| Sortation per SKU | — | 31.2981 / 29.946 / 24.15 |

Invoice-billing conventions verified from worksheets: e-com **pick charges
invoice at exactly half the supporting-worksheet pick-column sum** (both eras —
the worksheet counts pick+pack events); SC bills pallets through **VAS work
orders**, not SP/LTL invoices; Fontana embeds wrap in a combined pallet rate
while NJ lines it separately (both superseded by the $10 all-in).

NJ admin labor tax: 5% through the week invoiced 2026-04-20, dropped from
2026-04-27 (modeled as on/off date-intervals — a future reinstatement is a
config line, not a code change). Canada admin ($1,000 + $100 WMS) bills
**monthly** (Notion card note corrected 2026-08-05).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/validate_rate_card.py` | Header validation, `--write` stamps, `--init` provisioning, `--mark-paid`/`--unmark-paid` (+ `--report-file`), intl breakdown sum-check |
| `scripts/parse_invoice_excel.py` | Supporting-doc parser (all layouts, deduped, prefix-stripped) |
| `scripts/validate_stedi.py` | Sequential 945/940 order check (env `STEDI_API_KEY`) |
| `scripts/validate_nl_invoice.py` | NL EUR/VAT validator (transport + warehousing families) |

## Setup

```bash
pip3 install google-cloud-bigquery requests openpyxl
gcloud auth application-default login          # BigQuery (ADC — no key files)
export STEDI_API_KEY=<key>                     # see .env.example; never committed
python3 scripts/validate_rate_card.py --init   # one-time column provisioning
```

## Companion tooling (project repo, not packaged)

- `refresh_yusen_dashboard.py` — re-pulls the table into the HTML dashboard
  (`~/yusen_invoices_dashboard.html`): Validated + Paid chips, report card on hover.
  Idempotent; re-applies its columns after the dashboard is re-exported.
- `validation-reports/` — per-invoice markdown report files on request.

## See also

- `SKILL.md` — the agent workflow (authoritative)
- `references/netherlands.md` — NL model, zero-rating, indexation, `CA`-prefix trap
- `references/bigquery-schema.md` — columns + warehouse normalization
- `references/stedi-api.md` — endpoint, auth, 945-vs-940, order-ID hygiene
- `references/rate-card-snapshot.json` — fallback rates + pending-review annotations
