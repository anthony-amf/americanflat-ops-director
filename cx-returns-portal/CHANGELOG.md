# Changelog

All notable changes to this skill will be documented in this file.

## [0.2.0] - 2026-08-28

### Changed
- **Replacements now go into the Replacements tab of the replacements sheet**
  rather than being created directly in ShipStation. An automation that already
  existed reads that tab and creates the order, so this skill no longer connects to
  ShipStation at all — and needs no ShipStation credentials.
- The portal's second output tab emits a 22-column tab-separated row matching the
  live sheet, with the four automation-owned columns left empty and shown greyed.
  Channel is constrained to the sheet's own values, because the automation resolves
  a ShipStation store from it.

### Removed
- The direct ShipStation path — order creation, the read-only probe, the CSV
  fallback, and the environment/egress write-ups — moved to `retired/`, not
  deleted. Nothing live refers to them; `retired/README.md` says what each is still
  good for.

### Kept
- `scripts/confirm_940.py`, which matters more now, not less: the sheet reaching
  `CREATED` means ShipStation accepted the order, not that the 3PL was told. Only
  the EDI 940 shows that, and the order is now created by something this skill
  cannot see.

## [0.1.0] - 2026-08-27

### Added
- Initial release.
- Seven case types covering what CX actually sees: reship, missing units,
  unshipped balance, tracking verification, cancel replacement, return
  disposition, and damaged on arrival. Recipients, subject format and body shape
  were taken from live `[nyc_ops]` warehouse threads rather than invented, so the
  3PLs receive what they already know how to answer.
- Warehouse routing for five sites — Fontana, New Jersey, South Carolina, Yusen
  Canada and Yusen NL — with `NYC_Ops@americanflat.com` on every Cc.
- `scripts/create_reship_order.py` creates a replacement order in ShipStation,
  which transmits to the 3PL as an EDI 940. Dry-run by default; `--send` requires
  the operator to type the order number back, because a created order starts a
  real pick with no undo.
- `scripts/confirm_940.py` answers whether a reship actually reached the
  warehouse, which warehouse received it, and whether a 945 has come back.
  Verified against live Stedi data.
- `scripts/lookup_order.py` pulls SKUs and quantities from BigQuery so nobody
  retypes them, and states plainly what BigQuery cannot answer.
- `scripts/build_reship_csv.py` and the portal's CSV tab, as a fallback for when
  the API is unavailable.
- A self-serve portal (`portal/`), published as an Artifact, for CX teammates
  without a Claude session. Generated from `references/` so the config has one
  source of truth; `scripts/build_portal.py` warns when config and docs drift.
- Eight browser tests over real case shapes, covering routing, subject format,
  that customer email addresses and phone numbers never reach a warehouse, and
  that no unfilled placeholder can reach a sendable draft.

### Known limitations
- The ShipStation create payload's field names have **not** been validated against
  a real request. Run `scripts/shipstation_probe.py` and reconcile before the first
  production send.
- The `warehouseId` → site mapping is unknown and must come from the same probe.
  It decides which 3PL receives the 940.
- The CSV fallback's column headers are likewise unverified; do one test import.

### Noted, not fixed
- The Stedi API silently ignores `transaction_type`, and the Yusen invoice
  validator's `validate_stedi.py` treats any returned transaction as a 945 match.
  Orders that were received but never shipped are reported as shipped, which
  weakens a payment gate. Reproduced and documented in `references/edi-940.md`;
  the fix belongs to that skill, not this one.
