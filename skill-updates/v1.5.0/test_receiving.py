#!/usr/bin/env python3
"""
Regression test for receiving.py — no BigQuery, no Drive.

Fifteen real receiving invoices (text as Google Drive extracts it from the
PDF, Yusen's bank lines removed) must all come back `valid` to the cent, and a
set of planted mistakes must each be caught.

    python3 test_receiving.py [dir containing receiving.py] [fixtures.jsonl]
"""

import json
import sys
from datetime import date
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else here))
from receiving import check_receiving  # noqa: E402

fixtures_path = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "receiving_fixtures.jsonl"
fixtures = {}
for row in fixtures_path.read_text().splitlines():
    if row.strip():
        f = json.loads(row)
        fixtures[f.pop("invoice")] = f
failures = 0


def expect(name, result, status, variance=None):
    global failures
    good = result["status"] == status and (variance is None or abs((result["variance"] or 0) - variance) < 0.006)
    print(f"{name:58} {result['status']:13} {'ok' if good else 'FAIL'}")
    if not good:
        failures += 1
        print(f"    expected {status} {variance}; got {result['variance']}\n    {result['line_report']}")


# ---- Real invoices: every one reconciles at its own warehouse's rates ------
for n, f in fixtures.items():
    r = check_receiving(f["text"], f["warehouse"], date.fromisoformat(f["date"]), f["amount"])
    expect(f"{n} {f['warehouse']} ${f['amount']:,.2f}", r, f["expect"])

# ---- Planted mistakes -------------------------------------------------------
nj = fixtures["749279"]["text"]  # NJ, 03/23–03/31, pre-June rates + 5% surcharge

# Old rates billed for a July week: three overcharges plus a surcharge that ended 4/27.
july = nj.replace("03/23/2026 AND 03/31/2026", "07/06/2026 AND 07/12/2026")
expect("old pre-June rates on a July week", check_receiving(july, "new_jersey", date(2026, 7, 14), 11371.98),
       "discrepancy", 795.35 + 33.85 + 37.04 + 541.52)

# NJ invoice filed under Fontana: NJ's higher carton rate is an overcharge.
expect("NJ invoice text filed as Fontana", check_receiving(nj, "fontana", date(2026, 3, 31), 11371.98),
       "discrepancy", 308.28 + 541.52)

# Fontana's lower carton rate on a New Jersey invoice: not an overcharge, but the
# warehouse looks wrong, so it can't be stamped valid.
cheap = ("INBOUND PROCESSING BETWEEN 09/07/2026 AND 09/12/2026 RECEIVED CARTONS 1,218 @ 0.9173 $ 1,117.27 "
         "CONTAINER ADMIN FEE 1 @47.334 $ 47.33")
expect("another site's lower rate", check_receiving(cheap, "new_jersey", date(2026, 9, 17), 1164.60),
       "needs_detail")

# Surcharge math off by a dollar.
bad_pct = nj.replace("@5.00% $ 541.52", "@5.00% $ 542.52").replace("11,371.98", "11,372.98")
expect("surcharge amount off by $1", check_receiving(bad_pct, "new_jersey", date(2026, 3, 31), 11372.98),
       "discrepancy", 1.00)

# Total doesn't match the lines.
expect("billed total $50 above the lines", check_receiving(nj, "new_jersey", date(2026, 3, 31), 11421.98),
       "needs_detail")

# A rate that isn't on the receiving card at all.
odd = ("INBOUND PROCESSING BETWEEN 09/07/2026 AND 09/12/2026 RECEIVED CARTONS 1,000 @ 1.2500 $ 1,250.00")
expect("unknown rate", check_receiving(odd, "fontana", date(2026, 9, 17), 1250.00), "needs_detail")

# South Carolina pre-June rates are derived, never seen on an invoice: hold for review.
sc = ("INBOUND PROCESSING BETWEEN 05/04/2026 AND 05/09/2026 RECEIVED CARTONS 1,000 @ 0.8400 $ 840.00 "
      "CONTAINER ADMIN FEE 1 @51.4021 $ 51.40")
expect("SC pre-June (derived rates)", check_receiving(sc, "south_carolina", date(2026, 5, 12), 891.40),
       "needs_detail")

# June-rate LTL delivery with its minimum, clean.
ltl = ("INBOUND PROCESSING BETWEEN 09/07/2026 AND 09/12/2026 LTL DELIVERY CARTONS 40 @ 0.7728 $ 30.91 "
       "LTL MINIMUM 1 @ 72.45 $ 72.45 CONTAINER STORAGE 2 @ 43.47 $ 86.94")
expect("LTL cartons + minimum + storage", check_receiving(ltl, "fontana", date(2026, 9, 17), 190.30), "valid")

# Nothing readable.
expect("no charge lines", check_receiving("scanned page", "fontana", date(2026, 9, 17), 100.0), "needs_detail")

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
