---
name: skill-pr-helper
description: Walks any Claude through shipping a compliant change to an already-published Americanflat `skill-{name}` repo — committing directly to `main` (skill repos are no longer PR-gated, per the Repo Merge Policy of 2026-07-08), then notifying `@governors` to update the `ai-skills-registry` (Governors-only write access — you never open a registry PR yourself). Enforces the house rules: one logical change at a time, a semver bump in `skill.toml`, a matching prose `CHANGELOG.md` entry, keeping the SKILL.md and skill.toml descriptions in sync, and a `vX.Y.Z` tag after pushing. Use whenever the user wants to change, update, patch, fix, or bump a skill already live on GitHub — phrases like "update this skill", "bump the skill version", "change this skill's description", "update the skill registry", or "ship a fix to skill-foo". Do NOT use it to create a brand-new skill before v1.0.0 (that is the Builder create + publish flow); stop and escalate to a Governor on any leaked secret.
---

# Pull Request Helper (Americanflat)

You are helping someone change a skill that is **already published** to GitHub — a repo named `americanflat/skill-{name}` that already has a `v1.0.0`+ history on `main`.

**As of the Repo Merge Policy (2026-07-08), skill repos are no longer PR-gated.** The owner and any write+ collaborator commit **directly to `main`** — like editing a Notion page. So this skill makes the change on `main`, tags it, and then makes sure the companion entry in `ai-skills-registry` gets brought in line — by **notifying a Governor**, not by editing the registry yourself.

**Two different gates, don't confuse them:**
- The **skill repo** (`skill-{name}`) — *not* gated. You commit to `main` directly. Only force-push and branch deletion are blocked.
- The **registry** (`ai-skills-registry`) — *still* gated, and **Governors-only**. You have no write access: don't clone it, don't push a branch, don't open a PR against it. When your change touches the registry, you **notify `@governors`** and a Governor makes the edit.

Your job is to take the change all the way to a **clean commit on `main` with a matching version, changelog, and tag** — and then to **flag the Governors** if the registry needs updating, because that registry is the source of truth for each skill's version and description and it goes stale the moment a skill changes without it.

Read this whole file first. If the skill is brand-new and has never been published (no `v1.0.0` on `main`), this is the wrong flow — point the user at the Builder create → publish flow instead.

---

## The house rules (the bar every change meets)

1. **One change at a time.** Keep each commit to a single logical change; "while I was in there" cleanups get their own commit.
2. **Commit directly to `main`.** That is now the supported path. Don't create a branch or open a PR against the skill repo. (Force-push and branch deletion are blocked by the ruleset — don't try to work around them.)
3. **Bump the version** in `skill.toml` per semver, for every change that alters behavior.
4. **Record it in `CHANGELOG.md`** — a prose entry whose version matches `skill.toml`.
5. **Keep the description honest** — if behavior or triggers changed, update it in both `SKILL.md` frontmatter and `skill.toml`, identically.
6. **Tag after pushing** — `vX.Y.Z`, matching `skill.toml`.
7. **Ask a Governor to update the registry** — you don't have write access; notify `@governors` with what changed and a Governor updates it. The step everyone forgets.

---

## Phase A — make and ship the change (directly on `main`)

### Step 1 · Get onto a current `main`

```bash
git checkout main && git pull
```

No branch. You will commit here.

### Step 2 · Make the change

Keep it to a single logical change.

### Step 3 · Bump the version (semver)

Edit `version` in `skill.toml`. Pick the level by impact — when unsure, round up:

| Bump | When | Example |
|---|---|---|
| **PATCH** `x.y.Z` | Bug fix, wording, no new behavior | `1.2.0 → 1.2.1` |
| **MINOR** `x.Y.0` | New behavior, backward-compatible | `1.2.1 → 1.3.0` |
| **MAJOR** `X.0.0` | Breaking change to inputs/outputs/triggers | `1.3.0 → 2.0.0` |

A pure docs / tidy-up change with no behavior impact doesn't need a bump.

### Step 4 · Record it in `CHANGELOG.md`

Add a new entry at the top (newest first), matching the version you just set. House style is **prose, not bare bullets**: a one-line summary, then bullets that lead with the change in **bold**, plus a **Why now** bullet for the reasoning. Open the repo's existing `CHANGELOG.md` and match its voice — they read like short release notes, not a terse list.

