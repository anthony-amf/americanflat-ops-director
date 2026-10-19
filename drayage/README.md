# Drayage invoice check (O'Neill Logistics)

Checks an O'Neill drayage invoice (port → Edison NJ / Fontana CA / Hardeeville SC)
against the contracted rate sheet. Started 2026-10-19.

- `check_drayage.py` — the check. Reads invoice text or a JSON list of charges.
- `test_check_drayage.py` — 16 cases (clean invoices plus planted mistakes).
  The invoice layouts are made up until we have real O'Neill PDFs.

## Where the rates come from

`Dray_Rates-_Americanflat_4_3_2026.xlsx`, attached to the Notion
[Drayage Rates](https://app.notion.com/p/3828555c2abc8059b652c57cdde9bc8a) page.

| Charge | NJ (Edison) | CA (Fontana) | SC (Hardeeville, paused) |
|---|---|---|---|
| Line haul, per container (fuel incl. to $4.50/gal) | $450 | $525 | $300 |
| Chassis, O'Neill fleet / pool, per day | $25 / $45 | $25 / $45 | $25 / $45 |
| Pre-pull | $125 | $150 | $100 |
| Yard storage, per day | $40 | $50 | $30 |
| Off-dock return | $150 | $200 | $100 local / $150 Rincon |
| Attempted pick-up | $250 | $250 | $200 |
| Detention / live unload | 2 hrs free, then $85/hr | same | same |
| Bobtail | ½ lane rate | ½ lane rate | ½ lane rate |
| Empty container/chassis positioning | $200 | $200 | — |
| Saturday delivery, per driver | $250 | $250 (if available) | $250 |
| Triaxle, per day | $75 | — | $75 |
| Bonded freight, per container | $75 | — | $75 |
| Ocean terminal surcharge | — | — | $100 |

Terms from O'Neill's weekly statement email: per diem they advance carries a
**10% admin fee** and is due in 7 days; disputes must be registered on their
portal within **14 days** of the invoice; late payment is 1.5%/month.

## What it checks

- Line haul at the lane rate; bobtail at half.
- Each accessorial at its sheet rate × quantity, and the invoice's own line math.
- Fuel: none while diesel is at or below $4.50/gal; above that, the % from
  O'Neill's matrix (needs the EIA diesel price for the billing week — pass
  `--diesel`).
- Per diem admin fee = exactly 10% of the per diem. The per diem itself needs
  the ocean carrier's bill, so it always stays `needs_detail`.
- Charges add up to the invoice total; container count vs. line-haul moves.
- Pool chassis and detention are allowed but noted (ask why / confirm the
  free hours were excluded).

Result: `valid`, `discrepancy` (overcharge in the variance, payable amount in
the report) or `needs_detail` — the same words the Yusen ledger uses.

## Open questions

1. **Fuel threshold conflict.** The lane sheets say fuel is included up to
   $4.50/gal; the FSC matrix tab in the same workbook starts charging above
   $4.00 (1.2% per 10¢). The check follows the lane sheets. Confirm with O'Neill.
2. **Real invoices.** Only three came by email (N0185062 $798.29, N0185063
   $548.29, N0190164 $803.91); the rest go through bill.com. Need the PDFs —
   and the weekly statement xlsx — to tune the text reader to O'Neill's layout.
3. **Where results are stored.** Drayage isn't a Yusen invoice, so it doesn't
   belong in `yusen_invoices`. Planned home is `finance.freight_invoices`
   (needs Iván to grant write access) with an invoice-type column.
