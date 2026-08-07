# Changelog

## [1.1.0] — 2026-08-07

Fixes a systematic under-reporting of Target lateness, surfaces Amazon DF orders that auto-cancel overnight, and adds an acknowledgement-latency metric that separates a warehouse queue problem from a picking problem.

- **Target now runs on `STARTDATE`, not `RF.DATE` + 1.** Target holds AMF to its own Requested Shipment Date, which arrives in the Order Report as `STARTDATE` — verified 38/38 against Target's own past-due export. Keying off `RF.DATE` started the clock when the warehouse *acknowledged* the order rather than when Target expected it shipped, so any acknowledgement lag bought a day Target never granted. On 07/31/26 that hid 30 of Target's 41 past-due orders behind a `SHIP BY EOD` label. No weekend/holiday roll-forward is applied to Target — its ~10:00 placement cutoff is already baked into the RSD, and rolling would re-open the same gap.
- **New `ENTRYDATE` and `ENTRY-RF LAG` columns** in the standard-format flagged xlsx, placed so the sheet reads entry → RF → deadline. The lag is the acknowledgement-latency metric: a high lag means the order sat unacknowledged and the fix is upstream of picking, while a low lag on an aged order means it is stuck *after* RF and needs individual investigation. On 08/04/26 Fontana's past-due Target orders averaged a 2.36-day lag against NJ's ~1 day — the reason Fontana had 109 Target lates and NJ had 10.
- **Amazon DF cancel-today orders are now itemised** in the NJ and Fontana emails. They were always counted in the ship-by-EOD total but never listed, so the warehouse could not see which specific orders Amazon would cancel overnight. Fontana's subject also carries a `--- [D] DF to Ship Today` count.
- **Subject lines now read `AMF x TS [Warehouse] …`** for all three warehouses. Note for anyone with mail rules keyed on the old `AMF x [Warehouse]` prefix — they will need updating.
- **Seven standing order-ID exclusions added** (bulk-buy, wholesale, and stuck orders across all three warehouses) so orders that cannot be actioned stop appearing on the daily list.
- **Bundled `scripts/process_orders.py` brought back in sync.** The script implements the SLA logic independently and had drifted behind the documented rules; it now matches SKILL.md and is verified end to end against a real report.
- **Why now.** Target emailed a past-due list on 07/31/26 that our runs were not flagging. Tracing it showed the `RF.DATE` basis was the cause, and fixing it exposed how much of the remaining gap was acknowledgement latency rather than throughput.

## [1.0.0] — 2026-06-25

Initial release. Analyzes an AMF warehouse Open Order Report and flags every order that is past due, must ship by EOD to avoid going late, or is pending warehouse acknowledgement — producing a color-coded flagged-orders xlsx and a ready-to-send warehouse action email per warehouse.

- **Three warehouses in scope**, auto-detected from the order-ID prefix: New Jersey (`AME*`, Eastern), Fontana (`AMF*`, Pacific), and South Carolina (`AMS*`, Eastern). Multiple reports in one run are each analyzed independently in their own local timezone, with one xlsx and one email per warehouse.
- **Two report formats.** Standard (NJ, Fontana) drives off `RF.DATE`, drops Amazon Vendor Central (`AMZVC`/`S-AMZVC`), and has a PENDING ACKNOWLEDGEMENT bucket for blank-`RF.DATE` non-AMZC orders. SC variant drives off `Order Date`, keeps `Order Type == 'ECOM Order'`, de-dups on `Order No.`, and drops amazon.com wholesale (`AMZCWH`/`S-AMZCWH`).
- **Two-step weekend/holiday deadline.** The driving date is rolled forward to a processing day, then given one more processing day to ship (Mon–Fri; holidays passed in per run). AMZC (Amazon DF) orders are exempt and run purely on `CANCELDATE`.
- **Three deliverables per warehouse**: a short chat summary, a color-coded Flagged Orders xlsx sorted by urgency, and a warehouse action email listing past-due ORDERIDs (capped at 25, with an SC fallback to ship-by-EOD POs so the email is never empty).
- **Standing exclusions** are baked into `STANDING_EXCLUSIONS` in `scripts/process_orders.py` and applied automatically every run; one-time exclusions, holidays, and cancel lists are passed in per run.
