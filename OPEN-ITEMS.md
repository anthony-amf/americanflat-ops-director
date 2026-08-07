# Yusen validation — open items (decision queue)

*Mirror of the local memory note so cloud sessions see it. BigQuery
(`finance.yusen_invoices`, `paid_at IS NULL`) is the authoritative ledger;
this file is the human decision queue. Update or prune as decisions land.*
*Last updated: 2026-08-06.*

## MSA billing dispute — consolidated (2026-08-05, updated 8/6)

Full sweep of all US SP/LTL + SC VAS invoices against the 7.15 MSA markup
(Anthony confirmed draft-MSA rates are final): **≈$9,034 disputed across 14
invoices** — stretchwrap billed above the $10 all-in pallet (AF-9, $5,958.39),
pack-out billed after the 4/28 removal (AF-7, $786.60 — incl. **756156**,
$22.08, found in the 8/6 post-May revalidation), and Fontana charging
every ecom pick where the schedule line is "Per **Additional** Ecom Pick"
(~$2,289). $1,347.34 of it already paid (754699, 754704) → credit-memo claims.
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
| 754864 | NJ storage | $20,580.28 | 4,742 pallets @ $4.34, worksheet exact |

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

Mac launchd sweep (`skill-updates/v1.2.0/INSTALL.md`) remains available as a
fallback — safe to run alongside; unload it once the cloud sweep is confirmed.
Local dashboard refresh: curl command provided in chat 2026-08-06; Artifact
self-refreshes weekdays 7:09 AM ET.

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
