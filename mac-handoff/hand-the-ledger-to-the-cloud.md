# Make the cloud Routine the only writer

Anthony's decision, 2026-09-10: the cloud nightly run owns the ledger.

**This supersedes `point-launchd-at-1.6.0.md` in this folder.** That file is kept
(it is still the reference for what the LaunchAgent runs and how to repoint it) but
you no longer need it for this: a job that is not running does not need upgrading.

Only one step touches the Mac. Everything else was fixed cloud-side and is already
pushed.

---

## Why the cloud one can own it — the evidence, not the intent

Checked 2026-09-10 from a cloud session, all four things it needs:

| capability | result |
|---|---|
| write to BigQuery | probe succeeds; 13 `[STEDI]` stamps written 2026-09-09 |
| read the whole ledger | 383 rows over the REST API |
| fetch invoice PDFs from Drive | 758665.pdf, 514,776 bytes |
| resolve a row end to end | **758665: `needs_detail` → `valid`** |

That last one is the proof: 3,528 pallets x $4.34 = $15,311.52, exact, at the MSA
New Jersey rate, from the PDF, with no Mac involved. A $15,311.52 invoice the Mac
sweep could never have cleared, because it never opens a PDF.

## Why it was writing nothing anyway

The nightly run has been reporting SUCCEEDED and stamping zero rows. It was not a
permissions problem and not an empty work list — there were 56 rows waiting, all
with PDFs, and the write probe passes.

Step 2 of the sweep runbook began `cd ~/americanflat-ops-director`. In the cloud
container `$HOME` is `/root` and the repo is under `/home/user/`, so that `cd`
failed, `unzip` found no archive, `VALIDATOR_OK` never printed — and the runbook's
own rule then said, correctly, "STOP, sweep skipped, change nothing." One wrong
path, and the job skipped itself every night while looking healthy. Fixed, and the
runbook now takes the repo root from git and forbids `~` outright.

Second latent break, also fixed: step 4 calls `apply_vas_pallet_check` and
`apply_vas_labor_check`, which only exist in v1.6.0, while the preflight admitted
anything 1.4+. A 1.5.x package passed the gate and then died mid-step-4 having
written nothing. The preflight now tests for the functions it is about to call and
refuses the old package (verified both ways).

## The one Mac step — stop the sweep writing

`launchctl unload` stops the job. **It deletes nothing**: the plist stays in
`~/Library/LaunchAgents/`, the skill directory stays, and reloading is one command.

```bash
mkdir -p ~/quarantine/$(date +%F) && \
  cp ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist \
     ~/quarantine/$(date +%F)/ && \
  launchctl unload ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl list | grep -i yusen
```

The `grep` should now show only `yusen-invoice-processor` — the **ingestion** job,
which must keep running. It is a different job with a similar name. If you see
`yusen-validator-sweep` still listed, the unload did not take.

Copying the plist aside first is belt and braces: it is a Mac-only file with no
copy in git, and it is the one thing here with no other backup.

## Then confirm the handover, over the next two days

**Tomorrow, after 08:00 UTC** (the nightly run) — the sweep should finally do work:

```bash
bash mac-handoff/verify_1_6_0_landed.sh
```

Baselines in that script are as of today: 66 storage notes quoting the legacy
$5.90/$5.98/$5.09, none quoting the MSA $4.47/$4.34/$3.35, 756522 at
`needs_detail`. After a real run the legacy count should fall toward zero and the
MSA count rise. It also refuses to call it a success if `valid` or `disputed` ever
drops.

The signal that the handover worked is narrower and better than "the job ran":

* `MAX(validated_at)` moves to the new date. A run that reports success without
  moving this did nothing — that was the whole failure mode.
* Some of the 56 waiting rows leave `needs_detail`. Storage rows are the ones to
  watch; they resolve cleanly from the PDF, as 758665 did.
* No note anywhere quotes $5.90/$5.98/$5.09 again. With the Mac sweep stopped,
  nothing can write those numbers any more.

## If it goes wrong

Reload the Mac sweep — nothing was removed:

```bash
launchctl load ~/Library/LaunchAgents/com.americanflat.yusen-validator-sweep.plist && \
  launchctl list | grep -i yusen-validator-sweep
```

It will resume writing legacy-rate notes, which is worse than the cloud job but
better than nothing writing at all. If you want it back *and* correct, that is what
`point-launchd-at-1.6.0.md` is for.

## What this does not solve

Four SP/LTL invoices at South Carolina cannot be priced by anyone — Yusen sends a
shipped-order manifest with no charge columns. That needs a different document from
them, not a code change.

And the nightly run is now genuinely a single point of failure: one job, once a day,
and no second pass. `yusen-cloud-validation-sweep-midday` exists but is disabled
(last fired 2026-08-11). Worth deciding whether to re-enable it as a second pass now
that phase 1 actually runs.
