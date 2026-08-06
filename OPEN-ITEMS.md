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

Scheduled cloud sweep **`yusen-cloud-validation-sweep`** is LIVE
(`trig_016vL18kChzAxpv7tfZjqzyS`, daily 21:30 UTC ≈ 3:30 PM MDT, follows
`docs/CLOUD-SWEEP-RUNBOOK.md`, self-guarding until write access exists).
Two one-time actions to make it fully effective:

1. **Grant BigQuery write to the cloud service account — BLOCKED ON IVAN.**
   Checked 2026-08-06: Anthony's account can write data but cannot change
   permissions (no `setIamPolicy` on the table, and no project-level
   `getIamPolicy`). The `finance` dataset access list shows
   **ivan@americanflat.com as OWNER** — he can grant it; nobody else on the
   Mac can. Email draft prepared in Anthony's Gmail drafts 2026-08-06
   ("Quick BigQuery access request — Yusen invoice validation"), asking for
   `roles/bigquery.dataEditor` on TABLE `finance.yusen_invoices` for
   `cluade-service-account@americanflat.iam.gserviceaccount.com` — the same
   pattern `invoice-writer@…` already has. Until granted, each cloud run
   exits with "write grant not yet in place".
2. **Attach the Google Drive connector to the Routine** — claude.ai →
   Routines → `yusen-cloud-validation-sweep` → enable Google Drive. Without
   it the sweep can't fetch invoice PDFs (BigQuery works regardless); rows
   needing the PDF line pass stay header-level/needs_detail.

Mac launchd sweep (`skill-updates/v1.2.0/INSTALL.md`) remains available as a
fallback — safe to run alongside; unload it once the cloud sweep is confirmed.
Local dashboard refresh: curl command provided in chat 2026-08-06; Artifact
self-refreshes weekdays 7:09 AM ET.

## Standing follow-ups

- Publish **v1.1.0** of `skill-yusen-invoice-validator` (org repo stuck at
  v1.0.0). Per the 2026-07-08 Repo Merge Policy: direct commit + tag on the
  skill repo's `main`, then @governors ping in #ai-github-skills. Blocked on
  the Claude GitHub app being granted access to
  `americanflat/skill-yusen-invoice-validator` (admin: org Settings → GitHub
  Apps → Claude → Repository access).
- **Validate-on-ingest automation** — Mac punch list in
  `VALIDATION-AUTOMATION.md` (backfill SQL → dashboard refresh → skill v1.2.0
  disputed-status hook → post-ingestion launchd sweep).
- ~~Notion rate card April-2026 rates~~ — **done 2026-08-05**: card rebuilt
  from the MSA rate schedule (current rates + pre-June history + disputed-
  charges warning); Canada monthly-billing note corrected.
- Yusen NL: FTI0006458 was never emailed to Americanflat (resend was on the
  table in the John Alink action-tracker thread) — it has since been loaded
  via Drive, so only the process fix remains with Yusen.
