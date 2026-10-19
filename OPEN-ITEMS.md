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

## Receiving check — skill v1.5.0 staged (2026-10-19)

`skill-updates/v1.5.0/` adds a receiving check that knows each warehouse's
rates and the pre-June rates. All twelve pre-June receiving invoices
(749279 → 752504, $55,856.81) verify to the cent against their PDFs, so they
can leave `needs_detail` once v1.5.0 is installed on the Mac and they are
re-run with `--write` (steps in `skill-updates/v1.5.0/INSTALL.md`). Open:
- Install v1.5.0 on the Mac, run step 4, then publish to the org skill repo.
- ~~Notion rate card: Fontana pre-June sortation $34.0198 → $34.0197~~ **DONE
  2026-10-19** (cell and footnote ᵒ corrected).

## Drayage check — O'Neill (started 2026-10-19)

`drayage/check_drayage.py` checks O'Neill invoices against the 4/3/2026 rate
sheet (see `drayage/README.md`). Open:
- Fuel: lane sheets say fuel included to $4.50/gal, the FSC matrix tab starts
  at $4.00 — confirm with O'Neill which governs.
- Need real O'Neill invoice PDFs (N0185062, N0185063, N0190164 are in email;
  the rest via bill.com) and a weekly statement xlsx to tune the text reader.
- Storage for results: `finance.freight_invoices` once Iván grants write.

## Customs entry check — WWL / CBP 7501 (started 2026-10-19)

`customs/check_customs.py` checks a 7501 entry (line math, MPF/HMF, totals,
bill.com amount) and compares rates to the duty sheet (see `customs/README.md`).
Open: real WWL 7501s to build the reader; FY2027 MPF limits; whether
reciprocal tariffs are being collected; fix the sheet's self-flagged rows;
WWL brokerage rates; coordinate with Mahjoub's own validation tool.

## Factory invoice check — vs WIP purchase orders (started 2026-10-19)

`factory/check_factory.py` checks a factory invoice against the WIP tab: PO and
SKU exist under that factory, unit price = that PO's FOB, quantity within
ordered/shipped (incl. earlier invoices), line math and total (see
`factory/README.md`). Open: a real factory invoice + payment terms; who pays
factories and where paid history lives; live WIP instead of a CSV export.

## Containers — ocean freight check + container register (started 2026-10-19)

`containers/check_ocean_freight.py` checks WWL FCL invoices against the rate
sheet in effect at origin gate-in (WWL's rule, confirmed 2026-10-14).
`containers/register.py` builds a container register from WWL arrival-notice
emails (77 containers, 5/20–10/12) — the key linking freight, customs,
drayage and receiving bills. Open: rate sheets as data (PDF attachments),
real WWL invoices + gate-in dates, Century local charges, scheduled register
writes to BigQuery.

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
