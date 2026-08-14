-- Restore the validation_report history that --mark-paid overwrote
--
-- 2026-08-11: `validate_rate_card.py <inv> --mark-paid` stored its payment
-- report card with `validation_report = COALESCE(@report, validation_report)`
-- — a full replace, not a merge. On 754891 and 755265 that discarded the
-- [MSA REVAL 2026-08-06] and [DEEP PASS 2026-08-10] blocks (1,741 and 1,644
-- chars down to 386), including the itemized line math and the 106/106 and
-- 289/289 Stedi order matches. Both rows are `valid` + paid, so no future
-- sweep would ever have rebuilt them.
--
-- The text below was recovered from BigQuery time travel at 2026-08-11
-- 16:00/16:04 UTC, immediately before each overwrite. The two recovered blocks
-- go back verbatim; the header-level [AUTO] block is rewritten so it no longer
-- contradicts the deep pass; a [PAID] block is appended.
--
-- Additive: only validation_report changes, and only on a row that does not
-- already carry its [DEEP PASS] block. Safe to re-run — once restored, the row
-- has the block and the guard makes a second run a no-op.
--
-- (The guard was originally LENGTH(validation_report) < 500, matching the 386-char
-- clobbered state. A header-level Mac sweep later appended an [AUTO] block to both
-- rows, taking them to 764 chars, so that guard silently stopped matching and the
-- script became a no-op. Keying on the missing block instead is immune to that.)
--
-- Run once from the Mac. Fix for the underlying bug: skill v1.5.0
-- (skill-updates/v1.5.0/, mark_paid now merges instead of replacing).

-- 754891: restores [MSA REVAL, DEEP PASS]
UPDATE `americanflat.finance.yusen_invoices`
SET validation_report = '''[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 4 line(s) at MSA rates: 503 x 1.6422 ship carton SC = $826.03; 84 x 2.7531 ecom pnp carton SC = $231.26; 28 x 6.5 BOL = $182.00; 45 x 0.5796 additional ecom pick SC = $26.08. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.

[DEEP PASS 2026-08-10] Invoice 754891 - SMLPRCL/LTL, TS South (SC), outbound 07/01-07/06/2026, $1,265.37
Invoice math: OK exact. 84 ECOM PNP CARTONS @2.7531=231.26 (=distinct ECOM carton HUIDs); 45 ADDITIONAL ECOM PICKS @0.5796=26.08 (=129 ECOM units - 84 cartons); 503 WHOLESALE CARTONS @1.6422=826.03 (=distinct wholesale HUIDs); 28 WHOLESALE BOLS @6.50=182.00 (=distinct wholesale BOLs). Sum=1,265.37 = invoice total.
Rate card: OK 1.6422 and 0.5796 match live Notion card. Card gaps (not overbilling): SC ecom pnp carton 2.7531 and SC BOL 6.50 are blank in the SC column; 2.7531 is the ~8% June-2026 cut off the old SC 2.99 DTC rate, 6.50 is the national MSA BOL rate.
MSA dispute screen: clean - no separate stretchwrap, no pack-out, ecom picks billed additional-only.
Stedi: 106/106 orders shipped (945). 78 small parcel + 28 LTL. One order needed the documented id-hygiene fix (6719203862-1 in the report = 6719203862_1 in Stedi).
Verdict: OK to pay.

[AUTO 2026-08-11] Invoice 754891 — header-level re-check only. Itemized math, rate card and the order-level Stedi result are already on file in the [DEEP PASS 2026-08-10] block above; this pass adds no new findings and does not supersede it.

[PAID 2026-08-11] Payment confirmed by Anthony. Basis: the [DEEP PASS 2026-08-10] review above (invoice math exact, rates match the card, MSA screen clean, Stedi order match 106/106). Verdict at approval: OK to pay.'''
WHERE invoice_number = '754891'
  AND validation_report NOT LIKE '%[DEEP PASS%';

-- 755265: restores [MSA REVAL, DEEP PASS]
UPDATE `americanflat.finance.yusen_invoices`
SET validation_report = '''[MSA REVAL 2026-08-06] MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines at MSA-schedule rates. 5 line(s) at MSA rates: 3,005 x 1.6422 ship carton SC = $4,934.81; 85 x 6.5 BOL = $552.50; 128 x 2.7531 ecom pnp carton SC = $352.40; 205 x 0.84 small parcels SC = $172.20; 90 x 0.5796 additional ecom pick SC = $52.16. Stedi order-level pass + worksheet deep pass still pending (SP/LTL payment gate) -- status stays needs_detail until run.

[DEEP PASS 2026-08-10] Invoice 755265 - SMLPRCL/LTL, TS South (SC), outbound 07/07-07/13/2026, $6,064.07
Invoice math: OK exact, all five lines tie to the supporting shipped report. 128 ECOM PNP CARTONS @2.7531=352.40 (=distinct ECOM HUIDs 128); 90 ADDITIONAL ECOM PICKS @0.5796=52.16 (=218 units - 128 cartons); 3005 WHOLESALE CARTONS @1.6422=4,934.81 (=distinct wholesale HUIDs 3005); 205 WHOLESALE CARTONS FOR UPS/FEDEX @0.84=172.20 (=wholesale cartons on UPS/FedEx 205); 85 WHOLESALE BOLS @6.50=552.50 (=distinct truck BOLs excl UPS/FedEx 85). Sum=6,064.07.
Rate card: OK 1.6422 / 0.5796 / 0.84 match live Notion card. Same two SC card gaps as 754891 (2.7531 ecom carton, 6.50 BOL).
MSA dispute screen: clean.
Stedi: 289/289 orders shipped (945). 128 small parcel + 161 LTL. 1 id-hygiene fix.
Verdict: OK to pay.

[AUTO 2026-08-11] Invoice 755265 — header-level re-check only. Itemized math, rate card and the order-level Stedi result are already on file in the [DEEP PASS 2026-08-10] block above; this pass adds no new findings and does not supersede it.

[PAID 2026-08-11] Payment confirmed by Anthony. Basis: the [DEEP PASS 2026-08-10] review above (invoice math exact, rates match the card, MSA screen clean, Stedi order match 289/289). Verdict at approval: OK to pay.'''
WHERE invoice_number = '755265'
  AND validation_report NOT LIKE '%[DEEP PASS%';

-- Verify afterwards:
-- SELECT invoice_number, LENGTH(validation_report) len,
--        validation_report LIKE '%[DEEP PASS%' has_deep,
--        validation_report LIKE '%[PAID %'     has_paid
-- FROM `americanflat.finance.yusen_invoices`
-- WHERE invoice_number IN ('754891','755265');
-- Expect len ~1,900 and both flags true on each row.
