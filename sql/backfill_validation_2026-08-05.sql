-- Backfill: MSA dispute statuses + detailed validation notes (2026-08-05)
--
-- Run from the Mac (needs gcloud ADC write access; the cloud proxy credential
-- is read-only):
--   bq query --use_legacy_sql=false --max_rows=50 < sql/backfill_validation_2026-08-05.sql
--
-- What it does:
--   * Sets validation_status='disputed' on the 13 invoices with MSA billing
--     conflicts (AF-7 pack-out, AF-9 wrap, "Per Additional Ecom Pick" basis).
--   * Puts the disputed dollar amount in validation_variance so the dashboard
--     chip reads "disputed $X".
--   * Appends a detailed per-invoice spec to validation_report (rendered as
--     the chip tooltip / report card on both dashboards). Existing payment
--     report cards on 754699/754704 are preserved (append, not overwrite).
--   * Adds informational notes to 3 clean invoices (no status change).
--
-- Source: validation-reports/yusen-msa-billing-dispute-2026-08-05.md
-- NOTE: rows must be out of the streaming buffer (all are; oldest-newest
-- ingested well over 90 min ago). Re-runnable but NOT idempotent for the
-- report append — running twice duplicates the addendum text.

-- ---------- NJ SP/LTL ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 677.26,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $677.26 (AF-7/AF-9). Three-axis: invoice math exact; rates match MSA schedule; Stedi 3,773/3,773 orders verified. Disputed lines: STRETCHWRAP STD 134 x 4.347 = $582.50 (AF-9: national pallet rate $10.00 all-in incl. wrap); PACK CARTON (11+92) x 0.92 = $94.76 (Per Pack Out removed per Yusen 4/28). HOLD per Anthony 7/27. Clean payable $16,853.66.'), '\n ')
WHERE invoice_number = '754698';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 569.23,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $569.23 - ALREADY PAID 8/1, credit-memo claim. STRETCHWRAP STD 121 x 4.347 = $525.99 (AF-9 all-in pallet); PACK CARTON 47 x 0.92 = $43.24 (AF-7, removed 4/28). All other lines validated: math exact, MSA-schedule rates.'), '\n ')
WHERE invoice_number = '754699';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 283.41,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $283.41. Math exact: all 12 worksheet lines recompute to the penny; sections $8,632.98 + $4,108.30 = $12,741.28. Rates match MSA schedule: ecom order 2.2264, ship cartons 1.7871, order fee 2.1735, small parcels 0.6532, UCC 0.30, BOL 6.50. Disputed: STRETCHWRAP STD 58 x 4.347 = $252.13 (AF-9 all-in pallet); PACK CARTON 34 x 0.92 = $31.28 (AF-7, removed 4/28). Stedi order-level pass still pending (~3,849 orders in supporting doc). Clean payable $12,457.87.'), '\n ')
WHERE invoice_number = '754702';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 778.11,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $778.11 - ALREADY PAID 8/1, credit-memo claim. STRETCHWRAP STD 179 x 4.347 = $778.11 (AF-9: $10 pallet is all-in incl. wrap). All other lines validated.'), '\n ')
WHERE invoice_number = '754704';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 1072.40,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $1,072.40. STRETCHWRAP STD 114 x 4.347 = $495.56 (AF-9 all-in pallet); PACK CARTON 627 x 0.92 = $576.84 (AF-7, removed 4/28 - largest pack-out charge in the era). Other lines: math exact, MSA-schedule rates. Clean payable $17,629.24.'), '\n ')
WHERE invoice_number = '755486';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 18.40,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $18.40: PACK CARTON 20 x 0.92 (AF-7, removed 4/28). Pallets billed $10.00 flat with NO wrap line - Yusen has adopted the AF-9 all-in structure on this invoice. Clean payable $11,057.11.'), '\n ')
WHERE invoice_number = '755721';

-- ---------- Fontana SP/LTL ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 4134.32,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $4,134.32. Math exact: all 11 worksheet lines penny-perfect, total $57,858.38. Stedi 8,965/8,966 orders (99.99%). Rates match MSA schedule: cartons 1.8887, order 2.1585, ecom 2.2264, small parcels 0.6879; pick rate 0.506 is a legit -8% cut from the 0.55 actually billed Mar-May (old-card 0.455 was never billed). Disputed: (1) wrap component 446 x 4.317 = $1,925.38 embedded in 14.317 pallet rate (AF-9: $10 all-in); (2) picks billed on EVERY pick - 11,024 billed incl. 7,030 single-unit orders - where the MSA line is "Per ADDITIONAL Ecom Pick"; compliant additional-only ~= 6,659 picks, overcharge $2,208.94 (floor $1,778.59). Clean payable $53,724.06.'), '\n ')
WHERE invoice_number = '754807';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 602.36,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED ~$602. Wrap component 121 x 4.317 = $522.36 embedded in 14.317 pallet rate (AF-9 all-in). PICK & PACK ECOM 411 x 0.506 = $207.97 billed on the every-pick basis; recompute additional-only from the supporting worksheet (est. ~$80 over). Other lines: math exact, MSA-schedule rates.'), '\n ')
WHERE invoice_number = '755131';

-- ---------- SC VAS (wrap component in 14.317 "PALLETS W/SHRINKWRAP") ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 323.78,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $323.78: wrap component 75 x 4.317 inside "75 PALLETS W/SHRINKWRAP @ 14.317" (AF-9: $10 all-in national pallet rate). Math exact. Compliant charge at $10.00 = $750.00.'), '\n ')
WHERE invoice_number = '754386';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 207.22,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $207.22: wrap component 48 x 4.317 inside "48 PALLETS W/SHRINKWRAP @ 14.317" (AF-9 all-in). Math exact. Compliant charge at $10.00 = $480.00.'), '\n ')
WHERE invoice_number = '754388';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 246.07,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $246.07: wrap component 57 x 4.317 inside "57 PALLETS W/SHRINKWRAP @ 14.317" (AF-9 all-in). Math exact. Compliant charge at $10.00 = $570.00.'), '\n ')
WHERE invoice_number = '754391';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 56.12,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $56.12: wrap component 13 x 4.317 inside "13 PALLETS W/SHRINKWRAP @ 14.317" (AF-9 all-in). Math exact. Compliant charge at $10.00 = $130.00.'), '\n ')
WHERE invoice_number = '754532';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 43.17,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[MSA DISPUTE 2026-08-05] DISPUTED $43.17: wrap component 10 x 4.317 inside "10 PALLETS W/SHRINKWRAP @ 14.317" (AF-9 all-in). Math exact. Compliant charge at $10.00 = $100.00.'), '\n ')
WHERE invoice_number = '754854';

-- ---------- Informational notes on clean invoices (status unchanged) ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[NOTE 2026-08-05] Stretchwrap billed at 4.00 vs the 4.725 on every other Mar-May NJ invoice: 189 pallets -> $137.03 UNDER-billed (AF favor). Below-schedule = flag only, not a dispute. Other lines per old schedule.'), '\n ')
WHERE invoice_number = '750091';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[NOTE 2026-08-05] Printed pallet rate 10.3724 is a typo: charged amount $898.48 = 87 x 10.3274 (the standard Fontana rate). No dollar impact.'), '\n ')
WHERE invoice_number = '750791';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''),
    '\n\n[NOTE 2026-08-05] Printed wrap rate 4.72 is a typo: charged amount $694.58 = 147 x 4.725 (the standard NJ rate). No dollar impact.'), '\n ')
WHERE invoice_number = '752870';
