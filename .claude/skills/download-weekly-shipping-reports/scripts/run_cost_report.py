#!/usr/bin/env python3
"""Run shipping-cost-report's process_shipments.py against the five staged files.

Locates the sibling `shipping-cost-report` skill, globs the five canonical inputs out of
the staging folder, and invokes its matcher. Writes shipping_cost_report.xlsx +
marketplace_summary.json into the same folder, then prints the headline numbers and a
run_summary.txt.

Usage:
  python3 run_cost_report.py --dir "~/Documents/Claude/Projects/Weekly Shipping Reports/2026-06-08_to_2026-06-15"
  python3 run_cost_report.py --dir <staging> --cost-report-skill ~/.claude/skills/shipping-cost-report

Stdlib only (the matcher itself may need pandas/openpyxl).
"""
import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys

CANDIDATE_SKILL_DIRS = [
    "~/.claude/skills/shipping-cost-report",
    "~/.config/claude/skills/shipping-cost-report",
]


def find_process_script(explicit: str | None) -> str:
    roots = []
    if explicit:
        roots.append(explicit)
    roots.extend(CANDIDATE_SKILL_DIRS)
    # also try a sibling of THIS skill
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.path.join(os.path.dirname(here), "shipping-cost-report"))

    for root in roots:
        cand = os.path.join(os.path.expanduser(root), "scripts", "process_shipments.py")
        if os.path.isfile(cand):
            return cand
    sys.exit("Could not locate shipping-cost-report/scripts/process_shipments.py. "
             "Pass --cost-report-skill <path>.")


def one(patterns, folder, required=True, label=""):
    hits = []
    for pat in patterns:
        hits.extend(glob.glob(os.path.join(folder, pat)))
    hits = sorted(set(hits))
    if not hits and required:
        sys.exit(f"Missing required input for {label}: none of {patterns} in {folder}")
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="Staging folder with the 5 inputs")
    ap.add_argument("--cost-report-skill", help="Path to the shipping-cost-report skill")
    args = ap.parse_args()

    folder = os.path.expanduser(args.dir)
    if not os.path.isdir(folder):
        sys.exit(f"Staging folder not found: {folder}")

    script = find_process_script(args.cost_report_skill)

    fedex = one(["FedEx_Invoice_*_most-recent.csv", "FedEx_Invoice_*.csv"], folder, True, "FedEx")
    stamps = one(["Stamps_PrintHistory_*.csv"], folder, True, "Stamps")
    fontana = one(["Fontana_ShippedOrders_*.csv"], folder, True, "Fontana")
    nj = one(["NewJersey_ShippedOrders_*.csv"], folder, True, "New Jersey")
    sc = one(["SouthCarolina_OrderDetails_*.xlsx"], folder, True, "South Carolina")

    cmd = [sys.executable, script,
           "--fedex", *fedex,
           "--stamps", *stamps,
           "--nj-fontana", *fontana, *nj,
           "--sc", *sc,
           "--output-dir", folder]
    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        sys.exit(f"process_shipments.py exited {rc}")

    summary_path = os.path.join(folder, "marketplace_summary.json")
    blended = matched = None
    if os.path.isfile(summary_path):
        try:
            with open(summary_path) as fh:
                data = json.load(fh)
            blended = data.get("blended_cpu") or data.get("blendedCPU")
            matched = data.get("matched_shipments") or data.get("matched")
        except Exception:
            pass

    run_summary = os.path.join(folder, "run_summary.txt")
    with open(run_summary, "w") as fh:
        fh.write(f"Weekly Shipping Report run {dt.datetime.now().isoformat()}\n")
        fh.write(f"Staging folder: {folder}\n")
        fh.write(f"Deliverable: shipping_cost_report.xlsx\n")
        if blended is not None:
            fh.write(f"Blended CPU: {blended}\n")
        if matched is not None:
            fh.write(f"Matched shipments: {matched}\n")
    print(f"\nDone. Deliverable: {os.path.join(folder, 'shipping_cost_report.xlsx')}")
    if blended is not None:
        print(f"Blended CPU: {blended}   Matched: {matched}")
    print(f"Wrote {run_summary}")


if __name__ == "__main__":
    main()
