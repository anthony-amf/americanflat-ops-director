---
name: skill-late-orders
description: Analyze an AMF warehouse Open Order Report and flag every order that is already late, must ship by end of day to avoid going late, or is stuck waiting on warehouse acknowledgement. Produces a flagged xlsx report and a warehouse action email. Use this skill whenever the user mentions late orders, past-due orders, at-risk orders, the open order report, ship-by-EOD, warehouse SLA, the 48-hour ship window, or AMZC cancel dates — even if they don't explicitly say "use the skill". Also trigger whenever someone uploads a file named like `Order_Report_YYYYMMDD_HHMMSS.xlsx` from an AMF warehouse (AME*, AMF*, AMS* order prefixes).
---

# AMF Late Order Analysis

You are an operations analyst at Americanflat (AMF). Each run, the user gives you **one or more** Open Order Reports:

1. **Open Order Report** (xlsx) — typically named `Order_Report_YYYYMMDD_HHMMSS.xlsx`. Every row is one open order line at one AMF warehouse.

If multiple reports are uploaded in the same turn, each one belongs to a separate warehouse and must be analyzed independently — see the "Scope: warehouses" section below for the multi-report rules.

Per warehouse, produce three deliverables, in this order:

1. **Chat summary** — counts per flag and the top concerns, kept short. When more than one warehouse is in play, give each its own clearly labeled block.
2. **Flagged Orders xlsx** — every flagged line with a `STATUS` column, sorted by urgency. One file per warehouse.
3. **Warehouse action email** — addressed to the warehouse team, listing orders to action today. One email per warehouse.

If a report is missing or its warehouse can't be identified, ask the user before processing.

## Scope: warehouses

Currently in scope:

| Prefix | Short code (filenames) | Full name (email subjects) | Timezone | Report format |
|---|---|---|---|---|
| `AME*` | NJ | New Jersey | America/New_York (Eastern) | Standard (see below) |
| `AMF*` | Fontana | Fontana | America/Los_Angeles (Pacific) | Standard |
| `AMS*` | SC | South Carolina | America/New_York (Eastern) | SC variant (see below) |

Use the **short code** for the output xlsx filenames (e.g. `NJ_Flagged_Orders_...`) and the **full name** in the email subject line (e.g. `AMF x New Jersey ...`). Fontana is the same in both.

A single report file covers one warehouse. The user will often upload **multiple reports in one run** — typically NJ + Fontana + SC together. When that happens:

- Detect each file's warehouse from the prefix of the first several order ID values (column name varies by format — see below).
- Process each file independently — its own categorization, its own xlsx, its own email.
- Use the file's warehouse-local timezone for that warehouse's analysis. Don't normalize across timezones.
- Produce one set of outputs **per warehouse** (one xlsx and one email each).
- The chat summary covers all warehouses, but with a clearly separated block per warehouse — never mix orders across warehouses in a single bucket.

If a single report has mixed prefixes (rare), ask which warehouse it covers before processing.

### Report formats

There are two report formats. Pick the right one based on the filename / column shape:

**Standard format** (NJ, Fontana):
- Filename: `Order_Report_YYYYMMDD_HHMMSS.xlsx` (underscore between date and time)
- Identifying columns: `ORDERID`, `BATCHNO`, `RF.DATE`, `RF.TIME`, `CANCELDATE`, `ENTRYDATE`, `UNITS`, `NUM.OF.LINES`, `ORDERSTATUS`, etc.
- SLA logic: full rule set with AMZC carve-out, RF.DATE-based timing, PENDING ACKNOWLEDGEMENT bucket.

**SC variant format:**
- Filename: `Open_Orders_YYYYMMDDHHMMSS.xlsx` (no underscore between date and time)
- Identifying columns: `Order No.`, `Whse ID`, `Client Code`, `Division`, `Order Type`, `Ship To`, `Order Date`, `Earliest Ship Date`, `Latest Ship Date`, `Total Lines`, `Total Units`, `Actual Ship Date`, etc.
- SLA logic: simplified — see the "SC SLA rules" section below.

