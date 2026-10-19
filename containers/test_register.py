#!/usr/bin/env python3
"""Tests for register.py on subject lines copied from real WWL emails.

    python3 test_register.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from register import build, parse_message  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    ok = got == want
    print(f"{name:55} {'ok' if ok else 'FAIL'}")
    if not ok:
        failures += 1
        print(f"    want {want!r}\n    got  {got!r}")


p = parse_message("[nyc_ops] Arrival Notice - HBL: TAO26070091 - MBL: YMJAE235105936 - CONT: TLLU4085229 - "
                  "AMERICANFLAT CORPORATION",
                  "Arrival Notice - FCL Good day! … SHIPPER: DEZHOU NISSENS HANDICRAFT CO.,LTD VESSEL / VOYAGE SEASPAN")
check("single container arrival notice",
      (p["kind"], p["hbl"], p["mbl"], p["containers"], p["shipper"]),
      ("arrival_notice", "TAO26070091", "YMJAE235105936", ["TLLU4085229"], "DEZHOU NISSENS HANDICRAFT CO.,LTD"))

p = parse_message("[nyc_ops] Arrival Notice - HBL: TAO26080008 - MBL: ONEYTAOGQ4486900 - CONT: BEAU5456372, "
                  "NYKU5115110 - AMERICANFLAT")
check("two containers on one HBL", p["containers"], ["BEAU5456372", "NYKU5115110"])

p = parse_message("[nyc_ops] SAILING ADVICE - HBL: HCM26080083 - MBL: E490411918 - CONT: YMMU6821361 - AMERICANFLA",
                  "SHIPPER: Y&amp;J INTERNATIONAL CO.,LTD ETD")
check("sailing advice, HTML entity in shipper", (p["kind"], p["shipper"]),
      ("sailing_advice", "Y&J INTERNATIONAL CO.,LTD"))

rows = build([{"messages": [
    {"subject": "SAILING ADVICE - HBL: TAO26070091 - MBL: YMJAE235105936 - CONT: TLLU4085229", "date": "2026-08-09T01:00:00Z"},
    {"subject": "Arrival Notice - HBL: TAO26070091 - MBL: YMJAE235105936 - CONT: TLLU4085229", "date": "2026-10-12T16:45:37Z"},
    {"subject": "Re: Arrival Notice - HBL: TAO26070091 - MBL: YMJAE235105936 - CONT: TLLU4085229", "date": "2026-10-13T09:00:00Z"},
    {"subject": "Weekly update, no bill numbers", "date": "2026-10-13T09:00:00Z"},
]}])
check("one row per container, earliest date per kind",
      [(r["container"], r["sailing_advice"], r["arrival_notice"]) for r in rows],
      [("TLLU4085229", "2026-08-09", "2026-10-12")])

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
