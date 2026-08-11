#!/usr/bin/env python3
"""
Read-only BigQuery access that works both on the Mac and in a cloud session.

On the Mac it uses google-cloud-bigquery with gcloud ADC. In a Claude cloud
session there are no local credentials, but the agent proxy signs requests to
bigquery.googleapis.com, so the plain REST API works over https. This module
picks whichever path is available.

Reads only. Writes (the weekly load) run from the Mac — see
scripts/load_shipping_orders_to_bq.py.

Because the two paths return values differently (the REST API hands back
everything as strings, and timestamps as epoch seconds), queries used with this
module should return only STRING / INT64 / FLOAT64 / BOOL columns: wrap dates
and timestamps in FORMAT_DATE / FORMAT_TIMESTAMP and cast NUMERIC to FLOAT64.
"""

import json
import urllib.error
import urllib.request

PROJECT = "americanflat"
_API = "https://bigquery.googleapis.com/bigquery/v2"


def query(sql: str, project: str = PROJECT) -> list[dict]:
    """Run a SELECT and return a list of dicts."""
    client = _try_client(project)
    if client is not None:
        return [dict(row) for row in client.query(sql).result()]
    return _query_rest(sql, project)


def _try_client(project: str):
    """Return a bigquery.Client, or None when no local credentials exist."""
    try:
        from google.cloud import bigquery
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        return None
    try:
        return bigquery.Client(project=project)
    except DefaultCredentialsError:
        return None


# ── REST path (cloud sessions) ─────────────────────────────────────────────


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"BigQuery REST call failed ({exc.code}): {exc.read().decode()[:1000]}"
        ) from exc


def _get(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=180) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"BigQuery REST call failed ({exc.code}): {exc.read().decode()[:1000]}"
        ) from exc


def _query_rest(sql: str, project: str) -> list[dict]:
    body = {
        "query": sql,
        "useLegacySql": False,
        "timeoutMs": 120000,
        "maxResults": 20000,
    }
    payload = _post(f"{_API}/projects/{project}/queries", body)
    if payload.get("errors"):
        raise RuntimeError(f"BigQuery error: {payload['errors']}")

    fields = payload.get("schema", {}).get("fields", [])
    rows = list(_decode(payload.get("rows", []), fields))

    # Page through the rest of the result set.
    job = payload.get("jobReference", {})
    token = payload.get("pageToken")
    while token:
        url = (
            f"{_API}/projects/{project}/queries/{job['jobId']}"
            f"?pageToken={token}&maxResults=20000&timeoutMs=120000"
        )
        if job.get("location"):
            url += f"&location={job['location']}"
        page = _get(url)
        rows.extend(_decode(page.get("rows", []), fields))
        token = page.get("pageToken")
    return rows


_INT_TYPES = {"INTEGER", "INT64"}
_FLOAT_TYPES = {"FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC", "DECIMAL"}


def _decode(raw_rows: list, fields: list) -> list[dict]:
    out = []
    for raw in raw_rows:
        row = {}
        for field, cell in zip(fields, raw.get("f", [])):
            row[field["name"]] = _coerce(cell.get("v"), field.get("type", "STRING"))
        out.append(row)
    return out


def _coerce(value, bq_type: str):
    if value is None:
        return None
    if bq_type in _INT_TYPES:
        return int(value)
    if bq_type in _FLOAT_TYPES:
        return float(value)
    if bq_type in ("BOOLEAN", "BOOL"):
        return value == "true" or value is True
    return value
