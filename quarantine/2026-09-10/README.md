# Quarantined 2026-09-10

## `load_shipping_costs_to_bq.py`

Retired at Anthony's request. Moved rather than deleted, per the NO-DELETE rule
in CLAUDE.md.

It loaded Stamps.com and FedEx invoice exports into BigQuery. `americanflat/Ops`
does that job now, via `tools/stamps_shipping_costs_load.py`, and that tool is
better at it: it orders overlapping exports by which supersedes which rather than
by filename, and it refuses to run while the target table holds spreadsheet-
escaped tracking numbers.

This script needed that second guard and did not have it. Its MERGE normalized
the incoming rows but compared them against the raw target column, so any
escaped row would fail to match, insert instead of update, and count the
shipment twice. That is how `finance.stamps_shipping_costs` reached 25,948 rows
and $297,557.98 against a true 20,528 and $239,109.04. The join was fixed in
`sql/stamps_weekly_load.sql` before this was retired, but the lesson is the
reason it is retired: one tool per table.

Its FedEx half was the part nothing else covered. That work moves to
`americanflat/Ops` alongside the Stamps loader — see
`HANDOFF-fedex-cost-table.md`, which carries the whole spec inline because
neither repo's sessions can reach the other.

Nothing in this repo imports it. The portal builder's `--stamps-table` and
`--fedex-table` flags only *read* those tables and are unaffected.