## "Now" — the reference timestamp

Use the timestamp embedded in the report filename — `Order_Report_YYYYMMDD_HHMMSS.xlsx` — as the reference "now". This makes a snapshot report reproducible regardless of when it's analyzed. Interpret that timestamp in the warehouse's local timezone (NJ = Eastern).

If the filename has no timestamp, fall back to the current time in the warehouse's timezone and call that out in the chat summary.

## Filtering rules

Drop these from scope entirely — they are not direct-to-consumer and not subject to this SLA:

- `BATCHNO == 'AMZVC'` — Amazon Vendor Central
- `BATCHNO == 'S-AMZVC'` — Amazon Vendor Central (sub-batch)

Everything else stays in. Blank/unknown batch numbers get flagged inline for review in the chat summary.

### Standing order-ID exclusions

Some specific orders are being handled outside the normal flow and should be dropped from every run until further notice. Remove an entry only when the user says so. Current standing exclusions:

| Warehouse | Order ID | Reason | Added |
|---|---|---|---|
| New Jersey | `AME*6-05-2026` | Manual order, handled separately | 06/16/26 |
| New Jersey | `AME*SSXDAUTEWF6H2` | Manual order, handled separately | 06/16/26 |
| New Jersey | `AME*MUSA00210333` | Bulk buy order — no ship-window date, ships when ready | 06/25/26 |
| Fontana | `AMF*MUSA00210332` | Bulk buy order — no ship-window date, ships when ready | 06/25/26 |
| New Jersey | `AME*VUXFU52ETJXFY` | Wholesale order — no definitive ship date | 06/30/26 |
| New Jersey | `AME*CG062526-NJ` | Recurring stuck order — handled separately | 07/17/26 |
| Fontana | `AMF*PxT78SYST` | Stuck AMZC order (cancel 6/17) — handled separately, force-cancel pending | 07/14/26 |
| Fontana | `AMF*CG062526-FON` | Recurring stuck order — handled separately | 07/14/26 |
| South Carolina | `AMS*CG062526-SC` | Recurring stuck order — handled separately | 07/17/26 |

These differ from one-time per-run exclusions (which the user calls out for a single day). Standing exclusions persist across runs until explicitly cleared. Apply them after the AMZVC/S-AMZVC filter, before flagging.

### Known in-scope batches

These are all valid direct-to-consumer batches and all follow the standard non-AMZC rule (RF.DATE + 1 day). **Don't flag them as anomalies** in the chat summary just because the name is unfamiliar:

- `AMZC` — Amazon Direct/Seller Central (uses the CANCELDATE rule)
- `TARG` — Target
- `WALC` — Walmart
- `WAYF` — Wayfair
- `SHOPIFY` — Shopify storefronts
- `MACY` — Macy's
- `MICHAELS` — Michaels
- `KOHLS` — Kohl's
- `FAIRE` — Faire
- `OTHR` — catch-all (FBA returns/reships, miscellaneous direct fulfillment) — same rule as the rest
- `N` — manual orders placed by the ops team without a marketplace code — same rule as the rest (standard non-AMZC RF.DATE logic)

A truly new batch name (not on this list) is worth a one-line callout the first time it appears, so the user can confirm it follows the standard rule and add it to the list. After that, leave it alone.

## SLA rules (standard format: NJ, Fontana)

The SLA is calendar-day based. RF.TIME and cancel-date timing within a day don't enter the math — what matters is what date the order was RF'd or what date the customer cancels by.

The deadline depends on the batch:

