# Validate-on-ingest hook + Status/notes surfacing

*Design + punch list, 2026-08-05. Goal: every invoice gets validated as it
lands, carries a finance-visible Status (validated / disputed / needs detail),
and a detailed per-invoice spec readable from both dashboards.*

## What already exists (no new schema needed)

- `finance.yusen_invoices` already has `validation_status`, `validated_at`,
  `validated_by`, `validation_variance`, `validation_report`.
- Both dashboards (Artifact + local twin) already render a **Validated** chip
  per row, with `validation_report` as the hover tooltip / report card.
- Daily ingestion runs 3 PM MT via launchd; the validator sweep is
  `validate_rate_card.py --list-all --write` (run from the skill dir).

## What changed today (done in this repo)

1. **`refresh_yusen_dashboard.py`** now knows the `disputed` status: red chip
   labeled `⚠ disputed $X` (amount from `validation_variance`), detailed spec
   in the tooltip. Idempotent add-if-missing/upgrade-if-stale, per convention.
2. **`sql/backfill_validation_2026-08-05.sql`** stamps the 13 MSA-disputed
   invoices (`disputed` + disputed $ in `validation_variance` + full spec
   appended to `validation_report`) and annotates 3 clean ones.
   **Run it from the Mac** — the cloud BigQuery credential is read-only.

## Cloud rollout (2026-08-06, Anthony's direction: run in cloud, not the Mac)

The sweep runs as **scheduled cloud sessions** following
`docs/CLOUD-SWEEP-RUNBOOK.md` — three passes a day, times in **Eastern**
(Anthony, 2026-08-06):

| Routine | Cron (UTC) | Local (ET) | Trigger id |
|---|---|---|---|
| `yusen-cloud-validation-sweep` | `30 21 * * *` | 5:30 PM | `trig_016vL18kChzAxpv7tfZjqzyS` |
| `yusen-cloud-validation-sweep-midday` | `0 14,17 * * *` | 10:00 AM + 1:00 PM | `trig_01GQSfBrEkUVPJj6MqbkSn5D` |

The last pass is deliberately **5:30 PM ET = 3:30 PM Mountain, 30 minutes
after ingestion** — that is what makes same-day validation work. Keep that
relationship if either schedule moves. The 10 AM and 1 PM passes mop up rows
that were locked in BigQuery's streaming buffer the previous evening plus
anything uploaded by hand during the day.

Running several times a day is safe: settled rows (valid/disputed) are
skipped and never downgraded. On a quiet day a pass finds nothing and exits
in one line.

**DST note:** cron is fixed UTC, so these hold while ET is UTC-4. When DST
ends (2026-11-01) they shift an hour earlier in local terms (9 AM / noon /
4:30 PM ET) until the crons are moved forward an hour. Ingestion is on the
Mac's local clock and shifts with DST, so the 30-minute gap after ingestion
survives the change — but re-check it then.

**First-run finding (2026-08-06) — both Routines currently PAUSED.** The
first run swept only the Netherlands (`FTI…`) rows, which the runbook excludes,
and never reached the 61 US rows that needed checking. Verified via BigQuery
time travel: net data effect was 4 rows going from unstamped to `needs_detail`
(FTI0006502) — nothing downgraded, no report text lost, no payment flags
touched. Confirmed cause: the **default branch still carries validator
v1.1.0**, so a fresh cloud session unzips the old script (no status guards, no
line pass, and its `--list-all` sweep orders invoice numbers descending, which
puts `FTI…` first). The runbook now verifies the validator version and aborts
if it is not v1.2.0+, and forbids the `--list-all --write` path.

**Before re-enabling the Routines:** merge `main-07xt41` into the default
branch so fresh sessions get v1.2.0 by default (Anthony's call — cloud
sessions push to the feature branch by convention). Then re-enable both
Routines and watch one run.

**Write access:** granted 2026-08-06 by Iván Calderón (owner on the `finance`
dataset — Anthony can write data but not change permissions, so this needed
him). `cluade-service-account@americanflat.iam.gserviceaccount.com` now holds
`roles/bigquery.dataEditor` on TABLE `finance.yusen_invoices` — table-level,
so nothing else in `finance` is exposed; same pattern `invoice-writer@…` has
for the upload job. Note the account name really is spelled "cluade". Each
run still probes write access first and exits quietly if it ever disappears.

**Connectors:** each Routine needs the **Google Drive** connector attached
via the claude.ai Routines UI (the trigger API cannot store connectors for
this org). Without it a run still validates invoice totals but cannot open
the PDFs, so line-level checks degrade to header-level. Both Routines show
Drive attached as of 2026-08-06 — the midday one picked it up on update;
re-check in the UI if a run reports PDFs unavailable.

The Mac launchd sweep (below) is now an optional fallback, not the plan — the
two can coexist safely, but there is no need to install it. If it was
installed, unload it once the cloud runs are confirmed:
`launchctl unload ~/Library/LaunchAgents/com.americanflat.yusen-validation-sweep.plist`.
Ingestion itself (3 PM launchd) still runs on the Mac — moving it is a
separate project.

## Status 2026-08-06: items 4–5 BUILT — awaiting Mac install

