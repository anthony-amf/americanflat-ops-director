#!/usr/bin/env python3
"""Migrate the Slack 'Ops Projects' list export (CSV) into the Ops Projects Airtable base.

Usage:
    python3 migrate_slack_to_airtable.py <slack_export.csv> [--dry-run]

The Slack list export has columns:
    Name, Notes, Status, Date, "Last updated", People, Notes(2), Priority, Message

Cleaning rules:
  - blank Name rows are dropped
  - exact duplicate names are merged (latest 'Last updated' wins, owners unioned)
  - Status:   Completed -> Completed, In progress -> In Progress,
              Not yet started -> Not Started, blank -> Needs Review (for triage)
  - Priority: Top -> Top, Mid -> Mid, Last / "Low of the Low" -> Low,
              Ad Hoc -> Ad Hoc, Unassigned/blank -> (none)
  - People:   emails mapped to first names; unresolved Slack user IDs dropped
  - Category: keyword-based auto-categorization (first match wins)

Requests to api.airtable.com are authenticated transparently by the agent proxy.
"""
import csv
import html
import io
import json
import re
import sys
import urllib.request
from datetime import datetime

BASE_ID = "appaFuK87Xk9Nn5vR"
TABLE = "Projects"
API = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"

STATUS_MAP = {
    "completed": "Completed",
    "in progress": "In Progress",
    "not yet started": "Not Started",
    "": "Needs Review",
}

PRIORITY_MAP = {
    "top": "Top",
    "mid": "Mid",
    "last": "Low",
    "low of the low": "Low",
    "ad hoc": "Ad Hoc",
    "unassigned": None,
    "": None,
}

OWNER_MAP = {
    "anthony@americanflat.com": "Anthony",
    "kent@americanflat.com": "Kent",
    "jasmine@americanflat.com": "Jasmine",
    "jnunez@americanflat.com": "John N.",
    "maria.c@americanflat.com": "Maria C.",
    "bartolome@americanflat.com": "Bart",
    "mahjoub@americanflat.com": "Mahjoub",
    "ivan@americanflat.com": "Ivan",
    "carlosdubon@americanflat.com": "Carlos D.",
    "carlos@americanflat.com": "Carlos T.",
    "carolina.d@americanflat.com": "Carolina",
    "olivier@americanflat.com": "Olivier",
    "nica@americanflat.com": "Nica",
    "raja@americanflat.com": "Raja",
    "angela@americanflat.com": "Angela",
    "johnny@americanflat.com": "Johnny",
    "dorien@americanflat.com": "Dorien",
    "romancia@americanflat.com": "Romancia",
    "paul@surpass.biz": "Paul T. (Surpass)",
}

# First matching group wins. Keep rules coarse — the team can recategorize in Airtable.
CATEGORY_RULES = [
    ("AI & Data", r"\b(ai|claude|gpt|gemini|token|bigquery|bit query|pipeline|dashboard|power ?bi|data|agent|app scripts|automat)\b"),
    ("Shipping & Carriers", r"\b(fedex|ups|usps|endicia|stamps|shipping|carrier|wwl|agl|transit|post office|veeqo|lazer ship|drayage|tracking)\b"),
    ("Marketplaces & EDI", r"\b(amazon|amz|vc|vendor central|walmart|target|wayfair|kohls?|overstock|edi|stedi|asn|846|940|945|997|832|943|850|855|wfs|fba|awd|chargebacks?|oversolds?|gtin|asin|split po|marketplace|shopify|df|seller ?central|getida|acenda|castlegate|ebay)\b"),
    ("3PL & Warehouses", r"\b(wh|warehouse|yusen|taylored|3pl|fontana|netherlands|nl|japan|australia|aus|canada|inventory|consolidat|disposal|relabel|storage|o'?neill|plus ?haven|luminous|surpass|sku|case pack|receiving|inbound|container|customs|tariff|btr|dims)\b"),
    ("Finance & Billing", r"\b(billing|invoice|rebill|re-bill|refund|credit|payment|quickbooks?|qb|sales tax|statement|collateral|price ?disputes?|savings|\$|finance|p&l|payroll|rates?)\b"),
    ("People & HR", r"\b(hr|pto|recruit|job description|succession|onboarding|retention|attendance|enrollment|holiday coverage|position|hire|controller|demand planning)\b"),
    ("Lean & Culture", r"\b(3s|gemba|lean|kaizen|morning meeting|newsletter|badges?|book|improvement|culture|university)\b"),
    ("IT & Systems", r"\b(slack|notion|1 ?password|saas|linkedin|internet|remote desktop|sftp|mit|zapier|phones?|it|equipment|okr|meeting|calendar|glossary|sop)\b"),
]


