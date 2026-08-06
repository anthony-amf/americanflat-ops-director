-- Post-May-31 MSA revalidation stamps (2026-08-06)
--
-- Source: full re-parse of all 113 post-May US invoice PDFs against the MSA
-- rate schedule (7.15 draft; Anthony confirmed 8/5 the rates are final).
-- Key fix vs earlier sweeps: Yusen page-1 lines print rates TRUNCATED to 2dp
-- (1.7871 -> 1.78, 4.347 -> 4.34) while amounts use full precision -- the
-- earlier needs_detail stamps (e.g. 754889 vs the stale 5.09 card) came from
-- matching printed rates against old-card values.
--
-- Run ONCE from the Mac (cloud BigQuery credential is read-only):
--   bq query --use_legacy_sql=false --max_rows=50 < sql/backfill_postmay_revalidation_2026-08-06.sql
--
-- Guards:
--   * Existing disputed rows are never touched (13 rows keep their stamps).
--   * valid stamps only land on rows currently NULL or needs_detail, so a
--     second run no-ops (status is already valid).
--   * SP/LTL rows are NOT stamped valid on header evidence alone (hard rule:
--     SP/LTL validation includes Stedi) -- they get/keep needs_detail with an
--     MSA-header-pass note; the Stedi deep pass upgrades them later.
--   * SUPERSEDES sql/backfill_vas_validation_fixup_2026-08-05.sql -- the four
--     invoices it covered (755985, 756498, 756525, 756527) are stamped here
--     with the stronger guard. If the fixup already ran, they no-op here; do
--     not run the fixup after this file.
--   * NEW dispute found this sweep: 756156 (NJ SP/LTL 7/31) bills PACK CARTON
--     24 x 0.92 = $22.08 after the 4/28 AF-7 removal -- stamped disputed.

