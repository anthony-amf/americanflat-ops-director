#!/usr/bin/env python3
"""Load a Yusen Canada inventory CSV into BigQuery.

Transforms the 10-column daily inventory CSV into the 4-column
americanflat.Demand_Planning.Warehouse_Inventory format
(Warehouse='Yusen CA', sku, quantity=On Hand Qty, date=run timestamp),
deletes any existing same-day 'Yusen CA' rows (dedupe for re-runs),
submits a load job, polls to completion, and verifies row count + qty sum.

Auth: service-account JWT (RS256 via openssl) -> OAuth token. Stdlib only.

Usage:
    python3 bq_load.py /path/to/canada_inventory_YYYY-MM-DD.csv
    python3 bq_load.py --dry-run /path/to/csv     # build JWT + payload, no network

Exit codes: 0 = loaded + verified, 1 = failure (message on stderr).
"""
import base64
import binascii
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROJECT = "americanflat"
DATASET = "Demand_Planning"
TABLE = "Warehouse_Inventory"
WAREHOUSE_LABEL = "Yusen CA"
# The service-account key is never stored in this skill. Supply it at run time
# as CANADA_INVENTORY_SA_KEY (base64-encoded service-account JSON), or point
# CANADA_INVENTORY_SA_FILE at a key file outside the repo.
SA_KEY_ENV = "CANADA_INVENTORY_SA_KEY"
SA_FILE_ENV = "CANADA_INVENTORY_SA_FILE"
TOKEN_URL = "https://oauth2.googleapis.com/token"
BQ = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}"
BQ_UPLOAD = f"https://bigquery.googleapis.com/upload/bigquery/v2/projects/{PROJECT}/jobs?uploadType=multipart"


def b64url(b):
    if isinstance(b, str):
        b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def load_service_account():
    """Load the service-account key from the environment.

    Prefers CANADA_INVENTORY_SA_KEY (base64 JSON) and falls back to
    CANADA_INVENTORY_SA_FILE (path to a key file kept outside the repo).
    """
    raw = os.environ.get(SA_KEY_ENV)
    if raw:
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            sys.exit(f"{SA_KEY_ENV} is set but is not valid base64")
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            sys.exit(f"{SA_KEY_ENV} did not decode to valid JSON")

    path = os.environ.get(SA_FILE_ENV)
    if path:
        try:
            with open(path) as f:
                return json.load(f)
        except OSError as e:
            sys.exit(f"{SA_FILE_ENV}={path} could not be read: {e}")
        except json.JSONDecodeError:
            sys.exit(f"{SA_FILE_ENV}={path} is not valid JSON")

    sys.exit(
        f"No credentials found. Set {SA_KEY_ENV} to the base64-encoded "
        f"service-account JSON, or {SA_FILE_ENV} to a key file path."
    )


def make_jwt(sa):
    """RS256-sign a service-account JWT using openssl (no external deps)."""
    now = int(time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}))
    payload = b64url(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/bigquery",
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }))
    signing_input = f"{header}.{payload}".encode()
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(sa["private_key"])
        pem = f.name
    try:
        sig = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", pem],
            input=signing_input, capture_output=True, check=True,
        ).stdout
    finally:
        os.unlink(pem)
    return f"{signing_input.decode()}.{b64url(sig)}"


def http_json(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {body}") from e


def get_token(sa):
    body = (
        "grant_type=" + urllib.parse.quote("urn:ietf:params:oauth:grant-type:jwt-bearer")
        + "&assertion=" + make_jwt(sa)
    ).encode()
    d = http_json(TOKEN_URL, data=body,
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    if "access_token" not in d:
        raise RuntimeError(f"Token exchange failed: {json.dumps(d)[:300]}")
    return d["access_token"]


def build_payload(csv_path):
    """10-col inventory CSV -> (4-col no-header CSV bytes, row_count, qty_sum)."""
    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))[1:]  # skip header
    if not rows:
        raise RuntimeError(f"No data rows in {csv_path}")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    total = 0
    for r in rows:
        q = int(float(r[5] or 0))  # On Hand Qty
        total += q
        w.writerow([WAREHOUSE_LABEL, r[1], q, ts])  # r[1] = Item
    return out.getvalue().encode(), len(rows), total


def run_query(token, sql):
    d = http_json(
        f"{BQ}/queries",
        data=json.dumps({"query": sql, "useLegacySql": False}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    if d.get("errors"):
        raise RuntimeError(f"Query failed: {json.dumps(d['errors'])[:300]}")
    return d


def load(token, payload):
    meta = json.dumps({"configuration": {"load": {
        "destinationTable": {"projectId": PROJECT, "datasetId": DATASET, "tableId": TABLE},
        "sourceFormat": "CSV", "writeDisposition": "WRITE_APPEND",
        "skipLeadingRows": 0, "fieldDelimiter": ",",
    }}})
    boundary = "bq_boundary_7391"
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
        f"--{boundary}\r\nContent-Type: text/csv\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--".encode()
    d = http_json(BQ_UPLOAD, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    })
    job_id = d["jobReference"]["jobId"]
    for _ in range(30):
        j = http_json(f"{BQ}/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        status = j.get("status", {})
        if status.get("state") == "DONE":
            if status.get("errorResult"):
                raise RuntimeError(f"Load job failed: {json.dumps(status.get('errors'))[:400]}")
            stats = j.get("statistics", {}).get("load", {})
            return int(stats.get("outputRows", 0)), int(stats.get("badRecords", 0))
        time.sleep(2)
    raise RuntimeError(f"Load job {job_id} did not finish within 60s")


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        sys.exit("Usage: bq_load.py [--dry-run] /path/to/canada_inventory_YYYY-MM-DD.csv")
    csv_path = args[0]

    sa = load_service_account()

    payload, n_rows, qty_sum = build_payload(csv_path)
    print(f"Payload: {n_rows} rows, total on-hand {qty_sum}, {len(payload)} bytes")

    if dry:
        jwt = make_jwt(sa)
        print(f"DRY RUN ok — JWT built ({len(jwt)} chars), no network calls made")
        return

    token = get_token(sa)
    print("Authenticated")

    run_query(token, f"DELETE FROM `{PROJECT}.{DATASET}.{TABLE}` "
                     f"WHERE Warehouse='{WAREHOUSE_LABEL}' AND DATE(date)=CURRENT_DATE()")
    print("Dedupe: cleared any existing same-day rows")

    out_rows, bad = load(token, payload)
    if out_rows != n_rows or bad:
        sys.exit(f"FAIL: loaded {out_rows} rows ({bad} bad), expected {n_rows}")
    print(f"Loaded {out_rows} rows, 0 bad records")

    v = run_query(token, f"SELECT COUNT(*), SUM(quantity) FROM `{PROJECT}.{DATASET}.{TABLE}` "
                         f"WHERE Warehouse='{WAREHOUSE_LABEL}' AND DATE(date)=CURRENT_DATE()")
    c, q = (int(x["v"]) for x in v["rows"][0]["f"])
    if c != n_rows or q != qty_sum:
        sys.exit(f"FAIL verification: table has {c} rows / {q} qty, expected {n_rows} / {qty_sum}")
    print(f"Verified in BigQuery: {c} rows, {q} total on-hand units")


if __name__ == "__main__":
    main()
