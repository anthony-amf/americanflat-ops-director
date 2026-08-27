---
name: cx-returns-portal
description: >-
  Turns a pasted customer complaint into a correctly-formatted warehouse email for
  returns, reships and replacements at Americanflat. Use this skill when a CX or Ops
  teammate pastes customer/order details and wants the warehouse notified — phrases
  like "customer says their order arrived damaged", "need a reship for this order",
  "send this to the warehouse", "customer is missing items", "draft the WH email",
  "replacement order for #24074", "process this return", "open the returns portal",
  or when they paste a Gorgias/Shopify/marketplace message about a damaged, missing,
  short-shipped, wrong or undelivered order. Parses the paste into structured fields,
  picks the case type, routes to the right warehouse (Fontana / New Jersey /
  South Carolina / Yusen Canada / Yusen NL), and produces a Gmail draft in the house
  format. Never sends without explicit confirmation.
---

# CX Returns, Reships & Replacements

## What this does

A CX teammate hands over whatever they have — most often **two screenshots, one of
the Shopify order and one of the Zendesk ticket** — and this skill turns it into the
**exact warehouse email the Ops team already sends**, with the right recipients, the
right subject line, and the right body, left as a Gmail draft for a human to send.

Two ways to use it:

- **In Claude** (this skill) — drag the screenshots in, or paste the text, and get a
  Gmail draft. This is the main path: Claude reads images directly, so nothing has to
  be retyped, and the Zendesk thread comes along as context for free.
- **In the portal** (`portal/cx-returns-portal.html`, published as an Artifact) —
  a self-serve web page for teammates without a Claude session
  (https://claude.ai/code/artifact/79ea6e85-567c-4b07-ba7a-c91fd58bf7f3). Paste text
  on the left, the finished email appears on the right, one click copies it into
  Gmail. **The portal is text-only** — a published page has no way to read an image,
  so screenshots go to Claude, not to the portal.

Both produce identical output because both read from `references/templates.md` and
`references/warehouses.md`.

## The one hard rule

**Never send a warehouse email without the operator explicitly confirming that
exact draft.** Create the Gmail draft, show the operator the To / Cc / Subject /
Body in full, and wait. "Draft it" is not "send it." These emails go to an
external 3PL partner and set off physical work in a warehouse.

Two things are also never done automatically:

- **Never promise the customer a refund, credit, or dollar amount.** This skill
  moves goods, not money. Refund decisions belong to whoever owns the marketplace account.
- **Never place the replacement order.** CX places the `RS` order in Shopify/the
  marketplace first. This skill *notifies the warehouse that it exists*. If the
  operator hasn't placed it yet, say so and stop — an email about a PO the
  warehouse can't find just creates a confused reply thread.

## Workflow

### 1. Read the input

**Have the order number? Look it up first.**

```bash
python3 scripts/lookup_order.py 22397
```

That returns the SKUs and quantities exactly as ordered, straight from BigQuery
(~20 minutes behind Shopify), which removes the field most often mistyped. It
deliberately does **not** answer three things — the warehouse, the tracking number,
and whether the order is partially fulfilled — because none of them are in BigQuery.
`references/data-sources.md` has the evidence for each. Take those from the Shopify
screen, and the affected quantity from Zendesk.

**Screenshots are the normal case.** Read `references/screenshots.md` before
extracting — it maps the field landmarks in both UIs and, more importantly, the two
traps that produce wrong emails: Shopify's `× 2` is the quantity *ordered* (the
missing quantity comes from the Zendesk ticket), and an order with two fulfillments
may simply have had one parcel arrive late rather than a short-pick.

Split of duties between the two screenshots:

- **Shopify** — order number, SKUs, tracking, and the fulfillment **Location**, which
  is how you know the warehouse.
- **Zendesk** — what the customer actually says is wrong, and **how many units**.
  Never put the Zendesk ticket number in the warehouse email; the warehouse can't
  search it.

If only one screenshot arrives, work with it and ask for what's missing. A Shopify
screenshot alone can't tell you what the customer is complaining about; a Zendesk
screenshot alone usually can't tell you the warehouse.

