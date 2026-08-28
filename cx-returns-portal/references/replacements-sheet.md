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

| Columns | | Filled by |
|---|---|---|
| **A–P** | Original Order # · Channel · Reason · SKU · Qty · Ship To Name · Company · Street 1 · Street 2 · City · State · Postal Code · Country · Phone · Email · Notes | the form |
| **Q–V** | Status · SS Order # · Order Key · Submitted By · Submitted At · Message | **the automation** |

**The row stops at column P.** It does not emit trailing empty cells for Q onward:
pasting empties would write blanks over whatever the automation has put there, and
`Submitted By` / `Submitted At` are its columns too, not the form's.

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

## Multi-SKU replacements: one row per SKU

A replacement covering more than one SKU gets **one row per SKU**, with the
order-level fields repeated on each — same Original Order #, same address, same
Submitted By. Confirmed by Anthony, 2026-08-28.

The portal emits them together, so copying once and pasting once fills all the rows.
It shows the count above the preview so a three-SKU replacement is obviously three
rows before it goes in.

Note the activity log records the same replacement differently, as a single entry
with the items concatenated (`LX2430BLKNOMAT x1; LEDGE_BK14_3PK x2`). That is the
log's own format; it does not describe the Replacements tab.

## Verifying it worked

The automation writes back `Status`, `SS Order #` and `Message`. Once it has,
`scripts/confirm_940.py <SS Order #>` checks whether the order actually reached the
warehouse as an EDI 940 — the sheet saying `CREATED` means ShipStation accepted it,
not that the 3PL was told.

## Step 3 fills itself from the paste

The reply pasted into step 1 is read for everything the row needs, so step 3
opens already filled in rather than empty. What gets read:

| Field | Read from |
|---|---|
| Ship To Name | the line above the street, when it reads like a person's name; or a `Customer:` / `Ship to:` label |
| Street 1 / Street 2 | a line starting with a house number, or ending in a street word (`Lane`, `Blvd`, `Ct`…). `Apt`/`Suite`/`Unit` lines go to Street 2 |
| City · State · Postal Code | `Fredericksburg VA 22407`, `Fredericksburg, Virginia, 22407`, and `Edmond, OK, 73012` all work — full state names are converted to the two-letter code |
| Country | `United States` / `USA` → `US`, `Canada` → `CA` |
| Phone | a 10-digit number (or `+1` and 10). A 10-digit run inside a longer number is treated as a tracking number, not a phone |
| Email | the first address that isn't ours or a warehouse's |
| Channel | a channel named in the text, otherwise inferred from the marketplace — always one of the sheet's own values |
| Reason | "wrong item"/"sent the wrong…" → **Wrong Item Sent**; "damaged"/"broken"/"cracked"/"dented" → **Damaged in Transit** |
| Pick mode | "loose units", "individual", "piece pick" → loose; "full case", "sealed carton" → carton |

Commas and newlines are treated the same way, so a one-line address typed into a
ticket parses like a block address pasted from Shopify.

**Hand edits win.** Anything typed into a field is remembered as touched, and a
later re-paste will not overwrite it. Only still-empty fields get filled. Anything
the paste didn't cover stays blank and is flagged by the same missing-field check
as before — autofill removes typing, not the review.
