#!/usr/bin/env python3
"""Confirm the Mac sweep has actually stopped writing to the ledger.

Runs on the Mac, so it goes through the `bq` CLI and gcloud ADC rather than the
REST endpoint a cloud session would use. Read-only: it issues SELECTs and writes
nothing, so it is safe to run as often as you like.

    python3 mac-handoff/check_sweep_stopped.py

Two questions, because either one alone can mislead:

  1. Did anything write during the sweep's window? The sweep ran 16:30-16:58 UTC
     on 2026-09-22. A write in that hour tomorrow means it is still loaded.
  2. Did the count of legacy-rate notes grow? Only the v1.4.0 sweep can write
     $5.90 / $5.98 / $5.09 -- the committed v1.6.2 card holds the MSA rates. If
     that count rises, something is still running the old package, whatever the
     timestamps say.

Every `bq` call passes --max_rows explicitly: the CLI silently truncates at 100
rows without it, which has caused real bugs here. These queries return one row
each, but the flag stays so nobody copies a truncating call out of this file.
"""
import json
import subprocess
import sys

TABLE = "americanflat.finance.yusen_invoices"
# Baselines taken 2026-09-22 17:35 UTC, straight after the sweep's 16:30-16:58 pass:
# 74 rows carry a legacy-rate note, 390 of 396 read 'OK to pay'.
BASELINE_LEGACY_NOTES = 74
WINDOW_START, WINDOW_END = "16:00", "17:00"


def bq(sql):
    r = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=json", "--max_rows=10", sql],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("bq failed:\n" + (r.stderr or r.stdout).strip()[:500])
        sys.exit(2)
    return json.loads(r.stdout or "[]")


def main():
    rows = bq(f"""
        SELECT
          CAST(MAX(validated_at) AS STRING) AS newest,
          COUNTIF(validated_at >= TIMESTAMP(CONCAT(
                    FORMAT_DATE('%Y-%m-%d', CURRENT_DATE()), ' {WINDOW_START}:00+00'))
              AND validated_at <  TIMESTAMP(CONCAT(
                    FORMAT_DATE('%Y-%m-%d', CURRENT_DATE()), ' {WINDOW_END}:00+00'))) AS in_window,
          COUNTIF(REGEXP_CONTAINS(validation_report,
                    r'5\\.90|5\\.91|5\\.98|5\\.09')) AS legacy_notes,
          COUNTIF(REGEXP_CONTAINS(validation_report,
                    r'Verdict:       OK to pay')) AS ok_to_pay,
          COUNT(*) AS total
        FROM `{TABLE}`
    """)
    if not rows:
        print("no rows returned -- check the table name and your gcloud login")
        sys.exit(2)
    r = rows[0]
    newest = r["newest"]
    in_window = int(r["in_window"])
    legacy = int(r["legacy_notes"])
    ok = int(r["ok_to_pay"])
    total = int(r["total"])

    print(f"last write to the ledger      : {newest}")
    print(f"writes in the {WINDOW_START}-{WINDOW_END} UTC window : {in_window}")
    print(f"notes quoting a legacy rate   : {legacy}   (baseline {BASELINE_LEGACY_NOTES})")
    print(f"rows reading 'OK to pay'      : {ok} of {total}")
    print()

    problems = []
    if in_window:
        problems.append(
            f"{in_window} row(s) were written in the sweep's usual window today -- "
            f"the job still looks loaded. Re-check `launchctl list | grep -i yusen`.")
    if legacy > BASELINE_LEGACY_NOTES:
        problems.append(
            f"legacy-rate notes rose from {BASELINE_LEGACY_NOTES} to {legacy} -- "
            f"something is still writing with the old rate card.")

    if problems:
        print("STILL RUNNING")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    print("STOPPED -- no write in the sweep's window and no new legacy-rate notes.")
    if ok > 0:
        print()
        print(f"Note: {ok} row(s) still read 'OK to pay' from the old sweep. Stopping the")
        print("job freezes those verdicts, it does not clear them. They need a separate")
        print("corrective pass -- see stop-the-mac-sweep-2026-09-22.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
