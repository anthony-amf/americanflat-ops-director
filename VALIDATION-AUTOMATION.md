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

## Mac-side punch list (in order)

*Status 2026-08-05 (afternoon): ALL FIVE DONE. Backfill ran once (13 disputed
+ 3 notes verified); both dashboards refreshed/republished with disputed chips
and report tooltips; skill at v1.2.0 (repackaged + committed); sweep
LaunchAgent `com.americanflat.yusen-validator-sweep` loaded at 15:30 MT.
Two incidents found and fixed along the way: (a) `refresh_yusen_dashboard.py`
passed the DATA JSON as a regex replacement string, so `\n` escapes became raw
newlines and broke the embedded JS — now a lambda replacement; (b) a concurrent
invoice-processor session's "mark valid on payment" replay overwrote the fresh
disputed stamps on paid 754699/754704 — restored, and v1.2.0 makes both
disputed and paid-valid stamps sticky against re-sweeps.*

1. **Run the backfill:**
   `bq query --use_legacy_sql=false < sql/backfill_validation_2026-08-05.sql`
   (Run ONCE — the report append is not idempotent.) **DONE 2026-08-05.**
2. **Refresh the local dashboard:** `python3 refresh_yusen_dashboard.py`
   (picks up the disputed chips + notes automatically). **DONE.**
3. **Artifact dashboard:** add the same two `valChip` additions to
   `~/generate_yusen_dashboard.py` / `~/build_artifact_dashboard.py`
   (`.v-disputed` CSS + the `disputed` label branch — copy from
   `refresh_yusen_dashboard.py`), then let the 7:09 AM scheduled refresh
   republish, or run it manually. Remember: republish MUST pass the stable
   artifact `url:` or a duplicate gets minted. **DONE** — also: disputed chip
   checked *before* the hasVariance branch (disputed rows carry the disputed $
   in `validation_variance`, which otherwise shadows the chip), chip shows the
   amount, and `validation_report` now rides along as the hover tooltip.
4. **Skill v1.2.0 — the actual hook** (edit `~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py`): **DONE — shipped as v1.2.0.**
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
   - Ship via the usual flow: bump `skill.toml` to 1.2.0 + CHANGELOG, repackage
     `.skill`, commit here; publish after v1.1.0 finally lands in the org repo.
5. **Chain the sweep after ingestion** so validation happens as invoices come
   in: append to the launchd ingestion job (or a follow-on LaunchAgent ~30 min
   later, giving the streaming buffer time to clear):
   `cd ~/.claude/skills/yusen-invoice-validator && export STEDI_API_KEY=... && python3 scripts/validate_rate_card.py --list-all --limit 400 --write`
   Rows still in the streaming buffer auto-defer; the next day's sweep catches
   them (existing behavior). **DONE** —
   `~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist`,
   daily 15:30 Mountain (ingestion + 30 min), sources `~/.yusen/yusen.env`,
   logs to `~/Library/Logs/yusen-validator-sweep.log`.

## Status vocabulary (for finance)

| Chip | Meaning |
|---|---|
| ✓ valid | three-axis pass, no conflicts — OK to pay (SP/LTL additionally needs the Stedi gate before `--mark-paid`) |
| ⚠ disputed $X | validated, but contains MSA-conflict charges totaling $X — short-pay/hold; detail in the report tooltip |
| needs detail | header-only pass done; deep pass (worksheet/Stedi) not yet run |
| 🚨 discrepancy | math or rate mismatch — investigate before anything |
| $ paid | payment marked (explicit confirmation only) |
