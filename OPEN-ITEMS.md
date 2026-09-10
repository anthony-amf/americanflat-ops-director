# Yusen validation — open items (decision queue)

*Mirror of the local memory note so cloud sessions see it. BigQuery
(`finance.yusen_invoices`, `paid_at IS NULL`) is the authoritative ledger;
this file is the human decision queue. Update or prune as decisions land.*
*Last updated: 2026-08-06.*

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

**Consolidated to ONE run a day, 2:00 AM MT** (Anthony, 2026-08-11):
`yusen-nightly-validation-2am-mt` (`trig_016vL18kChzAxpv7tfZjqzyS`, cron
`0 8 * * *`) does phase 1 `docs/CLOUD-SWEEP-RUNBOOK.md` (rate card, math, MSA)
then phase 2 `docs/STEDI-NIGHTLY-RUNBOOK.md` (EDI shipping) in one session, in
that order. The former midday sweep and the standalone `yusen-stedi-nightly` are
disabled but retained. 2 AM MT is 11 hours after ingestion, so nothing is stuck in
the streaming buffer — the old 5:30 PM ET pass ran 30 min after ingestion and kept
deferring fresh rows. See VALIDATION-AUTOMATION.md for the table and the DST
caveat (cron is UTC-only; needs `0 9 * * *` after 2026-11-01). Remaining setup:

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

Mac launchd sweep: **still loaded and still running — the 2026-08-06 "unloaded"
note was wrong.** `launchctl list` on 2026-08-12 shows
`com.americanflat.yusen-validator-sweep` loaded with last exit 0, and time travel
shows it sweeping all ~335 rows repeatedly (8/10 20:30 UTC, 8/12 12:30, 8/12 16:30).
It runs **v1.4.0**, so every pass rewrites `[AUTO]` cards in the old format — which
is what re-created the 28 stale blocks cleaned up on 8/12, and what will undo that
cleanup again on its next pass. It also duplicates the cloud Routine's work.
**Unload it (or install v1.5.0 locally) — until then validation has not actually
moved to the cloud.**

`com.americanflat.yusen-invoice-processor` is also loaded, with **last exit 1 —
it is failing.** That is the Yusen ingestion job (own org repo,
`skill-yusen-invoice-processor`, pushed at v1.2.0 on 8/12) — the loader that
`skill-invoice-to-bigquery` was wrongly credited with. Its failures are a second,
independent reason invoices stop arriving, on top of the OOO gaps. Read its log
before moving ingestion to the cloud: whatever breaks it locally will likely break
the cloud port too.
Dashboard: Artifact self-refreshes weekdays 8:30 AM / noon / 3:30 PM / 6 PM ET.
Both refresh Routines were paused 2026-08-07 because their page template was an
old snapshot missing the Validated column — republishing would have stripped the
validation chips off the live page. Template re-taken from the live artifact and
the five validation fields added to both the query and the field whitelist
(`claude/website-auto-refresh-efficiency-9x474j`, `ffa3b8e`); both Routines
switched back on 2026-08-11.

## Ingestion moving to the cloud — phase 0 of the 2 AM MT run

Anthony's direction 2026-08-11: move ingestion off the Mac, and run it
**fully unattended** rather than keeping the loader's human sign-off. The
safeguard that replaces the operator is a hard money gate — an invoice whose
stated total does not equal the sum of its line items is **parked, never loaded**.
Procedure: `docs/INGESTION-RUNBOOK.md`.

Findings from the investigation, since they correct the record:

- **`skill-invoice-to-bigquery` is not what loads this table.** It writes to
  `finance.freight_invoices` (drayage/carrier bills) via gcloud impersonation.
  Whatever populates `yusen_invoices` is a separate Mac-side process, still
  unidentified.
- **Ingestion is not running daily at 3 PM MT.** Actual `ingested_at` history:
  8/10 one row at 2:00 PM MT, 8/7 five rows at 9:35 AM, 8/6 nine at 2:54 PM,
  8/5 twenty-nine at 3:02 PM, 7/28 five at 3:00 PM — irregular days (a week's gap
  7/28→8/5) at varying times, one batch each. It is a manual process, not a cron.
- **Drive is currently the *output* of ingestion, not its input.** 756711.pdf was
  created in Drive at 20:00:21 UTC and the row written at 20:00:30 — nine seconds
  apart, one flow. The PDFs live in **administrator@americanflat.com**'s Drive.
- **Email attachments are unreachable from the cloud.** The Gmail connector can
  read attachment names but has no tool to download attachment bytes. Drive
  downloads work. This is structural, not a permission.

**BLOCKING prerequisite: a Drive drop folder.** Something must put each invoice PDF
into one folder before 2 AM — best a Gmail filter + Apps Script saving attachments
from the Yusen sender; better still, Yusen sending somewhere that lands in Drive
directly. Then set `DROP_FOLDER_ID` in the runbook. Until it is set, phase 0
no-ops in one line by design.

Two smaller items: phase 0 is written but **not yet added to the Routine prompt**
(the trigger API was briefly unavailable) — the Routine currently runs phases 1-2,
which is correct and safe meanwhile. And phase 0 deliberately inserts via **DML
`INSERT`, not the streaming API**, so tonight's invoices are updatable
immediately — that removes the long-standing problem of fresh rows having their
validation stamps deferred a day by the ~90-minute streaming buffer.

