# The portal

**Live:** https://claude.ai/code/artifact/79ea6e85-567c-4b07-ba7a-c91fd58bf7f3

A single self-contained page. CX pastes what the customer sent, picks the case type,
and copies a warehouse email that matches the format Ops already uses. All parsing
happens in the browser — nothing pasted leaves the page, and nothing is stored except
the sender's own name and title (kept in that browser only, so they don't retype it).

## Refreshing it

`cx-returns-portal.html` is **generated**. Don't hand-edit it — the next build
overwrites your change. Edit `../references/routing.json` (contacts, case list) or
`../scripts/build_portal.py` (templates, parsing, layout), then:

```bash
cd cx-returns-portal && python3 scripts/build_portal.py
```

Republish with the **same URL** so it updates in place instead of creating a second
artifact people can't find:

> Artifact tool → `file_path` = `cx-returns-portal/portal/cx-returns-portal.html`,
> `url` = the link above.

## Two outputs

- **Warehouse email** — for the cases that ask a question (missing units, unshipped
  balance, tracking, return disposition).
- **ShipStation CSV** — for the cases that create a shipment (reship, damaged). The
  file places the replacement order directly, so nobody has to read an email and
  key it in. Saving goes through the viewer's download prompt; if `.csv` isn't
  enabled for the view it falls back to `.txt`, and if saving isn't available at
  all it copies the CSV instead.

Headers for the CSV live in `../references/shipstation-csv.json` and are **not yet
validated against a real ShipStation import** — see `../references/shipstation-csv.md`.

## What it does not do

- **It does not send.** It produces the text; a human pastes it into Gmail and sends.
  That's deliberate — these emails start physical work at a 3PL.
- **It does not place the replacement order.** CX places the `RS` order first; the
  portal writes the email that tells the warehouse it exists.
- **It does not look up orders.** It reads only what you paste. Anything it can't find
  is left blank and flagged under "Before you send".

## Tested

Five real case shapes are covered by `scripts/test_portal.mjs` (short-ship, damaged
with an RS order, invalid tracking, an NL return with an unidentifiable barcode, and a
cancellation). It checks routing, subject format, that `NYC_Ops` is always on Cc, that
customer email addresses and phone numbers never reach the warehouse email, and that no
placeholder survives into a sendable draft.

```bash
npm install playwright-core
node scripts/test_portal.mjs
```
