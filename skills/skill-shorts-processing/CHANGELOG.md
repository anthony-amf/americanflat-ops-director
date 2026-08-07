# Changelog

## [1.2.1] — 2026-08-07

Description-only change: records how South Carolina shorts actually reach us.

- **SC shorts come by email, not the portal export.** Fontana (`AMF*`) and NJ (`AME*`) shorts arrive as `Client_Short_Report` CSVs downloaded from the portal, but South Carolina's are emailed in, usually by Bryan at SC. The description now says so, so the skill triggers on a forwarded or pasted SC short list rather than waiting for a CSV that never comes. Also worth knowing when the CSVs do arrive: the portal names every export `Client_Short_Report.csv`, so the browser disambiguates with `_1`, `_2` suffixes — the filename never identifies the warehouse, only the `Order#` prefix does.


## [1.2.0] — 2026-08-06

Hardens the routing rules against three failure modes that cost real shipments in production, adds Walmart 1P and pricing-error recalls as first-class cases, and fixes the output formatting the ops team kept having to correct by hand.

- **Allocated stock is never cancelled — now a blocking check, not a guideline.** If `Alloc Qty > 0` on any line of a DTC order, that order is `Partial ship`, full stop. The skill must re-derive this over the finished email, order by order, and move anything misclassified before sending. Two exceptions are documented explicitly so they cannot be read as loopholes: full-carton channels, where a partial carton physically cannot ship, and pricing-error recalls, where stopping the shipment is the objective.
- **Check the base SKU before calling anything out of stock.** Many items exist under both a marketplace `MP-…` SKU and a base SKU, and warehouse systems routinely show the `MP-` form at zero while the base form has hundreds on hand. New Step 2.25 makes this check mandatory, gives the mechanical transform, and lists the repeat offenders.
- **Substitutions are cancel-and-resend, never ship-in-place.** The warehouse has to genuinely cancel so ops can raise a new order carrying the substitute SKU. Also fixes the language: it is a *substitution*, never a "wrong SKU" — the customer ordered a valid item that happens to be out of stock.
- **Action labels are channel-specific.** DTC lines use `Cancel` or `Partial ship`; Amazon VC and Walmart 1P use `Down confirm`, which is a vendor-portal quantity confirmation rather than a packslip cancel. Labelling everything "down confirm" flattened the email and the warehouse could no longer tell the actions apart.
- **Walmart 1P is now a recognised channel.** `Regional DC ####` consignees with `ROUT` ship-via are 1P purchase orders and take the Amazon VC full-carton treatment, including aggregating demand per SKU across every PO in the file before judging coverage.
- **Pricing-error recalls.** A mass single-SKU short at one warehouse should prompt "is this a listing error?" before any redirect is planned. Given a recall export, match by order number, cancel entirely including allocated units, and lead the email with whatever is closest to shipping.
- **Ad-hoc warehouse requests get a real procedure.** Resolve the UPC to a SKU first, ask if no item number was supplied, check the base SKU and the other warehouses, and never rubber-stamp a cancel.
- **Reading stock correctly.** `bq query` truncates silently at 100 rows without `--max_rows`, which reads as "no stock" and produces false cancels. Match on dimension tokens rather than exact SKU strings, treat negatives as zero, and distinguish "cannot locate" from genuinely zero.
- **Output formatting.** Slack posts identify every line by PO number, never customer name, and each order appears exactly once. Warehouse emails are never hard-wrapped, so they reflow properly when pasted into Gmail.
- **Why now.** Two weeks of daily production runs surfaced these the hard way — orders cancelled at a warehouse that was holding allocated stock, a substitution SKU that generated the same manual fix six days running, a 136-order mass short that turned out to be a $0.85 pricing error rather than a fulfillment gap, and a Slack post the ops team could not action because it listed customer names instead of PO numbers.


## [1.1.0] — 2026-06-12

Adds Amazon B2B handling, three new pre-cancel rescue paths, and a batch of output/process hardening accumulated since the initial release.

