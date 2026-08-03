---
name: marketplace-cpu-analysis
description: >
  Ad-hoc cost-per-unit analysis for Americanflat marketplaces — Target,
  Michaels, Shopify, Macy's. Pulls 3PL shipped orders + FedEx + Stamps.com
  invoices from /uploads, filters by marketplace / carrier / date window, and
  produces a weekly CPU table plus a pre/post comparison and projected annual
  impact.

  Use when the user asks about a marketplace's CPU on a specific carrier or
  routing window. Examples:
    "What's the Macy's CPU since going 100% FedEx?"
    "What did Target shipping cost in May?"
    "Compare Shopify FedEx vs Stamps CPU"
    "What's the impact of the Macy's routing change annualized?"
    "How much did Target spend YTD on FedEx?"
    "Shopify CPU pre/post a date cutoff"

  Triggered manually. Reads the same /uploads files the shipping-cost-report
  skill uses, but doesn't write to the baseline — purely analytical.
---

# Marketplace CPU Analysis

This skill answers ad-hoc questions about marketplace shipping costs using the same data the weekly Cost per SKU report runs on. It's purely read-only — no baseline mutation, no ledger updates.

## What it produces

A markdown report with:

1. **Weekly breakdown** — for each week in the window: total 3PL units shipped, FedEx-invoiced units, %FedEx, cost, CPU.
2. **Period summary** — total units / cost / CPU since the cutoff.
3. **Pre/post comparison** — if a cutoff date is supplied, also computes the prior-window CPU and the delta.
4. **Annual impact projection** — at the current weekly volume × CPU delta, what would the annual incremental cost be.

## Step 1 — Confirm the question

Get clear from the user on:

- **Which marketplace?** Target / Michaels / Shopify / Macy's (or "All").
- **Which carrier?** FedEx / Stamps / All. Default = All.
- **Window?** "Since W/O 5/4", "YTD", "May 2026", "last 4 weeks", or a custom start date.
- **Comparison baseline?** Optional — pre-cutoff period to compare against (e.g. for Macy's routing change, pre = before W/O 5/4).

## Step 2 — Run `analyze.py`

```bash
cp <skill-path>/scripts/analyze.py ./

python3 analyze.py \
  --uploads <uploads-dir> \
  --marketplace "Macy's" \
  --carrier FedEx \
  --since 2026-05-04 \
  [--compare-before 2026-05-04] \
  [--out report.md]
```

Flags:
- `--marketplace` — Target | Michaels | Shopify | "Macy's" | All
- `--carrier` — FedEx | Stamps | All (default All)
- `--since` — ISO date for window start (inclusive)
- `--until` — ISO date for window end (inclusive); default = today
- `--compare-before` — optional ISO date; everything before this is the "pre" comparison window. Implies a delta + annualized impact.
- `--out` — optional markdown output path; otherwise prints to stdout
- `--baseline-cpu` — optional explicit pre-CPU override (e.g. when the pre period predates available invoice data, you can pass `--baseline-cpu 5.37` to compare against a known historical rate)

## Examples

**"Macy's CPU since going 100% FedEx"** (the W/O 5/4 routing change):
```bash
python3 analyze.py --uploads /uploads --marketplace "Macy's" --carrier FedEx \
    --since 2026-05-04 --baseline-cpu 5.37 --out macys_routing_change.md
```

**"Target FedEx CPU YTD":**
```bash
python3 analyze.py --uploads /uploads --marketplace Target --carrier FedEx \
    --since 2026-01-01
```

**"Compare Shopify on FedEx vs Stamps for May":**
```bash
python3 analyze.py --uploads /uploads --marketplace Shopify \
    --since 2026-05-01 --until 2026-05-31 --carrier FedEx
python3 analyze.py --uploads /uploads --marketplace Shopify \
    --since 2026-05-01 --until 2026-05-31 --carrier Stamps
# (Run twice and diff the headline CPUs.)
```

## Matching logic

Same as the shipping-cost-report skill, condensed:

- 3PL orders loaded from NJ/Fontana CSVs (`Bill of Lading`) and SC XLSX (`Tracking Number`)
- Parcel-only filter (LTL freight, Pitt-Ohio, Global-e excluded — see `LTL_CARRIERS` constant)
- Marketplace normalization via the same map: TARG/TRGT→Target, MICHAELS/MCHL→Michaels, SHOPIFY/SHPFY→Shopify, MACY/MACYS→Macy's
- FedEx-matched: tracking appears in any FedEx invoice in /uploads, net charge > 0 (or refund-zero rule for Stamps net ≤ 0)
- A shipment with `--carrier FedEx` only counts when its tracking is in FedEx invoices
- A shipment with `--carrier Stamps` only counts when its tracking is in Stamps print history AND not in FedEx
- A shipment with `--carrier All` counts under FedEx if matched there, otherwise Stamps

## Interpretation tips for the user

When delivering the report, always remind:

1. **Recent weeks have invoice lag.** A week that just closed will show artificially low %carrier coverage because the invoices haven't all arrived. Wait 1-2 weeks for full coverage before drawing conclusions.

2. **The pre-period baseline-cpu override** is useful when the comparison window predates our invoice archive (e.g. historical Stamps rates from before we started ingesting Stamps print history).

3. **Annualization assumes flat volume.** The script's "× 52 weeks" extrapolation projects at the average weekly volume of the post window; if Macy's volume is still ramping, the projection will lag reality.
