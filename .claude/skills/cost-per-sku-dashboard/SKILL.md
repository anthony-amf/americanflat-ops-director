---
name: cost-per-sku-dashboard
description: >
  Refreshes the Americanflat Cost Per SKU dashboard (HTML site backed by 4 CSVs in Google Drive).
  Pulls the 5 source Google Sheets (FedEx invoices, Stamps.com invoices, Fontana 3PL, NJ 3PL, SC 3PL),
  matches invoices to shipped orders by tracking / BOL, filters to Target / Michaels / Shopify / Macy's,
  aggregates to unit-level cost per marketplace per week (NO SKU-level detail per Anthony's preference),
  and uploads new versions of the 4 dashboard CSVs to Drive so the existing site URLs keep working.

  Use this skill when the user says "refresh the cost per SKU dashboard", "update the shipping dashboard",
  "rerun the cost per unit dashboard", "refresh the CPU dashboard", "update the cost per SKU site",
  "regenerate the dashboard CSVs", or any variation involving refreshing the Cost Per SKU / shipping
  dashboard that lives on the HTML site backed by Google Drive CSVs.

  Triggered manually only — no schedule.
---

# Cost Per SKU Dashboard Refresh

This skill refreshes the 4 CSVs that power Anthony's Cost Per SKU dashboard site. The HTML file (`amf_shipping_dashboard.html`) reads these CSVs by URL from Google Drive — by replacing them as new versions of the same Drive files, the site URLs stay stable and the dashboard updates automatically.

## What This Skill Is NOT

This is **not** the full shipping cost report (that's the `shipping-cost-report` skill, which produces an Excel deliverable with SKU-level detail). This skill produces only the 4 aggregate CSVs needed for the dashboard:

1. `dashboard_weekly_by_marketplace.csv` — week × marketplace, units + cost + CPU
2. `dashboard_overall_by_week.csv` — week, all-marketplace totals + blended CPU
3. `dashboard_marketplace_totals.csv` — marketplace totals across the period
4. `dashboard_overall_stats.csv` — single-row top-line metrics (total units, total cost, blended CPU, week range)

**No SKU-level detail.** Anthony has explicitly said he only wants units, not individual SKUs, on this dashboard. Do not output SKU breakdowns even if it seems useful.

## Marketplaces Included

Filter to these 4 only:
- Target
- Michaels
- Shopify
- Macy's

Exclude wholesale, Amazon, Wayfair, Walmart, Faire, Kohl's, ShipStation, etc.

## Step 1 — Pull Source Data

The 5 source Google Sheets live in Anthony's Drive. Use the Google Drive MCP tools to read them:

| Source | Purpose |
|---|---|
| FedEx invoices sheet | Cost source |
| Stamps.com invoices sheet | Cost source |
| Fontana 3PL shipped orders sheet | Order source (uses BOL, may not match perfectly) |
| NJ 3PL shipped orders sheet | Order source (uses BOL, may not match perfectly) |
| SC 3PL shipped orders sheet | Order source (has actual carrier tracking numbers — best match rate) |

**File IDs are stored in `scripts/config.json`.** If the file IDs change, update that file rather than editing the script.

If the user hasn't filled in file IDs yet, ask them to paste the 5 Drive file URLs and write them into `config.json` before proceeding.

## Step 2 — Match and Aggregate

Run `scripts/refresh_dashboard.py`. It:

1. Loads all 5 sheets via Drive MCP
2. Matches invoices → orders on tracking number (SC) or BOL (NJ/Fontana) — accept imperfect BOL matches; include all 3 warehouses regardless
3. Normalizes marketplace codes (see map below)
4. Filters to Target / Michaels / Shopify / Macy's
5. Bins by ISO week (Monday-start, `%Y-W%U` format to match prior dashboard)
6. Writes the 4 CSVs to `/home/claude/dashboard_output/`

### Marketplace Code Map

| Raw code (NJ/Fontana Batch# or SC Division) | Display Name |
|---|---|
| TARG / TRGT | Target |
| MICHAELS / MCHL | Michaels |
| SHOPIFY / SHPFY | Shopify |
| MACYS / MACY | Macy's |

Anything else → drop from the dashboard.

## Step 3 — Upload as New Versions to Drive

For each of the 4 output CSVs, upload as a **new version** of the existing Drive file (do NOT create new files — the URL must stay the same so the HTML keeps working).

Drive file IDs for the 4 dashboard CSVs are also in `scripts/config.json`.

The Drive MCP path:
1. `Google Drive:get_file_metadata` to confirm the existing file
2. Use `Google Drive:create_file` with the same parent folder and same name to overwrite, OR use the Drive web "Manage versions" flow

If new-version upload via MCP isn't supported, fall back to: download current file, present the new CSV to the user, and instruct them to do "Manage versions → Upload new version" manually for each of the 4 files.

## Step 4 — Verify and Report Back

After upload, give Anthony a short summary:

- Date range covered (e.g., "Feb 2 – Apr 20, 2026")
- Total units shipped across the 4 marketplaces
- Total shipping cost
- Blended CPU
- Match rate (matched units / total shipped units)
- Per-marketplace one-liners: "Target: 1,958 orders, $26,594, $X.XX CPU"
- Link to the live dashboard so he can hard-refresh and confirm

Flag anything weird:
- Marketplace dropped to 0 orders (likely a code-map miss)
- CPU jumped >25% week-over-week
- Match rate fell below 80%

## Output Format Spec (must match what the HTML expects)

### `dashboard_weekly_by_marketplace.csv`
```
Week_Label,Marketplace,Orders,Units,Cost,Cost_Per_Unit
2026-W05,Target,142,287,2104.55,7.33
...
```

### `dashboard_overall_by_week.csv`
```
Week_Label,Orders,Units,Cost,Cost_Per_Unit
2026-W05,178,341,2589.10,7.59
...
```

### `dashboard_marketplace_totals.csv`
```
Marketplace,Orders,Units,Cost,Cost_Per_Unit
Target,1958,3104,26594.00,8.57
Shopify,464,512,5147.00,10.05
Michaels,160,176,4416.00,25.09
Macy's,28,29,190.00,6.55
```

### `dashboard_overall_stats.csv`
```
Metric,Value
Total Units,3821
Total Cost,38354.76
Blended CPU,10.04
Total Orders,2610
Match Rate,88.7
Week Range,2026-W05 to 2026-W16
Last Updated,2026-04-22
```

## Manual Trigger Phrases

Recognize any of:
- "refresh the cost per SKU dashboard"
- "update the shipping dashboard"
- "rerun the CPU dashboard"
- "refresh the dashboard"
- "update the cost per SKU site"
- "regenerate the dashboard CSVs"
- "run the cost per SKU refresh"
