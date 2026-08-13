# Yusen validation — open items (decision queue)

*Mirror of the local memory note so cloud sessions see it. BigQuery
(`finance.yusen_invoices`, `paid_at IS NULL`) is the authoritative ledger;
this file is the human decision queue. Update or prune as decisions land.*
*Last updated: 2026-08-13.*

## MSA billing dispute — consolidated (2026-08-05, updated 8/6)

Full sweep of all US SP/LTL + SC VAS invoices against the 7.15 MSA markup
(Anthony confirmed draft-MSA rates are final): **≈$9,207 disputed across 15
invoices** — stretchwrap billed above the $10 all-in pallet (AF-9, $6,131.07 —
incl. **755266**, $172.68, a 7/14 SC VAS work order billing the combined
$14.317 pallet rate, caught by the validator's line pass 8/6), pack-out billed
after the 4/28 removal (AF-7, $786.60 — incl. **756156**, $22.08, found in the
8/6 post-May revalidation), and Fontana charging
every ecom pick where the schedule line is "Per **Additional** Ecom Pick"
(~$2,289). $1,520.02 of it already paid (754699, 754704, 755266) → credit-memo claims.
Per-invoice detail + contract cites:
`validation-reports/yusen-msa-billing-dispute-2026-08-05.md`.
Yusen's own week-of-7/23 invoices bill $10 flat with no wrap — they appear to
have adopted AF-9 already.

## Awaiting Anthony's paid/hold decision (validation complete, gates passed)

| Invoice | What | Amount | Evidence |
|---|---|---|---|
| 754698 | NJ SP/LTL | $17,530.92 | **HOLD — MSA conflicts (Anthony, 2026-07-27):** validation fully passed (math exact, MSA-schedule rates, Stedi 3,773/3,773); disputed $677.26 (wrap $582.50 + pack-out $94.76) — see dispute report |
| 754807 | Fontana SP/LTL | $57,858.38 | Stedi 8,965/8,966; math exact; rates confirmed vs draft MSA (pick rate 0.506 = legit −8% from the 0.55 actually billed Mar–May; the old-card 0.455 was never billed). Disputed $4,134.32 (wrap component $1,925.38 + every-pick basis $2,208.94) — clean payable ≈ $53,724 |
| 754386 | SC VAS work order | $1,073.78 | 75 pallets w/shrinkwrap @ $14.317; wrap component $323.78 disputed under AF-9 |
| FTI0006458 | NL June warehousing | €20,317.20 | reconciles to Yusen AR statement exactly |

*Cleared: **754864** (NJ storage, $20,580.28) — marked **PAID 2026-08-07** on
Anthony's confirmation; 4,742 pallets x $4.34 exact, no MSA-conflict lines,
payment report card stored on the row.*

## Pre-approved, waiting on data

- **754375** ($4.20) — Anthony already confirmed paid; not yet in BigQuery.
  Validate + `--mark-paid` immediately when it lands.

## Auto-validation rollout — CLOUD (Anthony's direction 2026-08-06)

Cloud sweeps are LIVE, three passes a day (see VALIDATION-AUTOMATION.md for
the table): `yusen-cloud-validation-sweep` at 5:30 PM ET (30 min after ingestion)
(`trig_016vL18kChzAxpv7tfZjqzyS`) and `yusen-cloud-validation-sweep-midday`
at 10 AM + 1 PM ET (`trig_01GQSfBrEkUVPJj6MqbkSn5D`). Both follow
`docs/CLOUD-SWEEP-RUNBOOK.md`. Remaining setup:

1. ~~**Grant BigQuery write to the cloud service account**~~ — **DONE
   2026-08-06** by Iván Calderón (dataset owner; Anthony can write data but
   not change permissions). `cluade-service-account@americanflat.iam.gserviceaccount.com`
   now has write on TABLE `finance.yusen_invoices`; verified from a cloud
   session with a zero-row UPDATE probe.
2. **Attach the Google Drive connector to each Routine** — claude.ai →
   Routines → enable Google Drive. Done on the 3:30 Routine 2026-08-06;
   **still needed on `-midday`** (the trigger API can't store connectors for
   this org). Without it a run validates totals but can't open the PDFs, so
   line-level checks degrade to header-level.

Mac launchd sweep: **unloaded 2026-08-06** (it was installed as
`com.americanflat.yusen-validator-sweep`, not the never-installed
`yusen-validation-sweep` plist in `launchd/`) — the cloud Routines own this now.
Dashboard: Artifact self-refreshes weekdays 8:30 AM / noon / 3:30 PM / 6 PM ET.

## Nightly EDI (Stedi) check — scheduled, waiting on the key

`yusen-stedi-nightly` (`trig_019Drs2eEgyRt9G3DPu8rwJS`), **2:00 AM ET daily**,
follows `docs/STEDI-NIGHTLY-RUNBOOK.md`. Closes the shipping axis on SP/LTL
invoices so they stop parking at `needs_detail`, and recomputes the e-com pick
charge on the contract's additional-only basis (the AF-9/pick dispute basis).

**Blocked, by design, until `STEDI_API_KEY` is added to the cloud environment**
(Anthony, 2026-08-07: "I'll add the key to the cloud later"). Every night until
then it checks for the key, reports one line, and touches nothing — a clean
no-op, not a failure. Once the key lands the first run works through the 9 SP/LTL
invoices currently at `needs_detail` (~$62K, the largest unresolved block).
It never marks anything paid.

## Validator v1.5.0 — hourly labor by warehouse (waiting on the Mac)

Anthony asked 2026-08-13 whether $63/hour is in line. It is, but only at
**South Carolina**, and only for **physical inventory / stock consolidation**.
SC general labor is $53.55, NJ $53.55, Fontana $59.8278 (MSA hourly table).
The validator kept all hourly rates in one flat list, so $63 verified clean at
any warehouse; the bundled rate snapshot also still had SC labor at the old
$51.00 card rate. Audit of the ledger found no bad payments — the only hourly
lines ever line-checked are NJ $53.55 (755985, 756179) and Fontana $59.8278
(756527), all correct.

Finished files + step-by-step: `skill-updates/v1.5.0/APPLY-ON-MAC.md`
(warehouse-scoped `MSA_HOURLY_RATES`; a wrong-site rate now reports as an
off-card labor rate at `needs_detail`, deliberately **not** `disputed`; SC
snapshot rate corrected to $53.55; SC dray admin $51.45 added). Needs copying
into `~/.claude/skills/yusen-invoice-validator/`, repackaging, and committing.

## Standing follow-ups

- ~~Publish v1.1.0 of `skill-yusen-invoice-validator`~~ **DONE 2026-08-05**:
  org repo at v1.1.0 (`587b377`, tagged) via direct main commit per the
  2026-07-08 Repo Merge Policy. Remaining: publish **v1.2.0** (2026-08-05 local:
  `disputed` status hook, sticky disputed/paid-valid stamps, report card on
  every `--write`) the same way when ready. Registry deliberately not touched
  (Governors-only).
- ~~Notion rate card April-2026 rates~~ — **done 2026-08-05**: card rebuilt
  from the MSA rate schedule (current rates + pre-June history + disputed-
  charges warning); Canada monthly-billing note corrected.
- Yusen NL: FTI0006458 was never emailed to Americanflat (resend was on the
  table in the John Alink action-tracker thread) — it has since been loaded
  via Drive, so only the process fix remains with Yusen.
