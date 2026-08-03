# Claude Skills (version-controlled)

Americanflat's Claude skills, moved off the local Mac into this repo so they
survive machine loss and are usable from cloud sessions.

Because they live in `.claude/skills/`, any Claude Code session opened in this
repo — local, web, or CI — picks them up automatically. No copying, no
repackaging, no `~/.claude/skills` dependency.

## What's here

Migrated 2026-08-03 from `~/.claude/skills/` (14 skills).

| Skill | What it does |
|---|---|
| `amazon-df-morning-brief` | Amazon Vendor Central DF order metrics → Slack `#ops-vendorcentral` |
| `canada-inventory-report` | Yusen Canada portal → CSV → Drive → Slack → BigQuery |
| `cost-per-sku-dashboard` | Refreshes the Cost Per SKU dashboard CSVs in Drive |
| `download-weekly-shipping-reports` | Pulls the week's files from five carrier/3PL portals |
| `email-thread-summarizer` | Summarizes a Gmail thread from a pasted subject line |
| `luminous-inventory-report` | Yusen NL inventory → Slack `#dp-and-inventory` |
| `marketplace-cpu-analysis` | Ad-hoc cost-per-unit analysis by marketplace/carrier |
| `shipping-cost-report` | Weekly FedEx + Stamps vs 3PL shipped-order matching |
| `skill-design-system` | Americanflat brand tokens, logos, layout rules |
| `skill-fixer` | Brings a draft skill into ADR-001 compliance |
| `skill-invoice-to-bigquery` | PDF invoices → BigQuery `finance.freight_invoices` |
| `skill-pr-helper` | Ships a compliant change to a published `skill-*` repo |
| `stamps-invoice-validator` | Stamps.com invoices vs EDI reports |
| `yusen-invoice-validator` | Yusen/Taylored 3PL freight invoice audit (see `YUSEN-INVOICE-VALIDATOR.md`) |

Not migrated: `pdf`, `docx`, `xlsx`, `pptx` (Anthropic-managed, ship with Claude
and auto-update), and `morning` / `skill-creator` (Anthropic examples).

## Credentials

**No skill in this directory contains a credential, and none should.** Secrets
come from the environment at run time.

`canada-inventory-report` previously carried the
`canada-and-eu-inventory-update@americanflat.iam.gserviceaccount.com` private
key two ways — plaintext in `assets/sa.json` and base64-embedded in `SKILL.md`.
Both were stripped during the migration. It now reads:

- `CANADA_INVENTORY_SA_KEY` — base64-encoded service-account JSON, or
- `CANADA_INVENTORY_SA_FILE` — path to a key file kept outside the repo

`yusen-invoice-validator` needs `STEDI_API_KEY` (see its `.env.example`) plus
BigQuery credentials.

The root `.gitignore` blocks `sa.json`, `*-key.json`, and `*-credentials.json`
anywhere in the tree, and un-ignores only the config/reference JSON these
skills legitimately need.

## Editing a skill

Edit in place here and commit — this directory is the source of truth. That
replaces the old "edit `~/.claude/skills/…`, repackage, copy the `.skill` into
the repo" loop.

The root-level `*.skill` zips remain as distribution artifacts for skills
published org-wide. When you change a skill that has one, repackage and commit
the zip alongside your source change so the two don't drift. Skills already
published to `americanflat/skill-{name}` still go through the `skill-pr-helper`
flow; this repo is not a publishing channel.
