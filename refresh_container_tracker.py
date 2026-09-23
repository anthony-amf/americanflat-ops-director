#!/usr/bin/env python3
"""Build the Inbound Containers page: what is booked, what is on the water,
which ports it moves through, and what is inside each container.

Three sources, joined on container number, shipment ref and PO:

  1. WWL forwarder emails (Booking Advice / Sailing Advice / Arrival Notice),
     extracted to JSON by a Claude session via the Gmail connector — see
     CONTAINER-TRACKER.md for the extraction prompt and the record shape.
     These are the only source of departure dates, vessels and ports, and the
     only record of a container that has been booked but has not sailed.
  2. "AMF Container Tracker Tool" Google Sheet, tab "data from PL" — the
     packing-list lines: SKU, PO, container, units, cartons, date to hit the
     warehouse, status, delivery location. Download it as .xlsx.
  3. BigQuery MIT_backup.work_in_progress_tab (optional) — PO order lines, used
     only to show *planned* contents for a booking that has no packing list yet.
     This table is a partial backup (it skips many POs), so a booking often has
     no planned lines at all; the page says so rather than guessing.

A booking has no container numbers until it sails, so a not-yet-sailed row is
one per booking (shipment ref), carrying the container count ("4X40HQ") and
POs. Once a Sailing Advice or Arrival Notice names the containers, the booking
splits into one row per container.

Usage:
    python3 refresh_container_tracker.py --emails wwl_emails.json \\
        --tracker tracker.xlsx --out inbound_containers.html [--wip-bq]
"""

import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

PROJECT = "americanflat"
BQ = "https://bigquery.googleapis.com/bigquery/v2"

# Received containers stay on the page this long after they hit the warehouse,
# so a SKU search still finds the container that just landed.
RECEIVED_KEEP_DAYS = 45

# A booking whose ETD passed this many days ago with no Sailing Advice is
# flagged: either it sailed and nobody sent the advice, or it was rolled.
SAIL_GRACE_DAYS = 3

CNTR_RE = re.compile(r"^[A-Z]{4}\d{7}$")


