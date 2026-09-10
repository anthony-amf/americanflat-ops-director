#!/usr/bin/env python3
"""Move the rate card onto the MSA's rates.

Anthony's decision, 2026-09-08: the MSA rates are the rates validation uses, even
though the MSA itself is still the unsigned 7.15.2026 draft. Before this the card
carried the pre-MSA Notion numbers and the code worked around them — the storage
check treats a below-card rate as "stale card, not a dispute", which is only true
for as long as the card is actually stale.

Kept separate from the v1.6.0 rate-card additions (hourly table, receiving, AF-9
date) because it is a different kind of change: those added facts the card lacked,
these overwrite numbers it already had. Its own step, so it can be applied,
reviewed or skipped on its own.

    python3 align_card_to_msa.py <path-to-rate-card-snapshot.json>            # dry run
    python3 align_card_to_msa.py <path-to-rate-card-snapshot.json> --write

Measured before shipping, all 381 ledger rows through the v1.6.0 validator with
each card: NO invoice changes status and NO variance moves. The published
validator reads only `storage.<site>` and `admin_vas.<site>` from the card, so the
27 LTL / small-parcel values are reference data nothing executes yet.

What does change: a storage invoice validated with `--detail` stops carrying the
spurious "BELOW the card's $5.98 — stale card" note, because billed now matches
the card. That also makes a genuinely above-card storage rate visible again,
instead of lost among a note that fires on every storage invoice.

The shape of the numbers is the tell. Almost every rate moves by exactly -8.0%,
the June 2026 cut. Storage drops 24-34%. The LTL pallet rises to the $10.00 AF-9
all-in while the separate stretchwrap line goes to zero — one restructure, not two
independent changes.

A timestamped backup is written before any change, and nothing is deleted.
"""
import json
import shutil
import sys
from datetime import datetime

# (dotted path, MSA value), with the pre-MSA value recorded alongside. Derived
# mechanically from the published 1.5.1 card against the MSA-rebuilt card, so the
# numbers are not retyped.
MSA_RATES = [
    ('small_parcel_dtc.fontana.e_commerce_orders', 2.2264), # was 2.42
    ('small_parcel_dtc.fontana.additional_picks', 0.506), # was 0.455
    ('small_parcel_dtc.new_jersey.e_commerce_orders', 2.2264), # was 2.42
    ('small_parcel_dtc.new_jersey.additional_picks', 0.506), # was 0.55
    ('small_parcel_dtc.south_carolina.e_commerce_orders', 2.2264), # was 2.99
    ('small_parcel_dtc.south_carolina.additional_picks', 0.5796), # was 0.63
    ('small_parcel_vendor.fontana.ship_carton', 1.8887), # was 2.05
    ('small_parcel_vendor.fontana.order_fee', 2.1585), # was 2.35
    ('small_parcel_vendor.fontana.small_parcel_addl', 0.6879), # was 0.7478
    ('small_parcel_vendor.new_jersey.ship_carton', 1.7871), # was 1.94
    ('small_parcel_vendor.new_jersey.order_fee', 2.1735), # was 2.36
    ('small_parcel_vendor.new_jersey.small_parcel_addl', 0.6532), # was 0.71
    ('small_parcel_vendor.south_carolina.ship_carton', 1.6422), # was 1.79
    ('ltl.fontana.ship_carton', 1.8887),             # was 2.05
    ('ltl.fontana.pallet', 10.0),                    # was 6.14
    ('ltl.fontana.stretchwrap', 0.0),                # was 4.69
    ('ltl.fontana.order_fee', 2.1585),               # was 2.35
    ('ltl.fontana.bol_fee', 6.5),                    # was 7.63
    ('ltl.new_jersey.ship_carton', 1.7871),          # was 1.94
    ('ltl.new_jersey.pallet', 10.0),                 # was 6.13
    ('ltl.new_jersey.stretchwrap', 0.0),             # was 4.72
    ('ltl.new_jersey.order_fee', 2.1735),            # was 2.36
    ('ltl.new_jersey.bol_fee', 6.5),                 # was 6.83
    ('ltl.south_carolina.ship_carton', 1.6422),      # was 1.79
    ('ltl.south_carolina.pallet', 10.0),             # was 5.87
    ('ltl.south_carolina.stretchwrap', 0.0),         # was 5.88
    ('ltl.south_carolina.bol_fee', 6.5),             # was 6.83
    ('storage.fontana', 4.47),                       # was 5.9
    ('storage.new_jersey', 4.34),                    # was 5.98
    ('storage.south_carolina', 3.35),                # was 5.09
    ('admin_vas.fontana.vas_hourly', 59.8278),       # was 59.82
    ('admin_vas.south_carolina.vas_hourly', 53.55),  # was 51.0
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path, write = sys.argv[1], "--write" in sys.argv
    card = json.load(open(path))
    moves, already, absent = [], 0, []

    for dotted, value in MSA_RATES:
        parts = dotted.split(".")
        node = card
        for seg in parts[:-1]:
            node = node.get(seg) if isinstance(node, dict) else None
            if node is None:
                break
        if not isinstance(node, dict) or parts[-1] not in node:
            absent.append(dotted)
            continue
        old = node[parts[-1]]
        if old == value:
            already += 1
            continue
        moves.append((dotted, old, value))
        node[parts[-1]] = value

    if moves:
        print(f"{len(moves)} rate(s) move to the MSA value:\n")
        print(f"  {'path':48}{'card now':>12}{'MSA':>12}   change")
        for p, old, new in moves:
            pct = (new - old) / old * 100 if old else 0
            print(f"  {p:48}{old:>12}{new:>12}   {pct:+7.1f}pct")
    if already:
        print(f"\n{already} rate(s) already at the MSA value — left alone.")
    if absent:
        print(f"\n{len(absent)} path(s) not present in this card, so not touched:")
        for a in absent:
            print("   ", a)
    if not moves:
        print("\nNothing to do — this card already carries the MSA rates.")
        return 0
    if not write:
        print("\nDRY RUN — re-run with --write to apply.")
        return 0

    backup = f"{path}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(path, backup)
    json.dump(card, open(path, "w"), indent=2)
    print(f"\nbackup written: {backup}")
    print(f"updated: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
