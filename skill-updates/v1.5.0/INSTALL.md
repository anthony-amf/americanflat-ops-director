# Skill v1.5.0 (receiving check) — Mac install

*Every step is additive or an explicitly-approved quarantine move (NO-DELETE
compliant). Each block chains with `&&` so a failure stops the chain. Run the
blocks in order; paste the output back if anything errors.*

What changes: one new file (`scripts/receiving.py`) and four updated ones
(`scripts/validate_rate_card.py`, `SKILL.md`, `skill.toml`, `CHANGELOG.md`).
No new Python packages, no permission changes.

**Before you start — check the Mac copy is still v1.4.0.** These files were
built from the v1.4.0 copy in this repo. If the Mac copy has moved on, step 2
would overwrite those newer changes, so stop and ask instead.

```bash
grep -n '^version' ~/.claude/skills/yusen-invoice-validator/skill.toml
```

Expected: `version = "1.4.0"`.

## 1. Quarantine the four files being replaced (explicit approval step)

Moves the current copies into a dated folder. Nothing is deleted; moving them
back undoes it.

```bash
mkdir -p ~/quarantine/2026-10-19/yusen-skill-v1.4.0 && mv ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py ~/.claude/skills/yusen-invoice-validator/skill.toml ~/.claude/skills/yusen-invoice-validator/CHANGELOG.md ~/.claude/skills/yusen-invoice-validator/SKILL.md ~/quarantine/2026-10-19/yusen-skill-v1.4.0/
```

## 2. Download the v1.5.0 files

```bash
BASE=https://raw.githubusercontent.com/anthony-amf/americanflat-ops-director/claude/invoice-processor-edll4r/skill-updates/v1.5.0 && S=~/.claude/skills/yusen-invoice-validator && curl -fsSL -o $S/scripts/validate_rate_card.py $BASE/validate_rate_card.py && curl -fsSL -o $S/scripts/receiving.py $BASE/receiving.py && curl -fsSL -o $S/skill.toml $BASE/skill.toml && curl -fsSL -o $S/CHANGELOG.md $BASE/CHANGELOG.md && curl -fsSL -o $S/SKILL.md $BASE/SKILL.md && echo INSTALLED
```

(If the branch has been merged by then, swap `claude/invoice-processor-edll4r`
for `main` in the first line.)

## 3. Test it on the saved invoice texts (reads nothing from BigQuery)

Downloads the test and its saved invoice texts into a new folder, then runs
them against the receiving check you just installed.

```bash
T=~/yusen-receiving-test-$(date +%Y%m%d-%H%M%S) && mkdir "$T" && BASE=https://raw.githubusercontent.com/anthony-amf/americanflat-ops-director/claude/invoice-processor-edll4r/skill-updates/v1.5.0 && curl -fsSL -o "$T/test_receiving.py" $BASE/test_receiving.py && curl -fsSL -o "$T/receiving_fixtures.jsonl" $BASE/receiving_fixtures.jsonl && python3 "$T/test_receiving.py" ~/.claude/skills/yusen-invoice-validator/scripts "$T/receiving_fixtures.jsonl"
```

Expected: 24 lines ending `ok`, then `ALL PASSED`.

## 4. Re-check the twelve pre-June receiving invoices and save the results

These are the invoices that sat on `needs_detail` because the checker had no
pre-June rates. This writes their new status and report card to the ledger.
All twelve should come back `valid` (checked here against the same PDFs).

```bash
cd ~/.claude/skills/yusen-invoice-validator && for n in 749279 749384 750157 750322 750725 750792 751036 751336 751984 752032 752320 752504; do python3 scripts/validate_rate_card.py $n --write || break; done
```

Then repackage and commit per the skill workflow in CLAUDE.md, and push to the
org skill repo with the `skill-pr-helper` flow (tag `v1.5.0`).
