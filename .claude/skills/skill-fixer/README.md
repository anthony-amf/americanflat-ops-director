# skill-fixer

The skill that helps a Builder remediate a draft skill, then submits it for review via the CI-driven flow.

## What it does

Brings a draft skill into ADR-001 compliance — without rewriting the skill or replacing the Builder's judgment — and then optionally submits the candidate by pushing it to the `skill-candidates` quarantine repo and posting a Slack review request. The Builder, who is often non-technical, sees **three steps**; all the compliance rules run behind the scenes.

Skill Fixer runs in two modes, differing only in where the list of fixes comes from:

- **Remediation mode** — a Builder has a checklist (a `review-report.md` from the Publisher Framework, the CI workflow's auto-committed report, or a Publisher's send-back notes) and wants those fixes applied.
- **Standalone pre-flight mode** — a Builder has a draft skill but no checklist, and wants Skill Fixer to walk the candidate against ADR-001 v3.1 and surface issues *before* submitting.

**The three steps the Builder experiences:**

1. **Confirm** — Skill Fixer looks at the folder, works out what needs fixing, and shows a single screen: a plain "I'll set these up for you" summary of the automatic changes, plus a short **pre-filled form** for the few things only the Builder can decide. Everything the tool can infer is pre-filled for a one-tap confirm — the description drafted from the skill's own content, the department best-fit-guessed from the fixed set (`ops`/`sales`/`marketing`/`finance`/`pd`/`exec`), the trust level (tier) classified from what the skill reads and writes, the changelog drafted from the fixes that will land, and the version defaulted for a new skill. The **owner** (name + email) is the one thing genuinely asked. The Builder replies `ok`, or corrects any line.
2. **Apply** — Skill Fixer makes the changes and prints a plain "done" list. Scaffolded files and inferred settings apply on the summary consent from Step 1 — no wall of diffs for content the Builder can't meaningfully review — while `show me` reveals the exact change for anything, and any edit to text the Builder *wrote themselves* (e.g. trimming their description) is always shown as a before/after and approved on its own. Security findings are escalated to a Governor, never patched; script advisories are flagged, never edited. Skill Fixer does **not** verify the result — the Publisher's run (or the CI report) is the only verification.
3. **Submit for review** *(opt-in)* — after the Builder says `yes`, Skill Fixer runs a quick GitHub-readiness check, then pushes a branch named `<skill-name>--<gh-handle>--<YYYYMMDD>` to `americanflat/skill-candidates` and posts the review request in the publisher-reviews Slack channel via the `slack-by-salesforce` MCP connector. Same-session re-submissions thread automatically under the first post; across sessions a fresh top-level message is posted (the system-of-record audit trail lives in GitHub + CI logs regardless). A Publisher or Governor reacts 🔍 to trigger the compliance review CI; the rest of the flow lives in `skill-publisher-framework`, `af-skill-admin`, and the Playbook.

A fix-only run is two steps (Confirm, Apply); fix-and-submit is three. Steps 1–2 are local-only with zero network access; Step 3 is the only one that does git-remote or Slack work, and each remote action is gated by explicit Builder approval (`yes` to enter, `go` to push, `send` to post). The Builder can say `not yet` or `abort` at any point to stop cleanly.

Internally, every finding is still classified (mechanical fix / needs-your-input / escalate-to-Governor / advisory-note) and all the detailed rules — name normalization, the ≤350-character `[skill].description` limit that `af-skill-admin` reuses verbatim as the GitHub repo description, `.env.example` derivation, tier classification, manifest-vs-reality checks, the security escalations, and the script advisories — live in a "Checks reference" section of `SKILL.md` that the Builder never sees. Security findings (leaked secrets, malicious prompting) are not scanned in standalone mode; that detection lives in the Publisher Framework's `review.py`.

## Who uses it

