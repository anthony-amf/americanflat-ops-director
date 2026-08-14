## 1.6.0 — 2026-08-14

Teaches the validator to judge two kinds of VAS work that had no way to resolve, and
corrects three rate-card errors that were producing false disputes. Only
`validate_rate_card.py`, `references/rate-card-snapshot.json` and `skill.toml`
(version bump) differ from __BASE__.

### Savannah VAS pallet work orders

Savannah bills pallets as VAS jobs rather than on the SP/LTL invoice. The generic VAS
logic has no per-unit basis for those, so they parked at `needs_detail` indefinitely —
including invoices billed exactly right. New `apply_vas_pallet_check` reads the
quantity and rate from `notes` (no PDF and no OCR needed, which matters because SC VAS
PDFs are scanned images), then:

1. Recomputes pallets x printed rate against the invoice total. A mismatch is a
   `discrepancy` and the rate question is not asked.
2. Judges the rate against AF-9's $10.00 all-in, pallet and stretch wrap included:
   $10.00 is `valid`, above it is `disputed` for the excess, below it is a
   `discrepancy` needing a human.

Stage 2 is what protects money. 48 x $14.317 = $687.22 recomputes perfectly, so a
recompute-only rule would have stamped an AF-9 overcharge `valid` and dropped a live
claim.

Bounded by `ltl._af9_effective_from` (2026-06-01), so a pre-June invoice billed at the
documented pre-June rate is `valid` with a note, not disputed — the pre-June rate is
the correct rate for a pre-June invoice. Without that bound the rule would have
flipped three settled April invoices to `disputed` on every nightly sweep.

Two interference guards: `apply_msa_conflicts` stands aside when the pallet rule has
already judged the charge, and `_line_pass_keeping_disputes` skips these rows rather
than let a scanned PDF demote a sound `valid`.

### Hourly VAS projects vs the MSA hourly table

New `apply_vas_labor_check` divides the total by the hours in `notes`, works out which
row of the MSA table the work belongs to, and compares. The rate depends on both site
and kind of work, which is why one figure per warehouse was never enough. Matching
against the whole site column rather than only the guessed role means a wording
mismatch cannot turn a contracted rate into a dispute. Overtime at 1.5x any contracted
role rate reads as `valid` — agreed, so it is a contracted rate like any other, and a
multiplier on whichever row applies rather than a rate of its own. Above every rate in
the column is `disputed` for the excess over the highest contracted rate; below the
role rate is `valid`, noted as in Americanflat's favour.

It also clears validate()'s "provide hours from the invoice detail" placeholder once it
has supplied them, so a resolved row cannot read `valid` and "needs more detail" at
once.

### Three rate-card corrections

- **South Carolina hourly held $51.00**, which appears nowhere in the MSA — the
  superseded card value, as the live Notion card's own footnote says. Judged against
  it, five correctly-billed Savannah invoices read as overbilled, including a
  stock-consolidation project at the contracted $63.00. The card now carries the full
  role x site table, and `vas_hourly` defaults to general labour.
- **No `receiving` section at all**, so receiving invoices had nothing to check
  against. Now mirrored from the Notion card, including the pre-June rates that the
  card's own history table lacked — every observed line sits at exactly 1.087x the
  June rate, confirmed to the cent against the PDFs of 749279 and 752320.
- **AF-9 had no effective date**, covered above.

Also recorded: the 1.5x overtime multiplier, the IT and supplies/equipment rows, and
the New Jersey 5% labour tax appearing on receiving invoices as "NJ BILL OF RIGHTS
SURCHARGE" — the same charge under different wording, which a match on "labor tax"
misses.

### Effect on the ledger

Nineteen invoices resolved. All eleven hourly VAS jobs now read `valid` ($15,984, none
disputed) — the six already-valid Savannah and NJ labour invoices were right all
along. Net dispute movement is negative: $1,766 of claims raised against the stale
card were withdrawn once it was corrected. Every one was our own reference being
wrong, not Yusen's billing.
