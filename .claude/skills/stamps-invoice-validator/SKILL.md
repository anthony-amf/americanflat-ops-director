---
name: stamps-invoice-validator
description: >
  Validates Stamps.com shipping invoices against EDI reports for Americanflat (AMF).
  Use this skill when the user says "validate stamps invoice", "run the stamps validator",
  "check stamps against EDI", "invoice reconciliation", "stamps EDI audit", "missing shipments stamps",
  or asks to produce a marketplace cost breakdown from Stamps + EDI data.

  Opens an interactive agent that: (1) fetches the EDI report from Slack
  (#operations-team-information-channel), (2) downloads the Stamps.com invoice CSV,
  (3) matches on tracking number, (4) flags EDI shipments missing from Stamps,
  (5) outputs a summary table by marketplace (Target, Michaels, Shopify, Amazon DF,
  Wayfair, Walmart, Kohl's, Faire, ShipStation) showing Total Paid / Orders / Avg Cost / Missing.
  Manual upload fallback available if Slack/portal automation is unavailable.
---

# Stamps.com Invoice Validator

When triggered, open the validator app for the user to run.

## Step 1 — Open the App

Copy the pre-built app to outputs and present it to the user:

```bash
cp /mnt/skills/user/stamps-invoice-validator/assets/stamps-invoice-validator.html /mnt/user-data/outputs/stamps-invoice-validator.html
```

Then call `present_files` with `/mnt/user-data/outputs/stamps-invoice-validator.html`.

Tell the user:
> Here's the Stamps.com Invoice Validator. Set your date range and click **Run Agent** — it will pull the EDI file from Slack and attempt to download the Stamps invoice automatically. If either step can't complete (e.g., Stamps.com needs a login), use the **Manual Upload Fallback** panel on the bottom-left to upload the files directly.

## Step 2 — Help the User Interpret Results

After the user runs the agent, they may paste results or ask follow-up questions. Be ready to:

- Explain what "missing shipments" means (EDI confirmed the shipment happened, but Stamps.com has no matching charge — possible billing gap or carrier switch)
- Help investigate specific marketplaces with high miss rates
- Suggest next steps: pull the missing tracking numbers and cross-reference in FedEx or UPS billing if Stamps wasn't the carrier

## Key Column Mapping (for reference)

| Source | Column | Meaning |
|--------|--------|---------|
| EDI Sheet 1 | `Marks_and_Numbers` | UPS/carrier tracking number |
| EDI Sheet 2 | `reference_identification_02` | Marketplace (Target, Michaels, AMAZON.COM, etc.) |
| EDI Sheet 2 | `Marks_and_Numbers` | Join key back to Sheet 1 |
| Stamps CSV | `tracking_number` / `tracking #` | Match key |
| Stamps CSV | `total` / `charge` / `amount` | Shipment cost |

## Marketplace Name Normalization

The app normalizes raw EDI marketplace values to display names:

| Raw EDI value | Display name |
|---------------|-------------|
| `AMAZON.COM` | Amazon DF |
| `americanflat_amazon_df_prod` | Amazon DF |
| `Target` | Target |
| `MICHAELS` | Michaels |
| `SHOPIFY` | Shopify |
| `WALMARTCOM` | Walmart |
| `WAYFAIR LLC` | Wayfair |
| `KOHLS` | Kohl's |
| `FAIRE` | Faire |
| `SHIPSTATION` | ShipStation |
| `AMWV0` | Amazon VC |

## Troubleshooting

**Slack fetch returns no file**: The agent will log this and ask for manual upload. User should download the EDI .xlsx from Slack and upload via the fallback panel.

**Stamps portal can't auto-login**: Stamps.com requires an active browser session. User should log in manually, download the billing CSV (Reporting → Shipment History → Export CSV), and upload via the fallback panel.

**Tracking numbers not matching**: Check that both files cover the same date range. The EDI `Date` column and Stamps `ship date` should overlap. Adjust the date range in the app controls.

**Marketplace shows as "Unknown"**: The EDI Sheet 2 row for that tracking number has a null or unrecognized `reference_identification_02` value. These can be mapped manually if needed.