Whatever the input, extract the same fields. Nothing is required except the order
number — ask only for what the chosen case type actually needs.

| Field | Looks like | Notes |
|---|---|---|
| `order_number` | `#22562`, `AMS*24124`, `AME*25162`, `4765465595-A` | Shopify orders are bare 5-digit; NJ prefixes `AME*`, SC prefixes `AMS*` in the WMS |
| `customer_name` | `Liam Ohea` | |
| `marketplace` | Shopify, Amazon DF, Amazon VC, Walmart 1P, Target, Michaels, Macy's, Wayfair, Faire, Kohl's | Drives the subject line wording |
| `skus` | `MW0808WH44 x 1` | AF style codes; keep the exact casing |
| `tracking` | `525499496652`, `9302210663600002221607` | FedEx = 12 or 15 digits; USPS/Stamps = 20–22 |
| `issue` | damaged / missing units / wrong item / not delivered / short-ship / bad tracking | From the Zendesk thread; maps to the case type |
| `warehouse` | Fontana / NJ / SC / CA / NL | Shopify fulfillment location; **confirm if unsure** |

Then **restate what you extracted** in a few lines the operator can correct in one
reply, before you draft anything. Getting a SKU wrong sends the wrong product to a
customer who is already unhappy.

If the warehouse can't be determined confidently, ask. Sending a Fontana request to
the NJ team wastes a day and the customer is already unhappy.

### 2. Pick the case type

Seven real case types, each with a template in `references/templates.md`:

| # | Case type | When | Sends |
|---|---|---|---|
| 1 | **Reship — prioritize** | RS order already placed, needs to ship today | Prioritize request, full-carton **or** loose-unit |
| 2 | **Missing units investigation** | Order is **Fulfilled** and the customer came up short | Verification request |
| 3 | **Unshipped balance** | Order is **Partially fulfilled** — the rest was never released | Chase the balance |
| 4 | **Tracking verification** | Tracking invalid or never scanned | Tracking check |
| 5 | **Cancel replacement** | RS order no longer needed | Cancel request |
| 6 | **Return received at WH** | A return landed at the warehouse; restock or discard | Disposition instruction |
| 7 | **Damaged on arrival** | Product arrived broken | Reship + quality flag |

**Check the Shopify fulfillment status before choosing between 2 and 3.** A customer
saying "I only got 2 of 8" reads identically in Zendesk whether the warehouse
short-picked or the balance was never released — only the Shopify `Unfulfilled (n)`
card tells them apart, and sending the wrong one of the two costs a day.

Cases 1 and 2 very often go together: the replacement ships **now** (case 1) while
the short-ship investigation runs in parallel (case 2). When the paste describes a
short-ship and a replacement is warranted, offer both as two separate emails —
that is how the Ops team actually works it.

### 3. Number the replacement order

**Replacement orders are the original order number with `RS` appended.**
`22562` → `22562RS`. `24074` → `24074RS`. No dash, no space, uppercase.
This convention is load-bearing — the warehouse searches on it, and Ops uses the
suffix to separate replacement volume from normal volume in the 3PL invoice audit.

### 4. Route it

Recipients come from `references/warehouses.md`. `NYC_Ops@americanflat.com` is
**always** on Cc — it is the shared Ops mailbox and the reason anyone else can pick
up a thread. Never drop it.

### 5. Build the subject line

House format, matched exactly:

```
AMF x TS <Warehouse> <Marketplace> Order #<number> – <Topic>
```

Real examples from live threads:

- `AMF x TS Fontana Request to Prioritize Replacement order # 22562RS`
- `AMF x TS Fontana Shopify PO #22397 – Missing Units Verification`
- `AMF x TS South Carolina Shopify Order #24074 – Missing Quantity`
- `AMF x TS South Carolina Shopify Order #24124 – Tracking Verification`
- `AMF x TS South Carolina Request to Cancel 24074RS`

Note the en dash (`–`), not a hyphen, before the topic. Yusen Canada and NL drop
the `TS` (they are not Taylored Services sites): `AMF x Yusen Canada – ...`.

### 6a. Replacement? Build the CSV instead of an email