def parse_last_updated(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s.split(",")[0].strip(), "%m/%d/%y").date().isoformat()
    except ValueError:
        return None


def parse_target_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def map_owners(people):
    out = []
    for tok in re.split(r"[,\s]+", (people or "").strip()):
        tok = tok.strip()
        if not tok:
            continue
        name = OWNER_MAP.get(tok.lower())
        if name and name not in out:
            out.append(name)
    return out


def categorize(name, notes):
    text = f"{name} {notes}".lower()
    for cat, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return cat
    return "Other"


def clean_rows(path):
    with open(path, encoding="utf-8") as f:
        text = html.unescape(f.read())
    rows = list(csv.reader(io.StringIO(text)))
    header, rows = rows[0], rows[1:]

    projects = {}
    dropped = 0
    for r in rows:
        name, notes, status, date, last_upd, people, notes2, priority, message = (r + [""] * 9)[:9]
        name = re.sub(r"\s*\n\s*", " — ", name.strip())
        if not name:
            dropped += 1
            continue

        rec = {
            "Project": name,
            "Status": STATUS_MAP.get(status.strip().lower(), "Needs Review"),
            "Notes": notes.strip() or None,
            "Latest Update": notes2.strip() or None,
            "Last Discussed": parse_last_updated(last_upd),
            "Target Date": parse_target_date(date),
            "Owners": map_owners(people),
            "Category": categorize(name, f"{notes} {notes2}"),
            "Slack Link": message.strip() if message.strip().startswith("http") else None,
        }
        pri = PRIORITY_MAP.get(priority.strip().lower())
        if pri:
            rec["Priority"] = pri

        key = name.lower()
        if key in projects:
            old = projects[key]
            newer = rec if (rec["Last Discussed"] or "") >= (old["Last Discussed"] or "") else old
            older = old if newer is rec else rec
            merged = {k: (newer.get(k) or older.get(k)) for k in set(newer) | set(older)}
            merged["Owners"] = list(dict.fromkeys((newer.get("Owners") or []) + (older.get("Owners") or [])))
            projects[key] = merged
        else:
            projects[key] = rec

    records = [{k: v for k, v in p.items() if v not in (None, [], "")} for p in projects.values()]
    return records, dropped, len(rows)


def upload(records):
    created = 0
    for i in range(0, len(records), 10):
        batch = records[i:i + 10]
        body = json.dumps({"records": [{"fields": r} for r in batch], "typecast": True}).encode()
        req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            created += len(json.loads(resp.read())["records"])
        print(f"  uploaded {created}/{len(records)}", end="\r")
    print()
    return created


if __name__ == "__main__":
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv
    records, dropped, total = clean_rows(path)

    by_status, by_cat = {}, {}
    for r in records:
        by_status[r.get("Status")] = by_status.get(r.get("Status"), 0) + 1
        by_cat[r.get("Category")] = by_cat.get(r.get("Category"), 0) + 1
    print(f"source rows: {total}  |  blank dropped: {dropped}  |  merged dupes: {total - dropped - len(records)}")
    print(f"projects to load: {len(records)}")
    print("by status:", json.dumps(by_status, indent=2))
    print("by category:", json.dumps(by_cat, indent=2))

    if dry:
        print("(dry run — nothing uploaded)")
    else:
        n = upload(records)
        print(f"created {n} records in Airtable base {BASE_ID}")