-- ---------- 30 rows -> valid (storage / receiving / admin / VAS) ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 3,097 x 3.35 storage SC = $10,374.95.'), '\n ')
WHERE invoice_number = '753550' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,510 x 3.35 storage SC = $8,408.50.'), '\n ')
WHERE invoice_number = '753558' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 3 line(s) at MSA rates: 24,315 x 0.9173 recv carton CA = $22,304.15; 377 x 31.2981 sortation CA = $11,799.38; 28 x 52.8831 container admin CA = $1,480.73.'), '\n ')
WHERE invoice_number = '754676' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 4,742 x 4.34 storage NJ = $20,580.28.'), '\n ')
WHERE invoice_number = '754864' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,346 x 3.35 storage SC = $7,859.10.'), '\n ')
WHERE invoice_number = '754889' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 2 line(s) at MSA rates: 4,764 x 4.47 storage CA = $21,295.08; 209 x 4.47 storage CA = $934.23.'), '\n ')
WHERE invoice_number = '755001' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 2 line(s) at MSA rates: 876 x 0.9173 recv carton CA = $803.55; 1 x 52.8831 container admin CA = $52.88.'), '\n ')
WHERE invoice_number = '755033' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 4,526 x 4.34 storage NJ = $19,642.84.'), '\n ')
WHERE invoice_number = '755213' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,332 x 3.35 storage SC = $7,812.20.'), '\n ')
WHERE invoice_number = '755264' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,193 x 3.35 storage SC = $7,346.55.'), '\n ')
WHERE invoice_number = '755549' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 4,169 x 4.34 storage NJ = $18,093.46.'), '\n ')
WHERE invoice_number = '755601' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 3 line(s) at MSA rates: 5,539 x 4.47 storage CA = $24,759.33; 133 x 4.47 storage CA = $594.51; 4 x 0.7312 storage per bin CA = $2.92.'), '\n ')
WHERE invoice_number = '755705' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 2 line(s) at MSA rates: 7,003 x 0.9173 recv carton CA = $6,423.85; 9 x 52.8831 container admin CA = $475.95.'), '\n ')
WHERE invoice_number = '755726' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 4,024 x 4.34 storage NJ = $17,464.16.'), '\n ')
WHERE invoice_number = '755825' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,091 x 3.35 storage SC = $7,004.85.'), '\n ')
WHERE invoice_number = '755895' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 3 line(s) at MSA rates: 5,564 x 4.47 storage CA = $24,871.08; 169 x 4.47 storage CA = $755.43; 4 x 0.7312 storage per bin CA = $2.92.'), '\n ')
WHERE invoice_number = '755982' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 2 line(s) at MSA rates: 4,305 x 0.9173 recv carton CA = $3,948.98; 6 x 52.8831 container admin CA = $317.30.'), '\n ')
WHERE invoice_number = '755983' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 0 x 53.55 hourly = $26.78.'), '\n ')
WHERE invoice_number = '755985' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2 x 53.55 hourly = $107.10.'), '\n ')
WHERE invoice_number = '756179' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 3,936 x 4.34 storage NJ = $17,082.24.'), '\n ')
WHERE invoice_number = '756321' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 2,066 x 3.35 storage SC = $6,921.10.'), '\n ')
WHERE invoice_number = '756351' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 3 line(s) at MSA rates: 5,383 x 4.47 storage CA = $24,062.01; 220 x 4.47 storage CA = $983.40; 4 x 0.7312 storage per bin CA = $2.92.'), '\n ')
WHERE invoice_number = '756442' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 14 x 31.2981 sortation CA = $438.17.'), '\n ')
WHERE invoice_number = '756474' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 161 x 31.2981 sortation CA = $5,038.99.'), '\n ')
WHERE invoice_number = '756475' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 115 x 31.2981 sortation CA = $3,599.28.'), '\n ')
WHERE invoice_number = '756476' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 86 x 31.2981 sortation CA = $2,691.64.'), '\n ')
WHERE invoice_number = '756477' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 3 line(s) at MSA rates: 4,101 x 0.9173 recv carton CA = $3,761.85; 82 x 31.2981 sortation CA = $2,566.44; 5 x 52.8831 container admin CA = $264.42.'), '\n ')
WHERE invoice_number = '756479' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 914 x 0.42 label = $383.88.'), '\n ')
WHERE invoice_number = '756498' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 58 x 0.3 UCC/label = $17.40.'), '\n ')
WHERE invoice_number = '756525' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] VALID vs MSA rate schedule (rates final per Anthony 8/5). Invoice math exact, rates on schedule. 1 line(s) at MSA rates: 40 x 59.8278 hourly = $2,393.11.'), '\n ')
WHERE invoice_number = '756527' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

