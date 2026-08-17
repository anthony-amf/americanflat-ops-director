# Changelog

## 1.1.0 — 2026-08-17

Adds **judgment and empathy** on top of 1.0.0's policy lookup. Until now the skill
answered strictly by the book, which produced technically-correct answers that lose
customers — a rep enforcing a 30-day window to the day, against someone whose frame
arrived broken, has followed the rule and failed the job.

The latitude was already in the SOPs and simply wasn't usable: the refund policy says
*"use your judgement and try to keep Americanflat profitable"*, and the policy list
authorizes bending outright for an angry customer because a bad review costs more than
the order. This release makes that operational rather than buried.

- **New `references/judgment-and-empathy.md`.** Organizing principle: *be generous with
  warmth, deliberate with money.* Warmth is free and needs no approval; margin is finite,
  so latitude on money is bounded and sometimes escalated. Reps who conflate the two
  either give away margin to seem nice or stay cold thinking rigidity is safe.
- **Capability limits vs. policy choices** — the distinction reps get wrong in both
  directions. We genuinely cannot redirect a shipped package or cancel an order already
  processing; a restocking fee or a day-32 replacement is a decision that can flex.
  Softening a capability limit isn't generosity, it's a promise that breaks. The skill now
  says which kind of "no" it is, because "the carrier already has it" lands very
  differently from "our policy doesn't allow that."
- **Cost-of-remedy test.** Under ~$50 just fix it — policy already says the customer keeps
  it, so don't add proof and delay to a decision already made. ~$50–150, use the ladder
  generously. Above that or on a repeat claimant, escalate before promising.
- **Signals for and against latitude** — lean generous when it's our fault, first contact,
  barely outside a threshold, a real occasion was missed, or we've already failed once.
  Hold firm and escalate on patterns, review threats as leverage, non-returnable
  condition, and anything needing approval the rep lacks.
- **Empathy craft** with before/after pairs: lead with the fix not the rule, never cite
  "policy" as a reason, acknowledge the specific thing instead of generic regret,
  apologize once then act, name the emotion when it's plainly there, "yes, and" rather
  than a bare no, offer choices to someone who feels powerless, own it as "we" without
  blaming the warehouse or carrier, and match the customer's register.
- **Five de-escalation templates** — angry customer on a second failure, granting latitude
  just outside the window, the keep-it discount as the better outcome, a genuine no
  delivered warmly, and a missed occasion (gift, wedding, memorial) where no remedy fixes
  the timing.
- **Exception logging.** Bent rules get noted, because repeated exceptions are evidence the
  rule is wrong — a restocking fee everyone quietly waives is data, not a series of
  one-offs.
- **Authority gap flagged rather than invented.** The SOPs define no rep-level spend limit,
  so the skill refuses to fabricate one: remedies policy already prescribes are the rep's
  call, anything beyond prescribed policy is a manager's regardless of amount. Names the
  two numbers Anthony would need to set to remove most daily friction.
- Discretion is now part of the **answer contract**, not an optional file — a harsher-than-
  warranted answer must come with the room around it.

## 1.0.0 — 2026-08-17

First version. A policy reference bot for Americanflat's CX reps, built for claude.ai:
the rep asks in plain language, the skill answers what policy says, cites the Notion SOP,
and drafts the customer-ready reply.

- **Three-part answer contract.** Every response gives the verdict, the basis (rule +
  Notion source), and a paste-ready draft. A verdict without a draft leaves the rep
  writing it anyway; a draft without the basis can't be checked.
- **Policy digest** covering the master Customer Service Policies page by topic —
  cancellations, order status, stock-outs, missing parts, order adjustments, product,
  pricing, returns, refunds, replacements, response-time SLA, review inquiries, samples,
  shipping issues, phone orders — plus a numeric index of every threshold in one table.
- **Returns/refunds/replacements detail** — the Shopify return, refund, and replacement
  processes, cost responsibility, the customer-facing refund policy, non-returnable
  items, return-cost estimation, and all three label-creation methods (Stamps new, Stamps
  from history, FedEx return).
- **Reply templates** — Americanflat's three established templates (late order,
  reshipment, puzzle) preserved verbatim as the house voice, plus fifteen derived
  templates for the common scenarios, a voice guide, and hard limits on what a draft may
  never contain (invented numbers, promises faster than policy, unapproved commitments).
- **Escalation routing** — a stop-and-ask table for manager-level decisions, a
  route-to-another-team table, marketplace ownership, and wholesale intake by order size.
- **Conflict protocol.** The SOPs genuinely contradict each other; return-label handling
  has three different answers across three pages of different vintages. Rather than
  picking one silently, the skill names the conflict, gives the newest page's answer as
  the working one, shows the other version with its date, and tells the rep it needs a
  manager's decision. Five known conflicts catalogued in `references/sources.md`.
- **Freshness protocol.** The reference files are a dated snapshot; snapshots go stale.
  Qualitative rules are answered from the snapshot, but dollar figures, percentages, and
  day counts are re-fetched from live Notion before being quoted. Live Notion wins on
  disagreement, and the rep is told the snapshot needs refreshing.
- **Advisory only** — no refunds, no labels, no Zendesk or Shopify writes. The rep reads
  every draft before it reaches a customer, which keeps a wrong answer recoverable.

Snapshot taken from nine Notion SOPs (eight Live, one archived for voice only); page IDs
and last-edited dates recorded in `references/sources.md`.
