# Quarantined 2026-09-22

## `parcel_charges.ndjson.gz`

The charge snapshot as it stood from 2026-09-10 to 2026-09-22: 40,288 lines,
with FedEx coverage ending 2026-04-27. Superseded, not deleted, per the
no-delete rule in CLAUDE.md.

Its replacement at `data/parcel_charges.ndjson.gz` holds the same 40,288 lines
plus 15,447 new FedEx lines parsed from the weekly invoice exports Anthony
uploaded to Drive on 2026-09-22, carrying FedEx through shipments of
2026-09-08. Nothing was dropped in the swap — the new file is a superset.

Kept because it is what every page build between those dates was made from. If
a number from one of those builds ever needs explaining, this is the input that
produced it.
