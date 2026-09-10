"""Check the v1.5.0 report-merge fixes against the text that actually broke."""
import re
import sys
import types
from pathlib import Path

# The script imports google.cloud.bigquery at module scope; stub it so the pure
# report-composition helpers can be exercised without credentials.
g = types.ModuleType("google"); c = types.ModuleType("google.cloud")
bq = types.ModuleType("google.cloud.bigquery")
class _P:
    def __init__(self, *a, **k): pass
bq.Client = _P; bq.ScalarQueryParameter = _P; bq.QueryJobConfig = _P
sys.modules.update({"google": g, "google.cloud": c, "google.cloud.bigquery": bq})

sys.path.insert(0, "/home/user/americanflat-ops-director/skill-updates/v1.5.0")
import validate_rate_card as V

PRIOR = Path(__file__).with_name("fixtures-recovered_755265.txt").read_text()
fails = []

def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"   <- {detail}"))
    if not cond:
        fails.append(name)

print("1. merge_report keeps every other block (the mark_paid bug)")
paid_card = "Payment confirmed by the user. Basis: the DEEP PASS review already on this row."
merged = V.merge_report(PRIOR, paid_card, tag="PAID")
check("MSA REVAL survives", "[MSA REVAL 2026-08-06]" in merged)
check("DEEP PASS survives", "[DEEP PASS 2026-08-10]" in merged)
check("289/289 Stedi result survives", "289/289 orders shipped" in merged)
check("itemized line math survives", "3005 WHOLESALE CARTONS @1.6422=4,934.81" in merged)
check("PAID block added", "[PAID " in merged and paid_card in merged)
check("report grew, did not shrink", len(merged) > len(PRIOR),
      f"{len(PRIOR)} -> {len(merged)}")

print("\n2. a second payment mark replaces only the PAID block")
twice = V.merge_report(merged, "Second payment card.", tag="PAID")
check("one PAID block, not two", twice.count("[PAID ") == 1, f"count={twice.count('[PAID ')}")
check("DEEP PASS still there", "[DEEP PASS 2026-08-10]" in twice)
check("first paid card gone", paid_card not in twice)

print("\n3. AUTO merge still replaces only AUTO (v1.4.0 behaviour preserved)")
a = V.merge_report(PRIOR, "first auto")
b = V.merge_report(a, "second auto")
check("one AUTO block", b.count("[AUTO ") == 1, f"count={b.count('[AUTO ')}")
check("DEEP PASS untouched", "[DEEP PASS 2026-08-10]" in b)
check("prior auto text gone", "first auto" not in b)

print("\n4. header-level pass defers instead of contradicting the deep pass")
r = {"invoice_number": "755265", "status": "needs_detail", "billed_amount": 6064.07,
     "invoice_type": "SMLPRCL/LTL", "warehouse": "south_carolina", "period": "2026-07-14",
     "variance": None, "discrepancies": []}
defer = V._deferral_block(r, PRIOR)
check("names the deeper blocks", "DEEP PASS" in defer and "MSA REVAL" in defer, defer)
check("no 'provide itemized counts'", "provide itemized counts" not in defer, defer)
check("no false Stedi-pending claim",
      "Stedi check available" not in defer and "no order-level Stedi result" not in defer, defer)
check("says no new findings", "no new findings" in defer, defer)
print("     ->", defer)

print("\n5. a clean row still gets the normal full card")
check("no deeper block detected in empty report", not V._DEEPER_BLOCK.search(""))
card = V.compose_report(r)
check("normal card mentions itemized counts", "itemized counts" in card)
check("Stedi wording is accurate, not 'available'",
      "no order-level Stedi result recorded on this row yet" in card, card)

print("\n6. a completed Stedi result is printed when handed in")
r2 = dict(r, stedi_note="289/289 orders shipped (945), checked 2026-08-10")
check("stedi_note used", "289/289 orders shipped" in V.compose_report(r2))

print("\n7. _DEEPER_BLOCK recognises each deeper tag")
for tag in ("DEEP PASS", "STEDI", "MSA DISPUTE", "MSA REVAL"):
    check(f"detects [{tag}]", bool(V._DEEPER_BLOCK.search(f"[{tag} 2026-08-10] x")))
check("does NOT treat AUTO as deeper", not V._DEEPER_BLOCK.search("[AUTO 2026-08-11] x"))
check("does NOT treat PAID as deeper", not V._DEEPER_BLOCK.search("[PAID 2026-08-11] x"))

print("\n8. what the 8/11 sequence would produce under v1.5.0")
step1 = V.merge_report(PRIOR.split("\n\n[AUTO")[0], V._deferral_block(r, PRIOR))
step2 = V.merge_report(step1, "Payment confirmed by the user on 2026-08-11. Basis: the "
                              "DEEP PASS, MSA REVAL review already on this row.", tag="PAID")
check("final report retains the deep pass", "289/289 orders shipped" in step2)
check("final report has all four blocks",
      all(t in step2 for t in ("[MSA REVAL", "[DEEP PASS", "[AUTO", "[PAID")))
check("final length beats the 386 chars actually stored", len(step2) > 1500, len(step2))
print(f"     -> {len(step2)} chars vs the 386 that v1.4.0 left behind")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
