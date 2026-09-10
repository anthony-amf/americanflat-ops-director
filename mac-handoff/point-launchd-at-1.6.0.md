# Point the Mac sweep at validator v1.6.0

The LaunchAgent `com.americanflat.yusen-validator-sweep` runs:

```
cd ~/.claude/skills/yusen-invoice-validator && python3 scripts/validate_rate_card.py --list-all --limit 400 --write
```

It `cd`s into a directory, so **the version it runs is whatever is in that
directory** — nothing in the job names a version. Pointing it at v1.6.0 therefore
means giving it a different directory to enter, which is a one-key edit and is
undone by putting the old value back.

Deliberately NOT done by upgrading the existing directory in place: a fresh
versioned directory beside it leaves the current one untouched, so rollback is
changing one string rather than restoring files.

Everything below is copy-paste, in order. Each block stops on the first failure.

---

## Step 0 — confirm what is actually there

Nothing here changes anything. Read the output before continuing.

```bash
launchctl list | grep -i yusen ; \
  /usr/libexec/PlistBuddy -c "Print :ProgramArguments" \
    ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist ; \
  grep '^version' ~/.claude/skills/yusen-invoice-validator/skill.toml
```

Expected: the job listed with last exit 0, the command above, and a version line.
**Note what that version says** — the working assumption is 1.4.0, and the notes it
has been writing (legacy $5.90/$5.98/$5.09 storage rates) fit a pre-MSA card. If it
says 1.6.0 already, stop: something else is writing those notes and this is the
wrong fix.

## Step 1 — put v1.6.0 in a new directory of its own

The package is the one verified against all 383 ledger rows and committed on
`main-07xt41`. Two ways in; use whichever fits.

From your clone of the repo:

```bash
mkdir -p ~/.claude/skills/v1.6.0 && \
  cd ~/path/to/americanflat-ops-director && \
  git fetch origin main-07xt41 && \
  git show origin/main-07xt41:yusen-invoice-validator.skill > ~/Downloads/yusen-invoice-validator-1.6.0.skill && \
  unzip -q ~/Downloads/yusen-invoice-validator-1.6.0.skill -d ~/.claude/skills/v1.6.0 && \
  grep '^version' ~/.claude/skills/v1.6.0/yusen-invoice-validator/skill.toml
```

Or straight from GitHub (the repo is public, so no auth needed):

```bash
mkdir -p ~/.claude/skills/v1.6.0 && \
  curl -fsSL -o ~/Downloads/yusen-invoice-validator-1.6.0.skill \
    https://raw.githubusercontent.com/anthony-amf/americanflat-ops-director/main-07xt41/yusen-invoice-validator.skill && \
  unzip -q ~/Downloads/yusen-invoice-validator-1.6.0.skill -d ~/.claude/skills/v1.6.0 && \
  grep '^version' ~/.claude/skills/v1.6.0/yusen-invoice-validator/skill.toml
```

Must print `version = "1.6.0"`. Both blocks only create new paths.

## Step 2 — check it works there before the job depends on it

Writes nothing (no `--write`). Uses the same known invoices the change was tested
against.

```bash
cd ~/.claude/skills/v1.6.0/yusen-invoice-validator && \
  source ~/.yusen/yusen.env && \
  python3 scripts/validate_rate_card.py 755701 && \
  python3 scripts/validate_rate_card.py 752857 && \
  python3 scripts/validate_rate_card.py 752738
```

What to look for:

* **755701** — `valid`, "24.49 hrs x $63.0000 … at the south_carolina physical
  inventory rate". This is the new hourly check; on 1.4.0/1.5.0 it reads
  `needs_detail`. If it still says `needs_detail`, the job is reading the old
  directory and Step 1 did not take.
* **752857** — `valid`, unchanged.
* **752738** — `needs_detail` with the partial-week Admin note, unchanged.

## Step 3 — repoint the job

Its own step, because it is the only one that changes something already in place.
The plist is copied to a dated folder first, and git holds nothing here — this
file lives only on your Mac, so the copy is the rollback.

