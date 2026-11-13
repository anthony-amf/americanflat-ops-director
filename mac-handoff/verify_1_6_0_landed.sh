#!/bin/bash
# Did v1.6.0 actually reach the ledger?
#
# The launchd log says the job ran. Only the table says it wrote v1.6.0's
# verdicts. Run this after the first sweep on the new directory.
#
#   bash verify_1_6_0_landed.sh
#
# Reads only — no UPDATE, no DDL. Safe to run as often as you like.
#
# Baselines are as at 2026-09-10 11:00 UTC, before any v1.6.0 sweep:
#   storage notes quoting the legacy rate ($5.90/$5.98/$5.09) ...... 66
#   storage notes quoting the MSA rate    ($4.47/$4.34/$3.35) ......  0
#   756522 .......................................................... needs_detail
#   valid 261 · disputed 19 · needs_detail 101 · discrepancy 1 · unset 1
set -euo pipefail

read -r -d '' SQL <<'EOSQL' || true
SELECT
  COUNTIF(REGEXP_CONTAINS(validation_report, r'rate is .(5\.90|5\.98|5\.09)')) AS legacy_rate_notes,
  COUNTIF(REGEXP_CONTAINS(validation_report, r'rate is .(4\.47|4\.34|3\.35)')) AS msa_rate_notes,
  COUNTIF(validation_status = 'valid')        AS valid,
  COUNTIF(validation_status = 'disputed')     AS disputed,
  COUNTIF(validation_status = 'needs_detail') AS needs_detail,
  MAX(IF(invoice_number = '756522', validation_status, NULL)) AS status_756522,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', MAX(validated_at)) AS newest_stamp
FROM `americanflat.finance.yusen_invoices`
EOSQL

# --max_rows is mandatory: bq silently truncates at 100 rows without it.
bq query --use_legacy_sql=false --format=prettyjson --max_rows=1000 "$SQL" > /tmp/yusen_verify.json

python3 - <<'PY'
import json
r = json.load(open("/tmp/yusen_verify.json"))[0]
g = lambda k: int(r[k]) if r[k] is not None else 0
base = {"legacy_rate_notes": 66, "msa_rate_notes": 0, "valid": 261,
        "disputed": 19, "needs_detail": 101}

print(f"newest stamp in the table: {r['newest_stamp']}")
print(f"{'':2}{'check':34}{'before':>9}{'now':>9}")
for k in ("legacy_rate_notes", "msa_rate_notes", "valid", "disputed", "needs_detail"):
    print(f"  {k:34}{base[k]:>9}{g(k):>9}")
print(f"  {'756522':34}{'needs_detail':>9} -> {r['status_756522']}")
print()

ok = True
if g("msa_rate_notes") == 0:
    print("  NOT LANDED — no storage note quotes an MSA rate. The sweep either did not")
    print("               run, or it is still reading the old directory. Re-check step 1.")
    ok = False
elif g("legacy_rate_notes") > 0:
    print(f"  PARTIAL — {g('legacy_rate_notes')} note(s) still quote the legacy rate. Storage rows")
    print( "            settled or paid are not re-swept, so some may never be rewritten;")
    print( "            if the count is not falling run by run, that is the explanation.")
else:
    print("  LANDED — every storage note quotes the MSA rate.")

if r["status_756522"] == "valid":
    print("  LANDED — 756522 resolved (the hourly-overtime check).")
elif g("msa_rate_notes") > 0:
    print("  ODD — rates updated but 756522 did not resolve. Check the log for that")
    print("        invoice; it should read 4 hrs at 1.5x the Fontana general labour rate.")
    ok = False

if g("valid") < base["valid"] or g("disputed") < base["disputed"]:
    print(f"  STOP — valid went {base['valid']}->{g('valid')} and disputed {base['disputed']}->{g('disputed')}.")
    print( "         A sweep must never reduce either. Roll back and say so.")
    ok = False

raise SystemExit(0 if ok else 1)
PY
