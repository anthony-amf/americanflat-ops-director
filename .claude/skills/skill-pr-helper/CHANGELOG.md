# Changelog

All notable changes to `skill-pr-helper` will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.1] — 2026-07-09

Trims the `SKILL.md` frontmatter `description` to fit Claude's 1024-character limit for skill descriptions.

- **Frontmatter description shortened from 1117 to 981 chars.** The v2.1.0 description ran over the 1024-char ceiling Claude enforces on skill descriptions, which can prevent the skill from loading. Trimmed the prose (dropped bold markers, folded a couple of clauses, cut one redundant trigger phrase) while keeping the meaning and the key trigger phrases intact. No behavior change; `skill.toml` description (≤350, unchanged) still carries the short form.
- **Why now.** The 1024-char limit was flagged after v2.1.0 shipped; leaving it over-limit risks the skill silently failing to load.

## [2.1.0] — 2026-07-08

Corrects Phase B: the skill no longer tells Claude to clone `ai-skills-registry` and open a PR — it tells Claude to **notify the Governors**, who make the edit.

- **Registry updates are now notify-only.** Regular skill owners (and Claude on their behalf) have **no write access** to `ai-skills-registry` — it's Governors-only — so the v2.0.0 instruction to clone it and open a PR was both against policy and impossible for a non-Governor. Phase B is rewritten to: post an update request tagging `@governors` in #ai-github-skills with the skill name, new version, and (if changed) new description. A Governor makes the edit.
- **Slack template reworded.** From "registry merge needed / Registry PR: <url>" to a plain "registry update needed / can a Governor bring the entry in line" request with the version + description fields inline. No PR URL, because the author never opens a PR.
- **House rule 7, the two-gates intro, and the checklist** all now say "ask a Governor to update the registry / you don't have write access" instead of "open the registry PR." Description updated in both `SKILL.md` and `skill.toml`.
- **Why now.** Governor direction (2026-07-08): Claude must not attempt registry writes — only notify. Matches the same clarification made to the Notion guides (*Changing a Published Skill* and *Repo Merge Policy*).

## [2.0.0] — 2026-07-08

Reworks the skill for the **Repo Merge Policy** (`governance/Repo_Merge_Policy.md`): skill repos are no longer PR-gated, so the flow now commits **directly to `main`** instead of opening a Pull Request. This is a breaking change to how the skill operates — hence the major bump.

- **The skill-repo change goes straight to `main`.** Phase A no longer branches, opens a PR, or pings @governors for the skill change. It commits on `main`, pushes, and tags `vX.Y.Z`. The old "Never push to `main` / stop at open-the-PR / a Claude can't merge a protected branch" premise is gone — write+ collaborators now merge directly, per policy.
- **The registry step is unchanged and still gated.** Phase B still opens an `ai-skills-registry` PR and pings the @governors group, because `ai-skills-registry` keeps its PR + Governor-CODEOWNERS ruleset. The two-gates distinction (skill repo open, registry gated) is now called out explicitly at the top of the skill.
- **Slack templates trimmed to one.** The "PR up for review + merge" template (old template 1) is gone — there is no skill-repo PR to review. Only the registry-merge ping remains, reworded to say the skill change is "already committed + tagged on `main`." The v1.0.2 "wrap every URL in angle brackets" guidance is preserved on the surviving template.
- **New owner responsibility called out.** Direct commits don't auto-update the registry and nothing watches for drift, so Step 7 makes reporting version/description/tier/status changes an explicit owner duty (matching the policy's §6).
- **Description updated in both `SKILL.md` and `skill.toml`** to describe the direct-to-main flow; triggers broadened from "open a PR for this skill" to "update this skill" / "ship a fix to skill-foo". `CLAUDE.md` was also corrected — it previously described `skill-candidates` by mistake.
- **Why now.** A non-technical business team refused the PR workflow; Governors removed the PR gate from all skill repos on 2026-07-08 and updated `af-skill-admin` (v0.3.0) to provision new repos ungated. This skill had to stop instructing a PR flow that no longer exists.

## [1.0.2] — 2026-07-02

Stops Slack from hyperlinking the word after the PR URL in the merge-request pings.

- **URLs in the Slack templates must be sent wrapped in angle brackets.** A bare URL sent through the Slack API has no hard closing boundary, so when the newline after it gets flattened, Slack's autolinker swallows the next word — a real ping went out with "Ready" absorbed into the PR link. The Slack-templates section now instructs wrapping every PR/registry URL in Slack's explicit angle-bracket link syntax (described in prose, same as the subteam mention, so the org-skill loader stays happy). No change to what the skill does or when it triggers.

## [1.0.1] — 2026-06-04

Strips XML-tag-shaped tokens from `SKILL.md` (and the docs) so the skill loads cleanly as an Organizational skill.

- **Replaced angle-bracket placeholders with `{...}`.** Tokens like `skill-<name>`, `<short-slug>`, and `<skill-pr-url>` parse as HTML/XML tags and broke the org-skill loader; they're now `{name}`, `{short-slug}`, `{skill-pr-url}`.
- **Reworded the Slack group-mention.** The literal `<!subteam^…>` form (an `<!…>` token a parser reads as a malformed declaration) is gone from the templates; the prose now says to wrap `!subteam^S06R4FLS3T2` in angle brackets when sending via the Slack API. No change to what the skill does or when it triggers.
- **Why now.** The published v1.0.0 was promoted with the tag-shaped tokens in place, which prevented the skill from being added to Organizational skills.

## [1.0.0] — 2026-06-04

First release. Turns the "Pull Request Guide — changing a published skill (house rules)" into an actionable skill any Claude can follow.

- **End-to-end PR flow for an already-published skill.** Branch from `main`, make one logical change, bump `skill.toml` per semver, add a matching prose `CHANGELOG.md` entry, keep the SKILL.md and skill.toml descriptions in sync, and open a self-explaining PR — then stop, because a Claude can't merge a protected branch.
- **Companion registry update built in.** After a human merges, the skill tags `vX.Y.Z` and opens the `ai-skills-registry` PR (clone via the `git@github-americanflat:` alias, edit `registry.json` only, leave the auto-rendered `README.md` alone) so the registry's version and description never go stale.
- **Slack merge-request templates.** Two ready-to-fill messages that ping the @governors group (subteam ID `S06R4FLS3T2`) in #ai-github-skills (`C0B3P9LCK99`) — one for the skill PR, one for the Governor-only registry merge.
- **Why now.** The house rules existed only as a Notion guide; making them a skill means any Claude maintaining a published skill applies them the same way, and the easily-forgotten registry sync stops being optional.
