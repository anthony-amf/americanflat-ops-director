---
name: download-weekly-shipping-reports
description: >
  Browser-automation skill that pulls the prior week's shipping reports from five
  portals and feeds them into the shipping cost report for Americanflat. Use when the
  user says "run the weekly shipping reports", "download the weekly shipping reports",
  "pull this week's shipping files", "get the 3PL and carrier reports", "stage the
  shipping inputs", or any variation about gathering the weekly Fontana / New Jersey /
  South Carolina / Stamps.com / FedEx files. Logs into each portal via Claude in Chrome
  using browser-stored credentials, downloads the prior Monday→Monday week, stages all
  five files into a dated folder, runs shipping-cost-report's process_shipments.py, and
  posts a completion message to Slack. Also runs automatically via the scheduled task
  "weekly-shipping-reports" on Thursdays at 7:00 AM ET.
---

# Weekly Shipping Reports — Runbook

A browser-automation skill that pulls the prior week's shipping reports from five
portals and feeds them into the shipping cost report.

**Last verified:** 2026-06-19 — full chain produced a correct report ($8.18 blended CPU).

## What it does

1. Logs into 5 portals via Claude in Chrome and downloads the prior **Monday→Monday** week:
   - Taylored **Fontana** (Shipped Order Report CSV)
   - Taylored **New Jersey** (Shipped Order Report CSV)
   - Taylored **South Carolina** ("Order Details" XLSX — has Tracking Number)
   - **Stamps.com** (Print History CSV)
   - **FedEx** (most-recent invoice CSV from Reporting → Download center)
2. Stages all five into a dated folder with predictable names.
3. Runs `shipping-cost-report`'s `process_shipments.py` on them → `shipping_cost_report.xlsx`
   + `marketplace_summary.json` + the marketplace cost-per-unit table.
