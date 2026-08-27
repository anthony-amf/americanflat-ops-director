#!/usr/bin/env python3
"""Read-only probe of the ShipStation API — run this from the Mac, not a cloud session.

Cloud sessions cannot reach ShipStation (the egress proxy denies it by policy), so
this is for a local Claude Code session or a terminal on Anthony's Mac.

    export SHIPSTATION_API_KEY=...        # never pass these as CLI arguments:
    export SHIPSTATION_API_SECRET=...     # shell history keeps them
    python3 scripts/shipstation_probe.py

It only reads. It lists stores and warehouses, fetches one order, and writes the
shapes it saw to references/shipstation-discovered.json — which is what lets us
replace the guessed CSV headers with real field names, and eventually create
replacement orders through the API instead of a file.

The key is read from the environment, never stored, never printed, and never
written to the output file.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://ssapi.shipstation.com"
OUT = Path(__file__).resolve().parent.parent / "references" / "shipstation-discovered.json"


def creds() -> str:
    key = os.environ.get("SHIPSTATION_API_KEY", "").strip()
    secret = os.environ.get("SHIPSTATION_API_SECRET", "").strip()
    if not key or not secret:
        raise SystemExit(
            "Set SHIPSTATION_API_KEY and SHIPSTATION_API_SECRET in the environment.\n"
            "Export them in your shell; do not pass them as arguments and do not put\n"
            "them in a file inside this repo."
        )
    return base64.b64encode(f"{key}:{secret}".encode()).decode()


def get(path: str, auth: str):
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        if e.code == 401:
            return None, "401 unauthorized — check the key and secret pair."
        if e.code == 403:
            return None, ("403 — if this says CONNECT tunnel failed you are on a cloud "
                          "session; run this from the Mac.")
        if e.code == 429:
            return None, "429 rate limited — ShipStation allows 40 requests/minute."
        return None, f"HTTP {e.code}: {detail}"
    except urllib.error.URLError as e:
        return None, (f"Could not reach ShipStation ({e.reason}). A cloud session is "
                      f"blocked by policy — run this from the Mac.")


def field_names(sample) -> list:
    """Record the SHAPE of a response, never its values — orders carry customer data."""
    if isinstance(sample, dict):
        return sorted(sample.keys())
    if isinstance(sample, list) and sample and isinstance(sample[0], dict):
        return sorted(sample[0].keys())
    return []


def main() -> int:
    auth = creds()
    found = {"_comment": "Read-only probe output. Shapes and IDs only — no customer data, no credentials."}
    problems = []

    print("Probing ShipStation (read-only)…\n")

    stores, err = get("/stores", auth)
    if err:
        print(f"  stores      : {err}")
        problems.append(err)
    else:
        rows = stores if isinstance(stores, list) else []
        found["stores"] = [{"storeId": s.get("storeId"), "storeName": s.get("storeName"),
                            "active": s.get("active")} for s in rows]
        print(f"  stores      : {len(rows)}")
        for s in rows[:12]:
            print(f"      {s.get('storeId')}  {s.get('storeName')}  active={s.get('active')}")

    whs, err = get("/warehouses", auth)
    if err:
        print(f"  warehouses  : {err}")
        problems.append(err)
    else:
        rows = whs if isinstance(whs, list) else []
        # This is the mapping BigQuery could not give us: warehouseId -> a real name.
        found["warehouses"] = [{"warehouseId": w.get("warehouseId"),
                                "warehouseName": w.get("warehouseName"),
                                "isDefault": w.get("isDefault")} for w in rows]
        print(f"  warehouses  : {len(rows)}   <- the ID->name mapping BigQuery lacks")
        for w in rows:
            print(f"      {w.get('warehouseId')}  {w.get('warehouseName')}  default={w.get('isDefault')}")

    orders, err = get("/orders?pageSize=1", auth)
    if err:
        print(f"  orders      : {err}")
        problems.append(err)
    else:
        rows = (orders or {}).get("orders", [])
        found["order_fields"] = field_names(rows)
        if rows:
            found["order_item_fields"] = field_names(rows[0].get("items", []))
        print(f"  orders      : reachable, {len(found.get('order_fields', []))} order fields captured")

    if problems:
        print("\nProbe incomplete. Nothing was written.")
        return 1

    OUT.write_text(json.dumps(found, indent=2) + "\n")
    print(f"\nWrote {OUT.name}. Next:")
    print("  1. Check the warehouse names against Fontana / NJ / SC.")
    print("  2. Hand this file back to Claude to replace the guessed CSV headers")
    print("     with real field names, and to wire up API order creation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
