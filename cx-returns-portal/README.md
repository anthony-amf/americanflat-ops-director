# skill-cx-returns-portal

Turns a customer complaint into the right warehouse action — returns, reships and
replacements — for the Americanflat CX team.

## What it does

CX pastes a Zendesk ticket, or drags in screenshots of the Shopify order and the
ticket. The skill reads them into structured fields, works out which of seven cases
it is, routes it to the correct 3PL, and produces one of two things:

- **A row for the Replacements sheet** — for reships and damaged-on-arrival. An
  automation reads that tab and creates the ShipStation order; this skill does not
  connect to ShipStation.
- **A warehouse email in the house format** — for the cases that ask a question:
  missing units, an unshipped balance, tracking, return disposition.

Then it confirms, via Stedi, that the 940 actually reached the warehouse. A healthy
ShipStation order is not proof the 3PL was told.

There is also a self-serve web portal for teammates without a Claude session.

## What it will not do

- **Send anything by itself.** Emails are drafted for a person to send, and the
  sheet row is copied for a person to paste. Both start physical work at a 3PL.
- **Place the replacement order for you.** CX raises the `RS` order; this tells the
  warehouse it exists.
- **Pass customer contact details to the 3PL.** Email addresses and phone numbers
  are detected and withheld — the warehouse has no need for them.
- **Guess a warehouse.** If the site is ambiguous it asks, because a misrouted
  request costs a day on an order where the customer is already unhappy.

## Setup

The replacement flow needs no credentials — it produces a row you paste into the
sheet. `STEDI_API_KEY` is needed only by `scripts/confirm_940.py`, and
`scripts/lookup_order.py` reads BigQuery.

Read `references/replacements-sheet.md` before the first run. It has the column map,
the Channel → store lookup, and one open question about how multi-SKU replacements
are recorded.

## Layout

| Path | |
|---|---|
| `SKILL.md` | The workflow Claude follows |
| `references/warehouses.md`, `routing.json` | Who to contact at each 3PL |
| `references/templates.md` | The seven email templates |
| `references/playbook.md` | Which case to send, given what the customer said |
| `references/screenshots.md` | Reading a Shopify order and a Zendesk ticket |
| `references/replacements-sheet.md` | The replacement flow and the sheet's columns |
| `references/edi-940.md` | The verified 940/945 map |
| `references/data-sources.md` | What BigQuery can and cannot answer |
| `scripts/` | Order lookup, 940 confirmation, portal build, tests |
| `retired/` | The superseded direct-ShipStation path, kept for its research |
| `portal/` | The self-serve web portal |