def norm_cntr(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def po_base(po):
    """'10221-2' -> '10221'; 9792.0 -> '9792'. The -N suffix is the split
    shipment of one PO; the order lines are keyed by the base number."""
    s = str(po or "").strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s.split("-")[0].strip()


def po_str(po):
    s = str(po or "").strip()
    return s[:-2] if re.fullmatch(r"\d+\.0", s) else s


def to_int(v):
    """Sheet numbers arrive as floats, or as text with a space or comma for
    the thousands ('1 036')."""
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    s = re.sub(r"[\s,\u00a0]", "", str(v))
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def iso(d):
    if d is None or d == "":
        return None
    if isinstance(d, dt.datetime):
        return d.date().isoformat()
    if isinstance(d, dt.date):
        return d.isoformat()
    s = str(d)[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
def load_tracker(path):
    import openpyxl  # only needed here; keep the import local
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["data from PL"]
    it = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(it)]
    col = {h: i for i, h in enumerate(header)}
    need = ["SKU", "PO", "Container", "Units", "Cartons",
            "Approx Date to Hit WH", "Status", "Delivery Location"]
    missing = [h for h in need if h not in col]
    if missing:
        sys.exit(f"tracker tab 'data from PL' is missing columns: {missing}")
    lines = []
    for r in it:
        sku = str(r[col["SKU"]] or "").strip()
        cntr = norm_cntr(r[col["Container"]])
        if not sku or not cntr:
            continue
        lines.append({
            "sku": sku,
            "po": po_str(r[col["PO"]]),
            "container": cntr,
            "units": to_int(r[col["Units"]]),
            "cartons": to_int(r[col["Cartons"]]),
            "wh_date": iso(r[col["Approx Date to Hit WH"]]),
            "status": str(r[col["Status"]] or "").strip(),
            "location": str(r[col["Delivery Location"]] or "").strip(),
        })
    return lines


def load_emails(path):
    recs = json.load(open(path))
    for r in recs:
        r["containers"] = [c for c in (norm_cntr(x) for x in r.get("containers") or [])
                           if CNTR_RE.match(c)]
        r["pos"] = [po_str(p) for p in r.get("pos") or [] if str(p).strip()]
        r["ref"] = (r.get("ref") or r.get("hbl") or "").strip().upper()
    return [r for r in recs if r["ref"] or r["containers"]]


def access_token(mode):
    """None when the cloud agent proxy injects BigQuery credentials; the gcloud
    ADC token on the Mac."""
    if mode == "proxy":
        return None
    if mode == "gcloud" or (mode == "auto" and not os.environ.get("HTTPS_PROXY")):
        if not shutil.which("gcloud"):
            sys.exit("gcloud not found — run with --auth proxy inside a cloud session.")
        return subprocess.run(["gcloud", "auth", "print-access-token"],
                              capture_output=True, text=True, check=True).stdout.strip()
    return None


def bq_rows(sql, token):
    req = urllib.request.Request(
        f"{BQ}/projects/{PROJECT}/queries",
        data=json.dumps({"query": sql, "useLegacySql": False,
                         "maxResults": 100000, "timeoutMs": 120000}).encode(),
        headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=300) as resp:
        d = json.load(resp)
    names = [f["name"] for f in d["schema"]["fields"]]
    return [dict(zip(names, (c["v"] for c in r["f"]))) for r in d.get("rows", [])]


def load_wip(pos, token):
    """Planned order lines for the given base PO numbers."""
    nums = sorted({int(p) for p in pos if p.isdigit()})
    if not nums:
        return {}
    sql = f"""
      SELECT CAST(PO_clean_ AS STRING) po, SKU sku, SUM(QTY) units,
             ANY_VALUE(Delivery_location) location
      FROM `{PROJECT}.MIT_backup.work_in_progress_tab`
      WHERE PO_clean_ IN ({",".join(map(str, nums))}) AND SKU IS NOT NULL
      GROUP BY 1, 2"""
    out = collections.defaultdict(list)
    for r in bq_rows(sql, token):
        out[r["po"]].append({"sku": r["sku"], "units": int(float(r["units"] or 0)),
                             "location": r["location"]})
    return out


# --------------------------------------------------------------------------
# Join
# --------------------------------------------------------------------------
RANK = {"booking": 0, "sailing": 1, "arrival": 2}


def merge_refs(emails):
    """Collapse every email about one shipment ref into one shipment record.
    Later stages win for dates (an Arrival Notice ETA beats the Booking Advice
    guess); within a stage the newer email wins (a revised schedule)."""
    by_ref = collections.defaultdict(list)
    for r in emails:
        by_ref[r["ref"] or "+".join(r["containers"])].append(r)
    ships = {}
    for ref, rs in by_ref.items():
        rs.sort(key=lambda r: (RANK.get(r.get("type"), 0), r.get("email_date") or ""))
        s = {"ref": ref, "containers": [], "pos": [], "stages": set(), "sources": []}
        for r in rs:
            s["stages"].add(r.get("type"))
            s["sources"].append({"type": r.get("type"), "date": r.get("email_date"),
                                 "subject": r.get("subject")})
            for c in r["containers"]:
                if c not in s["containers"]:
                    s["containers"].append(c)
            for p in r["pos"]:
                if p not in s["pos"]:
                    s["pos"].append(p)
            for k in ("shipper", "carrier", "vessel", "pol", "pod", "final_dest",
                      "container_count_desc", "hbl", "mbl"):
                if r.get(k):
                    s[k] = r[k]
            for k in ("etd", "eta_pod", "eta_final"):
                if r.get(k):
                    s[k] = r[k]
            if r.get("etd") and r.get("etd_is_actual"):
                s["etd_actual"] = True
            if r.get("notes"):
                s.setdefault("notes", []).append(r["notes"])
        s["sailed"] = bool(s["stages"] & {"sailing", "arrival"}) or s.get("etd_actual", False)
        ships[ref] = s
    return ships


def build(emails, lines, wip, today):
    ships = merge_refs(emails)

    pl_by_cntr = collections.defaultdict(list)
    for ln in lines:
        pl_by_cntr[ln["container"]].append(ln)

    cntr_to_ref = {}
    for s in ships.values():
        for c in s["containers"]:
            cntr_to_ref[c] = s["ref"]

    # A packing-list container that no email names: attach it to the shipment
    # whose POs it shares, but only when exactly one shipment claims those POs
    # (one PO split across two bookings would otherwise be a coin toss).
    po_to_refs = collections.defaultdict(set)
    for s in ships.values():
        for p in s["pos"]:
            po_to_refs[p].add(s["ref"])
    for c, lns in pl_by_cntr.items():
        if c in cntr_to_ref:
            continue
        refs = set()
        for ln in lns:
            refs |= po_to_refs.get(ln["po"], set())
        if len(refs) == 1:
            ref = refs.pop()
            cntr_to_ref[c] = ref
            ships[ref]["containers"].append(c)
            ships[ref]["sailed"] = True  # packed into a named box: it has left the factory

    rows = []

    def shipment_fields(s):
        return {
            "ref": s["ref"], "shipper": s.get("shipper"), "carrier": s.get("carrier"),
            "vessel": s.get("vessel"), "pol": s.get("pol"), "etd": s.get("etd"),
            "etdActual": bool(s.get("etd_actual")), "pod": s.get("pod"),
            "etaPod": s.get("eta_pod"), "fdest": s.get("final_dest"),
            "etaFinal": s.get("eta_final"), "hbl": s.get("hbl"), "mbl": s.get("mbl"),
            "sources": s["sources"], "notes": s.get("notes") or [],
        }

    def status_for(pl_status, sailed, etd, eta, wh_date):
        if pl_status == "Received":
            return "received"
        if not sailed:
            if etd and etd < (today - dt.timedelta(days=SAIL_GRACE_DAYS)).isoformat():
                return "overdue"
            return "booked"
        # With no forwarder ETA, the sheet's warehouse date stands in: a box
        # whose warehouse date has passed has at least reached the port.
        landed = eta or wh_date
        if landed and landed <= today.isoformat():
            return "port"
        return "water"

    # One row per container we can name.
    for c in sorted(set(pl_by_cntr) | set(cntr_to_ref)):
        lns = pl_by_cntr.get(c, [])
        s = ships.get(cntr_to_ref.get(c))
        pl_status = "Received" if lns and all(l["status"] == "Received" for l in lns) else \
            ("In Transit" if lns else None)
        wh_date = max((l["wh_date"] for l in lns if l["wh_date"]), default=None)
        location = collections.Counter(l["location"] for l in lns).most_common(1)[0][0] if lns else None
        sailed = True if (lns or (s and s["sailed"])) else False
        st = status_for(pl_status, sailed, s and s.get("etd"), s and s.get("eta_pod"), wh_date)
        if st == "received" and wh_date and wh_date < (today - dt.timedelta(days=RECEIVED_KEEP_DAYS)).isoformat():
            continue
        row = {"id": c, "kind": "container", "container": c, "status": st,
               "location": location, "whDate": wh_date,
               "pos": sorted({l["po"] for l in lns} | set(s["pos"] if s else []), key=str),
               "lines": [[l["sku"], l["po"], l["units"], l["cartons"]] for l in lns],
               "linesSource": "packing" if lns else None,
               "units": sum(l["units"] for l in lns), "cartons": sum(l["cartons"] for l in lns)}
        row.update(shipment_fields(s) if s else {"ref": None, "sources": [], "notes": []})
        rows.append(row)

    # One row per booking that has not named its containers yet.
    for s in ships.values():
        if s["containers"]:
            continue
        planned = []
        loc = collections.Counter()
        for p in s["pos"]:
            for w in wip.get(po_base(p), []):
                planned.append([w["sku"], p, w["units"], None])
                if w.get("location"):
                    loc[w["location"]] += 1
        st = status_for(None, s["sailed"], s.get("etd"), s.get("eta_pod"), None)
        row = {"id": s["ref"], "kind": "booking", "container": None, "status": st,
               "cntrDesc": s.get("container_count_desc"),
               "location": loc.most_common(1)[0][0] if loc else None, "whDate": None,
               "pos": s["pos"], "lines": planned,
               "linesSource": "po" if planned else None,
               "units": sum(l[2] for l in planned), "cartons": None}
        row.update(shipment_fields(s))
        rows.append(row)

    order = {"overdue": 0, "booked": 1, "water": 2, "port": 3, "received": 4}
    rows.sort(key=lambda r: (order[r["status"]], r.get("etd") or r.get("etaPod") or r.get("whDate") or "9999", r["id"]))
    return rows


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def render(rows, built, template_path):
    counts = collections.Counter(r["status"] for r in rows)
    kpi = {
        "built": built,
        "booked": sum(1 for r in rows if r["status"] in ("booked", "overdue")),
        "overdue": counts["overdue"],
        "water": counts["water"],
        "port": counts["port"],
        "received": counts["received"],
        "receivedDays": RECEIVED_KEEP_DAYS,
        "unitsInbound": sum(r["units"] or 0 for r in rows if r["status"] in ("water", "port")),
    }
    tpl = open(template_path, encoding="utf-8").read()
    data = json.dumps(rows, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return tpl.replace("/*DATA*/[]", data).replace("/*KPI*/{}", json.dumps(kpi))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emails", required=True, help="WWL email extraction JSON")
    ap.add_argument("--tracker", required=True, help="Container Tracker sheet as .xlsx")
    ap.add_argument("--out", default="inbound_containers.html")
    ap.add_argument("--template", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                       "container_tracker_template.html"))
    ap.add_argument("--wip-bq", action="store_true",
                    help="look up planned PO lines in BigQuery for unpacked bookings")
    ap.add_argument("--auth", choices=["auto", "proxy", "gcloud"], default="auto")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    emails = load_emails(args.emails)
    lines = load_tracker(args.tracker)

    wip = {}
    if args.wip_bq:
        booking_pos = {po_base(p) for r in emails for p in r["pos"]}
        wip = load_wip(booking_pos, access_token(args.auth))

    rows = build(emails, lines, wip, today)
    from zoneinfo import ZoneInfo
    built = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%b %-d, %Y %-I:%M %p ET")
    html = render(rows, built, args.template)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    c = collections.Counter(r["status"] for r in rows)
    print(f"wrote {args.out}: {len(rows)} rows " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))


if __name__ == "__main__":
    main()
