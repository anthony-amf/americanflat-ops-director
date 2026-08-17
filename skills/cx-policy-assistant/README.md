# skill-cx-policy-assistant

A policy reference bot for Americanflat's CX reps. The rep asks a question in plain
language; the skill answers what our policy says, cites the Notion SOP it came from,
and drafts the customer-ready reply.

- **Owner:** Anthony Armstrong <anthony@americanflat.com>
- **Tier:** 1 (read-only — reads Notion SOPs, writes nothing, takes no action)
- **Department:** ops
- **Data:** Notion SOPs database (`collection://2d14ea2d-a1ac-4127-aece-57b523f44043`)
- **Surface:** claude.ai

---

## What the rep gets

Every answer has three parts, in this order:

1. **The verdict** — what to do, in a line or two.
2. **The basis** — the specific rule and which Notion SOP it's from, so it's checkable.
3. **The draft** — a message in Americanflat's voice, ready to paste into Zendesk.

Plus three conditional additions:

- **The room to move** when the by-the-book answer is harsher than the situation warrants.
- **Escalation flag** when policy assigns the decision to a manager or another team. The
  draft becomes a holding reply, not a resolution.
- **A live-Notion check** before any dollar figure, percentage, or day count is quoted.

## Example

> **Rep:** Customer got a 12x16 frame that arrived cracked, ordered on our site. Wants a refund.

> **Verdict:** Get photos first, then offer a replacement or store credit — refund is the
> last resort. Don't take the item back; they keep or dispose of it.
>
> **Basis:** Customer Service Policies → Replacements → Situations: damaged/quality issues
> require a detailed explanation and pictures, we don't accept the items back, and the order
> is replacement → store credit → refund. Because the damage is our fault, no return
> shipping is charged.
>
> **Draft:** *[damaged-on-arrival template, personalised]*

## Design decisions worth knowing

**Why it drafts as well as answers.** Quoting policy alone leaves the rep writing the
message anyway, and inconsistent wording is where policy-correct answers still go wrong.
The templates in `references/reply-templates.md` are Americanflat's own where they exist.

**Why it bends the rules on purpose.** Answering strictly by the book produces
technically-correct answers that lose customers. The latitude was already in the SOPs and
simply unusable — the refund policy says *"use your judgement and try to keep Americanflat
profitable"*, and the policy list authorizes bending outright for an angry customer because
a bad review costs more than the order. `references/judgment-and-empathy.md` makes that
operational: *be generous with warmth, deliberate with money.*

The load-bearing distinction there is **capability limits vs. policy choices.** We
genuinely cannot redirect a shipped package or cancel an order already processing —
softening that isn't generosity, it's a promise that breaks. A restocking fee or a day-32
replacement is a decision, and decisions can flex. Reps get this wrong in both directions,
over-promising the impossible while refusing things they could have granted.

**Why it won't name a spend limit.** The SOPs define no rep-level authority, so the skill
escalates instead of guessing — a fabricated approval figure is worse than an escalation.
Two numbers from you would remove most of the daily friction; they're named in the
Authority section of `judgment-and-empathy.md`.

**Why it surfaces conflicts instead of resolving them.** The SOPs were written at
different times and genuinely contradict each other — return-label handling has three
different answers across three pages. A confident single answer there would be a
fabrication the rep would act on. The skill names the conflict, gives the newest page's
answer as the working one, and says it needs a manager's decision. Catalogue in
`references/sources.md`.

**Why numbers get verified live.** The reference files are a snapshot, and snapshots go
stale — this workspace has been burned by that before. Qualitative rules (do we cancel?)
are stable and answered from the snapshot; money and deadlines are re-fetched from Notion
before being quoted. If live Notion disagrees, live Notion wins and the rep is told the
snapshot needs refreshing.

**Why it takes no actions.** Refunds, labels, and ticket changes stay with the rep. The
skill has no write path to Zendesk, Shopify, or the tracking sheets, which keeps a wrong
answer recoverable — the rep reads the draft before anything reaches a customer.

## Files

```
cx-policy-assistant/
├── SKILL.md                        the answer contract, decision rules, drafting limits
├── skill.toml                      packaging metadata
├── CHANGELOG.md
├── README.md
└── references/
    ├── policies.md                 master CX policy digest, by topic + numeric index
    ├── returns-refunds.md          return/refund/replacement processes, refund policy, label creation
    ├── judgment-and-empathy.md     how much room exists around the rules; the empathy craft
    ├── reply-templates.md          customer-ready templates and the Americanflat voice
    ├── zendesk.md                  ticket workflow, statuses, macros, common issues
    ├── escalation.md               who owns what; when to stop and ask
    └── sources.md                  Notion page IDs, freshness protocol, known SOP conflicts
```

## Installing for the rep (claude.ai)

The skill is a plain directory — no dependencies, no secrets, no scripts.

1. From the Mac, copy this directory into the skills folder (additive copy into a fresh
   directory, per the repo's no-delete rule):
   `cp -R skills/cx-policy-assistant ~/.claude/skills/cx-policy-assistant`
2. Package it with skill-creator's packager:
   `python3 -m scripts.package_skill ~/.claude/skills/cx-policy-assistant`
3. Upload the resulting `.skill` to claude.ai for the rep's account, or publish it
   org-wide as `americanflat/skill-cx-policy-assistant` following the `skill-pr-helper`
   flow (commit to `main`, tag `v1.0.0`, ask `@governors` to update
   `ai-skills-registry`).

The rep doesn't need to invoke it by name — the description triggers on ordinary CX
questions ("can this customer return this", "what do I tell them about the delay").

## Maintenance

Refresh the snapshot whenever a CX SOP changes, and periodically regardless — Notion
sends no change notifications. Procedure and the page list are in
`references/sources.md`. Bump the minor version and add a CHANGELOG entry.

Open items worth resolving. The first three are SOP contradictions recorded in
`sources.md`; the fourth is a gap:

1. The three-way return-label conflict (who creates labels).
2. The return-carrier conflict (Endicia/USPS vs. cheapest-of-Stamps-or-FedEx).
3. Whether the 20% restocking fee and the flat $5 handling cost stack.
4. **Rep spend authority is undefined.** Two numbers would remove most of the daily
   friction: the value a rep can resolve without asking, and whether they may waive the
   restocking fee alone. Until set, the skill escalates anything beyond prescribed policy
   rather than guessing. See the Authority section of `judgment-and-empathy.md`.
