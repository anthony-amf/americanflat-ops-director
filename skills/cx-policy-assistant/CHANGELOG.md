# Changelog

## 1.4.0 — 2026-08-17

**The Notion SOPs were updated to match the decisions**, so the skill no longer carries
overrides against its own sources. Notion is the single source of truth again.

Written into Notion:

- *How To: Customer Service Policies* — new **Rep Discretion & Spend Authority** section
  placed ahead of the individual rules, so a rep meets the discretion frame before the
  rules it applies to. States the $200/month pool, its discretion-only scope, the
  prescribed-remedies carve-out, what to do when the budget is spent, and the logging ask.
- *How To: Customer Service Policies* → Replacements — the post-30-day line now reads as
  the rep's own call within budget, replacing "consult with your manager before acting."
- *How To: Returns/Replacements/Refunds* → Refund Policy — a cross-reference to the budget
  placed directly after the SOP's own "use your judgement and try to keep Americanflat
  profitable" line, which is where a rep is standing when they need the number.

Changed here as a result:

- **Standing overrides table is now empty** and both entries recorded as retired. The
  section stays as the mechanism for future decisions that outrun the SOP text.
- Snapshot last-edited dates for both pages moved to 2026-08-17.
- `policies.md` gained the new Rep Discretion section and its post-30-day entry now
  mirrors the live Notion wording instead of annotating an override against it.
- The "Notion has not caught up" warnings in `escalation.md`, `policies.md`, and
  `judgment-and-empathy.md` are gone — they were true for about an hour.

- **⚠ New caution recorded in `sources.md`:** editing Notion through the MCP round-trips
  the page's markdown and can mangle untouched text nearby. A literal `$________`
  placeholder in the Refund Process steps collapsed to `$__` as a side effect of an
  unrelated edit on the same page; caught on verification and restored. After any write to
  a Notion SOP, re-fetch and diff the whole page, not just the part you changed.

## 1.3.0 — 2026-08-17

Resolves the collision 1.2.0 surfaced: **the $200 budget overrides the post-30-day
manager gate** (Anthony, 2026-08-17). A post-30-day replacement is now ordinary rep
discretion — if it fits the month's budget, the rep decides and acts without checking.
Escalation applies only for the reasons any discretionary spend escalates: over budget,
month spent, or a pattern of repeat claims.

Minor rather than patch because this changes what the skill tells a rep to do — one
fewer escalation on a scenario that comes up often.

Updated in six places that still routed the rep to a manager: the decision-rules table in
`SKILL.md`, its drafting limits, the stop-and-ask table and collision note in
`escalation.md`, the hold-firm signals and budget scope in `judgment-and-empathy.md`, the
never-draft list in `reply-templates.md`, and the Replacements section of `policies.md`.

- **New: *Standing overrides* register in `references/sources.md`.** The reason this needed
  more than an edit — the Notion SOP still reads "consult with your manager before acting.
  This is not a rep-level call." Anyone refreshing the snapshot would re-import that line
  and silently reverse the decision, with nobody noticing. The register lists every
  decision that supersedes live SOP text, and the refresh procedure now requires walking it
  after every re-import. A refresh that quietly restores a superseded rule is worse than a
  stale snapshot.
- **The SOP quote is preserved, not rewritten,** in `policies.md` — the snapshot stays a
  faithful record of what Notion says, with the override marked inline against it. Editing
  the quote would have made the snapshot lie about its source.
- Best fix remains updating the Notion page itself so the override can be retired; flagged
  in both `sources.md` and `escalation.md`.

## 1.2.0 — 2026-08-17

Fills the authority gap 1.1.0 flagged: **$200 per agent per month** of discretionary
spend (Anthony, 2026-08-17). The skill no longer escalates every step beyond prescribed
policy — within the pool the rep decides alone.

- **A monthly pool, not a per-ticket cap.** The rep paces it across the month. Roughly
  $46/week or $10/business day, so a steady trickle of small gestures fits comfortably; a
  single gesture over ~$75 eats a third of the month and is worth a second thought even
  though it's affordable.
- **Scope of the budget — the load-bearing decision.** It funds **discretion only**:
  waiving the 20% restocking fee, absorbing return shipping, a keep-it discount above the
  15–25% band, a replacement past day 30, a full refund where policy says store credit,
  goodwill with no policy basis. Remedies policy **already prescribes** never touch it —
  a replacement for a damaged item, keep-it under $50, the missing-accessory partial
  refund are normal cost of doing business. Had prescribed remedies counted, two
  damaged-frame replacements would exhaust a rep's month and they could not do their job.
  The budget buys judgment, not the baseline.
- **Answers the restocking-fee question outright:** yes, a rep may waive the 20% fee
  alone — $20 on a $100 order sits comfortably inside the pool.
- **When the budget is spent, warmth doesn't run out.** Prescribed remedies remain
  available (they were never coming out of the pool) and the whole empathy section still
  applies. Discretionary asks escalate as normal requests. The budget is an internal
  constraint the customer never hears about — no "I've used up my allowance."
- **Harmonized with the cost-of-remedy bands.** Those bands describe posture on
  *prescribed* remedies; the budget is the authority for going *beyond* them. Previously
  the bands were the only guidance and could be misread as a spend limit.
- **⚠ Surfaces a new collision.** The SOP says a post-30-day replacement requires
  consulting a manager; the budget lists exactly that as rep-funded discretion. A spend
  limit doesn't dissolve a named process gate, so the working answer is: act if it's small
  and inside budget, keep the manager check otherwise. Needs a one-line decision from
  Anthony, and the SOP text should be updated either way. Recorded in `escalation.md`.
- **⚠ Tracking gap flagged.** Nothing tracks the discretionary tally automatically, so it's
  a manual running count today — and an untracked budget becomes either unused or
  unbounded. A shared sheet of date / ticket / amount / reason would fix it and would feed
  the exception review.
- Two assumptions stated rather than buried: calendar month with **no rollover**, and
  **per agent** rather than a shared team pot.

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
