# Skill v1.2.0 + validation sweep — Mac install

*Every step is additive or an explicitly-approved quarantine move (NO-DELETE
compliant). Each block chains with `&&` so a failure stops the chain. Run the
blocks in order; paste the output back if anything errors.*

## 1. Quarantine the files being replaced (explicit approval step)

Moves the four v1.1.0 files into a dated quarantine folder — nothing is
deleted, and this can be reversed by moving them back.

```bash
mkdir -p ~/quarantine-2026-08-06/yusen-skill-v1.1.0 && mv ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py ~/.claude/skills/yusen-invoice-validator/skill.toml ~/.claude/skills/yusen-invoice-validator/CHANGELOG.md ~/.claude/skills/yusen-invoice-validator/SKILL.md ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json ~/.claude/skills/yusen-invoice-validator/requirements.txt ~/quarantine-2026-08-06/yusen-skill-v1.1.0/
```

## 2. Install the v1.2.0 files

```bash
BASE=https://raw.githubusercontent.com/anthony-amf/americanflat-ops-director/main-07xt41/skill-updates/v1.2.0 && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py $BASE/validate_rate_card.py && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/skill.toml $BASE/skill.toml && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/CHANGELOG.md $BASE/CHANGELOG.md && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/SKILL.md $BASE/SKILL.md && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json $BASE/rate-card-snapshot.json && curl -fsSL -o ~/.claude/skills/yusen-invoice-validator/requirements.txt $BASE/requirements.txt && echo INSTALLED
```

## 3. New Python dependencies

```bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pip install pypdf cryptography
```

## 4. Give ADC the Drive scope (enables the PDF deep pass)

Re-authenticates gcloud Application Default Credentials with Drive read-only
added, so the sweep can download invoice PDFs from Drive. BigQuery keeps
working (cloud-platform scope is retained). Opens a browser window.

```bash
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.readonly
```

If you skip this step the sweep still runs — it just degrades to header-level
results for invoices whose PDF isn't already in `~/.yusen-pdf-cache`.

*(Optional, for the scanned SC VAS PDFs: `brew install tesseract poppler` —
without it those invoices report needs_detail with "OCR unavailable".)*

## 5. Smoke test — one settled invoice, one unstamped

```bash
cd ~/.claude/skills/yusen-invoice-validator && python3 scripts/validate_rate_card.py 754889 && python3 scripts/validate_rate_card.py --list-all --limit 15
```

Expected: 754889 prints "settled: already stamped valid" (it will NOT be
re-judged), and the sweep shows the new ⚠ disputed count in the summary.
Nothing is written without `--write`.

## 6. Install the daily sweep (3:30 PM, 30 min after ingestion)

```bash
curl -fsSL -o ~/Library/LaunchAgents/com.americanflat.yusen-validation-sweep.plist https://raw.githubusercontent.com/anthony-amf/americanflat-ops-director/main-07xt41/launchd/com.americanflat.yusen-validation-sweep.plist && launchctl load ~/Library/LaunchAgents/com.americanflat.yusen-validation-sweep.plist && launchctl list | grep yusen-validation && echo LOADED
```

To run the sweep immediately instead of waiting for 3:30 PM:

```bash
launchctl start com.americanflat.yusen-validation-sweep && sleep 5 && tail -20 ~/Library/Logs/yusen-validation-sweep.log
```

## What the sweep will and won't do

- Stamps `valid` / `needs_detail` / `discrepancy` / `disputed` (+ disputed $
  in `validation_variance`) and refreshes the `[AUTO-SWEEP]` report section
  on every run.
- Never downgrades `disputed`; never downgrades a `valid` to `needs_detail`;
  rows already valid/disputed are skipped outright.
- Never stamps SP/LTL `valid` (Stedi payment gate) and never touches
  `paid_at` (payment stays human-confirmed only).
- Rows still in the streaming buffer defer to the next day's run.
