# Moving this into `americanflat/skill-cx-returns-portal`

This directory is the complete skill and is self-contained — nothing in it reaches
outside its own folder. It is ready to become its own repo.

**This has to run from the Mac.** Cloud sessions scoped to `anthony-amf` cannot
create or push to `americanflat/*` (cross-tier), so a session there can prepare the
contents but not publish them. That is why this file exists instead of a push.

## Why it is moving

It was built inside `americanflat-ops-director`, which is an invoice-audit
workspace: its `CLAUDE.md` is ~200 lines of Yusen invoice-validation instructions,
loaded by every session in that repo. A CX skill living underneath that gets read in
the wrong context.

That is not theoretical. On 2026-08-27 a fresh cloud session asked to "run the cloud
reship runbook" could not find it — it was on an unmerged branch — matched
`docs/CLOUD-SWEEP-RUNBOOK.md` instead, and ran the invoice validation sweep,
writing 32 stamps to the production ledger. The session behaved correctly; the repo
was the wrong home and the names differ by one word.

## Steps

Run from the Mac, in a scratch directory. Nothing here deletes anything.

```bash
# 1. Take a copy of the skill directory out of the ops-director checkout
mkdir -p ~/skill-cx-returns-portal-staging && \
  cp -R <ops-director>/cx-returns-portal/. ~/skill-cx-returns-portal-staging/

# 2. Make it a repo
cd ~/skill-cx-returns-portal-staging && \
  git init -b main && git add . && \
  git commit -m "Initial release: CX returns, reships and replacements

Seven case types with warehouse routing for five 3PL sites, replacement orders
created in ShipStation and confirmed as an EDI 940 via Stedi, and a self-serve
portal. See CHANGELOG.md for what is verified and what is not."

# 3. Create the repo on GitHub under americanflat, then
git remote add origin git@github.com:americanflat/skill-cx-returns-portal.git && \
  git push -u origin main && \
  git tag v0.1.0 && git push origin v0.1.0
```

## Then

1. Ask `@governors` in **#ai-github-skills** to add the registry entry. Never edit
   `ai-skills-registry` directly — Governors-only write access.
2. Close **PR #3** on `americanflat-ops-director` rather than merging it. That
   branch never landed on `main`, so closing it leaves that repo untouched — no
   deletion needed anywhere.
3. Delete nothing from `americanflat-ops-director`. The copy under
   `cx-returns-portal/` only ever existed on the feature branch.

## Before tagging anything above 0.1.0

Two inputs are still unverified, both called out in
`references/cloud-reship-runbook.md`:

- The ShipStation create payload's field names — run `scripts/shipstation_probe.py`
  and reconcile.
- The `warehouseId` → site mapping, from the same probe. It decides which 3PL
  receives the 940, and a wrong value ships a real customer's replacement from the
  wrong building.

The version is deliberately `0.1.0`, not `1.0.0`, for that reason.

## Also outstanding

- **Rotate `STEDI_API_KEY`** — leaked into a session transcript on 2026-08-27.
- **The invoice validator's false-945 bug** (`references/edi-940.md`) is documented
  but unfixed, and it weakens a payment gate. It belongs to
  `skill-yusen-invoice-validator`, not this skill.
- **Order 24235RS** — Sarah Imler's reship — is prepared and unrun. Details in the
  runbook.
