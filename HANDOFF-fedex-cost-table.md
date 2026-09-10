# Handoff: FedEx cost table in `americanflat/Ops`

Prompt for a **new session sourced on `americanflat/Ops`**. A session sourced on
`anthony-amf/americanflat-ops-director` cannot attach `americanflat/*` (cross-tier
adds are refused), and the reverse is also true — so this prompt is written to
stand alone rather than pointing at the other repo. Everything needed is inline.

---

## Copy from here

Add a FedEx shipping-cost table to BigQuery and a loader for it, mirroring the
Stamps.com one that already exists in this repo.

**What is already here.** On branch `claude/stamps-shipping-costs-table-q5zskg`:
`tools/stamps_shipping_costs_load.py` (subcommands `prepare` and `load`, plus
`--no-impersonate`), `docs/stamps-shipping-costs.md`, and two repair scripts under
`sql/`. Read those first and match their shape, their CLI and their voice — this
should look like the same author wrote both. It loads
`americanflat.finance.stamps_shipping_costs`, which is currently correct: 20,528
rows, 20,528 distinct tracking numbers, $239,109.04, ship dates 2026-04-30 to
2026-08-31, UPS 15,108 / USPS 5,420, zero escaped tracking numbers.

**What to build.** `americanflat.finance.fedex_shipping_costs`, plus
`tools/fedex_shipping_costs_load.py` and `docs/fedex-shipping-costs.md`.

### The one structural difference from Stamps — get this right first

Stamps states a final figure per label: quoted + adjusted = paid. One row per
shipment, keyed on tracking, is correct there.

FedEx does not. It bills a shipment, then bills it **again on a later invoice**
when it re-rates one — a dimensional-weight correction, an address surcharge —
and both lines are money we paid. In the export I measured, tracking
`476147675207` carries $26.67 on the 2026-02-02 invoice and $13.09 on the
2026-02-16 one. That shipment cost $39.76, the sum.

So:

| | Stamps (existing) | FedEx (this task) |
|---|---|---|
| Grain | one row per shipment | one row per **invoice line** |
| Key | tracking | (tracking, invoice_date, net_charge) |
| A shipment's cost | `amount_paid` | `SUM(net_charge)` |
| Invariant | rows = distinct tracking | rows **>** distinct tracking is CORRECT |

Keying FedEx on tracking alone drops the later line. Measured, that is small —
9 of 3,688 shipments, $151.33 of $100,883.90, 0.2% — so do not oversell it. The
reason to key it properly is that the correct key costs nothing, the wrong one
fails with no symptom, and dimensional-weight re-rates are the thing most likely
to grow if large-format frames keep moving on FedEx.

**Do not copy the Stamps invariant check into the FedEx loader.** `rows_total`
greater than `distinct_tracking` is the re-rates and is expected. What must hold
for FedEx is: no two rows share (tracking, invoice_date, net_charge), and no
tracking number contains a non-alphanumeric character.

### Required schema — a consumer depends on these names

A separate tool reads this table with:

```sql
SELECT tracking_number, CAST(invoice_date AS STRING) AS charge_date, net_charge
FROM `americanflat.finance.fedex_shipping_costs`
WHERE tracking_number IS NOT NULL AND tracking_number != ''
  AND net_charge IS NOT NULL
```

So `tracking_number`, `invoice_date` and `net_charge` must exist with those
names and types (STRING, DATE, NUMERIC). Everything else is yours to choose;
what I had was `ship_date` DATE, `service_type` STRING, `package_weight`
NUMERIC, `zone` STRING, `source_file` STRING, `ingested_at` TIMESTAMP,
`ingested_by` STRING, partitioned by `invoice_date`, clustered by
`tracking_number`.

### The input files

Two shapes turn up. The consolidated Drive sheet:

`Invoice Date, Shipment Date, Tracking Number, Service Type, Package Weight, Zone, Net Charge, Source File`

and the raw FedEx Billing Online export, whose columns include:

`Express or Ground Tracking ID, Net Charge Amount, Shipment Date, Original Customer Reference, Original Ref#2, Original Ref#3/PO Number, Shipper City, Rated Weight Amount, Actual Weight Amount`

**Verify before you build:** I have only measured the consolidated sheet. I do
not know for certain that the raw Billing Online export carries an invoice date
column — the list above does not show one. If it does not, the charge key needs
a substitute (an invoice number if present, else the export's own statement
date), and that decision belongs in the doc. Check a real export rather than
assuming.

Dates in the consolidated sheet arrive as `20260202`, so parse rather than cast.

### Traps, all measured on the real files

- **The exports overlap heavily.** 7,965 rows in the consolidated sheet carry
  only 3,697 distinct charges across 3,688 shipments. De-duplicate on the
  three-part charge key: an identical line collapses, a different amount or
  invoice date is a genuine re-rate and is kept.
- **Two rows are stray header rows** from stacked exports. Tolerate a
  non-numeric amount by skipping the row; do not fail the load.
- **FedEx tracking numbers arrive clean** — no spreadsheet escaping in any of
  the 7,965 rows, unlike every USPS row in the Stamps export. Normalize anyway
  (`REGEXP_REPLACE(UPPER(x), r'[^A-Z0-9]', '')`) so both tables' tracking
  columns are the same shape and can be joined or unioned.
- **Normalize both sides of any MERGE join.** The Stamps table was pushed to
  25,948 rows and $297,557.98 against a true 20,528 and $239,109.04 because a
  merge compared cleaned source values against raw target values: no match, so
  rows inserted instead of updating, and shipments counted twice. The Stamps
  loader now refuses to run while the target holds escaped values, and that
  guard is worth having here too.
- **Never load overlapping exports by shell glob.** With last-occurrence-wins, a
  glob orders files alphabetically by the date range in the filename, not by
  when they were exported. A wide backfill sorts early but is usually the newest
  and most adjusted, so a glob overwrites post-audit amounts with stale weekly
  ones. On the September Stamps files that was worth $3,464.17 understated. The
  existing Stamps loader prints this warning; make the FedEx one do the same,
  and say in the doc: load one wide export, not the glob.

### Credentials, as they actually behave

`anthony@americanflat.com` **cannot** impersonate
`invoice-writer@americanflat.iam.gserviceaccount.com` — it lacks
`roles/iam.serviceAccountTokenCreator` on that account, and cannot grant it to
itself. Writing directly as `anthony@` works, which is why the Stamps loader has
`--no-impersonate`. Give the FedEx loader the same flag and the same default, and
do not build anything that depends on the impersonation working until someone
grants that role.

### Done looks like

- `prepare` parses the files, prints per-file and deduped totals, and writes
  nothing.
- `load` stages, merges, then prints the FedEx invariants and refuses rather than
  double-counting if they would break.
- `docs/fedex-shipping-costs.md` explains the grain difference from Stamps in its
  first paragraph, since that is the thing a reader will otherwise get wrong.
- A dry run on real files reproduces: 3,697 charge lines, 3,688 shipments, 4,266
  repeats collapsed, $100,883.90 total.
- Committed to a branch, not `main`.

## Copy to here
