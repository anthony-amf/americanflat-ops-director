# Weekly Shipping Reports — Runbook

A browser-automation skill that pulls the prior week's shipping reports from five portals and feeds them into the shipping cost report.

**Skill:** `download-weekly-shipping-reports` (installed at `~/.claude/skills/download-weekly-shipping-reports/`)
**Last verified:** 2026-06-19 — full chain produced a correct report ($8.18 blended CPU).

---

## What it does

1. Logs into 5 portals via Claude in Chrome and downloads the prior **Monday→Monday** week:
   - Taylored **Fontana** (Shipped Order Report CSV)
   - Taylored **New Jersey** (Shipped Order Report CSV)
   - Taylored **South Carolina** ("Order Details" XLSX — has Tracking Number)
   - **Stamps.com** (Print History CSV)
   - **FedEx** (most-recent invoice CSV from Reporting → Download center)
2. Stages all five into a dated folder with predictable names.
3. Runs `shipping-cost-report`'s `process_shipments.py` on them → `shipping_cost_report.xlsx` + `marketplace_summary.json` + the marketplace cost-per-unit table.

---

## How to run

**Manually:** say *"run the weekly shipping reports"* (or invoke the `download-weekly-shipping-reports` skill).

**Scheduled:** task `weekly-shipping-reports`, **Thursdays 7:00 AM ET** (cron `0 5 * * 4` — Mac is Mountain time, so −2h). Auto-runs the cost report after downloading. Notifies on completion.

---

## Output

Dated staging folder:
```
~/Documents/Claude/Projects/Weekly Shipping Reports/{prev_monday}_to_{this_monday}/
    Fontana_ShippedOrders_*.csv
    NewJersey_ShippedOrders_*.csv
    SouthCarolina_OrderDetails_*.xlsx
    Stamps_PrintHistory_*.csv
    FedEx_Invoice_*_most-recent.csv
    shipping_cost_report.xlsx        <- the deliverable
    marketplace_summary.json
    run_summary.txt
```
These are the inputs the cost skills (`shipping-cost-report`, `marketplace-cpu-analysis`, `cost-per-sku-dashboard`) read from `/uploads` in the Claude.ai analysis sandbox. There is **no literal `/uploads`** locally — upload this folder's files when running those skills.

---

## Date window

Run on a Thursday → `this_monday` = the Monday earlier this week; `prev_monday` = `this_monday − 7`. Window = `prev_monday` → `this_monday` **inclusive** (8-day Mon→Mon). Matches the established manual practice.

---

## Portal quick reference

| Portal | URL | Path | Export | Fingerprint |
|---|---|---|---|---|
| Fontana | tsonline.tpservices.com/tayloredaccess.aspx | Sales Orders → Shipped Orders, client **AMF** | green "Export to Excel" = CSV | ~2.5k rows, mixed FedEx/USPS |
| New Jersey | (same portal) | client **AME** (wait for grid repaint) | same | ~4k rows, UPS `1Z…` |
| South Carolina | tsonline2.tpservices.com | Sales Orders → **Order Details** | Export to Excel (XLSX, all rows) | has `Tracking Number` col |
| Stamps.com | print.stamps.com | History → Advanced Search | Export (CSV) | `Tracking #`, `Amount Paid` |
| FedEx | fedex.com/en-us/billing.html → FBO | **Reporting → Download center** | newest `FEDEX_INVOICE_*` CSV | `Express or Ground Tracking ID`, `Net Charge Amount` |

All logins use **browser-stored credentials** — click the login button, never type passwords.

---

## Known issues & fixes (hard-won)

1. **Extension tab collapses to 0×0.** If the Claude-in-Chrome tab reports `innerWidth: 0`, screenshots fail → forces JS clicks → JS clicks lack the "user gesture" Chrome needs → every download after the first per origin is throttled (the 2nd file never lands). **Fix:** the skill's preflight creates a fresh MCP tab (which renders with real dimensions). If the whole session is degraded (fresh tab also misbehaves or loses domain permissions), **fully quit and reopen Chrome** to get a healthy session — a fresh session works end-to-end (proven).

2. **Domain permissions are per-tab in the harness.** A freshly created tab may not carry the Taylored/Stamps domain allowance the original had. A clean browser session re-grants these on first navigation.

3. **Telerik date pickers (Taylored)** ignore raw `.value` sets. With a visible window, normal typing works. Via DOM, use `$find(id).set_selectedDate(new Date(yyyy, monthIndex, dd))` (June = month index 5).

4. **Stamps date fields (React)** also ignore programmatic value-set — **type** the dates and verify the grid shows the closing Monday before exporting. "To" is inclusive.

5. **Safe staging.** Capture downloads by *mtime newer than the export click* + a content fingerprint — never `ls -t | head -1` blindly. (A blocked download once caused a stale Fontana file to overwrite NJ.)

6. **Closed-week data is static.** Past-week 3PL/Stamps reports don't change intraday; only a newly-posted FedEx invoice can differ.

---

## Current status (2026-06-19)

- ✅ Report for **6/8→6/15** delivered: `…/2026-06-08_to_2026-06-15/shipping_cost_report.xlsx` — blended **$8.18/unit** (Target $8.30, Shopify $6.85, Michaels $9.87, Macy's $13.76, Walmart $9.79), 1,666 matched shipments.
- ✅ Download mechanism proven (FedEx file downloaded via a real click on a rendered tab).
- ✅ Skill hardened: self-healing preflight + safe staging.
- ⚠️ A live full re-run was blocked by a degraded browser session (collapsed tab + split domain permissions). Fix = restart Chrome for a fresh session, then run.
