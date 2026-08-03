#!/usr/bin/env python3
"""Safely capture a just-downloaded portal file and stage it under a canonical name.

Why this exists (Known issue #5): never trust `ls -t | head -1`. A blocked or throttled
download can leave a STALE file as "newest", which once caused a stale Fontana file to
overwrite the NJ slot. This helper only accepts a file that is BOTH:
  1. newer than the moment you clicked Export (--since-epoch), AND
  2. a content/extension fingerprint match for the requested portal "kind".

Usage:
  # Just before clicking Export in the browser, capture the time:
  #   T=$(python3 -c 'import time;print(time.time())')
  python3 stage_download.py \
    --downloads-dir ~/Downloads \
    --since-epoch "$T" \
    --kind fontana \
    --dest "~/Documents/Claude/Projects/Weekly Shipping Reports/2026-06-08_to_2026-06-15"

Exit codes: 0 staged OK; 2 no qualifying file found (likely a blocked download — retry).
Stdlib only.
"""
import argparse
import csv
import datetime as dt
import os
import shutil
import sys
import time

# kind -> (canonical name template, allowed extensions, header fingerprint substrings)
KINDS = {
    "fontana": (
        "Fontana_ShippedOrders_{date}.csv", {".csv"},
        ["bill of lading", "batch", "units"],
    ),
    "newjersey": (
        "NewJersey_ShippedOrders_{date}.csv", {".csv"},
        ["bill of lading", "batch", "units"],
    ),
    "southcarolina": (
        "SouthCarolina_OrderDetails_{date}.xlsx", {".xlsx"},
        ["tracking number"],  # checked loosely for xlsx (see below)
    ),
    "stamps": (
        "Stamps_PrintHistory_{date}.csv", {".csv"},
        ["tracking #", "amount paid"],
    ),
    "fedex": (
        "FedEx_Invoice_{date}_most-recent.csv", {".csv"},
        ["tracking id", "net charge amount"],
    ),
}


def header_text(path: str) -> str:
    """Return a lowercased sample of the file's first row(s) for fingerprinting.
    For .xlsx we just trust the extension (reading needs openpyxl); we sniff CSVs."""
    ext = os.path.splitext(path)[1].lower()
    if ext != ".csv":
        return ""  # extension is the fingerprint for xlsx
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = csv.reader(fh)
            cells = []
            for i, row in enumerate(reader):
                cells.extend(row)
                if i >= 2:
                    break
            return " | ".join(cells).lower()
    except Exception:
        return ""


def fingerprint_ok(path: str, kind: str) -> bool:
    _, exts, needles = KINDS[kind]
    ext = os.path.splitext(path)[1].lower()
    if ext not in exts:
        return False
    if ext == ".xlsx":
        return True  # extension match is sufficient for the SC order-details xlsx
    text = header_text(path)
    if not text:
        return False
    return all(n in text for n in needles)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--downloads-dir", default="~/Downloads")
    ap.add_argument("--since-epoch", type=float, required=True,
                    help="Only accept files with mtime >= this unix time")
    ap.add_argument("--kind", required=True, choices=sorted(KINDS))
    ap.add_argument("--dest", required=True, help="Staging folder")
    ap.add_argument("--grace", type=float, default=2.0,
                    help="Seconds of slack subtracted from since-epoch (clock skew)")
    args = ap.parse_args()

    downloads = os.path.expanduser(args.downloads_dir)
    dest = os.path.expanduser(args.dest)
    os.makedirs(dest, exist_ok=True)
    cutoff = args.since_epoch - args.grace

    candidates = []
    for name in os.listdir(downloads):
        p = os.path.join(downloads, name)
        if not os.path.isfile(p):
            continue
        if name.endswith((".crdownload", ".part", ".tmp")):
            continue  # still downloading
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        if not fingerprint_ok(p, args.kind):
            continue
        candidates.append((mtime, p))

    if not candidates:
        sys.stderr.write(
            f"[stage_download] No qualifying '{args.kind}' file in {downloads} "
            f"newer than {dt.datetime.fromtimestamp(cutoff)}. "
            f"Download likely blocked/throttled — retry the export.\n")
        sys.exit(2)

    candidates.sort()  # oldest..newest; take the newest qualifying file
    _, src = candidates[-1]

    tmpl, _, _ = KINDS[args.kind]
    stamp = dt.date.today().isoformat()
    out_name = tmpl.format(date=stamp)
    out_path = os.path.join(dest, out_name)
    shutil.copy2(src, out_path)

    print(f"Staged: {os.path.basename(src)}  ->  {out_path}")
    print(f"  size={os.path.getsize(out_path)} bytes  "
          f"mtime={dt.datetime.fromtimestamp(os.path.getmtime(src))}")


if __name__ == "__main__":
    main()
