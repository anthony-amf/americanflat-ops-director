# The Replacements sheet

Replacements are recorded as a row in the **Replacements** tab of
[the replacements sheet][sheet]. An automation reads that tab and creates the
ShipStation order — this skill does not talk to ShipStation at all.

[sheet]: https://docs.google.com/spreadsheets/d/1OzF8inTsmtegKUWjWtbLLzdFTuI-Nba26jO8dY8Br9I/edit?gid=1268836353#gid=1268836353

## How a row gets there

The portal's **Replacement row** tab emits one tab-separated line per column, in
sheet order. Copy it, click the next empty row in the Replacements tab, and paste —
tabs make it land across columns. There is no API write: no Sheets write tool is
available here, and a paste needs no credentials and no permissions to maintain.

## The 22 columns

Structure read from the live sheet on 2026-08-28 and held in
`replacements-sheet.json`. **Column order is load-bearing** — a row pasted with the
wrong number of cells puts every later value under the wrong header.

| # | Column | Filled by |
|---|---|---|
| 1–16 | Original Order # · Channel · Reason · SKU · Qty · Ship To Name · Company · Street 1 · Street 2 · City · State · Postal Code · Country · Phone · Email · Notes | the form |
| 17–19 | Status · SS Order # · Order Key | **the automation** |
| 20–21 | Submitted By · Submitted At | the form |
| 22 | Message | **the automation** |

The four automation columns are emitted empty and shown greyed in the preview.
Filling them by hand risks colliding with whatever the script writes back.

## Channel decides the ShipStation store

The automation looks up a store from the Channel, so it has to be one of the
sheet's own values — free text will not resolve. From the sheet's config tab:

| Channel | Store | Channel | Store |
|---|---|---|---|
| Shopify | 438065 | Faire | 438066 |
| Wayfair | 438064 | Overstock | 438067 |
| Walmart | 438063 | Amazon · Target · Etsy · eBay · Other | 194231 |
| Macys | 438069 | Kohls | 438068 |
| Michaels | 438105 | | |

The portal shows the resolved store above the preview, so a wrong Channel is
visible before the paste rather than after the order exists.

## Reason

Only three values appear in the live data: **Wrong Item Sent**, **Damaged in
Transit**, **Other**. The dropdown offers those. If a case genuinely needs
something else, check what the automation accepts first — an unrecognised string
may not map to anything.

## Settings the sheet already holds

From its config tab, for reference — the form does not set these:

- Order number prefix `RPL` — the automation generates `RPL-<order>-<hash>`, e.g.
  `RPL-23280-2D1B9304`. Note this differs from the `<order>RS` convention the
  warehouse emails use; both exist, for different systems.
- Custom Field 1 tag `REPLACEMENT`, stamped for BigQuery filtering
- Default country `US`
- Require second approver: `FALSE`

## Open question: multi-SKU replacements

The tab has one `SKU` and one `Qty` column, and every row in it so far is a single
SKU. The activity log records multi-item replacements as one entry with the items
concatenated (`LX2430BLKNOMAT x1; LEDGE_BK14_3PK x2`), so how the Replacements tab
itself represents them is **unconfirmed**.

The portal currently emits **one row per SKU** with the order details repeated, and
says so in the preview when there is more than one. If the automation instead
expects a single row per replacement, that is a one-line change in
`sheetRows()` — confirm before the first multi-item replacement goes through.

## Verifying it worked

The automation writes back `Status`, `SS Order #` and `Message`. Once it has,
`scripts/confirm_940.py <SS Order #>` checks whether the order actually reached the
warehouse as an EDI 940 — the sheet saying `CREATED` means ShipStation accepted it,
not that the 3PL was told.