```bash
mkdir -p ~/quarantine/$(date +%F) && \
  cp ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist \
     ~/quarantine/$(date +%F)/ && \
  /usr/libexec/PlistBuddy -c "Set :ProgramArguments:2 'cd ~/.claude/skills/v1.6.0/yusen-invoice-validator && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 scripts/validate_rate_card.py --list-all --limit 2000 --write'" \
     ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  /usr/libexec/PlistBuddy -c "Print :ProgramArguments" \
     ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist
```

Two changes on that line, and the second is not cosmetic:

1. the directory, which is the point of this exercise;
2. **`--limit 400` becomes `--limit 2000`.** `--list-all` selects
   `ORDER BY invoice_number DESC LIMIT <n>`, and that sort is alphabetical, so the
   `CA…` and `FTI…` international rows sort ahead of every numeric invoice. The
   ledger holds 383 rows, so 400 still reaches all of them — but it is 17 rows from
   silently dropping the oldest invoices off the end of the sweep, and the symptom
   would be rows quietly going stale rather than an error.

**Check the index before running it.** `:ProgramArguments:2` assumes Step 0 printed
three entries — `/bin/bash`, `-lc`, then the command string — which is the shape of
the plist in this repo. The live one is a different file (`yusen-validator-sweep`,
not the never-installed `yusen-validation-sweep` under `launchd/`) and could be laid
out differently. Whatever position Step 0 shows the `cd …` string at, use that
number; `Set`ting the wrong index would overwrite `/bin/bash` or `-lc` and the job
would stop running.

Likewise, if Step 0 showed a python path other than
`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`, use the one it
printed.

## Step 4 — reload and run it once by hand

```bash
launchctl unload ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl load ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl list | grep -i yusen-validator-sweep && \
  launchctl start com.americanflat.yusen-validator-sweep && \
  sleep 60 ; tail -40 ~/Library/Logs/yusen-validator-sweep.log
```

## Step 5 — prove it took, from the ledger

The log says the job ran; only the table says it wrote v1.6.0's verdicts. Run
`verify_1_6_0_landed.sh` in this folder, or the query inside it. It checks three
things:

1. **storage notes now quote the MSA rate.** Before: 66 rows quoting
   $5.90/$5.98/$5.09 and none quoting $4.47/$4.34/$3.35. After: the reverse. This
   is the single clearest signal, because only the old card can produce the old
   numbers.
2. **756522 moved to `valid`** — 4 hrs at 1.5x overtime on the Fontana general
   labour rate, $358.97. It is the one row in the queue that v1.6.0 resolves and
   nobody has already fixed by hand.
3. **nothing was lost** — the count of `valid` and `disputed` rows must not fall,
   and no `disputed` variance may change.

## Rollback

```bash
/usr/libexec/PlistBuddy -c "Print :ProgramArguments:2" ~/quarantine/$(date +%F)/com.americanflat.yusen-validator-sweep.plist
```

Take the string it prints and `Set` it back with the Step 3 command shape, then
reload as in Step 4. The old skill directory was never touched, so it is still
there and still works.

---

## What this fixes, and what it does not

**Fixes:** the wrong rates in every note the Mac writes, and the 19 VAS rows
(pallet work orders and hourly projects) that v1.6.0 can resolve. Those 19 matter
here specifically because their basis is in the invoice's own `notes` — quantity,
rate and total — so a header-only sweep like this one can reach a verdict on them
with no PDF and no OCR.

**Does not fix the other 82 `needs_detail` rows.** They need a count that exists
only in the PDF or the supporting worksheet, and this job never opens either. The
cloud sweep runbook is blunt about it: *"Without PDFs every row stays needs_detail
for ever — the header pass alone cannot resolve a single invoice."* Pointing this
job at v1.6.0 makes it correct; it does not make it sufficient.

**One thing to decide separately.** After this, the Mac and the cloud Routine run
byte-identical code, which removes the disagreement — but they are still two jobs
writing the same rows, and the Mac one runs several times a day and writes last.
The cloud one is the one that fetches PDFs and can actually clear invoices. Worth
deciding which owns the ledger rather than leaving both running.