4. Posts a completion message to Slack (#dp-and-inventory) with the blended CPU and
   matched-shipment count.

## Requirements

- **Claude in Chrome MCP** connected, with Anthony's browser already signed in to all five
  portals. Every login uses **browser-stored credentials** — click the login button, never
  type passwords. The portals have no headless API access, so the browser is required.
- **python3** on PATH (the staging helper and `process_shipments.py` are stdlib + pandas/openpyxl).
- The **`shipping-cost-report`** skill installed alongside this one (this skill calls its
  `scripts/process_shipments.py`).
- **Optional:** Slack MCP for the completion post. If not configured, skip it and say so.

---

## Step 0 — Preflight (self-healing browser session)

Browser automation here is fragile; do this first, every run.

1. Confirm a browser is connected (`list_connected_browsers`).
2. **Create a fresh MCP tab** with `tabs_create_mcp` and verify it renders with real
   dimensions — run `javascript_tool`: `({w: window.innerWidth, h: window.innerHeight})`.
   If `innerWidth` is `0`, the tab has collapsed to 0×0; screenshots will fail, which forces
   JS clicks, which lack the "user gesture" Chrome needs — and every download after the first
   per origin gets throttled (the 2nd file never lands).
3. If the fresh tab still misbehaves (0×0, or lost domain permissions), **fully quit and
   reopen Chrome** to get a healthy session, then re-create the MCP tab. A clean session
   re-grants the Taylored / Stamps domain allowances on first navigation and works
   end-to-end (proven).
4. Do all downloading from a single healthy, real-dimensioned tab.

---

## Step 1 — Compute the date window

Run the bundled helper (defaults to today; pass `--date YYYY-MM-DD` to override):

```bash
python3 scripts/date_window.py
```

It prints `prev_monday`, `this_monday`, the inclusive 8-day window, and the staging
folder name. The rule:

> Run on a Thursday → `this_monday` = the Monday earlier this week; `prev_monday` =
> `this_monday − 7`. Window = `prev_monday` → `this_monday` **inclusive** (8-day Mon→Mon).

This matches the established manual practice. Create the staging folder:

```
~/Documents/Claude/Projects/Weekly Shipping Reports/{prev_monday}_to_{this_monday}/
```

---

## Step 2 — Download from each portal

See the **Portal quick reference** table below for URLs, paths, and fingerprints. For
every portal: navigate, let browser-stored credentials log you in (never type passwords),
set the date window to `prev_monday`→`this_monday` **inclusive**, export, then **stage
safely** (Step 3) before moving on.

**Order matters for safe staging** — download one file, stage it (verify mtime + fingerprint),
then proceed to the next portal. Do not batch all clicks then sweep Downloads.

- **Fontana** — `tsonline.tpservices.com/tayloredaccess.aspx` → Sales Orders → Shipped Orders,
  client **AMF**. Green "Export to Excel" button (actually emits a CSV). ~2.5k rows, mixed FedEx/USPS.
- **New Jersey** — same portal, client **AME** (wait for the grid to fully repaint after the
  client switch before exporting). Same export. ~4k rows, UPS `1Z…` tracking.
- **South Carolina** — `tsonline2.tpservices.com` → Sales Orders → **Order Details** →
  Export to Excel (XLSX, all rows). Has a `Tracking Number` column.
- **Stamps.com** — `print.stamps.com` → History → Advanced Search → set the date range,
  Export (CSV). Columns `Tracking #`, `Amount Paid`.
- **FedEx** — `fedex.com/en-us/billing.html` → FBO → **Reporting → Download center** →
  download the newest `FEDEX_INVOICE_*` CSV. Columns `Express or Ground Tracking ID`,
  `Net Charge Amount`.

### Date pickers (read carefully)

- **Telerik date pickers (Taylored Fontana/NJ/SC)** ignore raw `.value` sets. With a visible,
  real-dimensioned window, normal typing works. If you must go through the DOM, use:
  `$find(id).set_selectedDate(new Date(yyyy, monthIndex, dd))` — note **monthIndex is
  0-based** (June = `5`).
- **Stamps date fields (React)** also ignore programmatic value-set — **type** the dates and
  **verify the grid shows the closing Monday** before exporting. The "To" date is inclusive.

---

## Step 3 — Stage each download safely

Past-week 3PL/Stamps reports are static — only a newly-posted FedEx invoice can differ. But
captures still go wrong, so never trust `ls -t | head -1`. A blocked download once caused a
stale Fontana file to overwrite NJ.

Use the bundled helper, which captures the newest matching file **by mtime newer than the
export-click timestamp** plus a content fingerprint, and copies it into the staging folder
with the canonical name:

```bash
python3 scripts/stage_download.py \
  --downloads-dir ~/Downloads \
  --since-epoch <unix-time-just-before-the-export-click> \
  --kind fontana|newjersey|southcarolina|stamps|fedex \
  --dest "<staging folder>"
```

Canonical staged names:

```
Fontana_ShippedOrders_*.csv
NewJersey_ShippedOrders_*.csv
SouthCarolina_OrderDetails_*.xlsx
Stamps_PrintHistory_*.csv
FedEx_Invoice_*_most-recent.csv
```

After all five are staged, confirm the folder holds exactly five inputs with the right
extensions before running the cost report.

---

## Step 4 — Run the cost report

Call `shipping-cost-report`'s matching script against the five staged files. The helper
locates that skill and runs it for you:

```bash
python3 scripts/run_cost_report.py --dir "<staging folder>"
```

Or run `process_shipments.py` directly:

```bash
python3 <shipping-cost-report skill>/scripts/process_shipments.py \
  --fedex "<staging>/FedEx_Invoice_*_most-recent.csv" \
  --stamps "<staging>/Stamps_PrintHistory_*.csv" \
  --nj-fontana "<staging>/Fontana_ShippedOrders_*.csv" "<staging>/NewJersey_ShippedOrders_*.csv" \
  --sc "<staging>/SouthCarolina_OrderDetails_*.xlsx" \
  --output-dir "<staging folder>"
```

This writes `shipping_cost_report.xlsx` (the deliverable) and `marketplace_summary.json`
into the staging folder. Read `marketplace_summary.json` for the blended CPU, matched count,
and per-marketplace CPU. Write a short `run_summary.txt` into the folder.

---

## Step 5 — Notify on Slack

Post to **#dp-and-inventory** (channel ID `C03A2NFA8AD`) via `slack_send_message`:

```
Weekly Shipping Report ({prev_monday} → {this_monday})
Blended CPU: $X.XX/unit · NNN matched shipments
Target $X.XX · Shopify $X.XX · Michaels $X.XX · Macy's $X.XX · Walmart $X.XX
```

Pull every figure from `marketplace_summary.json` — never hand-type numbers. If the run
**failed**, post instead:
`Weekly Shipping Report ({prev_monday} → {this_monday}) — :warning: failed at <step>. Needs a manual run.`
and DM Anthony Armstrong (Slack user ID `U06MW1DCG9Y`) with the details.

> The deliverable `shipping_cost_report.xlsx` lives in the staging folder. If Slack file
> upload isn't available, DM Anthony the filename + folder so he can attach it.

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

These same five files are the inputs the cost skills (`shipping-cost-report`,
`marketplace-cpu-analysis`, `cost-per-sku-dashboard`) read from `/uploads` in the Claude.ai
analysis sandbox. There is **no literal `/uploads`** locally — when running those skills,
upload this folder's files.

---

## How to run

**Manually:** say *"run the weekly shipping reports"* (or invoke the
`download-weekly-shipping-reports` skill).

**Scheduled:** task **`weekly-shipping-reports`**, **Thursdays 7:00 AM ET**
(cron `0 5 * * 4` — the Mac running this is on Mountain time, so −2h from ET). The scheduled
run does the full chain: download → stage → cost report → Slack notify.

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

1. **Extension tab collapses to 0×0.** If the Claude-in-Chrome tab reports `innerWidth: 0`,
   screenshots fail → forces JS clicks → JS clicks lack the "user gesture" Chrome needs →
   every download after the first per origin is throttled (the 2nd file never lands).
   **Fix:** the Step 0 preflight creates a fresh MCP tab (which renders with real dimensions).
   If the whole session is degraded (fresh tab also misbehaves or loses domain permissions),
   **fully quit and reopen Chrome** for a healthy session — a fresh session works end-to-end (proven).
2. **Domain permissions are per-tab in the harness.** A freshly created tab may not carry the
   Taylored/Stamps domain allowance the original had. A clean browser session re-grants these
   on first navigation.
3. **Telerik date pickers (Taylored)** ignore raw `.value` sets. With a visible window, normal
   typing works. Via DOM, use `$find(id).set_selectedDate(new Date(yyyy, monthIndex, dd))`
   (June = month index 5).
4. **Stamps date fields (React)** also ignore programmatic value-set — **type** the dates and
   verify the grid shows the closing Monday before exporting. "To" is inclusive.
5. **Safe staging.** Capture downloads by *mtime newer than the export click* + a content
   fingerprint — never `ls -t | head -1` blindly. (A blocked download once caused a stale
   Fontana file to overwrite NJ.) Use `scripts/stage_download.py`.
6. **Closed-week data is static.** Past-week 3PL/Stamps reports don't change intraday; only a
   newly-posted FedEx invoice can differ.

---

## Reference IDs

- Slack channel **#dp-and-inventory**: `C03A2NFA8AD`
- Anthony Armstrong Slack user ID: `U06MW1DCG9Y`
- Marketplaces in the primary report: Target, Shopify, Michaels, Macy's (Walmart shown when present)

## Current status (2026-06-19)

- Report for **6/8→6/15** delivered: `…/2026-06-08_to_2026-06-15/shipping_cost_report.xlsx`
  — blended **$8.18/unit** (Target $8.30, Shopify $6.85, Michaels $9.87, Macy's $13.76,
  Walmart $9.79), 1,666 matched shipments.
- Download mechanism proven (FedEx file downloaded via a real click on a rendered tab).
- Skill hardened: self-healing preflight + safe staging.
- A live full re-run was once blocked by a degraded browser session (collapsed tab + split
  domain permissions). Fix = restart Chrome for a fresh session, then run.
