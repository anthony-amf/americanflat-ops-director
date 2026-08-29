#!/usr/bin/env python3
"""Did the reship actually reach the warehouse?

    python3 scripts/confirm_940.py 25402RS
    python3 scripts/confirm_940.py 25402RS 24074RS --json

Creating an order in ShipStation is only half of it — the warehouse doesn't see it
until the EDI 940 goes out. This asks Stedi whether that happened, which warehouse
received it, and whether a 945 (shipped) has come back.

Needs STEDI_API_KEY in the environment. Read-only. Works from cloud sessions —
Stedi is reachable even though ShipStation is not.

Correctness note: the Stedi API ignores `transaction_type`, so this filters on the
real value at x12.metadata.transaction.transactionSetIdentifier. Trusting the
request parameter instead is what makes the invoice validator report unshipped
orders as shipped (references/edi-940.md).
"""

import argparse
import json
import os
import subprocess
import sys

BASE = "https://core.us.stedi.com/2023-08-01/transactions"

# Verified against live outbound 940s, 2026-08-27. See references/edi-940.md.
PARTNERSHIP_TO_WAREHOUSE = {
    "americanflat_taylored": "Fontana",
    "americanflat_Taylored-EAST_NJ": "New Jersey",
    "americanflat_Taylored-SC": "South Carolina",
    "americanflat-vc_taylored-FON": "Fontana (Vendor Central)",
    "americanflat-vc_Taylored-EAST-NJ": "New Jersey (Vendor Central)",
    "americanflat-vc_Taylored-SC": "South Carolina (Vendor Central)",
}


def api_key() -> str:
    key = os.environ.get("STEDI_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set STEDI_API_KEY in the environment (never as a CLI argument).")
    return key


def transactions_for(order: str, key: str) -> list:
    order = order.strip().lstrip("'").strip()
    url = f"{BASE}?businessIdentifier={order}"
    proc = subprocess.run(
        ["curl", "-sS", "--max-time", "45", "-H", f"Authorization: {key}", url],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Could not reach Stedi: {proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"Unexpected Stedi response: {proc.stdout[:200]}")
    if "items" not in payload:
        raise SystemExit(f"Stedi error: {json.dumps(payload)[:200]}")
    return payload["items"]


def classify(items: list) -> dict:
    """Read the type off each transaction; never infer it from the request."""
    out = {"transactions": [], "sent_940": None, "received_945": None}
    for it in items:
        meta = ((it.get("x12") or {}).get("metadata") or {}).get("transaction") or {}
        kind = meta.get("transactionSetIdentifier")
        partnership = (it.get("partnership") or {}).get("partnershipId")
        rec = {
            "type": kind,
            "direction": it.get("direction"),
            "partnership": partnership,
            "warehouse": PARTNERSHIP_TO_WAREHOUSE.get(partnership),
            "processed_at": it.get("processedAt"),
            "status": it.get("status"),
        }
        out["transactions"].append(rec)
        if kind == "940" and it.get("direction") == "OUTBOUND":
            if not out["sent_940"] or rec["processed_at"] > out["sent_940"]["processed_at"]:
                out["sent_940"] = rec
        if kind == "945" and it.get("direction") == "INBOUND":
            if not out["received_945"] or rec["processed_at"] > out["received_945"]["processed_at"]:
                out["received_945"] = rec
    return out


def report(order: str, res: dict) -> None:
    sent, back = res["sent_940"], res["received_945"]
    print(f"\n{order}")
    if not res["transactions"]:
        print("  Nothing in Stedi for this order.")
        print("  If the order was just created, EDI can lag a few minutes — re-check")
        print("  shortly. If it stays empty the warehouse has not been told about it.")
        return

    if sent:
        wh = sent["warehouse"] or f"unmapped partnership: {sent['partnership']}"
        print(f"  940 sent      {sent['processed_at']}  ->  {wh}  ({sent['status']})")
    else:
        print("  940 sent      NO — the warehouse has not received this order")

    if back:
        wh = back["warehouse"] or back["partnership"]
        print(f"  945 back      {back['processed_at']}  <-  {wh}  (shipped)")
    elif sent:
        print("  945 back      not yet — received by the warehouse, not shipped")

    others = [t for t in res["transactions"] if t["type"] not in ("940", "945")]
    if others:
        kinds = ", ".join(sorted({f"{t['type']}" for t in others if t["type"]}))
        print(f"  also present  {kinds}  (not evidence of shipment)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Confirm a reship reached the warehouse by EDI.")
    ap.add_argument("orders", nargs="+", help="Order number(s), e.g. 25402RS")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a summary")
    args = ap.parse_args()

    key = api_key()
    results = {}
    for order in args.orders:
        res = classify(transactions_for(order, key))
        results[order] = res
        if not args.json:
            report(order, res)

    if args.json:
        print(json.dumps(results, indent=2))
    elif len(args.orders) > 1:
        missing = [o for o, r in results.items() if not r["sent_940"]]
        print(f"\n{len(args.orders) - len(missing)}/{len(args.orders)} reached a warehouse.")
        if missing:
            print("No 940 for: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
