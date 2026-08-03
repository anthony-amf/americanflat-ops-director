# Claude instructions for skill-candidates

This repo is the quarantine zone for draft Americanflat AI skill submissions. It is **not** a normal codebase.

## What you should know

- Each branch is a different candidate skill submitted by a different Builder. Branches share no code lineage.
- `main` contains only metadata (README, this file, CHANGELOG). The interesting content lives on feature branches named `<skill-name>--<builder>--<date>`.
- Each branch is reviewed by a Publisher per [`skill-publisher-framework`](https://github.com/americanflat/skill-publisher-framework). The CI in [`af-skill-admin`](https://github.com/americanflat/af-skill-admin) auto-generates `review-report.md` on each branch when a Publisher or Governor reacts 🔍 to the request in Slack.

## What you should NOT do here

- **Do not merge candidate branches into `main`.** Candidates do not graduate by merging here — they graduate by being pushed to a new `skill-<name>` repo via `skill-publisher-framework`'s `publish.py`.
- **Do not edit files on a candidate branch** unless you are the Builder remediating findings in `review-report.md`. Even then, prefer running `skill-fixer` locally on the candidate folder and re-pushing the branch — the branch should mirror what the Builder has on disk.
- **Do not auto-fix security findings** (leaked secrets, malicious prompting). Escalate to a Governor.
- **Do not delete branches** without confirming with the Builder and a Publisher. The history is the audit trail.

## See also

- This repo's `README.md` for the end-to-end workflow.
- `americanflat/skill-publisher-framework` for the Publisher's review process.
- `americanflat/skill-fixer` for the Builder's pre-flight and submit flow.
