"""Check apply_vas_pallet_check against the real Savannah pallet work orders.

Cases are the actual notes strings and totals from finance.yusen_invoices, so a
passing run means the rule agrees with the ledger on invoices a human has already
judged, and resolves the ones that were stuck.

    python3 skill-updates/v1.6.0/test_vas_pallet_check.py
"""
import sys
import types
from pathlib import Path

g = types.ModuleType("google"); c = types.ModuleType("google.cloud")
b = types.ModuleType("google.cloud.bigquery")


class _P:
    def __init__(self, *a, **k):
        pass


b.Client = _P; b.ScalarQueryParameter = _P; b.QueryJobConfig = _P
sys.modules.update({"google": g, "google.cloud": c, "google.cloud.bigquery": b})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_rate_card as V  # noqa: E402

# invoice, notes, amount, expected status, expected variance
CASES = [
    # --- the $10.00 MSA all-in era: these were stuck at needs_detail ---
    ("756396", "WORK ORDER 5001859 PALLETS (Savannah) - 7 PALLETS W/SHRINKWRAP @ $10.00/PALLET",
     70.00, "valid", 0.0),
    ("755908", "WORK ORDER 5001847 PALLETS (Savannah) - 49 PALLETS W/SHRINKWRAP @ $10.00/PALLET",
     490.00, "valid", 0.0),
    ("755675", "WORK ORDER 5001844 PALLETS (Savannah) - 56 PALLETS W/SHRINKWRAP @ $10.00/PALLET",
     560.00, "valid", 0.0),
    # --- the $14.317 combined pallet+wrap era: disputed for the wrap component ---
    ("755266", "WORK ORDER 5001833 PALLETS (Savannah) - 40 PALLETS W/SHRINKWRAP @ $14.317/PALLET",
     572.68, "disputed", 172.68),
    ("754854", "WORK ORDER 5001824 PALLETS - 10 PALLETS W/SHRINKWRAP @ $14.317/PALLET",
     143.17, "disputed", 43.17),
    ("754388", "WORK ORDER 5001786 PALLETS - 48 pallets w/shrinkwrap @ $14.317",
     687.22, "disputed", 207.22),
    ("754391", "WORK ORDER 5001793 PALLETS - 57 pallets w/shrinkwrap @ $14.317",
     816.07, "disputed", 246.07),
    ("754386", "WORK ORDER 5001778 PALLETS - 75 pallets w/shrinkwrap @ $14.317",
     1073.78, "disputed", 323.78),
    ("754532", "WORK ORDER 5001801 PALLETS - 13 pallets w/shrinkwrap @ $14.317",
     186.12, "disputed", 56.12),
    # --- pre-MSA $11.74: NOT grandfathered (Anthony, 2026-08-12) ---
    ("752058", "WORK ORDER 5001727 PALLETS - 57 pallets @ $11.74", 669.18, "disputed", 99.18),
    ("752056", "WORK ORDER 5001721 PALLETS (Savannah) - 30 pallets @ $11.74", 352.20, "disputed", 52.20),
    ("750984", "WORK ORDER 5001697 PALLETS - 25 pallets @ $11.74", 293.50, "disputed", 43.50),
    ("750576", "WORK ORDER 5001690 PALLETS (Savannah) - 64 pallets @ $11.74", 751.36, "disputed", 111.36),
    ("750206", "WORK ORDER 5001678 PALLETS (Savannah) - 41 pallets @ $11.74", 481.34, "disputed", 71.34),
]

# Non-pallet VAS work orders: the rule must not touch these at all.
UNTOUCHED = [
    ("756671", "WORK ORDER: 5001877 P65 Cancer Warning Labels (SAVANNAH)", 6.72),
    ("755701", "WORK ORDER 5001838 MAY 2026 CONSOLIDATION PROJECT - 24.49 HRS", 1542.87),
    ("754284", "WORK ORDER 5001797 FBA VAS Re-Labeling (Savannah) - 55 hrs @ $53.55", 2945.25),
    ("756631", "WORK ORDER: 5001873 AMAZOM RE-LABELING REQUEST", 589.05),
]

fails = []


def result_for(notes, amount, itype="VAS"):
    inv = {"invoice_number": "T", "type_of_invoice": itype, "warehouse": "TS South (SC)",
           "amount": amount, "notes": notes, "date": "2026-07-31", "bill_period": "",
           "validation_status": "", "validation_report": ""}
    r = {"invoice_number": "T", "status": "needs_detail", "billed_amount": amount,
         "variance": None, "discrepancies": [], "warehouse": "south_carolina",
         "invoice_type": itype}
    V.apply_vas_pallet_check(inv, r)
    return r


print("Savannah pallet work orders — recompute, then rate vs AF-9 $10.00 all-in\n")
print(f"  {'invoice':9}{'amount':>10}  {'got':11}{'want':11}{'variance':>10}{'want':>10}")
print("  " + "-" * 62)
for inv, notes, amount, want_status, want_var in CASES:
    r = result_for(notes, amount)
    got_var = r.get("variance")
    ok = r["status"] == want_status and abs((got_var or 0) - want_var) < 0.005
    if not ok:
        fails.append(f"{inv}: got {r['status']}/{got_var}, want {want_status}/{want_var}")
    print(f"  {'OK ' if ok else 'BAD'} {inv:6}{amount:>10,.2f}  {r['status']:11}{want_status:11}"
          f"{(got_var if got_var is not None else 0):>10,.2f}{want_var:>10,.2f}")

print("\nNon-pallet VAS work orders must be left alone")
for inv, notes, amount in UNTOUCHED:
    r = result_for(notes, amount)
    ok = not r.get("_pallet_rule") and r["status"] == "needs_detail"
    if not ok:
        fails.append(f"{inv}: rule fired on a non-pallet VAS job -> {r['status']}")
    print(f"  {'OK ' if ok else 'BAD'} {inv:8} untouched={not r.get('_pallet_rule')}  "
          f"status={r['status']}")

print("\nGuards")
checks = [
    ("work-order number is never read as a quantity",
     result_for("WORK ORDER 5001859 PALLETS - 7 PALLETS W/SHRINKWRAP @ $10.00/PALLET",
                70.00).get("variance") == 0.0),
    ("non-VAS invoice types are ignored",
     not result_for("57 pallets @ $11.74", 669.18, itype="Storage").get("_pallet_rule")),
    ("a line that does not recompute is a discrepancy, not a dispute",
     result_for("PALLETS - 10 pallets @ $10.00", 250.00)["status"] == "discrepancy"),
    ("a rate below the all-in is flagged, not silently accepted",
     result_for("PALLETS - 10 pallets @ $8.00", 80.00)["status"] == "discrepancy"),
    ("the pallet rule blocks the generic conflict detector from re-judging",
     True),
]
for name, ok in checks:
    if not ok:
        fails.append(name)
    print(f"  {'OK ' if ok else 'BAD'} {name}")

# The last guard, exercised properly: apply_msa_conflicts must not overwrite.
r = result_for("WORK ORDER 5001786 PALLETS - 48 pallets w/shrinkwrap @ $14.317", 687.22)
before = r["variance"]
V.apply_msa_conflicts({"notes": "48 pallets w/shrinkwrap @ $14.317", "type_of_invoice": "VAS"}, r)
if r["variance"] != before:
    fails.append(f"apply_msa_conflicts overwrote the pallet-rule variance "
                 f"({before} -> {r['variance']})")
print(f"  {'OK ' if r['variance'] == before else 'BAD'} variance survives "
      f"apply_msa_conflicts ({before})")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURES:"))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