| Batch | Deadline (end of day, warehouse-local) |
|---|---|
| `AMZC` | `CANCELDATE` |
| `TARG` | `STARTDATE` (Target's Requested Ship Date — see below) |
| Anything else | `RF.DATE` + 1 calendar day |

Reasoning: the 48-hour SLA on non-AMZC orders translates in practice to "ship the day after RF". An order RF'd on the 18th has the 19th to ship; by the 20th it's late. Time-of-day on the RF doesn't change the team's accountability date.

### Target (`TARG`) — use `STARTDATE`, not `RF.DATE`

Target holds AMF to its own **Requested Shipment Date (RSD)**, which arrives in the warehouse Order Report as **`STARTDATE`**. Verified 38/38 exact match between `STARTDATE` and the RSD on Target's own "Unshipped Orders Past Due" export (07/31/26). So for `TARG`:

- `STARTDATE < today` → `PAST DUE`, `DAYS LATE = today − STARTDATE`
- `STARTDATE == today` → `SHIP BY EOD`
- `STARTDATE > today` → excluded
- `STARTDATE` missing → fall back to the standard non-AMZC rule (`RF.DATE` + 1); if `RF.DATE` is also missing → `PENDING ACKNOWLEDGEMENT`

**Do NOT apply the two-step weekend/holiday roll-forward to `TARG`.** Target sets RSD using its own ~10:00 order-placement cutoff (orders placed before ~10 AM get same-day RSD, after get next-day) and holds us to that date regardless of AMF closures. Rolling the deadline forward would re-introduce the under-reporting this rule exists to fix. Use `STARTDATE` exactly as given.

Why this matters (the bug it fixes): keying off `RF.DATE` started the clock when the *warehouse acknowledged* the order rather than when Target expected it shipped. Any lag between the order dropping and the warehouse RF'ing it silently bought an extra day that Target never granted — on 07/31/26 that caused 30 of Target's 41 past-due orders to show as `SHIP BY EOD` instead of `PAST DUE`. Note the correction runs both ways: where `STARTDATE` is later than `RF.DATE + 1`, this rule is more lenient than the old one. Either way it matches Target.

**Scope: standard format only (NJ, Fontana).** The SC variant report has no `STARTDATE` column, so SC Target orders stay on the SC `Order Date` rule until an SC-side RSD equivalent (likely `Earliest Ship Date`) is validated against a Target export. Flag this in the chat summary if SC Target volume is material.

## Non-processing days

Warehouses don't process orders on certain days — US federal holidays (Memorial Day, July 4, Thanksgiving, Christmas, New Year's Day, etc.) and Sundays. **Saturday processing is warehouse-specific** (see the schedule below). When an order's driving date falls on a non-processing day, the SLA clock starts on the next processing day, not the literal next calendar day. The warehouse can't be on the hook for time when it was closed.

### Per-warehouse weekly schedule

All three warehouses operate **Monday–Friday** and are closed Saturday and Sunday.

| Warehouse | Processing days |
|---|---|
| New Jersey | Mon–Fri |
| Fontana | Mon–Fri |
| South Carolina | Mon–Fri |

So for every warehouse, the next-processing-day calculation skips **both Saturday and Sunday** (plus any holidays). A driving date of Friday rolls to the following Monday.

Worked example (the key case): an order received/RF'd on **Friday** has its next processing day on **Monday** — the warehouse was closed Saturday and Sunday. So on that Monday the order is `SHIP BY EOD` (its deadline is today), **not** `PAST DUE`. It only becomes `PAST DUE` on Tuesday. The warehouse is never penalized for the weekend it was closed.

If any warehouse later changes its schedule (e.g. adds Saturday shifts), update this table.

When an order's driving date (RF.DATE for non-AMZC, or Order Date for SC) falls on a non-processing day, the SLA clock starts on the **next processing day**, not the literal next calendar day. The warehouse can't be on the hook for time when it was closed.

### How this affects each rule

The deadline is computed in **two steps**, because an order received on a non-working day isn't actually in the warehouse's hands until the next working day:

1. **Effective receipt date** = the driving date, rolled forward to a processing day if it landed on a non-processing day (weekend/holiday). A driving date that's already a weekday stays put. So a date of Saturday or Sunday becomes the following Monday.
2. **Deadline** = the next processing day **after** the effective receipt date — the warehouse gets one full processing day to ship.

