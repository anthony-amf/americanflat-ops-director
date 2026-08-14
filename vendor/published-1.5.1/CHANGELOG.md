# Changelog

## 1.5.1 — 2026-08-12

- **`--mark-paid` no longer destroys the report it is meant to preserve.** It wrote
  `validation_report = COALESCE(@report, validation_report)` — a straight replace —
  while the report it hands over is a fresh *header* pass, always thinner than the
  deep passes that accumulate on a row. So approving an invoice deleted the evidence
  that justified approving it: on 2026-08-11, marking 754891 and 755265 paid dropped
  their `[MSA REVAL]` and `[DEEP PASS]` blocks, taking each row from ~1,700 characters
  down to 764. It now merges through `merge_report()`, exactly as `write_result()`
  already did, so prior blocks survive and only the `[AUTO]` block self-replaces.
  A supplied `--report-file` merges the same way instead of overwriting.

## 1.5.0 — 2026-08-11

`--detail` lets an operator hand the validator the itemized lines the header row
doesn't carry, which is the only thing standing between 66 invoices (~$350K, all
unpaid) and a real verdict.

- **`--detail "QTY x RATE [label]; ..."` validates against supplied line items.**
  Every family here bills as a sum of quantity × rate, but the BigQuery row stores
  only the header total, so Storage, VAS, Receiving and Admin all parked at
  `needs_detail` forever — `invoice.get("pallet_count")` read a column that does not
  exist and always came back empty. The flag takes the lines read off the PDF
  worksheet, checks their sum against the billed amount, and closes the invoice-math
  axis. Malformed input is refused by name rather than skipped, because a silently
  dropped line would under-count the total and read as an overbilling.
- **Quantity *and* rate, deliberately — not a bare count.** US storage has billed
  below the Notion card since ~May 2026 (NJ $4.34 vs card $5.98, Fontana $4.47 vs
  $5.90), so a `--pallet-count` flag that multiplied by the card rate would have
  invented a ~25% discrepancy on all 14 storage invoices. The supplied rate is what
  was billed; the card comparison is a separate labelled line, and below-card is
  reported as a stale card rather than a dispute. Only the largest line is compared,
  since a storage invoice also carries per-bin charges on a different basis.
- **A `--detail` verdict survives the scheduled sweep.** Writes from a detail run
  stamp `validated_by` as `yusen-invoice-validator (detail supplied by operator)`,
  which the 1.3.0 human-stamp rule treats as a person's verdict. Without this the
  06:30 header sweep — which by construction can only ever return `needs_detail` —
  would revert the row the next morning and throw the work away. Escalations still
  win: a later `discrepancy` or `disputed` overrides it, and a `disputed` stamp is
  still never cleared by a detail pass.

## 1.4.0 — 2026-08-07

Two Stedi bugs that made the order-level check unreliable in both directions:
it reported orders as shipped that weren't, and reported LTL freight as missing
that had shipped. Both were found while validating invoice 756521.

- **The `transaction_type` filter never worked.** `validate_stedi.py` queried
  `?transaction_type=945`, and on an empty result retried with `940`. The Stedi
  `/transactions` endpoint **ignores that parameter** — verified 2026-08-07:
  945, 940, 856 and 999 all return byte-identical item sets for the same
  `businessIdentifier`. The first query therefore always returned every document
  type, and the script labelled `items[0]` as `945 / Shipped` whatever it was. An
  order with only an 850 purchase order reported as shipped, and the 940 branch
  was dead code. The script now makes **one** request per identifier and reads
  the real X12 `transactionSetIdentifier` off each item.
- **`shipped` replaces `found` as the headline.** Classification is explicit:
  945 = shipped, 856 = ASN sent but no warehouse 945, 940 = in warehouse, and
  anything else = "other EDI activity only". Results carry `doc_types` (every
  real type seen) plus a `shipped` boolean, and the summary now calls out orders
  that are present in Stedi but have **no** 945 — precisely the case the old code
  passed off as shipped. The SP/LTL payment gate keys on `shipped`.
- **LTL bills of lading are now resolvable.** Stedi does not index BOLs: it
  indexes the depositor/PO number (W06-02), while the invoice worksheet's "Bol#"
  column is **W06-04**, which lives only inside the 945 payload. Feeding BOLs to
  the identifier lookup returned "missing" for every LTL line on every invoice,
  forever. A fallback pass now scans 945 payloads and matches on W06-04 (and
  W06-02), recording the PO, ship-to, carton count and ship date it recovers.
  Matches are tagged `matched_by: "bol"` so BOL-derived evidence stays
  distinguishable from a direct hit.
