# amf-late-orders

A Claude skill that analyzes AMF warehouse Open Order Reports and flags every
order that is **past due**, **must ship by EOD** to avoid going late, or is
**pending warehouse acknowledgement**. It produces a color-coded flagged-orders
spreadsheet and a ready-to-send warehouse action email per warehouse.

## What's in here

```
amf-late-orders/
├── SKILL.md                 # The skill definition + full business ruleset (read this first)
└── scripts/
    └── process_orders.py    # Reusable processing engine (standard + SC formats)
```

## Using it in Claude Code

Drop the `amf-late-orders/` folder into your skills directory (e.g.
`.claude/skills/amf-late-orders/`). Claude reads `SKILL.md` to learn when and
how to trigger. The `scripts/process_orders.py` module is the engine — import
it from the code tool rather than rebuilding the logic each run:

```python
from process_orders import process_standard, process_sc

# Standard format (New Jersey = AME*, Fontana = AMF*)
res = process_standard(
    "/path/to/Order_Report_YYYYMMDD_HHMMSS.xlsx",
    short="NJ", full="New Jersey",
    ts="YYYYMMDDHHMMSS",                       # run "now", taken from the filename
    one_time_exclude=set(),                    # orders the user names for that day only
    holidays=set(),                            # e.g. {date(2026,5,25)} for Memorial Day
    cancel_ids=[],                             # one-off "please CANCEL" block for the email
)
print(res["subject"]); print(res["body"])     # email
# res["path"] -> the flagged-orders xlsx in /mnt/user-data/outputs
```

**Standing exclusions are baked in.** They live in the `STANDING_EXCLUSIONS`
dict at the top of `process_orders.py` (keyed by warehouse short code) and are
applied automatically every run — you do not pass them. Today that's the two NJ
manual orders (`AME*6-05-2026`, `AME*SSXDAUTEWF6H2`). To retire one when it
clears, delete it from that dict. Anything passed via `standing_exclude=` is
merged on top, so you can still add more ad hoc.

```python
# SC variant (South Carolina = AMS*)
res = process_sc(
    "/path/to/Open_Orders_YYYYMMDDHHMMSS.xlsx",
    ts="YYYYMMDDHHMMSS",
    drop_amazon_wholesale=True,                # drops AMZCWH / S-AMZCWH (amazon.com)
)
```

## Key rules baked into the engine (see SKILL.md for the full spec)

- **All three warehouses run Mon–Fri.** Saturday and Sunday are non-processing;
  add holidays via the `holidays` argument.
- **Two-step weekend-receipt deadline.** An order's driving date (RF.DATE for
  standard, Order Date for SC) is first rolled forward to a working day, then
  given one more processing day to ship. So a Friday receipt is SHIP BY EOD
  Monday / past due Tuesday; a Saturday or Sunday receipt is SHIP BY EOD
  Tuesday / past due Wednesday.
- **AMZC (Amazon DF) orders are exempt** from the weekend logic and run purely
  on CANCELDATE.
- **Standard format** drops Amazon Vendor Central (AMZVC / S-AMZVC) and has a
  PENDING ACKNOWLEDGEMENT bucket (blank RF.DATE on a non-AMZC order).
- **SC variant** keeps `Order Type == 'ECOM Order'`, de-dups on `Order No.`,
  drops amazon.com wholesale (AMZCWH / S-AMZCWH), and has no pending-ack bucket.
- **Email** lists past-due ORDERIDs (capped at 25). SC falls back to listing
  ship-by-EOD POs when there are zero past due, so its email is never empty.

## Things that change run to run

One-time exclusions, holidays, and cancel lists are passed in as arguments, not
embedded. **Standing exclusions are the exception** — they're baked into the
`STANDING_EXCLUSIONS` dict in `process_orders.py` and applied automatically;
edit that dict to add or retire one. Confirm the run timestamp from the uploaded
filename each time. Per the operator's standing instruction, **do not add,
change, or remove skill rules without explicit permission** — surface
suggestions instead.
