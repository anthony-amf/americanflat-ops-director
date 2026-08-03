# skill-pr-helper

A conversational skill that walks any Claude through shipping a **compliant change** to an already-published Americanflat `skill-{name}` repo — committing **directly to `main`** (skill repos are no longer PR-gated, per the *Repo Merge Policy* of 2026-07-08) — and then **notifying the Governors** to bring the companion `ai-skills-registry` entry in line.

It is the actionable form of the Notion guide *"Changing a Published Skill — house rules"* (Playbooks & Guides → For builders), updated for the direct-to-main policy.

> **Name note:** the skill keeps its `skill-pr-helper` name for continuity, but it no longer opens any PR. Skill-repo changes go straight to `main`, and the registry is **Governors-only** — the skill *notifies* a Governor to update it rather than opening a registry PR.

## What it does

- Enforces the house rules: one logical change at a time, a semver bump in `skill.toml`, a prose `CHANGELOG.md` entry that matches the version, and keeping the SKILL.md + skill.toml descriptions identical.
- Commits the change **directly to `main`**, pushes, and tags `vX.Y.Z` with a conventional-commit message.
- Drafts the Slack request that pings the **@governors** group in **#ai-github-skills** asking a Governor to update the registry entry (version + description).

## What it deliberately does NOT do

- **It never touches the registry.** `ai-skills-registry` is Governors-only; the skill has no write access and never clones it or opens a PR against it — it notifies a Governor with what changed.
- **It isn't for brand-new skills.** Before `v1.0.0`, use the Builder create → publish flow instead.
- **It never touches secrets.** On any leaked secret it stops and escalates to a Governor.

## When it triggers

Phrases like "update this skill", "bump the skill version", "update the changelog and version", "change this skill's description", "update the skill registry", or "ship a fix to skill-foo".

## Requirements

- A git checkout of the published `skill-{name}` repo and GitHub SSH access (see the Notion *GitHub & SSH Setup Guide*).
- `git` (required); `gh` (optional, for `gh pr create`).
- The `slack-by-salesforce` MCP connector to post the merge-request ping (optional — the message can also be sent by hand).

## See also

- Notion: *Repo Merge Policy — Direct-to-Main* (why the skill repo commits are no longer PR-gated)
- Notion: *Pull Request Guide — changing a published skill (house rules)*
- Notion: *Publishing a Skill — the current flow* (for brand-new skills)
- `ADR-001 — Skill Repository Standard (v3.1)`