-- ---------- 9 SP/LTL rows: MSA header pass done, Stedi pending -> needs_detail ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 4 line(s) at MSA rates: 503 x 1.6422 ship carton SC = $826.03; 84 x 2.7531 ecom pnp carton SC = $231.26; 28 x 6.5 BOL = $182.00; 45 x 0.5796 additional ecom pick SC = $26.08. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '754891' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 5 line(s) at MSA rates: 3,005 x 1.6422 ship carton SC = $4,934.81; 85 x 6.5 BOL = $552.50; 128 x 2.7531 ecom pnp carton SC = $352.40; 205 x 0.84 small parcels SC = $172.20; 90 x 0.5796 additional ecom pick SC = $52.16. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '755265' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 5 line(s) at MSA rates: 1,146 x 1.6422 ship carton SC = $1,881.96; 183 x 2.7531 ecom pnp carton SC = $503.82; 18 x 6.5 BOL = $117.00; 78 x 0.5796 additional ecom pick SC = $45.21; 48 x 0.84 small parcels SC = $40.32. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '755550' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 11 line(s) at MSA rates: 4,149 x 1.8887 ship carton CA = $7,836.22; 991 x 2.2264 ecom order = $2,206.36; 181 x 10.0 pallet all-in = $1,810.00; 4,149 x 0.3 UCC/label = $1,244.70; 1,451 x 0.506 additional ecom pick = $734.21; 51 x 6.5 BOL = $331.50; 54 x 2.1585 order fee CA = $116.56; 47 x 1.8887 ship carton CA = $88.77; 47 x 0.6879 small parcels CA = $32.33; 12 x 2.1585 order fee CA = $25.90; 47 x 0.3 UCC/label = $14.10. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '755725' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 5 line(s) at MSA rates: 991 x 1.6422 ship carton SC = $1,627.42; 347 x 2.7531 ecom pnp carton SC = $955.33; 376 x 0.5796 additional ecom pick SC = $217.93; 25 x 6.5 BOL = $162.50; 79 x 0.84 small parcels SC = $66.36. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '755896' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 11 line(s) at MSA rates: 1,528 x 1.8887 ship carton CA = $2,885.93; 1,241 x 2.2264 ecom order = $2,762.96; 1,956 x 0.506 additional ecom pick = $989.74; 72 x 10.0 pallet all-in = $720.00; 1,528 x 0.3 UCC/label = $458.40; 26 x 6.5 BOL = $169.00; 89 x 1.8887 ship carton CA = $168.09; 89 x 0.6879 small parcels CA = $61.22; 26 x 2.1585 order fee CA = $56.12; 89 x 0.3 UCC/label = $26.70; 6 x 2.1585 order fee CA = $12.95. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '756028' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 5 line(s) at MSA rates: 242 x 2.7531 ecom pnp carton SC = $666.25; 150 x 1.6422 ship carton SC = $246.33; 155 x 0.5796 additional ecom pick SC = $89.84; 62 x 0.84 small parcels SC = $52.08; 5 x 6.5 BOL = $32.50. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '756355' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 10 line(s) at MSA rates: 2,757 x 2.2264 ecom order = $6,138.18; 1,819 x 1.7871 ship carton NJ = $3,250.73; 75 x 10.0 pallet all-in = $750.00; 1,819 x 0.3 UCC/label = $545.70; 40 x 6.5 BOL = $260.00; 94 x 1.7871 ship carton NJ = $167.99; 49 x 2.1735 order fee NJ = $106.50; 40 x 2.1735 order fee NJ = $86.94; 94 x 0.6532 small parcels NJ = $61.40; 94 x 0.3 UCC/label = $28.20. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '756472' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'needs_detail',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 11 line(s) at MSA rates: 3,415 x 1.8887 ship carton CA = $6,449.91; 1,154 x 2.2264 ecom order = $2,569.27; 173 x 10.0 pallet all-in = $1,730.00; 3,415 x 0.3 UCC/label = $1,024.50; 1,883 x 0.506 additional ecom pick = $952.80; 235 x 1.8887 ship carton CA = $443.84; 38 x 6.5 BOL = $247.00; 235 x 0.6879 small parcels CA = $161.66; 60 x 2.1585 order fee CA = $129.51; 59 x 2.1585 order fee CA = $127.35; 235 x 0.3 UCC/label = $70.50. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.'), '\n ')
WHERE invoice_number = '756521' AND IFNULL(validation_status,'') IN ('', 'needs_detail');

-- ---------- 1 NEW disputed ----------

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'disputed',
  validation_variance = 22.08,
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'msa-reval-2026-08-06',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[MSA DISPUTE 2026-08-06] DISPUTED $22.08 (AF-7). PACK CARTON 24 x 0.92 = $22.08 (Per Pack Out removed per Yusen 4/28). All other page-1 lines at MSA-schedule rates, math exact. Stedi order-level pass pending. Clean payable $10,263.58.'), '\n ')
WHERE invoice_number = '756156' AND IFNULL(validation_status,'') != 'disputed';

-- Verify:
SELECT IFNULL(validation_status,'(null)') s, COUNT(*) n, ROUND(SUM(CAST(amount AS FLOAT64)),2) total
FROM `americanflat.finance.yusen_invoices`
WHERE validated_by = 'msa-reval-2026-08-06'
GROUP BY s ORDER BY s;
