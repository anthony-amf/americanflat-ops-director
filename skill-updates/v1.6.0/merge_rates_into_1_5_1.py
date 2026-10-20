#!/usr/bin/env python3
"""Merge v1.6.0's rate-card additions into an existing rate-card snapshot.

Why a merge and not a copy: the canonical snapshot on the Mac belongs to 1.5.1,
which was developed separately. Overwriting it with this repo's copy would discard
anything that release changed. This only *adds* the paths v1.6.0 introduces, and
reports every value it would overwrite so a real conflict is visible rather than
silent.

  python3 merge_rates_into_1_5_1.py <path-to-rate-card-snapshot.json>            # dry run
  python3 merge_rates_into_1_5_1.py <path-to-rate-card-snapshot.json> --write

A timestamped backup is written next to the file before any change.

ADDITIONS below is derived mechanically from the diff between the v1.5.0 snapshot
shipped in `yusen-invoice-validator.skill` and this release's
`rate-card-snapshot.json` — so running this against a 1.5.0-era card reproduces
that file exactly. Verified as part of building the review candidate: 13 paths,
byte-identical result.
"""
import json
import shutil
import sys
from datetime import datetime

# (dotted path, value) — every path v1.6.0 adds or changes. Order is not
# significant; parents are created as needed.
ADDITIONS = [
    ('ltl._af9_effective_from', '2026-06-01'),
    ('ltl._af9_effective_note', "The AF-9 $10.00 all-in pallet rate applies to invoices dated on or after this date. Before it, the documented pre-June rate is the correct rate and the invoice is valid, not disputed. Set to 2026-06-01 (Anthony, 2026-08-12) to match the Notion rate card's own wording: the new US rates 'took effect on invoices from the June 2026 billing weeks'. This supersedes an earlier 2026-05-01 setting and returns the two 2026-05-20 SC pallet invoices (752056, 752058 — $151.38) to valid; the three April invoices were already out of scope under either date."),
    ('admin_vas.fontana.hourly_roles', {'material_handler': 35.0, 'clerical': 42.0, 'general_labor': 59.8278, 'physical_inventory': 59.8278, 'stock_consolidation': 59.8278, 'salaried_supervisor': 82.1166, 'dray_admin_fee': 52.8831, 'qa': 47.1232}),
    ('admin_vas.fontana.overtime_multiplier', 1.5),
    ('admin_vas.new_jersey.hourly_roles', {'material_handler': 35.0, 'clerical': 42.0, 'general_labor': 53.55, 'physical_inventory': 53.55, 'stock_consolidation': 53.55, 'salaried_supervisor': 77.7, 'dray_admin_fee': 47.334}),
    ('admin_vas.new_jersey.overtime_multiplier', 1.5),
    ('admin_vas.south_carolina.vas_hourly', 53.55),
    ('admin_vas.south_carolina.hourly_roles', {'material_handler': 32.0, 'clerical': 40.0, 'general_labor': 53.55, 'physical_inventory': 63.0, 'stock_consolidation': 63.0, 'salaried_supervisor': 77.7, 'dray_admin_fee': 51.45}),
    ('admin_vas.south_carolina.overtime_multiplier', 1.5),
    ('admin_vas._hourly_roles_note', "Full MSA hourly table, role x site, valid April 2026 - March 31 2027 (Anthony, 2026-08-12; mirrored on the Notion rate card rebuilt from the MSA 8/5). general_labor covers equipment operator, office, admin, returns, photography, floor loading, oversize, QA and routing. NOTE: the single vas_hourly figure this replaces had south_carolina at 51.00, which appears nowhere in the MSA and caused correctly-billed Savannah labour to read as above card. Verified against the live Notion card 2026-08-12, whose footnote reads: 'SC hourly per the MSA hourly table (was $51.00 on the old card)'. The 51.00 previously stored here was the superseded card value, not an MSA rate."),
    ('admin_vas._hourly_roles_extra', {'it_hourly': 185.0, 'supplies_equipment': 'cost + 12% margin'}),
    ('admin_vas._overtime_note', 'Overtime is 1.5x the applicable role rate — AGREED (Anthony, 2026-08-12), so an hourly line at exactly 1.5x a contracted role rate is valid, not a dispute. It is a multiplier on whichever role row applies, not a rate of its own. Straight-time general labour OT: Fontana $89.7417, New Jersey $80.325, South Carolina $80.325.'),
    ('receiving', {'fontana': {'handling_in_per_carton': 0.9173, 'container_admin': 52.8831, 'ltl_air_delivery_per_carton': 0.7728, 'ltl_air_delivery_minimum': 72.45, 'container_trailer_storage_per_spot_day': 43.47, 'sortation_per_sku': 31.2981}, 'new_jersey': {'handling_in_per_carton': 0.9467, 'container_admin': 47.334, 'ltl_air_delivery_per_carton': 0.7728, 'ltl_air_delivery_minimum': 72.45, 'container_trailer_storage_per_spot_day': 43.47, 'sortation_per_sku': 29.946}, 'south_carolina': {'handling_in_per_carton': 0.7728, 'container_admin': 47.288, 'ltl_air_delivery_per_carton': 0.7728, 'ltl_air_delivery_minimum': 72.45, 'container_trailer_storage_per_spot_day': 43.47, 'sortation_per_sku': 24.15}, '_note': "Receiving & handling-in, mirrored from the live Notion rate card 2026-08-12. This section did not exist before v1.6.0, so Receiving invoices had no per-unit basis in the snapshot at all — the only reason any validated is that container_admin and sortation happen to appear in the script's rate-label table, which the PDF line pass consults. Receiving notes carry no quantities (just 'INBOUND PROCESSING BETWEEN <dates>'), so unlike the VAS pallet and labour rules there is no notes-only shortcut: these invoices require the PDF.", '_pre_june': {'note': "Pre-June 2026 receiving rates. Absent from the Notion card's pre-June history table, which covers small parcel, LTL, pallet, BOL and storage but not receiving — so before v1.6.0 there was nothing to validate a pre-June receiving invoice against. Every observed line sits at exactly 1.087x the June rate, the inverse of the ~8% June cut (1/1.087 = 0.920). Confirmed 2026-08-12 against the PDFs of 749279 (NJ, 2026-03-31) and 752320 (Fontana, 2026-05-26); both recompute to the cent. Rates marked observed came off those invoices; south_carolina is derived and unconfirmed.", 'effective_until': '2026-06-01', 'fontana': {'handling_in_per_carton': 0.9971, 'container_admin': 57.4816, 'sortation_per_sku': 34.0198, '_source': 'observed (752320)'}, 'new_jersey': {'handling_in_per_carton': 1.029, 'container_admin': 51.45, 'sortation_per_sku': 32.55, '_source': 'observed (749279)'}, 'south_carolina': {'handling_in_per_carton': 0.84, 'container_admin': 51.4021, 'sortation_per_sku': 26.2511, '_source': 'derived x1.087, unconfirmed'}}, '_nj_surcharge_note': "New Jersey receiving invoices carry the 5% labour tax under the line name 'NJ BILL OF RIGHTS SURCHARGE' — 749279 bills 5.00% of $10,830.4560 = $541.52. Same charge as admin_vas.new_jersey.labor_tax, different wording, so anything matching on the phrase 'labor tax' will miss it. Effective-dated: dropped from the week of April 20 2026."}),
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path, write = sys.argv[1], "--write" in sys.argv
    card = json.load(open(path))
    added, unchanged, conflicts = [], 0, []

    for dotted, value in ADDITIONS:
        parts = dotted.split(".")
        node = card
        for p in parts[:-1]:
            nxt = node.get(p)
            if nxt is None:
                nxt = node[p] = {}
            elif not isinstance(nxt, dict):
                conflicts.append(f"{dotted}: {'.'.join(parts[:parts.index(p)+1])} "
                                 f"is a value, not a section — cannot descend")
                node = None
                break
            node = nxt
        if node is None:
            continue
        key, old = parts[-1], node.get(parts[-1])
        if old == value:
            unchanged += 1
            continue
        if old is not None:
            conflicts.append(f"{dotted}: {old!r} -> {value!r}"
                             if not isinstance(old, (dict, list))
                             else f"{dotted}: replacing an existing section")
        added.append(dotted)
        node[key] = value

    print(f"{len(added)} path(s) to add or update:")
    for a in added:
        print("   ", a)
    if unchanged:
        print(f"{unchanged} path(s) already correct — left alone.")
    if conflicts:
        print(f"\n{len(conflicts)} value(s) this OVERWRITES — check these are what you expect:")
        for c in conflicts:
            print("   ", c)
    if not added:
        print("\nNothing to do — this card already carries v1.6.0's rates.")
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