- **`fromDate`/`toDate` are ignored too**, so the fallback cannot ask the server
  for a window. It pages newest-first, applies the cutoff client-side, and drains
  in chunks so it **stops as soon as every BOL is accounted for** rather than
  reading the whole window. Bounded by `--bol-days` (default 14) and skippable
  with `--no-bol-fallback`.
- **Identifier lookups now run concurrently** (`--workers`, default 10). With the
  ignored-filter retry gone it is one request per order instead of two, which is
  what made the sequential loop slow enough that `CLAUDE.md` told operators to
  write their own concurrent checker instead of using this script.
- **Artifact fetches follow redirects without auth.** Artifact URLs 302 to
  presigned object storage that rejects a replayed Stedi `Authorization` header.
- **Verified on invoice 756521** (1,252 lines, Fontana, week of 7/26–7/31): 1,214
  small-parcel orders all carry a genuine 945, and 37 of 38 LTL BOLs resolve via
  W06-04. The 38th (…3882) is the paired trailer of a single 1,493-carton HLI2
  shipment whose 945 references the sibling BOL, so it is correctly reported as
  unresolved rather than silently passed. Before this change the same invoice
  scored "97.0%" with all 38 BOLs listed as missing.

## 1.3.0 — 2026-08-05

Human verdicts outrank the automated header pass. A stamp recorded by a person is
now as sticky as a `disputed` stamp, so supplying the itemized detail once makes it
stick instead of being reverted by the next sweep.

- **A human stamp is preserved against re-sweeps.** `write_result` treats any prior
  stamp whose `validated_by` is not `yusen-invoice-validator` as human-set: an
  automated pass returning `valid` or `needs_detail` refreshes `validated_at` and the
  `[AUTO]` report block but leaves the status, variance and provenance alone. This
  generalises the previous rule, which only protected a *paid* row's explicit `valid`
  — it now covers unpaid rows too, which is the common case for an invoice whose
  hours or unit counts were entered by hand.
- **Escalations still win.** Preservation applies only when the sweep comes back
  `valid`/`needs_detail`. A pass that finds `disputed` or a discrepancy overrides a
  human `valid`, because that is new information rather than missing information.
- **`fetch_invoice` now selects `validated_by`.** Without it the guard above could
  never see who set the prior stamp and would silently never fire.
- **Stedi key loads from `~/.yusen/yusen.env`.** `validate_stedi.py` previously
  relied on `~/.claude/settings.json` injecting `STEDI_API_KEY` into every session's
  environment — a live credential sitting in a settings file. The key moved to the
  gitignored, chmod-600 env file, and the script now loads it itself (respecting
  `$YUSEN_ENV_FILE`, and never overriding a value already in the environment).
- **Why now.** A header-level pass cannot see hours or itemized counts, so VAS,
  Storage and SP/LTL invoices land on `needs_detail` by default. When those details
  are supplied by hand and the row is marked `valid`, the 15:30 MT sweep was set to
  overwrite it the next day — a treadmill that would have reverted invoice 755879 and
  the 226 rows bulk-marked valid on 2026-08-05.

## 1.2.0 — 2026-08-05

Validate-on-ingest hook: every sweep now stamps a finance-visible status and a
stored report card, and invoices carrying known MSA-conflict charges surface as
`disputed` automatically instead of waiting for a manual review.

- **New `disputed` status** (⚑, short-pay/hold): emitted when a validated
  invoice contains any known 2026-MSA conflict line — AF-9 wrap billed
  separately (NJ STRETCHWRAP at 4.34–4.35) or embedded (Fontana/SC 14.317
  pallet rate → wrap component × 4.317) against the $10.00 all-in national
  pallet rate; AF-7 PACK CARTON pack-out at 0.92 (removed per Yusen 4/28);
  Fontana PICK & PACK ECOM billed on every pick where the MSA line is "Per
  Additional Ecom Pick" (flagged for additional-only recompute). The disputed
  dollar total goes to `validation_variance`, so both dashboards render
  "⚑ Disputed $X".