Builders — anyone who drafted a skill that the Publisher (or the Publisher Framework's automated checks) sent back. The Publisher does not run this skill; their role is to review and publish, not to edit candidate skills on the Builder's behalf.

## Installation

**Most people don't need to install anything.** Skill Fixer is distributed as part of the Americanflat **organizational skills**, so any Builder with the org skill set already has it — they just invoke it (see "Using it" below). There's no per-user clone, no `~/.claude/skills/` copy step, and nothing to keep up to date by hand.

**Governors:** the only people who clone this repo are Governors maintaining or editing the skill itself. To get a local working copy:

```bash
git clone git@github-americanflat:americanflat/skill-fixer.git
```

(Use the `github-americanflat` SSH host alias, not raw `git@github.com:` — see the Notion GitHub & SSH Setup Guide.) Edits land in the org skill set through the normal publish flow, not by copying into individual users' skill directories.

Skill Fixer is purely conversational — it ships no `.py` files and runs entirely through Claude's interpretation of `SKILL.md`. There are no Python prerequisites: no Python version, no third-party packages, no installer. **Git is required** (for Step 3's `git clone` / `commit` / `push` to `americanflat/skill-candidates`); if the Builder will only run Steps 1–2 and submit manually, git is still recommended for cleaner diff display. The Builder also needs SSH access to GitHub configured per the Notion GitHub & SSH Setup Guide before Step 3 can run. The `slack-by-salesforce` MCP connector is required for Step 3's review-request post; without it, the Builder can still complete Steps 1–2 and submit manually. Skill Fixer does **not** require `skill-publisher-framework` to be installed locally — that's the Publisher's tool, and Skill Fixer never invokes it from the Builder's machine even if it happens to be present. The Publisher's run (or the CI's `review.py` report) is the only verification step.

## Using it

Open Claude Code, point the folder picker at the candidate skill's directory, and say one of:

- "Fix this skill" — Skill Fixer asks if you have a checklist (remediation) or want a pre-flight (standalone).
- "Apply the review-report fixes" — explicit remediation; expects `review-report.md` in the folder or pasted in chat.
- "Pre-flight this skill against ADR-001" — explicit standalone; no checklist needed.
- "Submit this skill for review" — explicit submit; Skill Fixer infers the mode from whether a checklist is present, applies fixes (if any), then offers Step 3 (submit).
- `/skill-fixer` — same as "Fix this skill".

## Owner and tier

- **Owner:** Ivan Calderon `<ivan@americanflat.com>` — Data Integrity team, Governor.
- **Tier:** 2 (writes-with-notify). The skill modifies files in the candidate skill folder (Steps 1–2), and in Step 3 it also pushes a branch to `americanflat/skill-candidates` and posts a Slack message via the `slack-by-salesforce` MCP. Changes apply only after the Builder's consent (a plain-language summary for scaffolds and inferred settings, an explicit before/after for edits to their own words, and `show me` reveals any exact diff on demand); the Step 3 push and Slack post each have their own approval prompts (`go` and `send`). The human is in the loop on every change that hits disk and every remote operation that fires.

## What this skill does NOT do

