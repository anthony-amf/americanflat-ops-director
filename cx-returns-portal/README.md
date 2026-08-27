# skill-cx-returns-portal

Turns a customer complaint into the right warehouse action — returns, reships and
replacements — for the Americanflat CX team.

## What it does

CX pastes a Zendesk ticket, or drags in screenshots of the Shopify order and the
ticket. The skill reads them into structured fields, works out which of seven cases
it is, routes it to the correct 3PL, and produces one of two things:

- **A replacement order created in ShipStation**, which transmits to the 3PL as an
  EDI 940 and becomes a pick — for reships and damaged-on-arrival.
- **A warehouse email in the house format** — for the cases that ask a question:
  missing units, an unshipped balance, tracking, return disposition.

Then it confirms, via Stedi, that the 940 actually reached the warehouse. A healthy
ShipStation order is not proof the 3PL was told.

There is also a self-serve web portal for teammates without a Claude session.

## What it will not do

- **Send or create without confirmation.** Emails are drafted; order creation is
  dry-run by default and `--send` makes the operator type the order number back.
  These start physical work at a 3PL and there is no undo.
- **Place the replacement order for you.** CX raises the `RS` order; this tells the
  warehouse it exists.
- **Pass customer contact details to the 3PL.** Email addresses and phone numbers
  are detected and withheld — the warehouse has no need for them.
- **Guess a warehouse.** If the site is ambiguous it asks, because a misrouted
  request costs a day on an order where the customer is already unhappy.

## Setup

Needs `SHIPSTATION_API_KEY` and `SHIPSTATION_API_SECRET` to create orders, and
`STEDI_API_KEY` to confirm the 940. Read from the environment only — never as CLI
arguments, which shell history keeps.

Read `references/cloud-reship-runbook.md` before the first run. Two inputs are still
unverified and are called out there: the create payload's field names, and the
`warehouseId` that decides which 3PL receives the 940.

## Layout

| Path | |
|---|---|
| `SKILL.md` | The workflow Claude follows |
| `references/warehouses.md`, `routing.json` | Who to contact at each 3PL |
| `references/templates.md` | The seven email templates |
| `references/playbook.md` | Which case to send, given what the customer said |
| `references/screenshots.md` | Reading a Shopify order and a Zendesk ticket |
| `references/edi-940.md` | The verified 940/945 map |
| `references/data-sources.md` | What BigQuery can and cannot answer |
| `scripts/` | Order lookup, order creation, 940 confirmation, CSV fallback, tests |
| `portal/` | The self-serve web portal |
