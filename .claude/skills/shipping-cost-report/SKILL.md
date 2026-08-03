---
name: shipping-cost-report
description: >
  Generates the weekly Americanflat shipping cost report by matching FedEx invoices and
  Stamps.com print history against 3PL shipped order reports from three warehouses
  (NJ, Fontana, SC). Produces an Excel report with marketplace summary, weekly cost per unit,
  carrier breakdown, and matched/unmatched order detail — plus an optional PDF visual summary
  with charts.

  Use this skill when the user says "run the shipping cost report", "generate the shipping report",
  "match invoices to 3PL", "shipping cost validator", "cost per unit report", "FedEx Stamps matching",
  "weekly shipping analysis", "marketplace shipping breakdown", or any variation involving matching
  shipping invoices against warehouse shipped orders. Also use when the user uploads FedEx CSVs,
  Stamps.com print history, or 3PL shipped order files and wants cost analysis. Even if they just say
  "run the report" or "do the shipping thing" in the context of shipping costs, trigger this skill.
---

# Shipping Cost Report

This skill matches shipping invoices (FedEx + Stamps.com) against 3PL shipped order reports to calculate cost per unit by marketplace. It's the core weekly report for Americanflat's shipping cost analysis.

## What It Does

1. Parses FedEx invoice CSVs and Stamps.com print history CSVs
2. Parses 3PL shipped order reports from NJ, Fontana (CSV), and SC (XLSX — item-level, needs aggregation)
3. Matches invoices to orders via tracking number, PO/order reference, and reverse-pass multi-package logic
4. Calculates weighted cost per unit by marketplace, weekly trends, and carrier breakdown
5. Outputs an Excel report and optionally a PDF visual summary

## Step 1 — Gather Input Files

The report needs three categories of files. Ask the user for any they haven't already provided:

### Invoice Files (cost sources)
- **FedEx invoice CSVs** — columns include: `Express or Ground Tracking ID`, `Net Charge Amount`, `Shipment Date`, `Original Customer Reference`, `Original Ref#2`, `Original Ref#3/PO Number`, `Shipper City`, `Rated Weight Amount`, `Actual Weight Amount`
- **Stamps.com print history CSVs** — columns include: `Tracking #`, `Amount Paid`, `Adjusted Amount`, `Ship Date`, `Cost Code`, `Order ID`, `Reference 1`, `Printed Message`, `Weight`

### 3PL Shipped Order Reports (source of truth)
- **NJ / Fontana** — CSV format with columns: `Order`, `PO #`, `Bill of Lading` (tracking), `Ship Date`, `Batch#` (marketplace code), `Units`, `Carrier`, `Consignee`
- **South Carolina** — XLSX with item-level rows: `Order No.`, `Cust PO No.`, `Tracking Number`, `Division` (marketplace code), `Shipped Quantity`, `Actual Ship Date`, `Carrier`, `Ship To Name`. These need aggregation by order+tracking since each row is a line item.

If files aren't uploaded, check Slack (#operations-team-information-channel) for recent EDI reports, or ask the user to upload them.

## Step 2 — Run the Matching Script

The bundled `scripts/process_shipments.py` handles all parsing, matching, and report generation. Copy it to the working directory and run:

```bash
cp <skill-path>/scripts/process_shipments.py ./process_shipments.py

python3 process_shipments.py \
  --fedex <fedex_file1.csv> [<fedex_file2.csv> ...] \
  --stamps <stamps_file1.csv> [<stamps_file2.csv> ...] \
  --nj-fontana <nj_report.csv> [<fontana_report.csv> ...] \
  --sc <sc_order_details.xlsx> [<sc_order_details2.xlsx> ...] \
  --output-dir <output_directory>
```

This produces:
- `shipping_cost_report.xlsx` — full report with 5 tabs
- `marketplace_summary.json` — structured data for downstream use

### How Matching Works

The script uses a multi-pass matching strategy because not every 3PL order has a tracking number that directly appears in the invoice:

1. **Direct tracking match** — 3PL tracking → FedEx or Stamps tracking number (most common)
2. **PO/reference match** — 3PL PO number → FedEx ref1/ref2/ref3 fields, or 3PL order number → Stamps order_ref
3. **Reverse pass** — Remaining unmatched FedEx records are checked against ALL 3PL POs via ref3 (catches multi-package shipments where package #2+ has a different tracking but same PO)
4. **Stamps reverse pass** — Same logic for remaining Stamps records via order_ref

### Marketplace Code Normalization

The script normalizes raw codes from 3PL reports to display names:

| NJ/Fontana Batch# | SC Division | Display Name |
|---|---|---|
| TARG | TRGT | Target |
| SHOPIFY | SHPFY | Shopify |
| MICHAELS | MCHL | Michaels |
| MACYS / MACY | — | Macy's |
| KOHLS | KOHL | Kohl's |
| WAYF | — | Wayfair |
| WALC | — | Walmart |
| FAIRE | FAIR | Faire |
| AMZC | — | Amazon |
| AMZVC / S-AMZVC | — | Amazon VC |
| — | AMZCWH / S-AMZCWH | Amazon WH |
| SHIPSTATION / MANUAL | OTHR | ShipStation |

## Step 3 — Build the Enhanced Excel Report

After the base script runs, enhance the report with these features the user has refined over time:

### Marketplace Filtering
The primary report focuses on **Target, Shopify, Michaels, and Macy's**. Create a separate "OTHER" report for remaining marketplaces. Filter matched orders by marketplace and rebuild each workbook from the filtered data.

### Weekly Summary Tabs
Add two summary tabs at the front of the workbook:

- **Weekly Cost per Unit** — Rows grouped by marketplace, columns for each week showing FedEx CPU, Stamps CPU, Combined CPU. Show overlap weeks only (weeks where both FedEx and Stamps data exist).
- **Weekly Volume** — Same structure but showing order counts and unit counts by carrier.

For each marketplace section, include an OVERLAP TOTAL row that sums only weeks with both carriers present. Add an "ALL MARKETPLACES" section at the bottom.

### Marketplace Summary Tab
For each marketplace, show weekly rows with these columns:
`Week | FedEx Orders | FedEx Units | FedEx Cost | FedEx CPU | Stamps Orders | Stamps Units | Stamps Cost | Stamps CPU | Combined Orders | Combined Units | Combined Cost | Combined CPU | Total Shipped Units | Coverage %`

Coverage % = matched units / total 3PL shipped units for that week.

### Matched Orders Tab
Include these 13 columns: `Ship Date | Order Number | PO # | Marketplace | Units | Shipping Cost | Weight (lbs) | Cost/Unit | Carrier Source | Match Method | Warehouse | Tracking | Consignee`

### Formatting
- 170% zoom on all tabs
- Navy header row with white text (font: Arial 11pt)
- Alternating row fills on detail tabs
- Green highlight on overlap-period rows in summary
- Medium borders between marketplace groups
- Currency format: $#,##0.00
- Percentage format: 0.0%

## Step 4 — Optional PDF Visual Summary

If the user asks for a visual or presentation version, generate a 3-page PDF using matplotlib + reportlab:

**Page 1:** KPI cards (Total Shipped, Matched Units, Total Cost, Blended CPU) + marketplace breakdown table + total cost bar chart

**Page 2:** Weekly CPU trend line chart (each marketplace + "All Combined" dashed) + CPU by carrier grouped bar chart

**Page 3:** Weekly volume stacked bar chart + FedEx vs Stamps cost split bar chart

Color scheme:
- Target: #CC0000 (red)
- Shopify: #5A9C3E (green)
- Michaels: #1565C0 (blue)
- All Combined: #000000 (black, dashed line)
- FedEx: #4D148C (purple)
- Stamps: #E31837 (red)

## Step 5 — Deliver Results

Present the user with:
1. Quick summary: total matched, coverage %, blended CPU
2. Link to the Excel report
3. Link to the PDF (if generated)
4. Flag any concerns: low coverage marketplaces, large unmatched invoice amounts, significant week-over-week CPU changes

## Weight Handling

FedEx weight: Use `Rated Weight Amount` (dimensional weight) if > 0, otherwise fall back to `Actual Weight Amount`.

Stamps weight: The Weight column may be numeric (decimal pounds) or formatted as "Xlb Yoz". Parse with regex:
```python
def parse_weight_lbs(val):
    if not val: return 0.0
    s = str(val).strip()
    try: return float(s)
    except ValueError: pass
    lbs = oz = 0.0
    lb_m = re.search(r'([\d.]+)\s*lb', s, re.IGNORECASE)
    oz_m = re.search(r'([\d.]+)\s*oz', s, re.IGNORECASE)
    if lb_m: lbs = float(lb_m.group(1))
    if oz_m: oz = float(oz_m.group(1))
    return round(lbs + oz / 16.0, 2)
```

## Troubleshooting

**Low match rate (<80%):** Check that the invoice date range overlaps with the 3PL report dates. Also verify tracking number formats — FedEx uses 12-digit or 15-digit numbers, Stamps uses mixed formats (1Z... for UPS, 94... for USPS).

**"Unknown" marketplace:** The 3PL Batch# or Division code isn't in the normalization map. Add it to MARKETPLACE_MAP in the script.

**SC file timeout:** SC XLSX files can be large. Use `read_only=True` and `data_only=True` when loading with openpyxl.

**Stamps weight = 0:** The weight field is in "Xlb Yoz" format. Use the regex parser above instead of `float()`.

**Week of 3/30 shows low coverage:** The last week of the month often has incomplete invoice data (FedEx/Stamps invoices lag by a few days). Note this in the report.
