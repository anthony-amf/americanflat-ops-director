# Stop the Mac sweep — it is still running

**Status check, 2026-09-22.** The unload in `hand-the-ledger-to-the-cloud.md` was
written on 2026-09-10 and never ran. The Mac sweep is still loaded, still on
v1.4.0, and swept the whole ledger this morning.

Nothing in the command below has changed since that document. This one exists
because the situation is now measured rather than predicted, and because a second
problem came with it that the unload alone does not fix.

---

## Proof it is the Mac, not a cloud Routine

Four independent checks, all from the ledger and the Routine list on 2026-09-22.

**1. It quotes rates the current validator cannot produce.** The blocks written
this morning say `$5.09/pallet for south_carolina` and `$5.90/pallet for fontana`.
The committed package is v1.6.2 and its card holds fontana 4.47 / new_jersey 4.34 /
south_carolina 3.35, with 5.9055 / 5.98 / 5.0925 filed under pre-June history. The
packaged validator reads the live values, so it cannot emit $5.90. This is the
fingerprint — same one this repo already documents as the way to tell the two
writers apart.

**2. The clock matches no Routine.** The sweep ran 16:30–16:58 UTC and touched all
396 rows. Today's Routine fires:

| Routine | fired (UTC) |
|---|---|
| `yusen-nightly-validation-2am-mt` | 08:03 |
| `refresh-yusen-artifact-830am-330pm` | 12:42 |
| `refresh-yusen-artifact-noon-6pm` | 16:13 |
| `yusen-cloud-validation-sweep-midday` | 17:08 |

Nothing at 16:30. That is 10:30 AM Mountain — a job on the Mac.

**3. No v1.6.1 wording.** Storage blocks should read "at the MSA rate of
$4.47/pallet for fontana, live from 2026-05-04. Supersedes the pre-MSA $5.91."
That sentence appears nowhere in the ledger.

**4. No v1.6.2 gate.** Every verdict reads `OK to pay` whatever did or did not pass.

## What it is doing

**390 of 396 rows now read `Verdict: OK to pay`** — 13 of them `disputed`, 145 of
them unpaid — while the invoice-math and rate-card lines on those same rows are
still pending. On 754698 that sits directly above the "HOLD per Anthony 7/27" note.

It is stamping "OK to pay" on invoices where nothing was checked.

**What it is not doing:** it replaces only its own `[AUTO]` block. The 15
`[MSA DISPUTE]`, 18 `[DEEP PASS]` and 29 `[STEDI]` blocks are all intact. It does
overwrite `validated_at` on every row, which is why the ledger looks freshly
validated, and why earlier runs are invisible — that column holds only the most
recent write, not a history.

---

## The step

`launchctl unload` stops the job. **It removes nothing**: the plist stays in
`~/Library/LaunchAgents/`, the skill directory stays, and reloading is one command.
The copy is taken first because the plist is a Mac-only file with no copy in git.

```bash
mkdir -p ~/quarantine/$(date +%F) && \
  cp ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist \
     ~/quarantine/$(date +%F)/ && \
  launchctl unload ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl list | grep -i yusen
```

The `grep` should now show **only** `yusen-invoice-processor`. That is the
**ingestion** job and it must keep running — different job, similar name. If
`yusen-validator-sweep` is still listed, the unload did not take.

## Confirm it actually stopped

Tomorrow, any time after 17:00 UTC, run this from the repo. It reports the last
write to the ledger and whether any legacy-rate note was added since today:

```bash
python3 mac-handoff/check_sweep_stopped.py
```

A pass looks like: no ledger write in the 16:00–17:00 UTC window, and no more than
74 notes quoting $5.90 / $5.98 / $5.09 — today's baseline, taken right after the
sweep finished.

The window check is the sharper of the two. Run against today's ledger it already
reports 396 writes in that hour, which is the sweep being caught in the act; after
a successful unload it should report 0.

## If you want it back

Nothing was removed, so:

```bash
launchctl load ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl list | grep -i yusen-validator-sweep
```

---

## The part the unload does not fix

**Those 390 "OK to pay" verdicts do not correct themselves.** A settled row is never
re-swept, so stopping the sweep freezes the stale verdicts exactly where they are
rather than clearing them. They need one corrective pass afterwards, which is a
separate, reviewable step — not something to bundle into the unload.

Two other things still open, both unrelated to the Mac:

* **The midday Routine fired at 17:08 today and wrote nothing.** Zero rows in the
  half hour after. The silent-success problem is not fixed.
* **Four South Carolina SP/LTL invoices still cannot be priced by anyone** — Yusen
  sends a shipped-order manifest with no charge columns. That needs a different
  document from them, not a code change.
