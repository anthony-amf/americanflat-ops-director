# Changelog

## 1.6.0 — 2026-08-12

Teaches the validator to judge **Savannah VAS pallet work orders**. Savannah bills
pallets as VAS jobs rather than on the SP/LTL invoice, and the generic VAS logic
cannot resolve them — it has no per-unit basis to check — so they parked at
`needs_detail` indefinitely, including invoices billed exactly right.

Only `validate_rate_card.py` and `skill.toml` differ from 1.5.0.

### What it does

New `apply_vas_pallet_check(invoice, result)`, called after `validate()` and before
`apply_msa_conflicts()` at both call sites. It reads the quantity and rate out of
`notes` — which matters, because SC VAS PDFs are scanned images, so **no OCR is
needed to reach a verdict** — then applies two stages:

1. **Recompute.** pallets × printed rate must equal the invoice total. If it does
   not, `discrepancy`, and the rate question is not even asked.
2. **Judge the rate against AF-9's $10.00 all-in** (pallet *and* stretch wrap
   included):
   - `$10.00` → **valid**
   - above `$10.00` → **disputed** for the excess, `(rate − 10.00) × pallets`
   - below `$10.00` → **discrepancy**, unrecognised rate, needs a human

Stage 2 is the one that protects money. Arithmetic alone is not enough:
48 × $14.317 = $687.22 recomputes perfectly, so a rule that only recomputed would
stamp an AF-9 overcharge `valid` and silently drop a live claim.

### The pre-MSA rate is not grandfathered

Anthony, 2026-08-12: apply the MSA pallet rate, do not defer to the pre-MSA one. So
the old SC `$11.74` rate is treated like any other overage — `disputed` for the
$1.74/pallet excess — rather than accepted as historic. This moved five already-paid
invoices from `valid` to `disputed` (750206, 750576, 750984, 752056, 752058 — $377.58
total), which become credit-memo claims rather than short-pays.

### Why not reclassify them as SMLPRCL/LTL

Considered and rejected. SP/LTL carries the Stedi shipping gate: nothing is stamped
`valid` without an order-level EDI match. These work orders have no order numbers to
match, so reclassifying would park them at `needs_detail` **permanently** — the exact
opposite of the goal — and would misdescribe the document in a ledger whose
dashboards group by type.

### Two interference guards

- `apply_msa_conflicts()` returns early when the pallet rule has fired. Both look at
  the same charge; running the generic detector afterwards would overwrite the
  variance with a second, differently-derived figure.
- `_line_pass_keeping_disputes()` skips these rows outright. The notes already carry
  the full basis, and the PDF is a scan that would come back `needs_detail` and
  demote a sound `valid`.

### Verified

`python3 skill-updates/v1.6.0/test_vas_pallet_check.py` — 24 checks against the real
notes strings and totals from `finance.yusen_invoices`: all fourteen pallet work
orders land on the status and variance the ledger already holds (or, for the three
$10.00 invoices, the status they should have had), four non-pallet VAS jobs are left
untouched, the work-order number is never misread as a quantity, non-VAS types are
ignored, and the variance survives `apply_msa_conflicts`.

### Applied to the ledger ahead of this release

756396 → valid ($70.00) and 755908 → valid ($490.00); 752056 → disputed ($52.20) and
752058 → disputed ($99.18). The three April 2026 `$11.74` invoices (750206, 750576,
750984 — $226.20) were left alone pending a decision on whether the MSA rate reaches
back before its ~May 4-10 effective date.
