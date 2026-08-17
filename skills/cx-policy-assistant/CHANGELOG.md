# Changelog

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