For the two cases that **create a shipment** — a reship and the replacement half of
a damaged-on-arrival — don't email the warehouse asking them to place an order.
Build the ShipStation import CSV and load it: the warehouse picks from ShipStation,
so an imported order becomes work without anyone reading an email.

```bash
python3 scripts/build_reship_csv.py 22397 --sku "MW1114WH57:6" \
  --name "Sarah Whitfield" --address1 "1842 Larkin St" --address2 "Apt 4" \
  --city "San Francisco" --state CA --postal 94109 \
  --reason "damaged on arrival" --pick units --out reship-22397RS.csv
```

Item names come from BigQuery automatically. **The street address does not** — it
isn't in BigQuery at all, so copy it off the Shopify order screen. The portal has
the same output on its ShipStation CSV tab.

Read `references/shipstation-csv.md` before the first real import: the column
headers have not yet been validated against a live ShipStation import, and the file
is a draft until someone does one test load.

Everything else stays an email. A CSV creates a shipment; it cannot ask what
physically shipped, when the balance will allocate, or whether to restock a return.

### 6b. Draft it

Use `mcp__Gmail__create_draft`. Show the operator the complete draft. Wait for
confirmation before `mcp__Gmail__send_message`.

Body rules that make these emails work:

- **Lead with the ask.** First line says what you want done, not background.
- **State the deadline plainly** — "by EOD today", "by 8/25". Warehouses triage on it.
- **One order per email** for customer-facing issues. Batch only for the daily
  shorted-orders sweep, which is a different workflow and not this skill's job.
- **Ask for tracking back** on every reship. CX cannot close the ticket without it.
- **Say how it should be picked.** A reship goes out either as a full sealed master
  carton or as loose individual units, and the warehouse follows whichever line you
  send. Full carton for a short-shipped set; loose units for one damaged piece out of
  a bigger order. A loose pick must list the SKUs and quantities or it can't be
  actioned.
- **Say the customer is unhappy when they are.** It moves things. Don't overuse it.
- Sign as the sending teammate, not as John, unless John is the one sending.

## Refreshing the portal

The portal is a single self-contained HTML file, generated by
`scripts/build_portal.py`, which reads the routing table and templates out of
`references/` so the two can't drift:

```bash
cd cx-returns-portal && python3 scripts/build_portal.py
```

Then republish it as an Artifact **passing the existing `url:`** so it updates in
place instead of minting a duplicate. The stable URL is recorded at the top of
`portal/README.md`.

## When warehouse contacts change

They do — Don Kistner's address changed in August 2026, and CSR staffing rotates.
Contacts in `references/warehouses.md` were verified against live threads on
**2026-08-24**. If a warehouse replies from a new address or an email bounces,
update that file *and* re-run `build_portal.py`, or the portal will keep sending
to the dead address.

## Files

- `references/warehouses.md` — routing table, contacts, escalation paths
- `references/routing.json` — the same contacts, machine-readable; what the portal reads
- `references/screenshots.md` — how to read a Shopify order and a Zendesk ticket
- `references/data-sources.md` — what BigQuery can and can't answer, with evidence
- `references/shipstation-csv.md` — the reship CSV, and why its headers need a test import
- `references/shipstation-csv.json` — the CSV column map; edit here, not in the code
- `scripts/build_reship_csv.py` — order + SKUs + address → ShipStation import CSV
- `scripts/shipstation_probe.py` — read-only API probe; **Mac only**, cloud is blocked by policy
- `scripts/lookup_order.py` — order number → SKUs and quantities from BigQuery
- `references/templates.md` — the seven email templates, verbatim
- `references/playbook.md` — decision rules: reship vs. investigate vs. return
- `scripts/build_portal.py` — regenerates the portal HTML from `routing.json`
- `scripts/test_portal.mjs` — browser tests over five real case shapes
- `portal/cx-returns-portal.html` — the built portal (generated; don't hand-edit)
- `portal/README.md` — the live URL and how to republish it

`warehouses.md` and `routing.json` hold the same contacts in two forms. Change both;
`build_portal.py` warns when an address is in one and not the other.
