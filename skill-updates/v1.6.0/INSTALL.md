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

## Step 2 — dry-run the code changes

```bash
python3 <PATH>/skill-updates/v1.6.0/install_v1_6_0.py ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py
```

It prints one line per change and stops without writing. Six changes, all inserts:

```
  ADD              apply_vas_pallet_check + apply_vas_labor_check (261 lines) before apply_msa_conflicts
  ADD              carry the rate card on validate()'s result
  ADD              _line_pass_keeping_disputes skips pallet rows
  ADD              apply_msa_conflicts stands aside for pallet rows
  ADD              both checks wired in after validate()   x2
```

Then apply it:

```bash
python3 <PATH>/skill-updates/v1.6.0/install_v1_6_0.py ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py --write
```

It writes its own timestamped backup first, and it compiles the result before saving —
if the outcome would not run, nothing is written.

If it prints **REFUSING**, 1.5.1 changed something at one of the six spots. Nothing was
touched; send me the message.

**Why not the `.patch` file.** `v1.6.0-onto-1.5.x.patch` is still in this directory and
still correct against a pristine 1.5.0, but `patch` matches on line numbers, and 1.5.1's
line numbers drifted — hunk 6 of 6 failed on the Mac for that reason and no other. The
installer finds each spot by the code around it, so drift cannot break it. Re-running it
is safe: anything already in place is reported as "already present" and left alone.

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

The installer was run against a pristine 1.5.0 and its output diffed byte-for-byte
against this repo's v1.6.0 file — identical. Then against two rewritten copies: one with
55 lines injected at three points (line-number drift), and one with
`_line_pass_keeping_disputes` rewritten to hold its state in a dict, given a keyword-only
argument, a signature split over six lines and a one-line docstring, plus
`apply_msa_conflicts` split across multiple lines too. All six changes landed on both,
both compiled, and the 24-check suite passed against both. Re-running on any installed
file reports "already present" six times and writes nothing. Deliberately broken files
(a renamed function, an unexpected call after `validate()`) produce REFUSING with the
file untouched.

The merge script was run against a pristine
pre-v1.6.0 snapshot and the pair reproduced every v1.6.0 verdict exactly: 755701 valid,
756523 valid (1.5× overtime), 756396 valid ($10 pallet), 754388 disputed ($14.317 wrap),
750206 valid (pre-AF-9 April invoice).