```markdown
## [1.3.0] — YYYY-MM-DD

One-sentence summary of what this release changes.

- **The headline change, in bold.** A sentence or two on what changed and what it does now.
- **Why now.** The request or problem that prompted it.
```

The `CHANGELOG` version and the `skill.toml` version must match. If they disagree, the change is wrong — fix it before committing.

### Step 5 · Keep the description honest

The `description` is how Claude decides **when to trigger** the skill, so a stale one is a real bug, not cosmetics. If your change alters what the skill does or when it should fire, update the description in **both** places so they stay identical:

- the `description` in **SKILL.md** YAML frontmatter, and
- the `description` in **`skill.toml`**.

Keep it one sentence and end with concrete trigger phrases. If the description didn't change, leave it alone.

> **Watch the 350-char limit on the `skill.toml` description.** That field is reused verbatim as the GitHub repo description, and GitHub rejects anything over 350 characters or containing newlines/tabs. The SKILL.md frontmatter description can run longer (it's for trigger matching) — don't blindly copy it into `skill.toml`.

### Step 6 · Commit and push to `main`, then tag

```bash
git add -A
git commit -m "fix: handle empty ASIN column"
git push origin main
git tag v1.3.0
git push origin v1.3.0
```

Use a conventional-commit message (`fix:`, `feat:`, `docs:`, `chore:`). The tag must match `skill.toml` — tags are how installs pin to a known-good version.

> If `git push origin main` is rejected, the repo may still carry the old PR-gated ruleset. That shouldn't happen after 2026-07-08, but if it does, tell the user to ask a Governor to apply the current `main-protection` ruleset (see `Repo_Merge_Policy.md`) — don't try to force it.

---

## Phase B — get the registry updated (notify a Governor)

Do this whenever **version**, **description**, **tier**, or **compatibility** changed. (A pure docs change that touched none of those needs no registry update.)

**You do not edit the registry yourself.** `ai-skills-registry` is **Governors-only** — you have no write access, you can't push a branch, and you must not try to clone it or open a PR against it. Your job is to **notify `@governors`** with exactly what changed; a Governor makes the edit. Direct commits do **not** auto-update the registry and nothing watches for drift, so this notification is the only thing that keeps the registry honest.

### Step 7 · Post the registry-update request

Post in **#ai-github-skills** (channel ID `C0B3P9LCK99`), tagging the **@governors** group, with the skill name, the new version, and — if it changed — the new one-line description. Use the template below, then you're done. A Governor takes it from there.

---

## Slack template

Tag the **@governors** group so the request isn't waiting silently. The template shows `@governors` for readability. When you send the message through the Slack tool/API, swap `@governors` for the group-mention token so it fires a real ping — wrap `!subteam^S06R4FLS3T2` in angle brackets (Slack's subteam syntax). A human typing into Slack by hand just types `@governors` and picks the group from autocomplete. Fill the `{...}` placeholders before sending.

**Registry update request — a Governor makes the edit**

```
@governors — registry update needed for `skill-{name}`
The change is already committed + tagged on `main` (v1.3.0). Can a Governor bring the registry entry in line?
• version: 1.2.1 → 1.3.0
• description changed? no  (if yes, paste the new one-liner)
Thanks! 🙏
```

You are **not** opening a PR here — you have no write access to the registry. You're handing a Governor everything they need to update it.

---

## Secrets — hard stop

Never put a secret (`.env` value, API token, service-account JSON, private key) into a commit, a diff, or a Slack message. If you discover a leaked secret in the repo or the change, **stop** and escalate to a Governor — do not "clean it up" quietly. Public items like SSH *public* keys and GitHub usernames are fine; anything that grants access is not.

---

## Quick checklist

Before you say a change is shipped:

- [ ] On a current `main`; one logical change (no branch, no skill-repo PR).
- [ ] `skill.toml` version bumped per semver.
- [ ] `CHANGELOG.md` entry added, prose style, version matches `skill.toml`.
- [ ] Description updated in **both** SKILL.md + skill.toml (or genuinely unchanged); `skill.toml` one ≤ 350 chars.
- [ ] Committed + pushed to `main`; tagged `vX.Y.Z`.
- [ ] *(If version/description/tier/compat changed)* notified `@governors` with the new version/description so a Governor can update the registry. **You did not edit the registry yourself.**