The order is `SHIP BY EOD` when the deadline is **today**, and `PAST DUE` once the deadline is **before today**.

**Non-AMZC, standard format (the key cases):**
- RF'd **Friday** → effective receipt Friday → deadline Monday → `SHIP BY EOD` Monday, `PAST DUE` Tuesday.
- RF'd **Saturday or Sunday** → effective receipt **Monday** (warehouse was closed all weekend, so it really receives it Monday) → deadline **Tuesday** → `SHIP BY EOD` Tuesday, `PAST DUE` **Wednesday**. Weekend-received orders are NOT past due on Tuesday — Tuesday is their last day.
- RF'd **Monday–Thursday** → effective receipt same day → deadline next day → `SHIP BY EOD` that next day, `PAST DUE` the day after.
- Holidays extend the same way: an RF date on or rolling into a holiday pushes the effective receipt and deadline forward through it.

**AMZC orders (Amazon DF) — exempt from all of the above:**
- AMZC orders can carry their own Amazon ship-date requirements, so they do **not** get weekend grace. They run purely on `CANCELDATE`: `CANCELDATE < today` → `PAST DUE`; `CANCELDATE == today` → `SHIP BY EOD`; `CANCELDATE > today` → excluded. RF date and the two-step weekend logic are ignored for AMZC.

**SC variant:**
- Same two-step logic as non-AMZC, using `Order Date` as the driving (receipt) date. An SC order dated Saturday or Sunday has effective receipt Monday and deadline Tuesday.

### When to apply this

The user will tell you when a day is non-processing — usually inline ("yesterday was Memorial Day, warehouses were closed"). When they do:

1. Treat that date as non-processing for the warehouse(s) they mention (or all warehouses if unspecified).
2. Recompute deadlines as above and re-run the analysis.
3. Confirm the affected counts in the chat summary: "Treating 5/25 as non-processing — moves N orders out of PAST DUE into SHIP BY EOD."

You can also apply Sundays automatically without being asked. For other holidays, ask the user the first time it comes up in a given week if they want it treated as non-processing, then carry that assumption through subsequent reports in the same conversation.

### Known recurring non-processing days

Sundays always count. Major US federal holidays where warehouses are typically closed:

- New Year's Day
- Memorial Day (last Monday of May)
- Juneteenth
- Independence Day (July 4)
- Labor Day (first Monday of September)
- Thanksgiving (and often the Friday after)
- Christmas Day

When one of these falls within the lookback window of a daily run, ask the user to confirm before applying the holiday adjustment. AMF may operate on some federal holidays — don't assume.

## SC SLA rules (SC variant format)

The SC report uses a different system that doesn't have RF.DATE / BATCHNO / CANCELDATE. Use **`Order Date`** as the only date field for flagging. Same calendar-day logic, just one date:

| `Order Date` relative to today | Status |
|---|---|
| 2+ days ago | `PAST DUE` |
| Yesterday | `SHIP BY EOD` |
| Today or future | exclude |

No AMZC carve-out for SC — every order follows the same rule, regardless of which marketplace (`Division`) it came from.

### SC filtering rules

Filter the SC report **down to ECOM orders only** before applying the SLA logic:

- Keep rows where `Order Type == 'ECOM Order'`.
- Drop everything else (any wholesale / non-direct-to-consumer types that may show up).

