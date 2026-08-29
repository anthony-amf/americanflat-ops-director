#!/usr/bin/env python3
"""Create a replacement order in ShipStation, which transmits a 940 to the 3PL.

    # prints the payload, sends nothing (default)
    python3 scripts/create_reship_order.py 25402 --sku "VF1114BLK810:2" \
        --name "Sarah Whitfield" --address1 "1842 Larkin St" \
        --city "San Francisco" --state CA --postal 94109 \
        --warehouse-id 512455 --store-id 123456

    # actually create it
    ... --send

THIS CREATES PHYSICAL WORK. A created order goes out as an EDI 940 and a picker at
Yusen acts on it: real product, real freight, billed. There is no undo from here —
cancelling means emailing the warehouse and hoping it is caught before the pick.

So: dry-run is the default, --send is required, and --send prompts for the order
number to be typed back. Confirm the reship is genuinely needed first.

Cloud sessions cannot reach ShipStation (proxy denies it by policy) — run from the
Mac. Credentials come from SHIPSTATION_API_KEY / SHIPSTATION_API_SECRET in the
environment, never CLI arguments.

PAYLOAD IS UNVERIFIED. No real createorder request has been observed from this
environment. Run scripts/shipstation_probe.py first and reconcile the field names
against a real order before the first production send. See
references/shipstation-csv.md.
"""

import argparse
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENDPOINT = "https://ssapi.shipstation.com/orders/createorder"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
from build_reship_csv import parse_sku, rs_number, lookup_titles  # noqa: E402


def creds():
    """Basic auth blob, or None when the egress proxy injects credentials.

    Mac: export SHIPSTATION_API_KEY and SHIPSTATION_API_SECRET (never CLI args —
    shell history keeps them). Cloud with proxy injection: no key present, and the
    proxy attaches auth for ssapi.shipstation.com, as it already does for BigQuery.
    """
    key = os.environ.get("SHIPSTATION_API_KEY", "").strip()
    secret = os.environ.get("SHIPSTATION_API_SECRET", "").strip()
    if key and secret:
        return base64.b64encode(f"{key}:{secret}".encode()).decode()
    if key or secret:
        raise SystemExit("Only one of SHIPSTATION_API_KEY / SHIPSTATION_API_SECRET is set — "
                         "set both, or neither to use proxy-injected credentials.")
    return None


def build_payload(args, items: list, titles: dict) -> dict:
    rs = rs_number(args.order)
    notes = [f"Replacement for #{args.order.lstrip('#')}"]
    if args.reason:
        notes.append(args.reason)
    if args.ticket:
        notes.append(f"Zendesk {args.ticket}")
    notes.append("Loose-unit pick - individual units only" if args.pick == "units"
                 else "PICK AS SEALED MASTER CARTON - do not split")
    notes.append("No charge - replacement, do not invoice")

    ship_to = {
        "name": args.name,
        "company": args.company or None,
        "street1": args.address1,
        "street2": args.address2 or None,
        "city": args.city,
        "state": args.state,
        "postalCode": args.postal,
        "country": args.country,
        "phone": args.phone or None,
        "residential": True,
    }

    advanced = {"customField1": f"Reship {args.order.lstrip('#')}"}
    if args.warehouse_id:
        advanced["warehouseId"] = int(args.warehouse_id)
    if args.store_id:
        advanced["storeId"] = int(args.store_id)

    return {
        # orderKey makes this idempotent: re-running updates the same order instead
        # of creating a second one. A duplicate here is a second real shipment.
        "orderKey": f"AMF-RESHIP-{rs}",
        "orderNumber": rs,
        "orderDate": args.date or datetime.date.today().isoformat() + "T00:00:00.0000000",
        "orderStatus": "awaiting_shipment",
        "shipTo": ship_to,
        "billTo": {"name": args.name},
        "items": [
            {
                "lineItemKey": f"{rs}-{i+1}",
                "sku": sku,
                "name": titles.get(sku, sku),
                "quantity": qty,
                "unitPrice": 0.00,
            }
            for i, (sku, qty) in enumerate(items)
        ],
        "internalNotes": " | ".join(notes),
        "advancedOptions": advanced,
    }


def send(payload: dict, auth) -> dict:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Basic {auth}"
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        if e.code == 401:
            raise SystemExit("401 — with a key/secret, check the pair; with proxy "
                             "injection, the proxy is not attaching credentials yet.")
        if e.code == 403:
            raise SystemExit("403 — cloud sessions are blocked by policy; run from the Mac.")
        if e.code == 429:
            raise SystemExit("429 rate limited — ShipStation allows 40 requests/minute.")
        raise SystemExit(f"ShipStation rejected the order (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach ShipStation ({e.reason}). Cloud sessions are "
                         f"blocked by policy — run this from the Mac.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a replacement order in ShipStation.")
    ap.add_argument("order", help="Original order number, e.g. 25402")
    ap.add_argument("--sku", action="append", required=True, metavar="SKU:QTY")
    ap.add_argument("--name", required=True)
    ap.add_argument("--address1", required=True)
    ap.add_argument("--city", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--postal", required=True)
    ap.add_argument("--address2", default="")
    ap.add_argument("--company", default="")
    ap.add_argument("--country", default="US")
    ap.add_argument("--phone", default="")
    ap.add_argument("--warehouse-id", default="", help="Decides WHICH 3PL gets the 940")
    ap.add_argument("--store-id", default="")
    ap.add_argument("--pick", choices=["carton", "units"], default="carton")
    ap.add_argument("--reason", default="")
    ap.add_argument("--ticket", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--send", action="store_true", help="Actually create it")
    ap.add_argument("--no-lookup", action="store_true")
    args = ap.parse_args()

    items = [parse_sku(s) for s in args.sku]
    titles = {} if args.no_lookup else lookup_titles(args.order)
    payload = build_payload(args, items, titles)
    rs = payload["orderNumber"]

    print(json.dumps(payload, indent=2))

    if not args.warehouse_id:
        print("\nNo --warehouse-id: ShipStation will use its default, which decides "
              "which 3PL receives the 940. Pass it explicitly.", file=sys.stderr)

    if not args.send:
        print(f"\nDRY RUN — nothing was sent. Add --send to create {rs}.", file=sys.stderr)
        print("Payload field names are UNVERIFIED; run shipstation_probe.py first.", file=sys.stderr)
        return 0

    print(f"\nThis will create {rs} in ShipStation and transmit a 940 to the warehouse.",
          file=sys.stderr)
    print("A picker will act on it. Type the order number to confirm: ", end="", file=sys.stderr)
    sys.stderr.flush()
    try:
        typed = input().strip()
    except EOFError:
        print("\nNo confirmation received — nothing sent.", file=sys.stderr)
        return 1
    if typed != rs:
        print(f"Got {typed!r}, expected {rs!r} — nothing sent.", file=sys.stderr)
        return 1

    result = send(payload, creds())
    print("\nCreated:", json.dumps(
        {k: result.get(k) for k in ("orderId", "orderNumber", "orderKey", "orderStatus")}, indent=2))
    print(f"\nNow confirm the warehouse actually got it:\n"
          f"  python3 scripts/confirm_940.py {rs}\n"
          f"Give EDI a few minutes. No 940 means the warehouse never saw it.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
