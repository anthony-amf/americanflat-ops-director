# Claude instructions for skill-pr-helper

This repo **is** the `skill-pr-helper` skill — a conversational skill that walks any Claude through shipping a compliant change to an already-published Americanflat `skill-{name}` repo. `SKILL.md` is the skill itself; treat it as the source of truth.

## When you change this repo

Follow the skill's own house rules (they apply to editing this repo too — dogfood them):

- **Commit directly to `main`.** Skill repos are no longer PR-gated (Repo Merge Policy, 2026-07-08). No branch, no PR against this repo. Force-push and branch deletion are blocked by the ruleset — don't work around them.
- **Bump `version` in `skill.toml`** per semver for any behavior change.
- **Add a matching prose `CHANGELOG.md` entry** — the version must equal `skill.toml`.
- **Keep the description identical** in `SKILL.md` frontmatter and `skill.toml`. Watch the 350-char / no-control-character limit on the `skill.toml` one (it doubles as the GitHub repo description).
- **Tag `vX.Y.Z`** after pushing, matching `skill.toml`.
- **Notify a Governor to update the registry.** When version or description changes, ping `@governors` — `ai-skills-registry` is Governors-only, so you don't have write access and never open a PR against it. A Governor makes the edit.

## What NOT to do

- **Don't leak secrets.** No tokens, `.env` values, or keys in commits, diffs, or Slack messages. On any leaked secret, stop and escalate to a Governor.
- **Don't let the two descriptions drift.** A stale `description` is a real trigger bug, not cosmetics.

## See also

- This repo's `SKILL.md` — the skill and its full flow.
- `README.md` — human-facing overview.
- `governance/Repo_Merge_Policy.md` — why this repo commits direct-to-main.
