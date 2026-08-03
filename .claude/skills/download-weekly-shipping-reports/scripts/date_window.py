#!/usr/bin/env python3
"""Compute the prior Monday->Monday window for the weekly shipping reports.

Rule (matches the established manual practice):
  Run on a Thursday -> this_monday = the Monday earlier this week
                       prev_monday = this_monday - 7 days
  Window = prev_monday .. this_monday INCLUSIVE (an 8-day Mon->Mon span).

Works on any run day: this_monday is always the Monday of the current week
(the most recent Monday on or before the run date).

Usage:
  python3 date_window.py                 # uses today
  python3 date_window.py --date 2026-06-19
  python3 date_window.py --json          # machine-readable

Stdlib only.
"""
import argparse
import datetime as dt
import json


def compute(run_date: dt.date):
    # weekday(): Monday=0 ... Sunday=6. Back up to this week's Monday.
    this_monday = run_date - dt.timedelta(days=run_date.weekday())
    prev_monday = this_monday - dt.timedelta(days=7)
    folder = f"{prev_monday.isoformat()}_to_{this_monday.isoformat()}"
    return {
        "run_date": run_date.isoformat(),
        "prev_monday": prev_monday.isoformat(),
        "this_monday": this_monday.isoformat(),
        "window_inclusive": f"{prev_monday.isoformat()} .. {this_monday.isoformat()}",
        "days_inclusive": (this_monday - prev_monday).days + 1,
        "folder_name": folder,
        "staging_path": (
            "~/Documents/Claude/Projects/Weekly Shipping Reports/" + folder
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="Run date as YYYY-MM-DD (default: today)")
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    args = ap.parse_args()

    run_date = (dt.date.fromisoformat(args.date) if args.date
                else dt.date.today())
    info = compute(run_date)

    if args.json:
        print(json.dumps(info, indent=2))
        return

    print(f"Run date     : {info['run_date']}")
    print(f"prev_monday  : {info['prev_monday']}")
    print(f"this_monday  : {info['this_monday']}")
    print(f"Window       : {info['window_inclusive']}  ({info['days_inclusive']} days, inclusive)")
    print(f"Folder name  : {info['folder_name']}")
    print(f"Staging path : {info['staging_path']}")


if __name__ == "__main__":
    main()
