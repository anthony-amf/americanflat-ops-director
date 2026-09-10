Judges two kinds of Savannah VAS work that previously had no way to resolve, and corrects three rate-card errors that were producing false disputes.

**Check for a PR template before using this** (`.github/pull_request_template.md`). If the repo has one, fill its sections with the material below rather than replacing it.

## Why

Two invoice shapes parked at `needs_detail` indefinitely, including ones billed exactly right:

- **Pallet work orders.** Savannah bills pallets as VAS jobs rather than on the SP/LTL invoice. The generic VAS logic has no per-unit basis for those, so it could never resolve them.
- **Hourly projects.** A job described as a project plus hours already carries everything needed for a verdict, but nothing derived the rate from it.

Meanwhile the rate card was wrong in three places, and that was costing more than the missing rules. Judged against a stale South Carolina hourly rate, five correctly-billed invoices read as overbilled.

## What changed

`apply_vas_pallet_check` reads quantity and rate from `notes` — no PDF, no OCR, which matters because SC VAS PDFs are scanned images — recomputes against the total, then judges the rate against AF-9's $10.00 all-in.

Recomputing alone would have been worse than useless: 48 × $14.317 = $687.22 recomputes perfectly, so a recompute-only rule would have stamped an AF-9 overcharge `valid` and silently dropped a live claim.

`apply_vas_labor_check` divides total by hours and matches the result against the site's column of the MSA hourly table. It matches the whole column rather than only the guessed role, so a wording mismatch can't turn a contracted rate into a dispute. Overtime at 1.5× reads as contracted.

Three rate-card corrections:

| | Was | Now |
|---|---|---|
| SC hourly | `$51.00` — a superseded card value that appears nowhere in the MSA | full role × site table; `vas_hourly` defaults to general labour |
| `receiving` | absent entirely | mirrored from Notion, including pre-June rates confirmed to the cent against two invoice PDFs |
| AF-9 | no effective date | `2026-06-01`, matching the card's own "June 2026 billing weeks" wording |

The effective date is load-bearing, not cosmetic. Without it the pallet rule would have flipped three settled April invoices to `disputed` on every nightly sweep, because a disputed result overrides an existing `valid` stamp.

Two interference guards: `apply_msa_conflicts` stands aside when the pallet rule has already judged the charge, and `_line_pass_keeping_disputes` skips those rows rather than let a scanned PDF demote a sound `valid`.

## Effect on the ledger

Nineteen invoices resolved. All eleven hourly VAS jobs now read `valid` — $15,984, none disputed; the six already-valid ones were right all along.

**Net dispute movement is negative.** $1,766 of claims raised against the stale card were withdrawn once it was corrected. Every one was our own reference being wrong, not Yusen's billing.

## Verification

- `test_vas_pallet_check.py` — 24 checks against real `notes` strings and totals from `finance.yusen_invoices`
- `test_report_merge.py` — 31 checks, carried over from 1.5.x and still passing
- Six known invoices land on the verdicts the ledger already holds: 750206 valid (pre-AF-9), 754388 disputed $207.22, 755701 valid, 756182 valid, 756396 valid, 756523 valid
- The changed files were built by script (`install_v1_6_0.py`, `merge_rates_into_1_5_1.py`) and diffed byte-for-byte against a separately reviewed copy

## Worth a reviewer's eye

**The trust level stays at 2, and that is arguable.** Writes to the ledger were human-invoked when the level was set. The skill now runs unattended — a nightly cloud run and a Mac sweep both stamp hundreds of rows with nobody watching, which reads like level 3 by the standard. `paid_at` remains human-gated and is never inferred. Flagging it rather than changing it.

**`SKILL.md` said VAS is always reported `needs_detail`.** That stopped being true with this release, so that line now describes the two shapes it resolves. It is the only prose change.
