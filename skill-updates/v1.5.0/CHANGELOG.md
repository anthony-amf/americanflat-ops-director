# Changelog

## 1.5.0 — 2026-08-11

Fixes two report-text bugs found on invoice 755265. Nothing about how invoices are
judged changes — status, variance and stamp stickiness behave exactly as in 1.4.0.
What changes is how the stored `validation_report` is assembled, and it fixes real
data loss.

**Only two files differ from 1.4.0:** `validate_rate_card.py` and `skill.toml`
(version bump). `SKILL.md` is included with the two documentation passages
updated. Everything else in the 1.4.0 package is unchanged — copy these over the
canonical source and repackage.

### 1. `--mark-paid` was destroying the row's report history

`mark_paid()` stored the payment card with
`validation_report = COALESCE(@report, validation_report)` — a full replace. Since
the mark-paid path always builds a report (auto-composed when `--report-file` is
omitted), **every payment mark silently discarded every other block on the row.**

Found on 755265: the row went from 1,644 chars to 386, losing its
`[MSA REVAL 2026-08-06]` block and its `[DEEP PASS 2026-08-10]` block — the
itemized five-line math and the 289/289 Stedi order match. 754891 lost the same
way (1,741 → 386, 106/106 Stedi). Both rows are `valid` and paid, so no later
sweep would ever have rebuilt them; the text survived only in BigQuery's 7-day
table history. Older paid rows escaped visible damage only because a later sweep
happened to re-add an `[AUTO]` block.

Now: the payment card goes in as its own `[PAID YYYY-MM-DD]` block via
`merge_report(..., tag="PAID")`, leaving every other block verbatim. A second
payment mark replaces only the `[PAID]` block. If the prior report cannot be read,
the field is left untouched rather than overwritten.

Recovery for the two damaged rows:
`sql/restore_clobbered_reports_2026-08-11.sql` in the ops-director repo.

### 2. A header-level pass could talk over a completed deep review

`write_result()` refreshed the `[AUTO]` block on every write — including writes
where it had just decided to *preserve* the existing status. So on 755265 an
`[AUTO 2026-08-11]` block reading "provide itemized counts" and "order-level Stedi
check available via supporting Excel" was appended directly beneath a
`[DEEP PASS 2026-08-10]` block that had already recorded the itemized math and
289/289 shipped. The AUTO block is written last, so it reads as the current
verdict — the invoice looked unfinished when it was fully checked and paid.

Now: when the result is `needs_detail` **and** the row already carries a
`[DEEP PASS]`, `[STEDI]`, `[MSA DISPUTE]` or `[MSA REVAL]` block, the AUTO block
becomes one line — "header-level re-check only, no new findings; itemized detail
already on file above (…); this pass does not supersede it" — instead of the full
card. Rows with no deeper block are unaffected and still get the normal card.

`--mark-paid`'s auto-composed card follows the same rule: with a deeper review on
the row it cites that review rather than re-stating header-level unknowns.

### 3. Smaller wording fix

`compose_report()`'s Stedi line said "order-level Stedi check available via
supporting Excel" — which reads as a to-do even on an invoice whose check is
finished. It now says "no order-level Stedi result recorded on this row yet", and
prints a completed result when the caller supplies one via `r["stedi_note"]`.

### API notes for callers

- `merge_report(prior, block, tag="AUTO")` gained the `tag` argument. Existing
  two-argument calls are unchanged — the cloud sweep's
  `V.merge_report(prior, V.compose_report(r))` still targets the `[AUTO]` block.
- New module-level helpers: `_block_pattern(tag)`, `_DEEPER_BLOCK`,
  `_deferral_block(r, prior_report)`.
- **Rule for anything that writes report text:** go through `merge_report` with the
  right tag. Never assign `validation_report` directly — that is what caused this.

Verified by `skill-updates/v1.5.0/test_report_merge.py` (31 checks over the real
recovered 755265 text): every other block survives a payment mark, repeat marks
don't stack, `[AUTO]` merge behaviour from 1.4.0 is preserved, the deferral names
the deeper blocks and drops the misleading wording, and clean rows still get the
full card.