## EDI (Stedi) check — now phase 2 of the 2 AM MT run

Follows `docs/STEDI-NIGHTLY-RUNBOOK.md`. Closes the shipping axis on SP/LTL
invoices so they stop parking at `needs_detail`, and recomputes the e-com pick
charge on the contract's additional-only basis (the AF-9/pick dispute basis).
No longer a separate Routine — the standalone `yusen-stedi-nightly` is disabled.

**Cost discipline (Anthony, 2026-08-11): every order lookup is a metered API call,
and we are not asking Stedi about pricing — they won't help.** So the runbook's
Guard 0 is the standing design, not a placeholder: never query an order twice, a
retry queries only the previously-unmatched IDs (stored parseably on the row for
exactly that purpose), results cache to disk so an interrupted run resumes, the
total order count is estimated before any call and the run stops above 20,000, and
any 429/5xx means back off and stop rather than push through. Scope is floored at
2026-01-01 and excludes paid and `valid` rows — 10 invoices rather than 61.

**Unblocked 2026-08-11.** Anthony added the key to the cloud environment and had
`core.us.stedi.com` allowed through the proxy. Verified the same day from a fresh
cloud session: `STEDI_API_KEY` present (id `rmyNws8`), authenticated call to Stedi
returned HTTP 200. The job's first real run works through the 9 SP/LTL invoices at
`needs_detail` (~$62K, the largest unresolved block). It never marks anything paid.

**One setup step still missing: attach the Google Drive connector to
`yusen-stedi-nightly`** (claude.ai → Routines → the Routine → enable Google Drive;
the trigger API cannot store connectors for this org). The job reads each invoice's
supporting worksheet from Drive to get the order numbers — with no Drive it can
reach Stedi but has nothing to look up, so the run does nothing. Same gap still
open on `yusen-cloud-validation-sweep-midday`.

Two defects in the job were corrected 2026-08-11 before its first real run:
its instructions carried the old "always halve the worksheet pick column" rule
(false on 756521 — would have doubled the pick overcharge), and a clean shipping
check alone could stamp a row `valid`, which drops it out of the daytime sweeps
permanently and could seal an invoice whose rates were never checked. The key
rotation note stands: the installed key was pasted in a chat transcript, and the
older `22R7W4M…` key is still live in the public repo and needs revoking.

**Re-check rule (Anthony, 2026-08-07):** an invoice whose shipping check comes
back clean is done — checked once, never looked at again. An invoice that comes
back with orders missing from the EDI feed is re-checked each night for **5
days**, then left alone, because shipment data can lag a day or two and those
gaps already trigger manual lookups on the ops side. A gap still open on day 5
is treated as a real finding and reported once, not raised nightly.

## Needs a Mac run — report-history bug (found 2026-08-11)

Marking an invoice paid was **erasing the row's validation history**. `--mark-paid`
replaced the whole `validation_report` field with its payment card instead of adding
to it, so 754891 and 755265 lost their itemized line math and their 106/106 and
289/289 Stedi order matches (1,741 and 1,644 characters down to 386). Both are
already paid and marked valid, so no future sweep would have rebuilt them. Caught
because the leftover note on 755265 claimed the Stedi check still needed doing —
directly under the block recording that it had been done.

A header-level sweep run from the Mac the same day (~10:30-10:58 AM MT, v1.4.0,
335 rows) then re-created the *display* half of the problem on 16 more rows: their
`[AUTO 2026-08-11]` block says "provide itemized counts" and "order-level Stedi
check available" directly beneath a `[DEEP PASS]`/`[MSA REVAL]` block recording that
the work was done. Nothing was lost on those 16 — verified: zero status changes,
zero deleted blocks — but every one is settled, so no future sweep will ever tidy
them. Affected: 755550, 755725, 755896, 756028, 756355, 756472 and 10 NL rows.

Three things to run on the Mac, in this order:

1. **Put the text back** — `sql/restore_clobbered_reports_2026-08-11.sql`, once.
   The wording was recovered from BigQuery's 7-day history before it expires
   (deadline **2026-08-18**). Safe to re-run; only touches a row still holding the
   short clobbered version.
2. **Install the fix** — copy `skill-updates/v1.5.0/validate_rate_card.py`,
   `skill.toml` and `SKILL.md` over `~/.claude/skills/yusen-invoice-validator/`,
   repackage, commit the `.skill`. Payment cards now merge in as their own
   `[PAID …]` block, and a header-level re-check no longer writes over a completed
   deeper review. Nothing about how invoices are judged changes. Details:
   `skill-updates/v1.5.0/CHANGELOG.md`; checks:
   `python3 skill-updates/v1.5.0/test_report_merge.py`.
   **Until this is installed, any Mac sweep re-creates the problem** — that is how
   the 16 rows above happened.
3. **Tidy the 16 stale blocks** —
   `python3 scripts/fix_stale_auto_blocks_2026-08-11.py` (dry run), then `--write`.
   Replaces only the misleading `[AUTO]` block with the v1.5.0 deferral wording and
   leaves every other block untouched. Run it after step 1 so 754891 and 755265
   have their history back and qualify too. Safe to re-run — it only matches rows
   still carrying the stale text.

Both cloud runbooks were updated the same day, so the scheduled sweeps already
follow the new rules without waiting on the repackage.

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
