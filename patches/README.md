# Patches for the invoice processor skill

The processor's runnable source lives on the Mac at
`~/skill-yusen-invoice-processor/scripts/invoice_processor.py`, outside this repo.
Patches here are written against that file so they can be applied there.

## invoice-processor-multi-pdf-forward.patch

Fixes two ways a forwarded invoice gets dropped without a word.

**1. A forward only counted if you titled it exactly right.** The search that
finds invoice emails required the phrase `Fwd: Invoice #` in the subject. Forward
a Yusen invoice under any other subject and the processor never saw it — no
error, no Slack alert, nothing. This is what happened on 2026-09-17: three
invoices Yusen had re-sent (755367, 755477, 755501) were forwarded to the
pipeline inbox under the vendor thread's own subject, "Fwd: Americanflat August
AR aging", and sat unseen.

The patch adds a clause for anything a person sends from an americanflat.com
address to `administrator@americanflat.com` — the pipeline's own inbox. Forwarding
an invoice there is already a deliberate act, so the subject no longer has to be
memorised. Widening it is safe: the existing Yusen/Taylored marker check drops
unrelated vendor PDFs silently, exactly as it does today.

**2. One email could only ever load one invoice.** The US path took
`pdf_paths[0]` and ignored the rest; the loop over every attachment was fenced
behind international mode. So even a correctly-titled forward carrying three
invoice PDFs would load the first and discard the other two.

The patch walks every PDF in the message. Each one is checked, parsed and
deduplicated on its own.

**Where the invoice number comes from.** For a classic single-invoice email the
subject stays authoritative, so the daily run behaves exactly as it does now.
When there are several PDFs — or the subject was never rewritten — the number is
read off the invoice itself. US invoices print it beside the invoice date
(`INVOICE  7110  759181 09/18/2026`), so the patch matches that number-and-date
pair rather than the "Invoice No." caption, which the PDF lays out far from its
value. Checked against a real 854 KB storage invoice: exactly one match, and a
5-digit work-order number next to a date does not false-positive.

A PDF with no number in either place is now Slack-alerted instead of being
guessed at.

### Applying it

    cd ~/skill-yusen-invoice-processor
    git apply --check patches/invoice-processor-multi-pdf-forward.patch   # dry run
    git apply patches/invoice-processor-multi-pdf-forward.patch

Then repackage and commit per the skill workflow in CLAUDE.md.

The patch is cut against the copy of `invoice_processor.py` exported into
`yusen-invoice-processor.skill.md` (generated 2026-07-14). If the Mac source has
moved on since and `git apply` refuses it, the four edits are small and clearly
separated — apply them by hand.

### Checked before shipping

- The patched file compiles.
- The patch applies cleanly to a fresh copy and yields byte-identical output.
- `invoice_no_from_text` returns 759181 and 759085 from the real invoice text of
  each, `None` when there is no number, and `None` for a work-order/date pair.
- `build_query(False)` now contains the pipeline-inbox clause.

Not tested end to end: running the processor needs Gmail OAuth and the Mac's
BigQuery credentials, neither reachable from a cloud session. Do the first run
with `--dry-run`.