Skill **v1.2.0** is written and staged in this repo (`skill-updates/v1.2.0/`,
packaged `.skill` updated), and the launchd sweep agent is at
`launchd/com.americanflat.yusen-validation-sweep.plist` (daily 3:30 PM, 30 min
after ingestion). Regression-tested against the 113 cached post-May invoice
PDFs — verdicts match the verified 2026-08-06 revalidation.
**Install steps (NO-DELETE compliant): `skill-updates/v1.2.0/INSTALL.md`.**

v1.2.0 delivers everything in item 4 below plus: truncated-rate matching
(page-1 rates print truncated to 2dp; amounts use full precision), a PDF
fetch chain (local cache → Drive API via ADC `drive.readonly` → public link),
OCR fallback for scanned SC VAS, settled-row skipping (valid/disputed rows are
never re-judged or re-downloaded), and an `[AUTO-SWEEP]` report section that
replaces itself so daily runs don't bloat report cards. SP/LTL is never
stamped valid by the sweep (Stedi gate); `paid_at` is never touched.

## Mac-side punch list (in order)

1. **Run the backfill:**
   `bq query --use_legacy_sql=false < sql/backfill_validation_2026-08-05.sql`
   (Run ONCE — the report append is not idempotent.)
2. **Refresh the local dashboard:** `python3 refresh_yusen_dashboard.py`
   (picks up the disputed chips + notes automatically).
3. **Artifact dashboard:** add the same two `valChip` additions to
   `~/generate_yusen_dashboard.py` / `~/build_artifact_dashboard.py`
   (`.v-disputed` CSS + the `disputed` label branch — copy from
   `refresh_yusen_dashboard.py`), then let the 7:09 AM scheduled refresh
   republish, or run it manually. Remember: republish MUST pass the stable
   artifact `url:` or a duplicate gets minted.
4. **Skill v1.2.0 — the actual hook** (edit `~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py`):
   - **VAS validation policy (Anthony, 2026-08-05):** comb the invoice PDF
     itself. If it contains supporting documentation — work order, email
     approval trail (e.g. John Nunez sign-off pages), count worksheets — and
     the line math verifies, stamp **`valid`** directly; do NOT leave VAS
     invoices parked at `needs_detail` just because they're VAS. Reserve
     **`needs_detail`** for exactly two cases: (a) no supporting documentation
     for the invoiced amount anywhere in the PDF, or (b) the validation
     errored (unreadable/scanned-without-OCR PDF, unparseable lines). SC VAS
     PDFs are scanned — OCR before concluding "no documentation".
   - **Write the detailed report at validation time**, not only on
     `--mark-paid`: the sweep already builds the per-invoice verdict; store it
     to `validation_report` (append-style with a dated tag) on every `--write`.
   - **Emit `disputed` status**: when a validated invoice contains any of the
     known MSA-conflict lines, stamp `disputed` instead of `valid` and put the
     disputed total in `validation_variance`. Detection rules:
     * NJ: `STRETCHWRAP` line at 4.34–4.35 alongside a $10.00 pallet line (AF-9)
     * NJ: `PACK CARTON` at 0.92 (AF-7 pack-out, removed 4/28)
     * Fontana/SC: pallet line at 14.317 → wrap component qty × 4.317 (AF-9)
     * Fontana: `PICK & PACK ECOM` present → flag for additional-only
       recompute against the supporting worksheet (single-unit orders with a
       pick charge = automatic dispute; MSA line is "Per Additional Ecom Pick")
   - **Never overwrite a `disputed` stamp back to `needs_detail`** on re-sweep;
     `disputed` clears only when the invoice is re-billed/credited or manually
     cleared.
   - **Rate matching must handle truncated printing** (learned in the 8/6
     post-May revalidation): Yusen page-1 lines print rates TRUNCATED to 2dp
     (1.7871 → "1.78", 4.347 → "4.34", 0.7312 → "0.73") while line amounts use
     the full-precision rate. Match a printed rate to the set of candidate
     full-precision MSA rates whose 2dp truncation equals it, then pick the
     candidate where qty × full ≈ amount — this also disambiguates collisions
     (NJ storage 4.34 vs stretchwrap 4.347). Also on the schedule: Fontana
     "STORAGE PER BIN" 0.7312. SP/LTL header passes alone never stamp `valid`
     — Stedi gate still applies.
   - Ship via the usual flow: bump `skill.toml` to 1.2.0 + CHANGELOG, repackage
     `.skill`, commit here; publish after v1.1.0 finally lands in the org repo.
5. **Chain the sweep after ingestion** so validation happens as invoices come
   in: append to the launchd ingestion job (or a follow-on LaunchAgent ~30 min
   later, giving the streaming buffer time to clear):
   `cd ~/.claude/skills/yusen-invoice-validator && export STEDI_API_KEY=... && python3 scripts/validate_rate_card.py --list-all --limit 400 --write`
   Rows still in the streaming buffer auto-defer; the next day's sweep catches
   them (existing behavior).

## Status vocabulary (for finance)

| Chip | Meaning |
|---|---|
| ✓ valid | three-axis pass, no conflicts — OK to pay (SP/LTL additionally needs the Stedi gate before `--mark-paid`) |
| ⚠ disputed $X | validated, but contains MSA-conflict charges totaling $X — short-pay/hold; detail in the report tooltip |
| needs detail | header-only pass done; deep pass (worksheet/Stedi) not yet run |
| 🚨 discrepancy | math or rate mismatch — investigate before anything |
| $ paid | payment marked (explicit confirmation only) |
