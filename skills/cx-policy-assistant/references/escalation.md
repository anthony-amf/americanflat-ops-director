# Escalation and routing — who owns what

Compiled from the CX Policies, Zendesk, Returns/Replacements/Refunds, and Wholesale
SOPs. Snapshot **2026-08-17**.

Named people are as recorded in the SOPs; roles are more durable than names, so if a
name looks out of date route by role and tell the rep to confirm.

---

## Stop and ask before acting

These are **not** rep-level decisions. Draft a holding reply, don't resolve.

| Situation | Who decides |
|---|---|
| Problem reported **after the 30-day window** | **The rep decides** — no manager check needed, if it fits the $200 budget. Anthony's 2026-08-17 decision supersedes the SOP's "consult your manager" line. Escalate only if it exceeds the budget or the month is spent |
| A judgement call on an unusual or high-value case | **Senior management** — the SOP's own instruction is "when in doubt, ask help from senior management" |
| The specific deduction to apply on a contested return (flat $5 vs. actual postage) | **Manager** — the SOPs conflict, see `returns-refunds.md` |
| Which return-label process to follow | **Manager** — three SOPs disagree, see `returns-refunds.md` |
| Wholesale **unit pricing** | **Angela** (pricing approval); initial review uses 10% off AMZ List Price |
| Anything committing money outside the standard remedies | **Manager** |

**Rep spend authority: $200 per agent per month** (Anthony, 2026-08-17). A monthly
discretionary pool, not a per-ticket cap. It funds goodwill *beyond* prescribed policy;
remedies policy already prescribes for the situation don't touch it. Within the pool the
rep decides alone — no escalation needed, including waiving the 20% restocking fee. Past
the pool, or once the month's budget is spent, a discretionary ask becomes a manager call.
Full scope, pacing, and tracking in the Authority section of `judgment-and-empathy.md`.

### Post-30-day replacements — the budget wins ✅

**Resolved (Anthony, 2026-08-17): the $200 budget overrides the manager gate.**

The SOP still reads *"we can send a replacement after the 30 days window for returns,
depending on the situation. Consult with your manager before acting."* That instruction is
**superseded.** A post-30-day replacement is now ordinary rep discretion: if it fits the
month's budget, the rep decides and acts, no manager check.

Escalate only for the reasons that apply to any discretionary spend — it exceeds the $200,
the month is already spent, or there's a pattern of repeat claims from that customer.

⚠ **The SOP text has not been changed in Notion.** Anyone refreshing this snapshot will
re-import the "consult your manager" line and silently reverse this decision. The override
is recorded in `sources.md` under *Standing overrides* — check that list on every refresh.
Better still, get the Notion page itself updated so the conflict disappears.

The standing instruction from the refund policy is worth quoting to the rep verbatim
when they're on the fence:

> Use your judgement and try to keep Americanflat profitable when making a decision.
> When in doubt, ask help from senior management.

## Route it to another team

| Inquiry | Goes to | How |
|---|---|---|
| Artist wants their artwork on our products | **Creative Director (Johnny Picardo)** | Assign the Zendesk ticket |
| Inventory levels / restock ETA | **Ops team (Receiving)**; check the Taylored Services portal first | Ask Ops |
| Inventory questions generally | **Taylored Services on-site employee** | — |
| Can this address still be updated? | **Taylored Services on-site employee** | Confirm before promising anything |
| Damage details for quality assurance | **Product development team** | Forward the photos and details |
| Marketplace replacement order | **Ops-Marketplace team** | Manual Order sheet, columns A–N |
| Order late and not yet shipped | **CS Slack channel** | Post in the channel's standard format |
| Wholesale shipping quote | **Ops (John Nuñez)** | Under ~50 units, Small Parcel Delivery is usually cheapest |
| Wholesale 300+ unit pricing approval | **Angela**, via the `cx-bulk-orders` Slack thread | Post order info and tag for approval |
| Tax-exempt wholesale purchase | **Finance** | Needs credit card authorization form, resale certificate, sales tax % confirmation |
| Return label creation (per the Apr-2026 SOP) | **Raul Sim** | ⚠ Conflicts with the May-2026 SOP — see `returns-refunds.md` |
| Return received at the warehouse | **Taylored Services warehouse contact** | Checks re-sellable condition, re-enters SKUs for resale |

## Route it back to the customer's marketplace

We don't own these. Say so kindly and point them the right way.

| Channel | Who handles returns/issues |
|---|---|
| **Shopify / americanflat.com** | **Us**, end to end |
| **Amazon — sold and shipped by Amazon** | Amazon support; we have no order detail |
| **Target, Wayfair (US & UK), Walmart, Etsy, eBay, Faire, Macy's, Michaels** | That marketplace's support. Returns go through them |
| **Any non-Shopify marketplace, order delayed** | The customer contacts that marketplace directly |

Where we're responsible for the **product** on a marketplace order (damage, defect), we
still replace it — via the Manual Order sheet — even though the return itself isn't ours.

**Answered inside the platform, not Zendesk:** Wayfair US & UK, Walmart, Amazon, Etsy
(help and support), eBay, Faire (help and support).

**Answered in Zendesk:** Shopify, some Amazon, Target, Bed Bath & Beyond, Facebook,
Instagram, phone calls, website live chat.

## Wholesale intake — route by order size

Full detail in **How to: Process Wholesale Orders** (`47cc57dd-5bd6-4bf3-be82-b8e6d2046cb0`,
last edited 2026-04-10). Inquiries arrive via the wholesale form on the website, reach CX
as a Tally form in Slack, and also land in Zendesk.

| Size | Path |
|---|---|
| **Under 100 units** | Refer to **Faire** (or Amazon). Template in `reply-templates.md` |
| **100–299 units** | Processed through **Shopify**: intro email → Ops shipping quote → add to the Wholesale Calculations Sheet → Angela approves unit price → create manual Shopify order → send invoice |
| **300+ units** | **Outside Shopify.** CX calls to qualify the customer → Amazon team for unit pricing, Ops for shipping → post in `cx-bulk-orders` Slack tagging Angela → Finance invoices → payment → Ops releases shipment |

Qualifying questions for a 300+ inquiry: what styles, sizes, and colors of frames are
they interested in?

Wholesale requests are tracked in the **Wholesale CRM** in Notion.

Note: the **100–299 process** is also the route used when a customer wants to keep a
duplicate item and pay for it — invoice them through Shopify.

## Never escalate — just don't respond

**Free products in exchange for a good review** (mostly Amazon). Policy is **no response
at all**. Don't decline politely, don't route it, don't explain. Leave it.
