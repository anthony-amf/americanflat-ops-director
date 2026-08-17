# Sources, freshness, and known SOP conflicts

Everything in this skill's reference files is a **snapshot taken 2026-08-17** of live
Notion SOPs. This file is how you check whether the snapshot is still true.

---

## Source pages

All CX SOPs live in the **SOPs** database in Notion
(data source `collection://2d14ea2d-a1ac-4127-aece-57b523f44043`, under the Company
Dashboard). Fetch a page with the Notion MCP tool `notion-fetch` using the ID below.

| Page | Notion page ID | Last edited at snapshot | Status |
|---|---|---|---|
| How To: Customer Service Policies | `0e07af7d-729e-4aac-8a04-ed88426c84e2` | 2025-10-07 | Live |
| How To: Returns/Replacements/Refunds | `1bcf13a0-15dc-41ae-a155-0b2894d5d3c1` | 2025-10-07 | Live |
| How To: Operate in Zendesk | `60797b21-c016-4d70-8d22-0502e58a1b07` | 2025-10-07 | Live |
| How To: Create Shipping Return Labels | `2fe8555c-2abc-8091-91f6-fea4436f034a` | 2026-05-25 | Live |
| How To: Get a Cost Estimation for a Return Shipping Label | `8d5336c1-d0bc-4433-9663-d4242ab2ff89` | 2026-04-28 | Live |
| How to: Process Wholesale Orders | `47cc57dd-5bd6-4bf3-be82-b8e6d2046cb0` | 2026-04-10 | Live |
| How To: Manual Shopify Order Process (USPS/UPS Ground Saver) | `1e38555c-2abc-8013-b71a-cb4696069d1e` | 2025-10-07 | Live |
| How To: Marketplaces Price Guideline | `d9e6b88c-ffba-40ac-8f3d-1523f80531f3` | 2026-04-10 | Live |
| CX: Customer Service *(voice/templates only)* | `19749ad7-8e83-4438-bfab-e60be99268ba` | 2022-08-11 | **Archived** |

The **Customer Service Policies** page (`0e07af7d…`) is the master policy document. When
two pages disagree on policy and dates don't settle it, that page governs.

**CX: Customer Service is archived.** Its reply templates are used in
`reply-templates.md` as the house voice, but never cite it as policy — its operational
content (which platforms use Zendesk, processing times) is superseded by the live pages.

## Owners

The four core CX SOPs share an owner and backup owner (Notion user IDs
`8e1810fd-ddcb-4509-9846-09f2e4ff2907` and `b9cfbc51-c842-488a-bc8c-63fb22cb5af5`),
Department: **Operations**, Category: **Customer Service**. The two label SOPs are owned
by `c03b30b0-1ac0-4d36-a1a5-1b084e8f95e4` under **Shipping**/**DTC**.

Send SOP corrections to the page owner rather than editing policy pages directly.

## When to verify live

**Always verify before quoting:**

- Any dollar amount ($50, $100, $5)
- Any percentage (20% restocking, 15–25% keep-it discount, 10% wholesale review)
- Any day count (30-day window, 12/24-hour SLA, 3–4 / 5–7 / 7–10 business days, 10-day
  lost-package window)
- Carrier and account specifics (FedEx account 110, Endicia/Stamps, ship-from warehouse)
- Named individuals in `escalation.md`

**Snapshot is fine for:**

- Whether we cancel, hold orders, take phone orders, ship accessories, send samples
- The remedy ladder (replacement → store credit → refund)
- Which channels route to Zendesk vs. their own platform
- Zendesk ticket statuses
- Tone and template wording

**If live Notion and the snapshot disagree: live Notion wins.** Say so to the rep so the
snapshot can be refreshed.

## Standing overrides — read before every refresh ⚠

Decisions Anthony has made that **supersede** what a live Notion page still says. The
Notion text has not caught up, so **a refresh will re-import the old rule and silently
reverse the decision** unless you re-apply the override.

| Override | Source page still says | Decided |
|---|---|---|
| **Post-30-day replacements are ordinary rep discretion** — no manager check when it fits the $200 monthly budget | *How To: Customer Service Policies* → Replacements: "Consult with your manager before acting. This is not a rep-level call." | Anthony, 2026-08-17 |
| **Rep spend authority is $200/agent/month** for discretion beyond prescribed policy | Nothing — the SOPs define no authority at all | Anthony, 2026-08-17 |

**On every refresh:** after re-importing a page, walk this table and re-apply each
override. A refresh that silently restores a superseded rule is worse than a stale
snapshot, because nobody will notice.

Best fix is to get the Notion pages updated so these entries can be retired. Until then
this table is load-bearing.

## Refreshing this snapshot

Re-fetch each page above, update the corresponding reference file, and update both the
snapshot date at the top of each file and the "last edited" column here. **Then walk the
Standing overrides table above and re-apply every entry.** Bump the minor version in
`skill.toml` and add a `CHANGELOG.md` entry.

Worth doing whenever a policy changes, and on a routine cadence regardless — the pages
carry no change notifications.

---

## Known conflicts

Real contradictions in the source SOPs. **Never resolve one silently.** Present the
newest page's answer as the working one, show the rep the other version, and tell them it
needs a manager's decision.

### 1. Who creates return labels — three answers

| Source | Edited | Says |
|---|---|---|
| Returns/Replacements/Refunds | 2025-10-07 | CX logs the request in the Replacement Orders sheet; someone else creates the label, uploads to Dropbox, CX emails the link |
| Cost Estimation for a Return Label | 2026-04-28 | CX must **never** create a label — "labels should only be requested from **Raul Sim**" |
| Create Shipping Return Labels | 2026-05-25 | **CX creates the label directly** in Stamps or FedEx |

Working answer: the **May-2026** page. Flag the disagreement.

### 2. Return carrier

- **Oct 2025:** "USPS is the preferred return carrier - purchased through Endicia."
- **May 2026:** Stamps (formerly Indicia) **or FedEx**, choosing the cheapest valid
  service.

Working answer: cheapest valid service per the May-2026 page.

### 3. Who pays return shipping on a Shopify return

- **Customer Service Policies:** order values over **$100** — Americanflat provides the
  label, cost deducted from the refund.
- **Refund Policy** (same date): customers pay return postage at their own expense, plus a
  **flat $5 return handling cost** when the return isn't our fault.

Reconcilable in spirit (the customer bears the cost either way), but the **$5 flat fee**
and **actual deducted postage** are different mechanics and neither page says which
applies. Don't quote a specific deduction without a manager's confirmation.

### 4. Restocking fee vs. handling cost

The 20% restocking fee (Shopify, personal-reason return) and the flat $5 handling cost
(returns not our fault) both apply to overlapping situations, and no SOP says whether they
stack. Assume they don't, and confirm before quoting a total.

### 5. Processing time — 3–4 days vs. 3–4 business days

The archived CX page says orders "usually take 3-4 days to process"; the live templates say
"3–4 business days." Use **business days** in customer-facing text — it's the safer promise
and matches the current templates.
