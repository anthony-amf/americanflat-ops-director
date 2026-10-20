# Moving Yusen validation 100% to the cloud

*Anthony's direction, 2026-08-14: releases go out through Slack with a `@governors`
mention, not from the Mac, and the whole validation process runs in the cloud.*

This file is the inventory: what still needs the Mac, and what unblocks each piece.
Findings dated 2026-08-14 were tested from a cloud session, not assumed.

## The one hard gate: GitHub App repository selection

**Neither skill repo can be reached from any cloud session.** This is what pins
releases to the Mac, and nothing else on this list matters as much.

Tested 2026-08-14:

| Attempt | Result |
|---|---|
| `add_repo americanflat/skill-yusen-invoice-validator` mid-session | refused — "cross-tier adds are not supported in v1" |
| `create_session` sourced on `skill-yusen-invoice-validator` | `github_repo_access_denied` |
| `create_session` sourced on `skill-yusen-invoice-processor` | `github_repo_access_denied` |
| `list_repos` | returns only `anthony-amf/americanflat-ops-director` and `americanflat/Ops` |

`americanflat/Ops` comes back with `can_push: true`, so this is **not** an
org-wide block on `americanflat/*` — it is a per-repo selection, and these two
repos are not in it. (The older note in CLAUDE.md saying cloud sessions cannot
reach `americanflat/*` at all is too strong; `Ops` disproves it.)

**Unblock:** GitHub → Org settings → GitHub Apps → Claude → Repository access →
add `skill-yusen-invoice-validator` and `skill-yusen-invoice-processor`. A
Governor or GitHub org admin has to do it; it is not something a session can
grant itself.

**Also note the session shape.** Even once access lands, a cross-tier repo cannot
be *added* to a running session — it has to be the session's **initial source**.
So the release flow is: start a new cloud session on the skill repo, do the
release there, post to Slack from it. Not: do it from a session on this repo.

## What the release flow looks like once that gate opens

Per the Repo Merge Policy (2026-07-08) skill repos are not PR-gated, so there is
no PR to open — commit straight to `main`. All of this runs in the cloud:

1. Start a cloud session sourced on `americanflat/skill-yusen-invoice-validator`.
2. Apply the change, bump `skill.toml`, add the `CHANGELOG.md` entry, keep the
   SKILL.md and skill.toml descriptions in sync (the `skill-pr-helper` skill
   walks this).
3. Commit to `main`, push, tag `vX.Y.Z` matching `skill.toml`, push the tag.
4. Post the registry request in **#ai-github-skills** (`C0B3P9LCK99`) addressed to
   **`<@S06R4FLS3T2>`** — that is the `@governors` user group. Never edit
   `ai-skills-registry` directly; registry writes are Governors-only.

The Slack half already works from the cloud — the connector is live here and PR #2
was posted to that channel from a cloud session on 2026-08-13. Only the git half
is blocked.

House format for the request, from the channel's own history:

```
<@S06R4FLS3T2> — registry update needed for skill-yusen-invoice-validator

The change is already committed + tagged on main (vX.Y.Z). Can a Governor bring
the registry entry in line?
• version: A.B.C → X.Y.Z
• description changed? no

<link to the release tag>

Thanks! :pray:
```

## The rest of the inventory

### Validator source of truth — resolved by the gate above

Today `~/.claude/skills/yusen-invoice-validator/` on the Mac is canonical and cloud
sessions unzip the committed `yusen-invoice-validator.skill` instead. Once the org
repo is reachable, that repo is canonical for both, and the committed `.skill` stays
only as the offline copy the nightly run unzips — refreshable from a cloud session.

### Ledger writes — partly done

- **The nightly Routine can already write.** Iván Calderón granted the cloud service
  account write on `finance.yusen_invoices` on 2026-08-06, and it has been stamping
  rows since.
- **Interactive cloud sessions cannot.** Reads work; an `UPDATE` is stopped by the
  session's own permission classifier, not by BigQuery. Confirmed twice on
  2026-08-13 trying to correct 755499 — which is why that fix had to ship as
  `sql/fix_755499_detail_entry_2026-08-13.sql` for the Mac to run.
  Needs a Bash permission rule in `.claude/settings.json`; see the note at the
  bottom of this file. Until then, ad-hoc corrections still round-trip through the Mac.
- **What genuinely still needs the Mac's gcloud login:** `tables.create` (never
  granted to the service account) and therefore `--init` on a fresh table. Neither
  is part of routine operation.

### Ingestion — the real remaining work

`com.americanflat.yusen-invoice-processor` runs on the Mac via launchd (6:00 /
10:00 / 14:00 MT) and reads invoice PDFs off Gmail attachments.

**The blocker is not permissions — the Gmail connector in the cloud cannot return
attachment bytes.** It can find the message and read the body, but not hand over
the file, so a cloud session has nothing to parse.

Two ways out, and this needs Anthony's decision:

1. **Drive drop folder.** A Gmail filter saves incoming Yusen attachments to a
   Drive folder; a cloud Routine reads that folder with the Drive connector, which
   *does* return bytes. Uses tooling already proven — the nightly sweep pulls
   invoice PDFs this way (`download_file_content`, with the spill-file decode in
   `docs/CLOUD-SWEEP-RUNBOOK.md` step 3).
2. **Gmail API through a service account**, like BigQuery. More setup, more
   permission surface, no dependence on a mail filter staying in place.

Option 1 is the smaller change and reuses a path that already works in production.

### Two Mac launchd jobs have to be retired, in this order

Both were live as of 2026-08-12 (`launchctl list`).

- **`com.americanflat.yusen-validator-sweep`** — retire as soon as v1.6.0 is
  released. It sweeps all ~335 rows several times a day on **v1.4.0**, so it keeps
  rewriting `[AUTO]` blocks in the superseded format and would fight the nightly
  cloud run. Leaving both on is worse than either alone.
- **`com.americanflat.yusen-invoice-processor`** — retire when ingestion moves
  (above). Not before: it is the only thing loading invoices today.

### Dashboards — already cloud, with one trap

The artifact refresh runs from two cloud Routines (weekdays 8:30, 12:00, 15:30,
18:00 ET) and is gated on a row fingerprint. The local twin
`~/yusen_invoices_dashboard.html` and `refresh_yusen_dashboard.py` are Mac-only and
can be retired once nobody reads them.

The trap is unchanged and worth restating: the cloud refresher renders from a
**snapshot** of the published page, so any design change made elsewhere silently
falls behind and republishing downgrades the live page. See the Dashboards section
of CLAUDE.md for the re-sync procedure.

## Sequencing

1. **Governors add both skill repos to the GitHub App.** Everything else waits on
   this. (Slack draft prepared 2026-08-14.)
2. Release validator **v1.6.0** from a cloud session on the skill repo; post the
   registry request to `@governors`.
3. **Unload the Mac validator sweep** — the moment v1.6.0 is out, so the two runs
   never overlap.
4. Decide the ingestion port (Drive folder vs Gmail service account), build it as a
   Routine, verify it against a day the Mac job also ran, then unload the Mac job.
5. Retire the local dashboard twin.

Steps 1 and 4 need someone other than a cloud session. 2, 3 and 5 follow from them.

## Pending: the permission rule for interactive ledger writes

Not added yet — it grants future sessions unprompted write access to the finance
ledger, so it is Anthony's call rather than something to slip in. The rule belongs
in `.claude/settings.json` under `permissions.allow`, scoped to the BigQuery REST
endpoint and nothing else. Worth a single test write (the 755499 correction is a
good candidate) to confirm the rule actually bites before relying on it.
