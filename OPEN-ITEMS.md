# Yusen validation — open items (decision queue)

*Mirror of the local memory note so cloud sessions see it. BigQuery
(`finance.yusen_invoices`, `paid_at IS NULL`) is the authoritative ledger;
this file is the human decision queue. Update or prune as decisions land.*
*Last updated: 2026-07-13.*

## Awaiting Anthony's paid/hold decision (validation complete, gates passed)

| Invoice | What | Amount | Evidence |
|---|---|---|---|
| 754698 | NJ SP/LTL | $17,530.92 | **HOLD — MSA conflicts (Anthony, 2026-07-27):** validation fully passed (math exact, MSA-schedule rates, Stedi 3,773/3,773) but bills $582.50 stretchwrap + $94.76 pack-out, both disputed under AF-7/AF-9 of the 7.15 MSA markup ($10 all-in pallet; pack-out removed per Yusen 4/28) |
| 754807 | Fontana SP/LTL | $57,858.38 | Stedi 8,965/8,966; **open judgment:** pallet $10.00+$4.317 (+63%) and ecom picks +11% vs old card need confirming against the signed 2026-04-06 rate sheet (Kent Nunez) |
| 754386 | SC VAS work order | $1,073.78 | 75 pallets w/shrinkwrap @ $14.317 (= new $10+$4.317 structure) |
| FTI0006458 | NL June warehousing | €20,317.20 | reconciles to Yusen AR statement exactly |
| 754864 | NJ storage | $20,580.28 | 4,742 pallets @ $4.34, worksheet exact |

## Pre-approved, waiting on data

- **754375** ($4.20) — Anthony already confirmed paid; not yet in BigQuery.
  Validate + `--mark-paid` immediately when it lands.

## Standing follow-ups

- **Artifact dashboard auto-refresh** — rebuilt 2026-08-04 as a fingerprint-gated
  cloud Routine (`refresh-yusen-artifact-gated`, Mon/Thu 7:09 AM ET,
  `trig_01YG7tbcgDnpBRKkxo1KDHok`). Two things still open: (1) the refresher
  lives on branch `claude/website-auto-refresh-efficiency-9x474j` and the
  Routine checks that branch out by name — once it merges to `main`, simplify
  the trigger prompt to drop the checkout; (2) the old Mac-side
  `refresh-yusen-dashboard-artifact` task is now redundant and should be
  disabled so the two don't both publish. Also worth cleaning up: the orphaned
  duplicate artifact `cedf6b82…` from 2026-07-09.

- Publish **v1.1.0** of `skill-yusen-invoice-validator` (org repo stuck at
  v1.0.0, many commits behind) — via skill-fixer → `skill-candidates` → review.
- **Notion rate card** needs the April-2026 rates entered (see the verified
  rate-history table in `YUSEN-INVOICE-VALIDATOR.md`); Canada admin is billed
  monthly, not weekly as the card says.
- Yusen NL: FTI0006458 was never emailed to Americanflat (resend was on the
  table in the John Alink action-tracker thread) — it has since been loaded
  via Drive, so only the process fix remains with Yusen.
