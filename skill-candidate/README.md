# Review candidate — not a release

`yusen-invoice-validator/` is a **complete v1.6.0 skill folder**, built in the cloud so
`skill-fixer` has something real to point at. Steps 1–2 of that skill are local-only, so
they run fine here; Step 3 does not (see below).

Point the skill at the folder, not at this file:

```
skill-candidate/yusen-invoice-validator/
```

## How it was built, and how to rebuild it

Every file came from the committed package plus this repo's release artifacts — nothing
was hand-copied:

1. `unzip yusen-invoice-validator.skill` → the v1.5.0 skill, 15 files.
2. `skill-updates/v1.6.0/install_v1_6_0.py` over `scripts/validate_rate_card.py`.
3. `skill-updates/v1.6.0/merge_rates_into_1_5_1.py` over
   `references/rate-card-snapshot.json`.
4. `skill.toml` version 1.5.0 → 1.6.0, and the 1.6.0 `CHANGELOG.md` entry.
5. One `SKILL.md` correction: the line saying VAS is always reported `needs_detail` is
   no longer true, so it now describes the two shapes v1.6.0 resolves.

Verified after building:

- `scripts/validate_rate_card.py` is **byte-identical** to
  `skill-updates/v1.6.0/validate_rate_card.py`.
- `references/rate-card-snapshot.json` is **identical** to
  `skill-updates/v1.6.0/rate-card-snapshot.json`.
- Both suites pass against this folder — 24 checks and 31 checks.
- Six known invoices land on the verdict the ledger already holds: 750206 valid
  (pre-AF-9), 754388 disputed $207.22, 755701 valid, 756182 valid, 756396 valid,
  756523 valid.

## What this candidate is built on — read before releasing

It is v1.5.0 **plus** the v1.6.0 changes, because v1.5.0 is what the committed
`.skill` package contains and what the installer was verified against.

**The Mac's canonical copy is 1.5.1** — a separately-developed fix for the same
`mark_paid` report-clobbering bug that v1.5.0 fixes its own way. So this folder is not
"1.5.1 plus v1.6.0", and whatever 1.5.1 changed beyond that bug is not in here.

Before this ships, someone with the 1.5.1 file has to confirm the two lines agree — or
run `install_v1_6_0.py` against the real 1.5.1 and use that result instead. The
installer is content-anchored precisely so it works on either base.

## Step 3 cannot run in a cloud session

`skill-fixer` submits by cloning `git@github-americanflat:americanflat/skill-candidates.git`
over SSH after checking `gh auth status`. This container has **no `ssh`, no `gh`, and no
`rsync`** — the programs are not installed — and `americanflat/skill-candidates` is not in
the Claude GitHub App's repository selection, so a cloud session cannot be sourced on it
either. See `docs/CLOUD-MIGRATION.md`.

So: Steps 1–2 here, Step 3 from the Mac, until either skill-fixer gains a cloud path
(GitHub tools instead of SSH) or the repo is enabled and the push runs over HTTPS.
