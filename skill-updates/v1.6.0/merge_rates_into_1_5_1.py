#!/usr/bin/env python3
"""Merge v1.6.0's rate-card additions into whatever snapshot 1.5.1 already has.

Why a merge and not a copy: the canonical snapshot on the Mac belongs to 1.5.1,
which was developed separately. Overwriting it with this repo's copy would discard
anything that release changed. This only *adds* the keys v1.6.0 needs, and reports
every value it would overwrite so a real conflict is visible rather than silent.

  python3 merge_rates_into_1_5_1.py <path-to-rate-card-snapshot.json>            # dry run
  python3 merge_rates_into_1_5_1.py <path-to-rate-card-snapshot.json> --write

A timestamped backup is written next to the file before any change.
"""
import json
import shutil
import sys
from datetime import datetime

HOURLY_ROLES = {
    "fontana":        {"material_handler": 35.00, "clerical": 42.00, "general_labor": 59.8278,
                       "physical_inventory": 59.8278, "stock_consolidation": 59.8278,
                       "salaried_supervisor": 82.1166, "dray_admin_fee": 52.8831,
                       "qa": 47.1232},
    "new_jersey":     {"material_handler": 35.00, "clerical": 42.00, "general_labor": 53.55,
                       "physical_inventory": 53.55, "stock_consolidation": 53.55,
                       "salaried_supervisor": 77.70, "dray_admin_fee": 47.334},
    "south_carolina": {"material_handler": 32.00, "clerical": 40.00, "general_labor": 53.55,
                       "physical_inventory": 63.00, "stock_consolidation": 63.00,
                       "salaried_supervisor": 77.70, "dray_admin_fee": 51.45},
}

RECEIVING = {
    "fontana":        {"handling_in_per_carton": 0.9173, "container_admin": 52.8831,
                       "ltl_air_delivery_per_carton": 0.7728, "ltl_air_delivery_minimum": 72.45,
                       "container_trailer_storage_per_spot_day": 43.47,
                       "sortation_per_sku": 31.2981},
    "new_jersey":     {"handling_in_per_carton": 0.9467, "container_admin": 47.334,
                       "ltl_air_delivery_per_carton": 0.7728, "ltl_air_delivery_minimum": 72.45,
                       "container_trailer_storage_per_spot_day": 43.47,
                       "sortation_per_sku": 29.946},
    "south_carolina": {"handling_in_per_carton": 0.7728, "container_admin": 47.288,
                       "ltl_air_delivery_per_carton": 0.7728, "ltl_air_delivery_minimum": 72.45,
                       "container_trailer_storage_per_spot_day": 43.47,
                       "sortation_per_sku": 24.15},
    "_pre_june": {
        "note": ("Pre-June 2026 receiving rates. Absent from the Notion card's pre-June "
                 "history table before 2026-08-12. Every observed line sits at exactly "
                 "1.087x the June rate, the inverse of the ~8% June cut. Confirmed against "
                 "the PDFs of 749279 (NJ, 2026-03-31) and 752320 (Fontana, 2026-05-26); "
                 "both recompute to the cent. south_carolina is derived and unconfirmed."),
        "effective_until": "2026-06-01",
        "fontana":        {"handling_in_per_carton": 0.9971, "container_admin": 57.4816,
                           "sortation_per_sku": 34.0198, "_source": "observed (752320)"},
        "new_jersey":     {"handling_in_per_carton": 1.0290, "container_admin": 51.4500,
                           "sortation_per_sku": 32.5500, "_source": "observed (749279)"},
        "south_carolina": {"handling_in_per_carton": 0.8400, "container_admin": 51.4021,
                           "sortation_per_sku": 26.2511, "_source": "derived x1.087, unconfirmed"},
    },
    "_nj_surcharge_note": (
        "New Jersey receiving invoices carry the 5% labour tax as 'NJ BILL OF RIGHTS "
        "SURCHARGE' (749279: 5.00% of $10,830.4560 = $541.52). Same charge as "
        "admin_vas.new_jersey.labor_tax, different wording — a match on 'labor tax' "
        "misses it. Effective-dated: dropped from the week of 2026-04-20."),
    "_note": ("Receiving & handling-in, mirrored from the live Notion rate card 2026-08-12. "
              "Receiving notes carry no quantities, so unlike the VAS pallet and labour "
              "rules there is no notes-only shortcut: these invoices require the PDF."),
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path, write = sys.argv[1], "--write" in sys.argv
    r = json.load(open(path))
    changes, conflicts = [], []

    def put(container, key, value, label):
        old = container.get(key)
        if old == value:
            return
        if old is not None and not isinstance(old, (dict, list)):
            conflicts.append(f"{label}: {old!r} -> {value!r}")
        elif old is not None:
            conflicts.append(f"{label}: replacing an existing block")
        changes.append(f"{label} = {value if not isinstance(value, dict) else '{...}'}")
        container[key] = value

    av = r.setdefault("admin_vas", {})
    for site, roles in HOURLY_ROLES.items():
        s = av.setdefault(site, {})
        put(s, "hourly_roles", roles, f"admin_vas.{site}.hourly_roles")
        put(s, "overtime_multiplier", 1.5, f"admin_vas.{site}.overtime_multiplier")
        # vas_hourly becomes the general-labour default. SC previously held 51.00,
        # which is the superseded card value, not an MSA rate.
        put(s, "vas_hourly", roles["general_labor"], f"admin_vas.{site}.vas_hourly")
    put(av, "_hourly_roles_note",
        ("Full MSA hourly table, role x site, valid April 2026 - March 31 2027. "
         "general_labor covers equipment operator, office, admin, returns, photography, "
         "floor loading, oversize, QA and routing. The single vas_hourly figure this "
         "replaces had south_carolina at 51.00 — the superseded card value, per the Notion "
         "card's own footnote."), "admin_vas._hourly_roles_note")
    put(av, "_overtime_note",
        ("Overtime is 1.5x the applicable role rate — AGREED (Anthony, 2026-08-12). It is a "
         "multiplier on whichever role row applies, not a rate of its own."),
        "admin_vas._overtime_note")

    ltl = r.setdefault("ltl", {})
    put(ltl, "_af9_effective_from", "2026-06-01", "ltl._af9_effective_from")
    put(ltl, "_af9_effective_note",
        ("AF-9's $10.00 all-in pallet rate applies to invoices dated on or after this date. "
         "Before it the documented pre-June rate is correct and the invoice is valid, not "
         "disputed. Set to 2026-06-01 (Anthony, 2026-08-12) to match the Notion card's own "
         "wording: the new US rates took effect from the June 2026 billing weeks."),
        "ltl._af9_effective_note")

    put(r, "receiving", RECEIVING, "receiving")

    print(f"{len(changes)} key(s) to add or update:")
    for c in changes:
        print("   ", c)
    if conflicts:
        print(f"\n{len(conflicts)} value(s) this OVERWRITES — check these are what you expect:")
        for c in conflicts:
            print("   ", c)
    if not write:
        print("\nDRY RUN — re-run with --write to apply.")
        return 0

    backup = f"{path}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(path, backup)
    json.dump(r, open(path, "w"), indent=2)
    print(f"\nbackup written: {backup}")
    print(f"updated: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
