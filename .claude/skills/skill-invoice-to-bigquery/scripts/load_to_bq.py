#!/usr/bin/env python3
"""Review and load a parsed invoice into BigQuery.

Two modes, used in sequence by the skill:

    python load_to_bq.py review <invoice.json>
        Prints the header, the line-item table, and total_amount vs the
        summed line items. Touches NOTHING in the cloud - it exists so a
        human can eyeball the numbers before anything is written.

    python load_to_bq.py load <invoice.json> [--force] [--allow-duplicate]
        Loads the invoice into BigQuery by IMPERSONATING the configured
        service account (no key files). Refuses if the totals disagree
        (override with --force) or if the invoice_id already exists
        (override with --allow-duplicate).

This script never creates datasets, tables, service accounts, or IAM
bindings. Those are the admin's job (see references/admin_setup.md). If the
operator lacks permission to impersonate the service account, the load
fails with a clear message telling them whom to ask - it cannot and will
not grant itself access.

Config resolution (later wins): config.json next to the skill, then
environment variables INVOICE_BQ_PROJECT / INVOICE_BQ_DATASET /
INVOICE_BQ_TABLE / INVOICE_BQ_SA / INVOICE_BQ_LOCATION.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SKILL_DIR / "references" / "bq_schema.json"

# Cents-level tolerance so floating point / rounding noise doesn't trip the
# totals check. A real discrepancy (a missed or doubled line) is always
# bigger than this.
TOTAL_TOLERANCE = Decimal("0.05")

# Canonical columns the model is responsible for. Everything else on the row
# is provenance the load step stamps itself.
CONTENT_FIELDS = [
    "invoice_id", "invoice_date", "vendor_name", "bill_to", "ship_to",
    "po_number", "terms", "container_number", "currency", "total_amount",
    "line_items", "source_file",
]


def resolve_exe(name: str) -> str:
    """Resolve a CLI to its full path. On Windows ``bq`` and ``gcloud`` are
    ``.cmd`` shims, which subprocess won't find by bare name; shutil.which
    honors PATHEXT and returns the real path on every platform."""
    return shutil.which(name) or name


def load_config() -> dict:
    cfg = {}
    cfg_path = SKILL_DIR / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    env_map = {
        "project_id": "INVOICE_BQ_PROJECT",
        "dataset": "INVOICE_BQ_DATASET",
        "table": "INVOICE_BQ_TABLE",
        "impersonate_service_account": "INVOICE_BQ_SA",
        "location": "INVOICE_BQ_LOCATION",
    }
    for key, env in env_map.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def check_config(cfg: dict) -> None:
    missing = [k for k in ("project_id", "dataset", "table",
                           "impersonate_service_account")
               if not cfg.get(k) or str(cfg[k]).startswith("REPLACE_WITH")]
    if missing:
        sys.exit(
            "config.json still has placeholder values for: "
            + ", ".join(missing)
            + ".\nThe admin needs to fill these in (project id, dataset, "
            "table, service-account email) before the skill can load. "
            "Nothing was written."
        )


def to_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return Decimal("0")


def summarize_totals(invoice: dict) -> dict:
    line_sum = sum((to_decimal(li.get("amount")) for li in
                    invoice.get("line_items", [])), Decimal("0"))
    stated = to_decimal(invoice.get("total_amount"))
    delta = (stated - line_sum).copy_abs()
    return {
        "stated_total": stated,
        "line_sum": line_sum,
        "delta": delta,
        "match": delta <= TOTAL_TOLERANCE,
    }


def cmd_review(invoice: dict) -> int:
    print("INVOICE REVIEW  (nothing has been written to BigQuery)")
    print("-" * 60)
    for f in ("invoice_id", "invoice_date", "vendor_name", "po_number",
              "container_number", "currency"):
        if invoice.get(f):
            print(f"  {f:18}: {invoice[f]}")
    print("\n  Line items:")
    print(f"    {'#':>2}  {'description':30} {'qty':>5} {'rate':>10} {'amount':>10}")
    for li in invoice.get("line_items", []):
        print(f"    {str(li.get('line_number','')):>2}  "
              f"{str(li.get('description',''))[:30]:30} "
              f"{str(li.get('quantity','')):>5} "
              f"{str(li.get('rate','')):>10} "
              f"{str(li.get('amount','')):>10}")
    t = summarize_totals(invoice)
    print("-" * 60)
    print(f"  Sum of line items : {t['line_sum']}")
    print(f"  Stated total      : {t['stated_total']}")
    if t["match"]:
        print(f"  -> MATCH (delta {t['delta']})")
    else:
        print(f"  -> MISMATCH (delta {t['delta']}) - needs a human decision")
    print("-" * 60)
    return 0


def gcloud_account() -> str:
    try:
        out = subprocess.run(
            [resolve_exe("gcloud"), "auth", "list", "--filter=status:ACTIVE",
             "--format=value(account)"],
            capture_output=True, text=True, timeout=30,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def is_permission_error(text: str) -> bool:
    needles = ("permission", "does not have", "iam.serviceaccounts",
               "accessnotconfigured", "forbidden", "403",
               "caller does not have", "tokencreator")
    low = text.lower()
    return any(n in low for n in needles)


def permission_help(cfg: dict, raw: str) -> None:
    sa = cfg["impersonate_service_account"]
    print("\n" + "=" * 60, file=sys.stderr)
    print("PERMISSION DENIED - nothing was written.", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        f"\nYour account does not have permission to impersonate the\n"
        f"invoice writer service account:\n\n    {sa}\n\n"
        "This skill cannot grant access - that is the admin's job. Ask the\n"
        "admin (the person who owns the BigQuery dataset) to run, for you:\n\n"
        f"  gcloud iam service-accounts add-iam-policy-binding {sa} \\\n"
        f"    --member=\"user:YOUR_EMAIL@americanflat.com\" \\\n"
        f"    --role=\"roles/iam.serviceAccountTokenCreator\"\n\n"
        "Then run `gcloud auth login` once and retry.\n", file=sys.stderr)
    print("--- raw error ---", file=sys.stderr)
    print(raw.strip()[:1500], file=sys.stderr)


def run_bq(args: list, cfg: dict) -> subprocess.CompletedProcess:
    # Impersonate via env var rather than a CLI flag: it's honored by both
    # bq and gcloud, scoped to this subprocess, and doesn't mutate the
    # operator's global gcloud config the way `gcloud config set` would.
    env = dict(os.environ)
    env["CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT"] = cfg["impersonate_service_account"]
    cmd = [resolve_exe("bq"), f"--project_id={cfg['project_id']}",
           f"--location={cfg.get('location', 'US')}"] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def duplicate_exists(cfg: dict, invoice_id: str) -> bool:
    table = f"{cfg['project_id']}.{cfg['dataset']}.{cfg['table']}"
    sql = (f"SELECT COUNT(*) AS n FROM `{table}` "
           f"WHERE invoice_id = '{invoice_id}'")
    res = run_bq(["query", "--nouse_legacy_sql", "--format=json", sql], cfg)
    if res.returncode != 0:
        if is_permission_error(res.stderr):
            permission_help(cfg, res.stderr)
            sys.exit(2)
        # A missing table or other read issue shouldn't silently pass as
        # "no duplicate" - surface it.
        sys.exit(f"Could not check for duplicates:\n{res.stderr.strip()}")
    try:
        return int(json.loads(res.stdout)[0]["n"]) > 0
    except Exception:  # noqa: BLE001
        return False


def build_row(invoice: dict, extracted_by: str) -> dict:
    row = {k: invoice.get(k) for k in CONTENT_FIELDS}
    # raw_extraction is stored as a JSON string so the load never fails on
    # nested-type quirks; query it later with PARSE_JSON(raw_extraction).
    raw = invoice.get("raw_extraction", invoice)
    row["raw_extraction"] = json.dumps(raw, ensure_ascii=False)
    row["source_gcs_uri"] = invoice.get("source_gcs_uri")
    row["extracted_by"] = extracted_by
    row["ingested_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    row["ingested_by"] = gcloud_account()
    return row


def cmd_load(invoice: dict, cfg: dict, args) -> int:
    check_config(cfg)
    if not invoice.get("invoice_id"):
        sys.exit("Invoice JSON has no invoice_id - cannot load.")

    t = summarize_totals(invoice)
    if not t["match"] and not args.force:
        sys.exit(
            f"Totals disagree: line items sum to {t['line_sum']} but the "
            f"invoice states {t['stated_total']} (delta {t['delta']}).\n"
            "Loading was stopped. Re-check the parse, fix it, or pass "
            "--force if you have confirmed the invoice itself is correct."
        )

    if duplicate_exists(cfg, invoice["invoice_id"]) and not args.allow_duplicate:
        sys.exit(
            f"Invoice {invoice['invoice_id']} is already in "
            f"{cfg['dataset']}.{cfg['table']}. Nothing was loaded. Pass "
            "--allow-duplicate only if you intend to insert it again."
        )

    row = build_row(invoice, args.extracted_by)
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        ndjson_path = fh.name

    table = f"{cfg['project_id']}:{cfg['dataset']}.{cfg['table']}"
    res = run_bq(
        ["load", "--source_format=NEWLINE_DELIMITED_JSON",
         f"--schema={SCHEMA_PATH}", table, ndjson_path], cfg)
    try:
        os.unlink(ndjson_path)
    except OSError:
        pass

    if res.returncode != 0:
        if is_permission_error(res.stderr):
            permission_help(cfg, res.stderr)
            return 2
        print(res.stderr, file=sys.stderr)
        return 1

    print(f"Loaded invoice {invoice['invoice_id']} into "
          f"{cfg['dataset']}.{cfg['table']} as {row['ingested_by']}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    p_rev = sub.add_parser("review", help="print totals comparison; no cloud access")
    p_rev.add_argument("invoice_json")

    p_load = sub.add_parser("load", help="load into BigQuery via impersonation")
    p_load.add_argument("invoice_json")
    p_load.add_argument("--force", action="store_true",
                        help="load even if totals disagree")
    p_load.add_argument("--allow-duplicate", action="store_true",
                        help="load even if invoice_id already exists")
    p_load.add_argument("--extracted-by", default="claude",
                        help="model id that parsed the PDF (provenance)")

    args = ap.parse_args()
    invoice = json.loads(Path(args.invoice_json).read_text(encoding="utf-8"))

    if args.mode == "review":
        return cmd_review(invoice)
    return cmd_load(invoice, load_config(), args)


if __name__ == "__main__":
    raise SystemExit(main())
