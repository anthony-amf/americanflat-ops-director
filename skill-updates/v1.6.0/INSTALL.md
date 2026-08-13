# Installing v1.6.0 on top of your local 1.5.1

1.5.1 was developed separately (the mark-paid merge fix) and this repo's line went
1.4.0 → 1.5.0 → 1.6.0. Rather than copy a whole file over yours and silently discard
1.5.1's work, v1.6.0 ships as **a patch plus a rate-card merge**. Both are additive.

**v1.6.0 does not touch `mark_paid` at all** — verified, zero lines. Whatever 1.5.1
does there survives untouched.

## What you are applying

Seven insertions into `validate_rate_card.py`, no deletions and no modified lines:

| Where | What |
|---|---|
| `_line_pass_keeping_disputes` | skip rows already judged by the pallet rule |
| `validate()` | carry the rate card on the result so later checks can read it |
| new block | `apply_vas_pallet_check` — Savannah VAS pallet work orders |
| new block | `apply_vas_labor_check` — hourly VAS work vs the MSA hourly table |
| `apply_msa_conflicts` | stand aside when the pallet rule has already judged |
| two call sites | wire both new checks in, after `validate()` |

Plus rate-card additions: the full hourly role × site table, the agreed 1.5×
overtime multiplier, the AF-9 effective date, and the whole `receiving` section
including pre-June rates.

## Step 1 — back up (this step overwrites files)

```bash
mkdir -p ~/skill-backups/2026-08-13-yusen-v151 && cp ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json ~/.claude/skills/yusen-invoice-validator/skill.toml ~/skill-backups/2026-08-13-yusen-v151/ && ls -la ~/skill-backups/2026-08-13-yusen-v151/
```

Three files listed before you continue.

## Step 2 — dry-run the code patch

From a clone of this repo (or wherever you have `skill-updates/v1.6.0/`):

```bash
cd ~/.claude/skills/yusen-invoice-validator/scripts && patch -p0 --dry-run validate_rate_card.py < <PATH>/skill-updates/v1.6.0/v1.6.0-onto-1.5.x.patch
```

- **Clean** → apply it: same command without `--dry-run`.
- **"Hunk #N FAILED"** → 1.5.1 changed something near an insertion point. Stop and
  send me the failed hunk; do not force it. The `.rej` file names the conflict.

## Step 3 — merge the rate card (never a straight copy)

```bash
python3 <PATH>/skill-updates/v1.6.0/merge_rates_into_1_5_1.py ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json
```

It lists what it would add and, separately, **anything it would overwrite**. Expect
exactly one overwrite:

```
admin_vas.south_carolina.vas_hourly: 51.0 -> 53.55
```

That one is intended — $51.00 is the superseded card value, and the Notion card's own
footnote says so. Any *other* overwrite means 1.5.1 changed a rate and you should tell
me before proceeding. When it looks right:

```bash
python3 <PATH>/skill-updates/v1.6.0/merge_rates_into_1_5_1.py ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json --write
```

It writes its own timestamped backup as well.

## Step 4 — bump the version and verify

```bash
cd ~/.claude/skills/yusen-invoice-validator && sed -i '' 's/^version = "1\.5\.1"/version = "1.6.0"/' skill.toml && grep '^version' skill.toml
```

Then the checks:

```bash
python3 <PATH>/skill-updates/v1.6.0/test_vas_pallet_check.py
python3 <PATH>/skill-updates/v1.5.0/test_report_merge.py
```

24 checks and 31 checks respectively, all passing. The second one matters here: it
exercises the report-merge behaviour, so if 1.5.1's `mark_paid` diverges from what the
rest of the code expects, that suite is where it shows up.

Finally, confirm on a real invoice that nothing regressed:

```bash
python3 scripts/validate_rate_card.py 755701     # expect valid — 24.49 hrs x $63.00 SC stock consolidation
python3 scripts/validate_rate_card.py 754388     # expect disputed $207.22 — AF-9 wrap component
```

## Step 5 — repackage and commit

Package as usual, copy the `.skill` into this repo, commit. That is what cloud
sessions unzip, so the nightly run picks up v1.6.0 from it.

## Verified before shipping

The patch was applied to a pristine 1.5.0, compiled, and diffed byte-for-byte against
this repo's v1.6.0 file — identical. The merge script was then run against a pristine
pre-v1.6.0 snapshot and the pair reproduced every v1.6.0 verdict exactly: 755701 valid,
756523 valid (1.5× overtime), 756396 valid ($10 pallet), 754388 disputed ($14.317 wrap),
750206 valid (pre-AF-9 April invoice).