- **Does not invent owner identity, the substance of a description, or changelog content for changes it didn't make.** Owner (name + email) is always asked; the description is drafted from the skill's own content and confirmed; the changelog is drafted from the fixes that actually landed and confirmed. Values it can *derive from evidence* — tier (from what the skill reads/writes), department (best-fit from a closed set), the trimmed repo description — are proposed for a one-tap confirm, never silently guessed. A version is never invented.
- **Does not auto-fix security findings.** Leaked secrets and malicious-prompting patterns are escalated to a Governor; Skill Fixer refuses to silently rewrite or scrub them.
- **Does not silently weaken the candidate to pass the check.** Removing a flagged sentence with no replacement, downgrading a tier, or deleting a check is a regression, not a fix.
- **Does not edit `skill-publisher-framework` itself.** That skill goes through its own self-review flow.
- **Does not push to published `skill-<name>` repos.** The only `git push` Skill Fixer ever runs is to `americanflat/skill-candidates` in Step 3, after Builder approval. Publishing to a `skill-<name>` repo is the Publisher Framework's job (legacy path) or the `af-skill-admin` promote-skill workflow's (CI-driven path).
- **Does not post Slack messages without `send` from the Builder.** Step 3 drafts a review-request message and waits for explicit approval. `cancel` or `not yet` leaves no Slack trace.
- **Does not propose improvements outside the checklist or the ADR-001 baseline.** Scope is what the Publisher flagged (remediation) or what ADR-001 v3.1 mechanically requires (standalone). Skill Fixer does not redesign the skill or suggest features. The one bounded exception is a pair of **advisory** script checks (below) — flagged, never auto-applied.
- **Does not edit candidate script code.** When a candidate ships `.py` files, Skill Fixer runs three read-only advisory checks — non-portable path construction (recommend `pathlib.Path`), machine-specific hardcoded paths (recommend moving to a `.env` variable), and BigQuery/GCP auth via a service-account key file (recommend a README note about the required key, or switching to `gcloud`/ADC, since the key won't travel with a shared skill) — so the same skill behaves the same on a Builder's Mac and another's Windows, and a shared skill doesn't silently break on missing credentials. It **flags** these with `file:line` and a recommended fix and offers to fix them on a separate ask, but it never rewrites the script inside its apply flow. (If a service-account key file is actually committed in the folder, that's a leaked secret — escalated to a Governor, not treated as an advisory.)
- **Does not verify the fixes.** Skill Fixer never invokes `skill-publisher-framework/scripts/review.py`, never reimplements its security/integrity checks, and never predicts whether the Publisher will pass the candidate. Verification is the Publisher's run (legacy) or the CI's auto-generated `review-report.md` (CI-driven). Standalone-mode discovery produces *advisory* pre-flight findings, not verification. Trust the process.

## How it relates to skill-publisher-framework

Skill Fixer fits at multiple points in the Publisher Framework's flow. The shape depends on the path (CI-driven, the default for new submissions; legacy, for folder-handoff submissions):

```
CI-driven path (default):
─────────────────────────
Builder drafts skill
    ↓
(optional) skill-fixer standalone pre-flight
    ↓
skill-fixer Step 3 (submit) — push branch + Slack post
    ↓
Publisher/Governor reacts 🔍 → CI runs review.py + semantic pass
    ↓
review-report.md committed to branch + Slack thread summary
    ↓
   pass ────────────────────────────────────────────────────►  Publisher posts "approved" → Governor reacts 🚀 → promote-skill CI publishes
    │
   send-back ──► skill-fixer remediation on new review-report.md ──► Step 3 again (new branch) ──► (re-review)
    │
   block ──► Governor handles (security, malicious prompting, tier disputes)

Legacy path:
────────────
Builder drafts skill
    ↓
(optional) skill-fixer standalone pre-flight
    ↓
Builder hands folder to Publisher
    ↓
Publisher runs skill-publisher-framework (Stages 1–6 locally)
    ↓
   pass ─► published to skill-<name>, registry live
   send-back ──► skill-fixer remediation ──► (re-hand-off)
   block ──► Governor handles
```

The two skills share assumptions deliberately. In **remediation mode**, Skill Fixer treats `review-report.md` (produced by the Publisher Framework's `scripts/review.py`) as the canonical checklist of what to fix. In **standalone mode**, Skill Fixer does *mechanical* discovery against ADR-001 v3.1 — file presence, schema validity, name agreement, manifest claims vs. reality — and produces its own checklist; these findings are advisory pre-flight, not authoritative verification. Skill Fixer never runs `review.py` itself, never reimplements its security and integrity checks, and never tries to verify the candidate locally. Once approved fixes are applied, the skill goes to the Publisher and the Publisher's run of the framework is the only verification step. This keeps the role boundary clean: Builders fix; Publishers verify; only one machine runs the full compliance checker, and it's the Publisher's.

## Files

```
skill-fixer/
├── SKILL.md              # Instructions Claude follows when invoked
├── skill.toml            # Manifest (owner, tier, deps, compatibility)
├── README.md             # This file
├── CHANGELOG.md          # Version history
└── .gitignore            # .env, __pycache__/, .venv/, review-report.md, ...

(No `scripts/` directory and no `setup.py` — Skill Fixer is purely conversational.
Every step requires Builder judgment, so there is no deterministic helper logic that
would belong in `scripts/`, and there's no install-time work that would belong in
`setup.py`. The skill installs via direct `git clone` into `~/.claude/skills/skill-fixer`;
prereqs are verified at first invocation by Claude Code. Both omissions are supported
by ADR-001 v3.1, which makes `scripts/` and `setup.py` conditional rather than
always-required.)
```

## See also

**Sibling skill (the one whose findings this skill remediates):**

- `skill-publisher-framework/SKILL.md` — the six-stage review and publish flow.
- `skill-publisher-framework/scripts/review.py` — the deterministic compliance check that produces the `review-report.md` Skill Fixer reads as input. Skill Fixer never invokes it.

**Org-wide governance docs:**

- ADR-001 (Skill Repository Standard) — the standard skills are checked against. Consolidated v3.1 lives on Notion: https://www.notion.so/3598555c2abc811b8bc2fdc94820ca37 (supersedes the local `ADR-001_Skill_Repository_Standard_v3.docx` and the `ADR-001_Amendment_v3.1_DRAFT.md` in the governance folder).
- `AF_Claude_Center.docx` — the broader AI program at Americanflat (in the governance folder).
