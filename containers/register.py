#!/usr/bin/env python3
"""
Container register from WWL's shipment emails.

WWL's arrival notices and sailing advices put the house bill (HBL), master
bill (MBL) and container numbers in the subject line, and the shipper in the
first lines of the body:

    [nyc_ops] Arrival Notice - HBL: TAO26070091 - MBL: YMJAE235105936 - CONT: TLLU4085229 - AMERICANFLAT …
    Arrival Notice - FCL … SHIPPER: DEZHOU NISSENS HANDICRAFT CO.,LTD VESSEL / VOYAGE …

The container number is the key that ties one inbound container's bills
together: WWL ocean freight (by HBL), the customs entry (by HBL/container),
O'Neill drayage (by container) and Yusen receiving (by container — the
receiving worksheet lists "PO: AME*MSMU6558953-051126 … Container: MSMU6558953").

This turns Gmail search results (the JSON the Gmail connector returns) into
one row per container. Later the same rows can be written to BigQuery.

    python3 register.py gmail_search_results.json [--csv out.csv]
"""

import argparse
import csv
import html
import json
import re
import sys

_HBL = re.compile(r"\bHBL[#:\s]*([A-Z]{3}\d{8,})", re.I)
_MBL = re.compile(r"\bMBL[#:\s]*([A-Z0-9]{8,})", re.I)
_CONT_FIELD = re.compile(r"\bCONT(?:AINER)?S?[#:\s]*((?:[A-Z]{4}\d{7}[,\s/&]*)+)", re.I)
_CONTAINER = re.compile(r"\b([A-Z]{3}[UJZ]\d{7})\b")
_SHIPPER = re.compile(r"SHIPPER:\s*(.+?)(?:\s+(?:VESSEL|CONSIGNEE|ETD|ETA|POL|POD)\b|$)", re.I)
_KIND = (("arrival notice", "arrival_notice"), ("sailing advice", "sailing_advice"),
         ("delivery order", "delivery_order"), ("invoice", "invoice"))


def parse_message(subject: str, snippet: str = "") -> dict:
    s = html.unescape(subject or "")
    snippet = html.unescape(snippet or "")
    kind = next((k for word, k in _KIND if word in s.lower()), "other")
    hbl = _HBL.search(s) or _HBL.search(snippet or "")
    mbl = _MBL.search(s)
    cf = _CONT_FIELD.search(s)
    containers = _CONTAINER.findall(cf.group(1)) if cf else []
    if not containers:
        containers = _CONTAINER.findall(s)
    shipper = _SHIPPER.search(snippet or "")
    return dict(kind=kind, hbl=hbl.group(1).upper() if hbl else None, mbl=mbl.group(1).upper() if mbl else None,
                containers=containers, shipper=shipper.group(1).strip(" -–") if shipper else None)


def build(threads: list) -> list:
    """One row per container; the earliest message of each kind wins its date."""
    rows = {}
    for t in threads:
        for m in t.get("messages", []):
            p = parse_message(m.get("subject", ""), m.get("snippet", ""))
            if not p["containers"] or not p["hbl"]:
                continue
            for c in p["containers"]:
                r = rows.setdefault(c, dict(container=c, hbl=p["hbl"], mbl=p["mbl"], shipper=p["shipper"],
                                            sailing_advice=None, arrival_notice=None, delivery_order=None,
                                            invoice=None))
                r["mbl"] = r["mbl"] or p["mbl"]
                r["shipper"] = r["shipper"] or p["shipper"]
                day = (m.get("date") or "")[:10]
                if p["kind"] in r and day and (r[p["kind"]] is None or day < r[p["kind"]]):
                    r[p["kind"]] = day
    return sorted(rows.values(), key=lambda r: (r["arrival_notice"] or r["sailing_advice"] or "", r["container"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("search_json", help="Gmail search_threads result saved as JSON")
    ap.add_argument("--csv", help="write the register to this CSV (must not exist yet)")
    a = ap.parse_args(argv)
    rows = build(json.load(open(a.search_json))["threads"])
    if a.csv:
        with open(a.csv, "x", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["container"])
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        print(f"{r['container']}  HBL {r['hbl']}  MBL {r['mbl'] or '-':18} sailed {r['sailing_advice'] or '-':10} "
              f"arrival {r['arrival_notice'] or '-':10}  {r['shipper'] or ''}")
    print(f"{len(rows)} containers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