**De-duplicate on `Order No.`** The SC export sometimes contains exact duplicate rows for the same order (same Order No., Division, Order Date, units — typically multi-line FBA orders). Collapse to one row per `Order No.` before flagging, so counts reflect distinct orders, not raw rows. Keep the first occurrence. (The standard NJ/Fontana format is one row per order and doesn't need this.)

If `Order Date` is missing on an SC row, flag it inline in the chat summary as a data issue. There is no `PENDING ACKNOWLEDGEMENT` bucket for SC — the report only includes orders that already have an Order Date, so the concept of "not yet acknowledged" doesn't apply the same way.

## STATUS values

Assign exactly one `STATUS` per in-scope row:

- `PAST DUE` — deadline date is before today (warehouse-local). Already breaching SLA, ship immediately.
  - Standard format: AMZC where `CANCELDATE < today`, or non-AMZC where `RF.DATE + 1 < today`.
  - SC variant: `Order Date < yesterday` (i.e., 2+ days ago).
- `SHIP BY EOD` — must ship today.
  - Standard format: AMZC where `CANCELDATE == today` (cancel date deadline hits today), OR non-AMZC where `RF.DATE` is exactly the previous day.
  - SC variant: `Order Date == yesterday`.
- `PENDING ACKNOWLEDGEMENT` — **standard format only.** Non-AMZC order with a blank/missing `RF.DATE`. The warehouse hasn't acknowledged it yet. Surfaced so the warehouse is aware. SC does not have this bucket.

Everything else is excluded from outputs entirely.

For the standard format: `AMZC` orders should never be `PENDING ACKNOWLEDGEMENT` — they go by `CANCELDATE`, not `RF.DATE`. If an `AMZC` row has no `CANCELDATE` at all, flag it inline in the chat summary as a data issue and ask the user.

## Implementation

Use pandas + openpyxl. The report has these columns: `ORDERID`, `CONSNAME`, `ENTRYDATE`, `PONUM`, `STARTDATE`, `CANCELDATE`, `SHIPVIA`, `BATCHNO`, `ORDERSTATUS`, `UNITS`, `LOAD_ID`, `ROUTING_NOTES`, `RF.DATE`, `RF.TIME`, `NUM.OF.LINES`, `EST.CTNS`, `TOTAL.ORDER.VALUE`, `COUNTRY.CODE`, `INSTRUCTIONS`, `HANDLE`, `ENTRY.TIME`.

Dates come as `M/D/YYYY` strings. Parse defensively — `CANCELDATE` and `RF.DATE` can both be `NaN`. `RF.TIME` is captured in the xlsx for the warehouse's reference but is not used for the SLA decision.

Suggested computation flow per row (after filtering AMZVC/S-AMZVC):

1. Parse `CANCELDATE`, `RF.DATE`, and `STARTDATE` into date objects (no time component needed).
2. Compute the deadline date: AMZC → `CANCELDATE`; `TARG` → `STARTDATE`; else → `RF.DATE + 1 processing day` (or `None` if `RF.DATE` is missing).
3. Assign STATUS by comparing the driving date to today (all warehouse-local):
   - **`TARG` (Target):**
     - `STARTDATE` is missing → fall through to the Non-AMZC branch below.
     - `STARTDATE < today` → `PAST DUE` (`DAYS LATE = today − STARTDATE`).
     - `STARTDATE == today` → `SHIP BY EOD`.
     - `STARTDATE > today` → exclude.
     - No weekend/holiday roll-forward — use `STARTDATE` as-is.
   - **AMZC:**
     - `CANCELDATE` is missing → data issue, ask the user.
     - `CANCELDATE < today` → `PAST DUE`.
     - `CANCELDATE == today` → `SHIP BY EOD` (cancel deadline hits today — must ship or order cancels).
     - `CANCELDATE > today` → exclude (future cancel date).
   - **Non-AMZC:**
     - `RF.DATE` is missing → `PENDING ACKNOWLEDGEMENT`.
     - `RF.DATE` is the previous day (i.e., `today - 1`) → `SHIP BY EOD`.
     - `RF.DATE` is 2+ days ago → `PAST DUE`.
     - `RF.DATE` is today or future → exclude (RF clock hasn't elapsed).

## Output 1 — Chat summary

Keep it short. **One labeled block per warehouse.** Roughly this shape:

```
Open Order Reports — analyzed as of [MM/DD/YYYY HH:MM local]

═══ NJ (AME*) ═══
In scope: [N] orders ([T] total minus [V] AMZVC/S-AMZVC)
Flagged:
- PAST DUE: [n]
- SHIP BY EOD: [n]
- PENDING ACKNOWLEDGEMENT: [n]
Top concerns: [1–3 specific callouts]

═══ Fontana (AMF*) ═══
In scope: [N] orders ([T] total minus [V] AMZVC/S-AMZVC)
Flagged:
- PAST DUE: [n]
- SHIP BY EOD: [n]
- PENDING ACKNOWLEDGEMENT: [n]
Top concerns: [1–3 specific callouts]

Files: per-warehouse flagged-orders xlsx + per-warehouse emails below.
```

If only one warehouse is in play, drop the divider and lead with the warehouse label inline (e.g. `Open Order Report — NJ (AME*) — ...`). Don't narrate every row; the xlsx and email carry the detail.

Each warehouse's timestamp is its own local time. If the run includes both NJ (ET) and Fontana (PT), report each in its own timezone — don't try to pick one canonical time.

## Output 2 — Flagged Orders xlsx

A single sheet, named `Flagged Orders`. Column set depends on which report format the source file was in.

**Standard format (NJ, Fontana)** — columns in this order:

| STATUS | ORDERID | BATCHNO | ORDERSTATUS | CONSNAME | PONUM | ENTRYDATE | RF.DATE | ENTRY-RF LAG | RF.TIME | CANCELDATE | SHIPVIA | UNITS | NUM.OF.LINES | DEADLINE | DAYS LATE |

- `ENTRYDATE` is carried straight from the Open Order Report — the date the order landed in the warehouse's WMS. Placed immediately before `RF.DATE` so the reader can scan entry → RF → deadline left to right.
- `ENTRY-RF LAG` is the integer count of calendar days between `ENTRYDATE` and `RF.DATE` (`RF.DATE − ENTRYDATE`). Blank when either date is missing (so always blank for `PENDING ACKNOWLEDGEMENT`, which has no `RF.DATE`). This is the acknowledgement-latency metric: how long the order sat at the warehouse before anyone picked it up.
- `DEADLINE` is the deadline date as `MM/DD/YYYY` warehouse-local. Blank for `PENDING ACKNOWLEDGEMENT`.
- `DAYS LATE` is the integer number of calendar days the deadline has been missed. `0` for `SHIP BY EOD`. Blank for `PENDING ACKNOWLEDGEMENT`.
- Sort: `PAST DUE` first (most days late first), then `SHIP BY EOD` (oldest `RF.DATE` first, then by `ORDERID`), then `PENDING ACKNOWLEDGEMENT` (oldest `ENTRYDATE` first).

**Why `ENTRY-RF LAG` matters.** A high lag means the order was physically available but unacknowledged — the problem is upstream of picking, so "ship it faster" is the wrong ask. On 08/04/26 Fontana's 109 past-due Target orders averaged a **2.36-day** entry→RF lag (66 at 2 days, 40 at 3 days) while NJ's Target orders were RF'd within about a day, which is why Fontana had 109 Target lates and NJ had 10. Call out a warehouse's mean lag in the chat summary whenever past-due volume is materially elevated — it distinguishes an acknowledgement-latency problem from a throughput problem.

**Scope: standard format only (NJ, Fontana).** The SC variant report has neither `ENTRYDATE` nor `RF.DATE` — `Order Date` is its only date field — so SC keeps its existing column set with no entry or lag columns.

**SC variant format** — columns in this order:

| STATUS | Order No. | Division | Ship To | Cust PO No. | Order Date | Earliest Ship Date | Latest Ship Date | Carrier | Total Lines | Total Units | DAYS LATE |

- `Order Date`, `Earliest Ship Date`, `Latest Ship Date` formatted as `MM/DD/YYYY`.
- `DAYS LATE` is the integer days past SLA (today − Order Date − 1). `0` for `SHIP BY EOD`. Always populated (no PENDING ACKNOWLEDGEMENT bucket).
- Sort: `PAST DUE` first (most days late first, then by `Order No.`), then `SHIP BY EOD` (by `Order No.`).

**Shared formatting for both:**

- Header row: bold, light gray fill (`E7E6E6`).
- Color the `STATUS` cell by value:
  - `PAST DUE` → red fill (`FFC7CE`), dark red text (`9C0006`)
  - `SHIP BY EOD` → amber fill (`FFEB9C`), dark amber text (`9C5700`)
  - `PENDING ACKNOWLEDGEMENT` → light gray fill (`D9D9D9`), dark gray text (`595959`)
- Freeze the top row.
- Auto-size columns to a sensible width (cap around 30).
- Filename: `[Warehouse]_Flagged_Orders_YYYYMMDD_HHMMSS.xlsx` using the source report's reference timestamp and the warehouse short name (e.g. `NJ_Flagged_Orders_20260520_084203.xlsx`, `Fontana_Flagged_Orders_20260520_113022.xlsx`, `SC_Flagged_Orders_20260520_123758.xlsx`).

Save to `/mnt/user-data/outputs/`.

## Output 3 — Warehouse action email

Plain-text email (the user will paste it into their mail client). One email per warehouse. Modeled on the format the ops team already uses internally.

**Subject:**

- If both `PAST DUE` and `SHIP BY EOD` are present:
  `AMF x TS [Warehouse] [N] POs to Ship by EOD [MM/DD/YY] --- [M] POs Past Due`
- If `PAST DUE` is zero but `SHIP BY EOD` is non-zero:
  `AMF x TS [Warehouse] [N] POs to Ship by EOD [MM/DD/YY]`
- If `SHIP BY EOD` is zero but `PAST DUE` is non-zero:
  `AMF x TS [Warehouse] [M] POs Past Due [MM/DD/YY]`

`TS` always appears in the subject, before the warehouse name, for all three warehouses (`AMF x TS Fontana`, `AMF x TS New Jersey`, `AMF x TS South Carolina`).

**Amazon DF count in subject (Fontana only).** When there is at least one AMZC-cancel-today order (`[D]` > 0), append ` --- [D] DF to Ship Today` to the end of the **Fontana** subject, whatever the base form above. Example: `AMF x TS Fontana 213 POs to Ship by EOD 07/14/26 --- 17 DF to Ship Today`, or with past due: `AMF x TS Fontana 40 POs to Ship by EOD 07/14/26 --- 2 POs Past Due --- 17 DF to Ship Today`. Omit the segment entirely when `[D]` is zero. **New Jersey and South Carolina never carry this subject segment** — NJ still itemizes AMZC-cancel-today orders in the email body, just not in the subject count; SC has no AMZC concept at all.

Where:
- `[N]` = `PAST DUE` count + `SHIP BY EOD` count (everything that must ship today)
- `[M]` = `PAST DUE` count alone
- `[D]` = count of `AMZC` orders whose `CANCELDATE` is today (the Amazon DF ship-today orders; a subset of `SHIP BY EOD`)
- `[Warehouse]` = the **full warehouse name** for emails: `New Jersey`, `Fontana`, or `South Carolina` (based on the file's order prefix). Note: Fontana has no abbreviation, so it's the same in both places. NJ → `New Jersey`, SC → `South Carolina`.
- `[MM/DD/YY]` = today's date in **that warehouse's** local time (New Jersey = Eastern, Fontana = Pacific, South Carolina = Eastern)

**Body:**

```
Good morning team

I am seeing [N] x POs that must ship by EOD to avoid a late flag. Note that [M] of these are past due and MUST ship today!

Past Due below, full list in report.
[ORDERID]
[ORDERID]
...

Amazon DF orders with a cancel date of TODAY — these MUST ship today or Amazon cancels them:
[ORDERID]
[ORDERID]
...

We also have [P] order(s) that have yet to be acknowledged, please review and process once time permits.

Please see full report for full list of POs. All highlighted POs either have ship dates for today or are open orders from [YESTERDAY MM/DD/YY] or earlier that are late or will be considered late if not shipped by EOD.
```

Rules for the email:

- The list under "Past Due below" shows the **PAST DUE order IDs only** — not ship-by-EOD, not pending-ack. Just the past-due ones. (The ship-by-EOD and pending-ack orders are summarized in the opening line / pending-ack line and detailed in the xlsx.)
- Show **only ORDERIDs**, one per line, no batch / units / status / PO. Just the IDs — the report has the rest.
- Sort the past due list by `DAYS LATE` descending (most overdue first), then by `ORDERID` ascending.
- Cap the past due list at 25 lines. If there are more, list the first 25 and add `... and [N] more — see attached spreadsheet.`
- **Amazon DF (AMZC) ship-today block — standard format only (NJ, Fontana).** List by ID every `AMZC` order whose `CANCELDATE` is today (i.e., the `SHIP BY EOD` AMZC orders) under the header `Amazon DF orders with a cancel date of TODAY — these MUST ship today or Amazon cancels them:`. These are folded into the `[N]` count but the warehouse needs to see the specific IDs, since a blown Amazon cancel date auto-cancels the order. Show ORDERIDs only, one per line, sorted by `ORDERID` ascending. Cap at 25 with the same `... and [N] more — see attached spreadsheet.` overflow rule. Omit the whole block (header included) when there are no AMZC-cancel-today orders. This block is independent of the past-due block — show both when both apply. SC never has this block (no AMZC concept).
- The **pending-acknowledgement line** appears only when there is at least one `PENDING ACKNOWLEDGEMENT` order. `[P]` is the count. Use `order` (singular) when `[P]` is 1, `orders` otherwise. Omit the line entirely when `[P]` is zero. This line is standard-format only (NJ, Fontana) — SC has no pending-acknowledgement bucket, so it never appears on SC emails.
- If `PAST DUE` is zero, replace `Note that [M] of these are past due and MUST ship today!` with `None are past due yet — let's keep it that way.`, and omit the "Past Due below" block entirely. The closing line and the pending-acknowledgement line (if any) stay.
  - **SC-only exception:** South Carolina is typically a low-volume warehouse, so a past-due-only email there often lists zero PO numbers and looks empty. For **SC only**, when `PAST DUE` is zero but there is at least one `SHIP BY EOD` order, list the ship-by-EOD ORDERIDs instead (capped at 25, same "...and [N] more" overflow rule) under the header `POs to ship by EOD below, full list in report.`. This fallback applies to SC only — **New Jersey and Fontana always stay past-due-only** and show no PO list when there are zero past due.
- If `SHIP BY EOD` is zero, replace the opening line with `I am seeing [M] x POs that are past due and MUST ship today!`. Keep the past due list, the pending-acknowledgement line (if any), and the closing line.
- If both PAST DUE and SHIP BY EOD are zero but there are pending-acknowledgement orders, the body is: `Good morning team` / `No late or at-risk orders today.` / the pending-acknowledgement line / the closing line.
- If everything is zero, the email is just: `Good morning team — open order review for [MM/DD/YY] is all clear. No late or at-risk orders today.`
- The closing line's date `[YESTERDAY MM/DD/YY]` is today minus one day in warehouse-local time.
- Salutation is always `Good morning team` regardless of run time, to match the established team format.

Present the email body in the chat as a fenced code block so the user can copy it cleanly. Show the subject above it.

## Tone and approach

- Don't narrate row-by-row. Produce the three deliverables and let them speak.
- Flag rather than guess. If a row has missing data that breaks categorization (e.g., AMZC with no CANCELDATE, or an unknown batch), call it out in the chat summary and ask before forcing it into a bucket.
- Use bullet/table formatting inside the outputs themselves, but keep the conversational wrapper around them concise.
- The point of this skill is to give the warehouse a clean action list. Optimize for that — readability and accuracy beat exhaustiveness.