- **Amazon B2B (FC replenishment) orders never cancel.** Lines for `Amazon`-prefixed consignees are down-confirmed to the nearest case-pack quantity at or below the allocated qty (or 0 if below one full pack) and the remainder short-ships — no redirect, no sub swap, no cancel. New `TS POA = Down-confirm`. Case-pack sizes are looked up from the PRODUCT DATA tab of the product master Google Sheet and the math is spelled out per line.
- **Amazon B2B orders are excluded from the Slack post** and acknowledged only in the origin warehouse email under a new `DOWN-CONFIRM (Amazon B2B)` section, keeping the marketplace/CS-facing post focused on DTC.
- **Sub-at-origin rescue (Step 3.5).** When the original SKU is out at every non-origin warehouse but the origin holds enough of the substitute, the origin cancels the original line and re-issues with the sub instead of cancelling the order. New `TS POA = Cancel & resend with sub` plus a matching email section.
- **VC PO reallocation rescue (Step 5.5), user-triggered only.** Documents how to encode a manual instruction to unallocate units from an open Amazon VC PO to rescue DTC shorts (`TS POA = Reallocate & Ship`). Never applied autonomously.
- **Disable list now defaults to every OOS SKU.** Removed the prior network-stock judgment filter; any SKU that shorts with no rescue path is surfaced for delisting (narrow exception for bulk B2B/3PL allocation edge cases, flagged in needs-review instead).
- **Ad-hoc warehouse cancel-request rules.** Guidance for mid-day "OK to cancel?" emails: cancel at origin when redirecting, do not cancel when partial-shipping, cancel when truly OOS — independent of how many warehouses the order has bounced through.
- **Slack post reformatted for the rich-text composer.** Bold now uses Unicode bold characters instead of `*asterisk*` markup, real emoji replace `:shortcode:` names, the three sections are framed with solid divider bars, and a fixed emoji-to-element mapping keeps every run consistent. The Customer Service partial-fulfillment block gives a per-shorted-line ship breakdown instead of a single rolled-up figure.
- **`.xlsx` report is mandatory on every run** and its filename now carries an `HHMM` timestamp (`AMF_Short_Report_YYYY-MM-DD_HHMM.xlsx`) so multiple batches in one day no longer collide as download duplicates. A clickable download link is required directly under the table.
- **All four deliverables are mandatory on every batch**, including supplementary mid-day batches (SC bounce-backs, additional warehouse shorts) — the Slack post is never skipped. Output text must reference real `Order#` / consignee / SKU values, never internal working labels.
- **On-brand outputs (Americanflat Brand Guidelines v5).** The `.xlsx` report is now styled to the AF brand — `americanflat` wordmark title, AF Black `#0F0F0F` header (replacing the old generic navy), AF Grey zebra rows, AF Red `#CE0E2D` reserved for Amazon-context/alert notes, Glacial Indifference throughout — instead of generic defaults.
- **Branded HTML summary, mandatory every run.** Each run also produces a self-contained, on-brand HTML summary from `reference/html-summary-template.html` (KPI cards, routing table with status pills, live BigQuery on-hand bars, Slack preview), paired to the xlsx by basename + HHMM timestamp. Brand tokens derived from `skill-design-system` v1.0.0.
- **Why now.** Two weeks of daily runs surfaced recurring real-world cases the original release didn't cover — Amazon FC replenishment POs that must never cancel, SKUs that bounce across warehouses for days, VC-allocated stock that can rescue DTC shorts, and a Slack format that rendered as literal markup in the team's composer.

## v0.1.0

- Reads one or more daily Client Short Report CSVs (one per origin warehouse or a consolidated file) and merges them into a single working set.
- Pulls per-warehouse on-hand stock from BigQuery (`americanflat.Demand_Planning.Warehouse_Inventory`) for every shorted SKU.
- Applies US redirect priority — SC → Fontana → NJ — always skipping the origin warehouse derived from the order prefix (AMF*/AME*/AMS*).
- Falls back to substitution SKUs via a bundled bidirectional mapping (`reference/sku-alternates.csv`, 1,444 pairs) when the original is OOS at all non-origin warehouses.
- Classifies each order's `TS POA` (Cancel / Partial Ship) from the origin's perspective and separately tracks the customer-facing outcome (full cancel / partial fulfillment / full fulfillment via redirect).
- Produces four deliverables per run: a 10-column AMF Short Report (markdown + xlsx), a single combined Slack post with three labeled sections, one warehouse action email per origin with action items, and inline needs-review callouts.
- Slack post always cc's `@opsmarketplaces` and `@Juan Portillo` on a top-line directly under the date header.
