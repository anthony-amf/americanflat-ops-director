#!/usr/bin/env python3
"""Refresh the Marketplace Shipments portal only when new carrier invoices land.

The portal's shipping costs come from three BigQuery tables that americanflat/Ops
loads each week from the carrier invoices: finance.stamps_shipping_costs,
finance.fedex_shipping_costs and finance.ups_shipping_costs. A scheduled Claude
task on the Mac runs this in three steps, the same shape as the Yusen dashboard
refresh (check, build, publish, then record):

    python3 marketplace_portal_refresh.py check
        exit 1 "SKIP — no new invoices": stop, nothing to do
        exit 0 "REFRESH — …": the tables changed since the last publish
        exit 2: the check itself failed; carry on (fails open so a broken
                check never lets the page go quietly stale)

    python3 marketplace_portal_refresh.py build
        one command, so it matches its permission allowlist entry — an
        unattended session that hits a permission prompt hangs rather than
        failing. Writes a new dated HTML file (never overwrites one) and prints
        "BUILT <path>". Refuses with "FAILED …" if the numbers look broken.

    python3 marketplace_portal_refresh.py mark-published <path>
        run only after the publish succeeded. Appends a line to the published
        log, which is what `check` compares against, so a failed publish leaves
        the change visible and the next run retries it.

State lives in ~/.marketplace_portal/: published.log (append-only, one line per
publish) and builds/ (one HTML plus a .json sidecar per build).
"""
import datetime as dt
import glob
import json
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent
STATE = pathlib.Path.home() / ".marketplace_portal"
LOG = STATE / "published.log"
BUILDS = STATE / "builds"

# Each carrier table and the column recording when a row was loaded.
TABLES = [
    ("stamps", "americanflat.finance.stamps_shipping_costs", "ingested_at"),
    ("fedex", "americanflat.finance.fedex_shipping_costs", "loaded_at"),
    ("ups", "americanflat.finance.ups_shipping_costs", "loaded_at"),
]

# A build below these is treated as broken and not published.
MIN_PRICED_SHARE = 0.85
MAX_SHIPMENT_DROP = 0.10


def _use_certifi():
    # python.org builds on macOS ship without system CA certificates.
    if not os.environ.get("SSL_CERT_FILE"):
        try:
            import certifi
            os.environ["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            pass


def fingerprint():
    """Row count and latest load time of each carrier table."""
    _use_certifi()
    sys.path.insert(0, str(REPO))
    import refresh_marketplace_shipments as mps
    token = mps.access_token("auto")
    sql = " UNION ALL ".join(
        "SELECT '%s' AS t, COUNT(*) AS n, CAST(MAX(%s) AS STRING) AS last_load FROM `%s`"
        % (name, col, table) for name, table, col in TABLES)
    rows = mps.query(sql, token)
    return {r["t"]: "%s@%s" % (r["n"], r["last_load"]) for r in rows}


def last_published():
    if not LOG.is_file():
        return None
    lines = [l for l in LOG.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


def cmd_check():
    try:
        now = fingerprint()
    except BaseException as err:  # mps calls sys.exit on BigQuery errors
        print("CHECK FAILED — %s; refreshing anyway" % err)
        return 2
    prev = last_published()
    if prev is None:
        print("REFRESH — nothing recorded as published yet")
        return 0
    changed = [t for t in now if now[t] != prev["fingerprint"].get(t)]
    if not changed:
        print("SKIP — no new invoices since %s" % prev["published_at"])
        return 1
    print("REFRESH — new invoice rows in: %s (%s)" % (
        ", ".join(changed),
        "; ".join("%s %s -> %s" % (t, prev["fingerprint"].get(t), now[t]) for t in changed)))
    return 0


def newest_charges_snapshot():
    # Dated snapshots sort by the date in the name; fall back to the undated one.
    dated = sorted(glob.glob(str(REPO / "data" / "parcel_charges_????-??-??.ndjson.gz")))
    return dated[-1] if dated else str(REPO / "data" / "parcel_charges.ndjson.gz")


def cmd_build():
    _use_certifi()
    try:
        fp = fingerprint()  # taken before the build, so a load mid-build is caught next run
    except BaseException as err:
        print("FAILED fingerprint — %s" % err)
        return 1
    BUILDS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = BUILDS / ("mps_%s.html" % stamp)
    if out.exists():
        print("FAILED — %s already exists; not overwriting" % out)
        return 1
    charges = newest_charges_snapshot()
    cmd = [sys.executable, str(REPO / "refresh_marketplace_shipments.py"),
           "--out", str(out), "--stamps-table", "--fedex-table", "--ups-table",
           "--charges", charges]
    try:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                              timeout=int(os.environ.get("MPS_BUILD_TIMEOUT", "600")))
    except subprocess.TimeoutExpired:
        print("FAILED refresh_marketplace_shipments.py — timed out")
        return 1
    log = proc.stderr
    if proc.returncode != 0:
        print("FAILED refresh_marketplace_shipments.py (exit %d)\n%s"
              % (proc.returncode, log[-2000:]))
        return 1

    m = re.search(r"(\d+) of (\d+) shipments priced, \$([\d,.]+)(?:, \$([\d.]+) per unit)?", log)
    if not m:
        print("FAILED — could not read the build summary\n%s" % log[-2000:])
        return 1
    priced, shipments = int(m.group(1)), int(m.group(2))
    summary = {"shipments": shipments, "priced": priced,
               "cost": m.group(3), "per_unit": m.group(4)}

    problems = []
    if priced < MIN_PRICED_SHARE * shipments:
        problems.append("only %d%% of shipments priced" % round(100 * priced / shipments))
    prev = last_published()
    if prev and prev.get("shipments") and shipments < (1 - MAX_SHIPMENT_DROP) * prev["shipments"]:
        problems.append("shipments fell from %d to %d" % (prev["shipments"], shipments))
    if problems:
        print("FAILED sanity check — %s. Built %s but do not publish it.\n%s"
              % ("; ".join(problems), out, log[-1500:]))
        return 1

    sidecar = out.with_suffix(".json")
    sidecar.write_text(json.dumps({"fingerprint": fp, "charges": charges, **summary}, indent=1))
    print(log.strip())
    print("BUILT %s" % out)
    return 0


def cmd_mark_published(path):
    html = pathlib.Path(path)
    sidecar = html.with_suffix(".json")
    if not html.is_file() or not sidecar.is_file():
        print("FAILED — %s or its .json sidecar is missing" % html)
        return 1
    info = json.loads(sidecar.read_text())
    entry = {"published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
             "file": str(html), **info}
    STATE.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as fh:  # append-only: the log is the publish history
        fh.write(json.dumps(entry) + "\n")
    print("recorded %s as published (%d shipments) -> %s"
          % (html.name, info["shipments"], LOG))
    return 0


def main(argv):
    if len(argv) >= 1 and argv[0] == "check":
        return cmd_check()
    if len(argv) >= 1 and argv[0] == "build":
        return cmd_build()
    if len(argv) == 2 and argv[0] == "mark-published":
        return cmd_mark_published(argv[1])
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
