# Claude Code handoff: AF Design System deploy

Paste the prompt below into your next Claude Code session. It will push the explainer HTML to af-dashboards, then push the full skill repo to both GitHub locations.

---

## The prompt

```
We're deploying the AF Design System skill from a prior chat session. Three tasks:

TASK 1: Push the visual explainer to af-dashboards
- File is in my Downloads folder: af-design-system-explainer.html
- Target repo: KentNunezNYC/af-dashboards
- Target filename: af-design-system-explainer.html (root of repo)
- Use the GitHub PAT from my Notion config page
- After push, confirm the URL: https://kentnuneznyc.github.io/af-dashboards/af-design-system-explainer.html
- Drop the URL back into a Slack DM to me (U01M5AXAXB9) with a one-line note

TASK 2: Push the standalone skill repo
- The full skill folder is in my Downloads, unzipped from af-design-system.zip
- Create new public repo: KentNunezNYC/af-design-system
- Push the whole af-design-system/ folder contents as the root of the repo
- Description: "Americanflat design system skill. Brand tokens, logos, templates, and rules for any tool or agent built for AF."
- Tag the initial commit as v1.0

TASK 3: Mirror into af-agents
- Clone KentNunezNYC/af-agents locally
- Create skills/af-design-system/ inside it
- Copy the same skill folder contents into skills/af-design-system/
- Prepend this line to the top of skills/af-design-system/SKILL.md:
  <!-- This is a mirror of KentNunezNYC/af-design-system. Source of truth is the standalone repo. -->
- Add scripts/sync.sh from DEPLOYMENT.md in the skill
- Commit with message: "Add af-design-system skill v1.0"
- Push

When all three tasks are done, post a single Slack DM summary to me with:
- The dashboard URL
- The standalone repo URL
- Confirmation that af-agents was updated
- Any errors encountered

If anything fails, stop and report. Do not improvise auth or create new tokens.
```

---

## Files Kent needs in his Downloads folder before running

Both should already be there from this chat session:

1. `af-design-system-explainer.html` (the visual page)
2. `af-design-system.zip` (the full skill, unzipped into a folder before Task 2)

If they got cleared, just re-download from this chat.

## Estimated time

3 to 5 minutes for Claude Code to run all three tasks, assuming no auth issues.