- **Disputed stamps are sticky**: a re-sweep whose header-level pass comes back
  `valid`/`needs_detail` refreshes `validated_at` and the report but never
  downgrades a `disputed` row — the conflict lives in line items a header pass
  can't see. Clears only on re-bill/credit or manual clearing.
- **Paid-valid stamps are sticky too**: a paid row explicitly stamped `valid`
  (the mark-paid user policy) is settled — a later header-level sweep coming
  back `needs_detail` refreshes the report but never un-checks it; real
  escalations (`discrepancy`/`disputed`) still overwrite.
- **Report card stored on every `--write`**, not only on `--mark-paid`: the
  per-invoice verdict is written to `validation_report` as a dated
  `[AUTO YYYY-MM-DD]` block that replaces only its own previous block —
  payment report cards, `[MSA DISPUTE …]` specs, and human notes are preserved.
- Sweep rollup now counts and lists MSA disputes alongside discrepancies.

## 1.1.0 — 2026-07-13

### Validation
- Three-axis reporting is now the standard: every report gives explicit verdicts on
  invoice math, rate-card alignment, and (for SP/LTL) Stedi shipment evidence.
- US Storage/SP-LTL invoices close the rate-card axis from the PDF worksheet
  (qty × full-precision rate); billing bases documented per site (SC peak-day
  pallets, NJ flat count, Fontana locations + bulk).
- Fixed: the intl (NL/Canada) breakdown sum-check never received the `notes`
  column in the live pipeline — one-line fetch fix; the check now genuinely runs.
- NL warehousing invoices (FTI series) are VAT **zero-rated** (art. 44 export
  service) — no longer false-flagged; NL 2026 rates carry ~+4.7% Panteia indexation.
- Recorded the verified 2026 Taylored rate transition (effective billing weeks
  ~May 4–10): storage SC 3.35 / NJ 4.34 / Fontana 4.47; per-fee cuts ~8%; pallet
  restructured to $10.00 + wrap; snapshot annotated pending the Notion card update.
- NJ admin labor tax modeled as on/off date-intervals with the verified cutover
  2026-04-27 (was: flat effective date).
- Warehouse mapping: SAVANNAH / TS South → south_carolina; token-safe matching for
  short codes (stops "Schiphol" → SC substring hits).

### Stedi (SP/LTL)
- Order-level Stedi verification is **automatic** when validating an SP/LTL
  invoice — supporting doc fetched from Drive, parsed, swept 945-then-940; a
  header-only SP/LTL report is labeled incomplete.
- **Payment gate:** SP/LTL invoices cannot be marked paid until the Stedi match
  rate has been run and reviewed.
- Parser supports all three supporting-doc layouts: modern Yusen, Taylored
  (header-driven — variable sheet names/columns/offsets), and the per-carton
  SHIPPED report (ORDER# dedupe + AME*/AMF*/AMS* prefix strip). BOL numbers are
  excluded from the Stedi denominator (verified by worksheet count instead).

### Payment tracking & audit
- New tracking columns (provisioned by `--init`): `paid_at`, `paid_marked_by`,
  `validation_report`.
- `--mark-paid` / `--unmark-paid`: payment marked only on explicit user
  confirmation; approval stores the full report card on the row
  (`--report-file` for document-level reports); reports shown on the dashboard.
- Unpaid invoices no longer print a "not marked paid" line — the ask-if-paid
  step covers it.

### Docs
- README rewritten as the comprehensive system doc (families, hard rules, data
  model, gotchas, rate history); `references/netherlands.md` expanded.

## 1.0.0 — 2026-06-30
- Initial release.
- Rate-card validation against the live Notion Yusen / Taylored 2026 rate card for Admin, Storage, VAS, Small Parcel, and LTL across Fontana, New Jersey, South Carolina, Canada, and Netherlands.
- Stedi EDI order validation (945 shipped / 940 in-warehouse) for Small Parcel / LTL order numbers.
- Netherlands (Yusen Benelux) support: EUR + 21% VAT; transport-invoice checks (Amazon Delivery flat €100, fuel = pct × transport, subtotal/VAT/total) and warehousing rates.
- International breakdown sum-check for NL (EUR) and Canada (USD) one-row-per-charge-type invoices.
- NJ admin labor tax modeled as on/off date-intervals (5% before 2026-04-27).
- Write-back tracking: `--write` persists validation status to BigQuery; `--init` self-provisions the tracking columns.
