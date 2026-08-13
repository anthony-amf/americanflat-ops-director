#!/usr/bin/env python3
"""
Rate Card Validator for Yusen / Taylored Service freight invoices.

Validates the billed amount on an invoice against the contracted rate card.
Rates are NOT hardcoded here — they are loaded from a JSON file so the caller
can supply a fresh copy pulled live from the Notion rate card. When no rates
file is supplied, falls back to the bundled snapshot (and says so loudly).

Validation depth (intentionally header-level for now):
  - Admin   -> weekly fee, pro-rated for partial weeks (5 business days = full week)
  - Storage -> per-pallet rate x pallet count (needs line items for pallet count)
  - VAS / Small Parcel / LTL -> total reported; flagged "needs detail" because a
    real check requires itemized hours/units, which the header row doesn't carry.

Usage:
    python validate_rate_card.py 752857 --rates /tmp/rates.json
    python validate_rate_card.py 752857                 # uses bundled snapshot
    python validate_rate_card.py --list-all --rates /tmp/rates.json
    python validate_rate_card.py 752857 --rates /tmp/rates.json --json
"""

import json
import os
import re
import sys
import argparse
from datetime import date
from pathlib import Path
from typing import Any, Optional

from google.cloud import bigquery

PROJECT = "americanflat"
TABLE = "americanflat.finance.yusen_invoices"
SNAPSHOT = Path(__file__).resolve().parent.parent / "references" / "rate-card-snapshot.json"

# Maps the free-text warehouse value in BigQuery to a rate-card key.
WAREHOUSE_MAP = {
    "fontana": ["fontana", "ts west", "ca west"],
    "new_jersey": ["new jersey", "nj", "ts east"],
    # Taylored's southern DC bills as "SAVANNAH" — same facility as TS South (SC).
    "south_carolina": ["south carolina", "savannah", "ts south", "sc"],
    "canada": ["canada", "yusen ca", "ts canada"],
    "netherlands": ["netherlands", "moerdijk", "benelux", "schiphol", "yusen nl"],
}


# =====================================================================
# MSA line-level engine (v1.4.0)
#
# Flat rate table from the AMERICANFLAT Yusen MSA (draft 7.15.2026; rates
# confirmed final by Anthony 8/5/26; validity April 2026 – March 31 2027).
# Extracted from the embedded rate image (word/media/image2.emf). Update at
# contract renewal. The Notion card mirrors these; this table exists so the
# unattended sweep can verify lines without a live Notion fetch.
# =====================================================================
MSA_LINE_RATES = {  # full-precision rate -> label
    4.34: "storage NJ", 4.47: "storage CA", 3.35: "storage SC",
    1.7871: "ship carton NJ", 1.8887: "ship carton CA", 1.6422: "ship carton SC",
    2.1735: "order fee NJ", 2.1585: "order fee CA",
    2.2264: "ecom order", 0.5060: "additional ecom pick", 0.5796: "additional ecom pick SC",
    0.6532: "small parcels NJ", 0.6879: "small parcels CA", 0.84: "small parcels SC",
    0.30: "UCC/label", 6.50: "BOL", 10.00: "pallet all-in",
    0.9467: "recv carton NJ", 0.9173: "recv carton CA", 0.7728: "recv/LTL carton",
    47.334: "container admin NJ", 52.8831: "container admin CA", 47.288: "container admin SC",
    72.45: "LTL recv minimum", 43.47: "container spot/day",
    29.946: "sortation NJ", 31.2981: "sortation CA", 24.15: "sortation SC",
    2.7531: "ecom pnp carton SC", 0.7312: "storage per bin CA",
    35.0: "hourly", 42.0: "hourly", 53.55: "hourly", 59.8278: "hourly", 63.0: "hourly",
    77.70: "hourly", 82.1166: "hourly", 47.1232: "hourly", 32.0: "hourly", 40.0: "hourly",
    56.82: "hourly (returns)", 0.42: "label", 0.45: "label", 0.92: "pack carton",
    1071.0: "weekly admin NJ", 2393.11: "weekly admin CA", 1092.0: "weekly admin SC",
    5.98: "legacy storage NJ", 5.9055: "legacy storage CA", 5.0925: "legacy storage SC",
}
# Known MSA-conflict rates (consolidated dispute, 2026-08-05):
#   AF-9 — $10.00 national all-in pallet incl. stretch wrap; separate wrap or
#          a 14.317 combined pallet+wrap line is disputed.
#   AF-7 — "Per Pack Out" removed per Yusen 4/28; 0.92/0.966 billings disputed.
DISPUTED_LINE_RATES = {
    4.347: "stretchwrap (AF-9)", 4.317: "stretchwrap (AF-9)",
    14.317: "pallet+wrap (AF-9)", 14.347: "pallet+wrap (AF-9)",
    0.966: "pack-out CA (AF-7 removed)",
}
# 0.92 is both a legit VAS pack rate and the removed NJ pack-out; on SP/LTL
# invoices it is the AF-7 pack-out (disputed), on VAS it is a pack rate.

_NUM = r"[\d,]+(?:\.\d+)?"
_LINE_PATTERNS = [
    # "2346 PALLETS ON HAND ... @ 3.3500/PALLET $ 7,859.10"  (qty DESC @rate $amt)
    re.compile(r"(" + _NUM + r")\s+[A-Z][^\n@$]{0,70}@\s*\$?\s*([\d.]+)(?:/[A-Z]+)?\s*\$\s*([\d,]+\.\d{2})", re.I),
    # "RECEIVED CARTONS  876 @ 0.9173 $ 803.55"  (DESC qty @rate $amt)
    re.compile(r"(" + _NUM + r")\s*@\s*\$?\s*([\d.]+)\s*\$\s*([\d,]+\.\d{2})"),
    # page-1 columns: "STRETCHWRAP STD  121  4.34 $ 525.99"  (qty rate $amt at line end)
    re.compile(r"(" + _NUM + r")\s+(" + _NUM + r")\s+\$\s*([\d,]+\.\d{2})\s*$", re.M),
    # worksheet: "121 STRETCHWRAP STD 4.3470 525.99"  (qty DESC rate amt)
    re.compile(r"^\s*(" + _NUM + r")\s+[A-Z][A-Z /&()#-]*?\s+(" + _NUM + r")\s+([\d,]+\.\d{2})\s*$", re.M),
]

DEFAULT_PDF_DIR = Path(os.environ.get("YUSEN_PDF_CACHE", str(Path.home() / ".yusen-pdf-cache")))


def _rate_candidates(rate: float) -> list:
    """All (full_rate, label, disputed) an invoice-printed rate could mean.

    Printed rates are either full precision or truncated (not rounded) to 2dp,
    so 4.34 can be storage-NJ 4.34 or stretchwrap 4.347 — the caller picks the
    candidate whose qty x full_rate matches the printed line amount.
    """
    import math as _math
    out = []
    for table, disp in ((DISPUTED_LINE_RATES, True), (MSA_LINE_RATES, False)):
        for full, label in table.items():
            if abs(rate - full) <= 0.0006:
                out.append((full, label, disp, 0))          # printed in full
            elif abs(_math.floor(full * 100) / 100 - rate) <= 0.0011:
                out.append((full, label, disp, 1))          # truncated to 2dp
            elif abs(round(full, 2) - rate) <= 0.0011:
                out.append((full, label, disp, 2))          # rounded to 2dp
    return sorted(out, key=lambda c: c[3])


def _drive_file_id(url: str) -> Optional[str]:
    m = re.search(r"/file/d/([\w-]+)", url or "") or re.search(r"[?&]id=([\w-]+)", url or "")
    return m.group(1) if m else None


def _download_pdf(invoice_number: str, pdf_url: str, cache_dir: Path) -> Optional[Path]:
    """Fetch the invoice PDF: cache first, then Drive API (ADC), then public link.

    The Drive API path needs the ADC login to carry the drive.readonly scope:
      gcloud auth application-default login \
        --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.readonly
    Without it this quietly falls through; the sweep then degrades to the
    header-level result for rows whose PDF isn't cached.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{invoice_number}.pdf"
    if p.exists() and p.stat().st_size > 1000:
        return p
    fid = _drive_file_id(pdf_url)
    if not fid:
        return None
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
        resp = AuthorizedSession(creds).get(
            f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media&supportsAllDrives=true",
            timeout=90)
        if resp.ok and resp.content[:4] == b"%PDF":
            p.write_bytes(resp.content)
            return p
    except Exception:
        pass
    try:
        import requests
        resp = requests.get(f"https://drive.google.com/uc?export=download&id={fid}", timeout=90)
        if resp.ok and resp.content[:4] == b"%PDF":
            p.write_bytes(resp.content)
            return p
    except Exception:
        pass
    return None


def _pdf_pages_text(path: Path) -> tuple[str, int]:
    """Extract (text, page_count). Scanned PDFs (SC VAS) fall back to OCR when
    tesseract + pdftoppm are installed; otherwise the caller sees short text
    and reports needs_detail per the VAS error policy."""
    try:
        from pypdf import PdfReader
        rd = PdfReader(str(path))
        n = len(rd.pages)
        text = "\n".join((pg.extract_text() or "") for pg in rd.pages)
    except Exception:
        return "", 0
    if len(text.strip()) >= 200:
        return text, n
    import shutil as _sh, subprocess as _sp, tempfile as _tf
    if _sh.which("tesseract") and _sh.which("pdftoppm"):
        try:
            with _tf.TemporaryDirectory() as td:
                _sp.run(["pdftoppm", "-r", "200", "-l", "6", "-png", str(path), td + "/pg"],
                        timeout=180, check=False, capture_output=True)
                chunks = []
                for img in sorted(Path(td).glob("pg*.png"))[:6]:
                    r = _sp.run(["tesseract", str(img), "-", "--psm", "6"],
                                capture_output=True, text=True, timeout=90)
                    chunks.append(r.stdout)
                ocr = "\n".join(chunks)
                if len(ocr.strip()) > 100:
                    return ocr, n
        except Exception:
            pass
    return text, n


def _parse_charge_lines(text: str, amount: float, invoice_type: str) -> list:
    """Parse charge lines and verify each against the MSA table.

    Returns [{qty, rate, amt, label, disputed}] — only lines whose math
    verifies at a known rate. Page-1 + worksheet echoes are deduped."""
    t = (invoice_type or "").lower()
    found, seen = [], set()
    for pat in _LINE_PATTERNS:
        for m in pat.finditer(text):
            try:
                qty = float(m.group(1).replace(",", ""))
                rate = float(m.group(2).replace(",", ""))
                la = float(m.group(3).replace(",", ""))
            except ValueError:
                continue
            if (qty, rate, la) in seen or qty <= 0 or rate <= 0 or la > amount + 0.05:
                continue
            cands = _rate_candidates(rate)
            if not cands and _rate_candidates(qty):
                qty, rate, cands = rate, qty, _rate_candidates(qty)
            hit = None
            for full, label, disp, _prio in cands:
                if abs(qty * full - la) <= max(0.02, qty * 0.0006):
                    hit = (full, label, disp)
                    break
            if hit is None and cands and abs(qty * rate - la) <= 0.02:
                full, label, disp, _p = cands[0]
                hit = (full, label, disp)
            if hit is None and t == "vas" and rate <= 500 and \
                    abs(qty * rate - la) <= max(0.02, qty * 0.01):
                # VAS work orders quote ad-hoc job rates not on the MSA
                # schedule; self-consistent math counts as verified and the
                # documentation policy supplies the evidence requirement.
                hit = (rate, f"job rate {rate}", False)
            if hit is None:
                continue
            full, label, disp = hit
            seen.add((qty, rate, la))
            if abs(full - 0.92) < 0.001 and t.startswith("sml"):
                label, disp = "pack-out (AF-7 removed)", True
            found.append(dict(qty=qty, rate=full, amt=la, label=label, disputed=disp))
    best = {}
    for l in found:
        best[(l["qty"], l["amt"])] = l
    return list(best.values())


def _line_spec(lines: list, cap: int = 12) -> str:
    spec = "; ".join(f"{l['qty']:,.0f} x {l['rate']} {l['label']} = ${l['amt']:,.2f}"
                     for l in sorted(lines, key=lambda z: -z["amt"])[:cap])
    if len(lines) > cap:
        spec += f"; +{len(lines) - cap} more lines"
    return spec


def apply_line_pass(invoice: dict, result: dict, pdf_dir: Path) -> None:
    """Upgrade a header-level result using the invoice PDF's charge lines.

    Mutates `result` (status / variance / line_report). Settled rows (already
    valid or disputed in BigQuery) are left alone — the sweep neither
    re-downloads their PDFs nor re-stamps them."""
    t = (invoice.get("type_of_invoice") or "").strip().lower()
    if result.get("warehouse") in ("canada", "netherlands", None):
        return
    existing = (invoice.get("validation_status") or "").strip()
    prior_by = (invoice.get("validated_by") or "").strip()
    # Settled rows are skipped before the PDF is fetched — that is what keeps a
    # daily sweep cheap. Mirrors write_result's stickiness: a disputed stamp, and
    # any `valid` stamp (human-set or previously earned here), stands.
    if existing == "disputed" or existing == "valid":
        result["_settled"] = existing + (" (human-set)" if prior_by and prior_by != AUTO_WRITER else "")
        return
    amount = result["billed_amount"]
    is_vas, is_spltl = t == "vas", t.startswith("sml")

    pdf_path = _download_pdf(result["invoice_number"], invoice.get("pdf_url") or "", pdf_dir)
    if pdf_path is None:
        result["line_report"] = ("PDF unavailable (not cached; Drive fetch failed — "
                                 "check ADC drive.readonly scope). Header-level result kept.")
        return
    text, npages = _pdf_pages_text(pdf_path)
    if len((text or "").strip()) < 200:
        result["status"] = "needs_detail"
        result["line_report"] = (f"PDF has no extractable text ({npages} page(s); scanned — "
                                 "OCR unavailable or failed). Needs manual review (error policy).")
        return

    lines = _parse_charge_lines(text, amount, t)
    if not lines and is_vas:
        # OCR fallback for scanned VAS work orders: the printed line amount is
        # often mangled, but a "qty ... @ rate" pair that reconciles to the
        # invoice total is the same evidence the 2026-08-05 VAS sweep used.
        for m in re.finditer(r"([\d,]+)\s*(?:[A-Z][^\n@$]{0,60})?@\s*\$?\s*([\d.]+)", text):
            try:
                qty, rate = float(m.group(1).replace(",", "")), float(m.group(2))
            except ValueError:
                continue
            if qty > 0 and 0 < rate <= 500 and abs(qty * rate - amount) <= max(0.02, qty * 0.01):
                lines = [dict(qty=qty, rate=rate, amt=amount,
                              label=f"job rate {rate} (OCR, reconciles to total)", disputed=False)]
                break
    disputed = [l for l in lines if l["disputed"]]
    explained = round(sum(l["amt"] for l in lines), 2)
    cover = explained >= amount - 0.06
    residual = round(amount - explained, 2)

    if disputed:
        d_amt = round(sum(round(l["qty"] * 4.317, 2) if "pallet+wrap" in l["label"] else l["amt"]
                          for l in disputed), 2)
        result["status"] = "disputed"
        result["variance"] = d_amt
        result["line_report"] = (
            "MSA-conflict lines: " + _line_spec(disputed)
            + f" => DISPUTED ${d_amt:,.2f}. Clean payable ${amount - d_amt:,.2f}."
            + (" All other lines at MSA-schedule rates." if cover else f" Unexplained ${residual:,.2f}.")
            + (" Stedi order-level pass still pending (SP/LTL gate)." if is_spltl else ""))
    elif is_vas:
        if lines and npages >= 2:
            result["status"] = "valid"
            result["variance"] = 0.0
            result["line_report"] = (f"VALID per VAS documentation policy: {_line_spec(lines)}; "
                                     f"PDF has {npages} pages incl. supporting documentation.")
        elif lines:
            result["status"] = "needs_detail"
            result["line_report"] = (f"Line math verifies ({_line_spec(lines)}) but the PDF is "
                                     f"{npages} page(s) with no supporting documentation — "
                                     "needs_detail per VAS documentation policy.")
        else:
            result["status"] = "needs_detail"
            result["line_report"] = ("No verifiable charge lines and no supporting documentation "
                                     f"for ${amount:,.2f} in the {npages}-page PDF (VAS policy).")
    elif cover and lines:
        if is_spltl:
            result["status"] = "needs_detail"
            result["line_report"] = ("MSA HEADER PASS COMPLETE: invoice math exact, all parsed lines "
                                     f"at MSA-schedule rates: {_line_spec(lines)}. Stedi order-level "
                                     "pass + worksheet deep pass still pending (SP/LTL payment gate).")
        else:
            result["status"] = "valid"
            result["variance"] = 0.0
            result["expected_amount"] = explained
            result["line_report"] = f"VALID vs MSA rate schedule: {_line_spec(lines)}."
    elif lines:
        result["status"] = "needs_detail"
        result["line_report"] = (f"MSA lines cover ${explained:,.2f} of ${amount:,.2f} — "
                                 f"unexplained ${residual:,.2f}: {_line_spec(lines)}.")
    else:
        result["status"] = "needs_detail"
        result["line_report"] = f"No charge lines verified against the MSA schedule in the {npages}-page PDF."


def _line_pass_keeping_disputes(invoice: dict, result: dict, pdf_dir: Path) -> None:
    """Run the PDF line pass, but never let it demote a dispute.

    apply_msa_conflicts() reads the ingestion `notes`; the line pass reads the
    PDF itself. Either can spot a conflict the other misses, so a `disputed`
    verdict from the header pass survives even if the PDF parse comes back
    clean — the line detail is still recorded for the report card.

    A VAS pallet work order judged by apply_vas_pallet_check is skipped outright.
    Its `notes` carry the full basis (quantity, rate, total) and the verdict is
    already definitive; the PDF adds nothing, and for these invoices it is a
    scanned image that would come back `needs_detail` and demote a sound `valid`.
    """
    if result.get("_pallet_rule"):
        return
    was_disputed = result["status"] == "disputed"
    prior_variance = result.get("variance")
    prior_notes = list(result.get("discrepancies") or [])
    apply_line_pass(invoice, result, pdf_dir)
    if was_disputed and result["status"] != "disputed":
        result["status"] = "disputed"
        result["variance"] = prior_variance
        result["discrepancies"] = prior_notes
        result["line_report"] = ("header pass found MSA-conflict charges (kept); "
                                 + (result.get("line_report") or ""))


def load_rates(rates_path: Optional[str]) -> tuple[dict, str]:
    """Return (rate_card, source_label). Prefer the caller-supplied live file."""
    if rates_path:
        with open(rates_path) as f:
            return json.load(f), f"live ({rates_path})"
    with open(SNAPSHOT) as f:
        return json.load(f), f"BUNDLED SNAPSHOT — may be stale ({SNAPSHOT.name})"


def normalize_warehouse(warehouse_name: str) -> Optional[str]:
    """Map a free-text warehouse value to a rate-card key.

    Short codes (≤3 chars like "sc"/"nj") match only as whole tokens — a naive
    substring match would route "Schiphol" (NL) to south_carolina via "sc".
    Longer aliases still match as substrings so multi-word names work.
    """
    if not warehouse_name:
        return None
    n = warehouse_name.lower().strip()
    tokens = set(re.split(r"[^a-z0-9]+", n))
    for key, aliases in WAREHOUSE_MAP.items():
        for alias in aliases:
            if len(alias) <= 3:
                if alias in tokens:
                    return key
            elif alias in n:
                return key
    return None


def _as_date(value) -> Optional[date]:
    """Coerce a BigQuery date (date object or 'YYYY-MM-DD' string) to a date."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def parse_intl_breakdown(notes: str):
    """Parse an international invoice's notes breakdown.

    Format (one row per charge type, EUR for NL / USD for Canada), e.g.:
      'Storage: EUR 13,526.31 | Storage=13,526.31'
      'VAS: USD 9,436.28 | Consumables=212.24, Val=9,224.04'
      'Storage: USD 8,429.00 | Storage Charge - April 2025=6,737.00, Warehouse Charge=1,692.00'

    Returns (currency, total, [(name, value), ...]) or None. Components are
    separated by ', ' (the thousands separator inside amounts has no space, so it
    doesn't collide); each component is 'name=amount'.
    """
    if not notes or "|" not in notes:
        return None
    head, comps = notes.split("|", 1)
    m = re.search(r"\b(EUR|USD|CAD)\b\s*([\d,]+\.\d{2}|[\d,]+)", head)
    if not m:
        return None
    try:
        total = float(m.group(2).replace(",", ""))
    except ValueError:
        return None
    items = []
    for part in comps.split(", "):
        if "=" in part:
            name, val = part.rsplit("=", 1)
            try:
                items.append((name.strip(), float(val.replace(",", "").strip())))
            except ValueError:
                pass
    return (m.group(1), total, items) if items else None


def active_tax_rate(tax: Optional[dict], inv_date: Optional[date]) -> float:
    """Return the labor-tax rate in effect for an invoice date, else 0.0.

    `tax` carries a default `rate` and a list of `active_periods`, each a
    [from, until) interval (from=null → open start, until=null → open-ended). An
    interval may override `rate`. The tax can switch on and off over time — to
    re-activate it later, just add another interval; no code change needed.
    """
    if not (tax and inv_date):
        return 0.0
    default = tax.get("rate", 0.0)
    for p in tax.get("active_periods", []):
        frm = _as_date(p.get("from")) if p.get("from") else None
        until = _as_date(p.get("until")) if p.get("until") else None
        if (frm is None or inv_date >= frm) and (until is None or inv_date < until):
            return p.get("rate", default)
    return 0.0


def validate(invoice: dict, rates: dict) -> dict:
    """Compare one invoice's billed amount to the rate card."""
    invoice_number = invoice["invoice_number"]
    invoice_type = (invoice.get("type_of_invoice") or "").strip()
    warehouse_raw = invoice.get("warehouse") or ""
    amount = float(invoice.get("amount") or 0)
    period_text = invoice.get("bill_period") or ""

    wh = normalize_warehouse(warehouse_raw)
    result = {
        "invoice_number": invoice_number,
        "invoice_type": invoice_type,
        "warehouse_raw": warehouse_raw,
        "warehouse": wh,
        "period": period_text,
        "date": str(invoice.get("date") or ""),
        "billed_amount": amount,
        "expected_amount": None,
        "variance": None,
        "variance_percent": None,
        "status": "valid",
        "paid_at": str(invoice["paid_at"]) if invoice.get("paid_at") else None,
        "discrepancies": [],
        # The rate card rides along so later checks (apply_vas_labor_check) can
        # look up a per-warehouse contracted rate without being handed it again.
        "_rates": rates,
    }

    if not wh:
        result["status"] = "error"
        result["discrepancies"].append(f"Unknown warehouse: '{warehouse_raw}' — not in rate card")
        return result

    # International invoices (Yusen NL = EUR, Yusen Canada = USD) come one row per
    # charge type with a breakdown in `notes`, in their own currency. The flat
    # USD rate-card math doesn't apply; instead verify internal consistency — the
    # breakdown components must sum to the billed amount. Per-unit rate checks
    # need counts (pallet-weeks / admin hours / cartons) the header lacks, so a
    # consistent invoice is needs_detail, an inconsistent one is a discrepancy.
    if wh in ("canada", "netherlands"):
        sym = {"EUR": "€", "USD": "$", "CAD": "C$"}
        default_cur = "EUR" if wh == "netherlands" else "USD"
        bd = parse_intl_breakdown(invoice.get("notes"))
        if bd:
            cur, total, items = bd
            s = sym.get(cur, "")
            comp_sum = round(sum(v for _, v in items), 2)
            breakdown_str = ", ".join(f"{n}={s}{v:,.2f}" for n, v in items)
            if abs(comp_sum - total) > 0.01 or abs(total - amount) > 0.01:
                result["status"] = "discrepancy"
                result["expected_amount"] = comp_sum
                result["variance"] = round(amount - comp_sum, 2)
                result["discrepancies"].append(
                    f"{invoice_type} ({cur}): breakdown [{breakdown_str}] sums to {s}{comp_sum:,.2f}, "
                    f"notes total {s}{total:,.2f}, billed {s}{amount:,.2f} — mismatch.")
            else:
                result["status"] = "needs_detail"
                vat_note = " NL totals are EUR + 21% VAT." if wh == "netherlands" else ""
                result["discrepancies"].append(
                    f"{invoice_type} ({cur}): breakdown sums correctly to {s}{amount:,.2f} "
                    f"[{breakdown_str}]. Per-unit rate check needs counts "
                    f"(pallet-weeks / admin hours / cartons).{vat_note}")
        else:
            result["status"] = "needs_detail"
            result["discrepancies"].append(
                f"{invoice_type} — {default_cur} intl invoice with no parseable breakdown in notes; "
                f"validate against the contract detail.")
        return result

    t = invoice_type.lower()

    # ---- Admin: flat weekly fee. NJ carried a 5% labor tax before May 2026.
    # The bill_period text can't be trusted for duration (single dates carry none;
    # even "Week of May 25" was a 4-day week — May 25 2026 is Memorial Day). So we
    # only call an exact full-week match `valid`; anything BELOW is needs_detail
    # (partial week / holiday — unprovable from the header), and only billing
    # ABOVE a full week is a real discrepancy (overbilling). ----
    if t == "admin":
        adm = rates.get("admin_vas", {}).get(wh) or {}
        base_weekly = adm.get("weekly")
        if base_weekly is None:
            result["status"] = "error"
            result["discrepancies"].append(f"No admin weekly rate for {wh}")
            return result

        # Labor tax that switches on/off over time (e.g. NJ 5%, dropped 2026-04-27).
        expected = base_weekly
        tax = adm.get("labor_tax")
        tax_note = ""
        rate = active_tax_rate(tax, _as_date(invoice.get("date")))
        if rate:
            expected = round(base_weekly * (1 + rate), 2)
            tax_note = f" (incl. {rate * 100:.0f}% labor tax)"

        if abs(amount - expected) <= 0.01:
            _set_variance(result, amount, expected)  # exact full week → valid
        elif amount > expected + 0.01:
            _set_variance(result, amount, expected)  # over a full week → discrepancy
            result["discrepancies"].append(
                f"Admin: billed ${amount:,.2f} exceeds full week ${expected:,.2f}{tax_note} — overbilled.")
        else:
            # Below a full week: partial week, holiday, or (for NJ) a missing tax.
            # Can't confirm billed days from the header → needs_detail, not a flag.
            result["expected_amount"] = expected
            result["variance"] = round(amount - expected, 2)
            result["variance_percent"] = round(result["variance"] / expected * 100, 1) if expected else 0.0
            result["status"] = "needs_detail"
            daily = base_weekly / 5
            if tax_note and abs(amount - base_weekly) <= 0.01:
                result["discrepancies"].append(
                    f"Admin: billed ${amount:,.2f} = full base week WITHOUT the {rate * 100:.0f}% labor tax "
                    f"that applied for this date (expected ${expected:,.2f}). Confirm whether tax applies.")
            else:
                implied = amount / daily if daily else 0
                result["discrepancies"].append(
                    f"Admin: billed ${amount:,.2f} vs full week ${expected:,.2f}{tax_note}; "
                    f"≈ {implied:.1f} business days at ${daily:,.2f}/day. Period '{period_text}' doesn't "
                    f"confirm duration — verify billed days (partial weeks/holidays are common).")
        return result

    # ---- Storage: per-pallet x count (count comes from line items) ----
    if t == "storage":
        rate = rates.get("storage", {}).get(wh)
        if rate is None:
            result["status"] = "error"
            result["discrepancies"].append(f"No storage rate for {wh}")
            return result
        pallets = invoice.get("pallet_count")
        if not pallets:
            result["status"] = "needs_detail"
            result["discrepancies"].append(
                f"Storage rate is ${rate:,.2f}/pallet for {wh}, but pallet count is "
                f"not on the invoice header. Provide pallet_count (from the invoice "
                f"detail) to validate ${amount:,.2f}."
            )
            return result
        expected = round(pallets * rate, 2)
        _set_variance(result, amount, expected)
        if result["status"] == "discrepancy":
            result["discrepancies"].append(
                f"Storage: {pallets} pallets x ${rate:,.2f} = ${expected:,.2f}, billed ${amount:,.2f}"
            )
        return result

    # ---- VAS / Small Parcel / LTL: header total only ----
    # A real check needs itemized hours (VAS) or per-fee units (SP/LTL), which
    # the header row doesn't carry. Report rather than guess.
    result["status"] = "needs_detail"
    hint = {
        "vas": "VAS bills at an hourly rate; provide hours from the invoice detail.",
        "smlprcl/ltl": "Small Parcel/LTL bills per fee (carton, pick, pallet, BOL); provide itemized counts.",
    }.get(t, "Provide itemized invoice detail to validate this charge against per-fee rates.")
    result["discrepancies"].append(
        f"{invoice_type}: header total ${amount:,.2f} recorded. {hint}"
    )
    return result


# ---- MSA-conflict detection (2026 MSA, eff. 01/01/2026) ----
# Charges Yusen keeps billing that conflict with the signed MSA. Detection is
# text-based over the invoice notes/line text, so it catches the VAS-style
# headers that carry line detail ("10 PALLETS W/SHRINKWRAP @ $14.317/PALLET")
# and any richer line text a deep pass stores. Each rule yields a description
# and, where the qty×rate is parseable, the disputed dollar amount.
_QTY = r"([\d,]+)"                      # quantity, possibly comma-grouped
_SEP = r"\s*(?:[X×x@]|@)?\s*\$?"        # "134 x 4.347" / "10 ... @ $14.317"

MSA_CONFLICT_RULES = [
    # AF-9: national pallet rate is $10.00 all-in INCLUDING wrap; a separate
    # NJ stretchwrap line at the 4.34–4.35 wrap rate double-bills the wrap.
    ("new_jersey", re.compile(rf"STRETCH\s*WRAP\W*(?:STD)?\D{{0,30}}?{_QTY}{_SEP}(4\.3[45]\d?)", re.I),
     "AF-9: STRETCHWRAP billed separately — the $10.00 national pallet rate is all-in incl. wrap"),
    # AF-7: Per Pack Out was removed per Yusen 4/28; PACK CARTON @ 0.92 is it.
    ("new_jersey", re.compile(rf"PACK\s*CARTON\D{{0,30}}?{_QTY}{_SEP}(0\.92)", re.I),
     "AF-7: PACK CARTON pack-out charge — removed per Yusen 4/28"),
    # AF-9 (Fontana/SC form): 14.317 pallet rate embeds a 4.317 wrap component.
    ("fontana|south_carolina", re.compile(rf"{_QTY}\s*PALLETS?\s*W/?\s*SHRINK\s*WRAP\s*@?\s*\$?(14\.317)", re.I),
     "AF-9: wrap component embedded in 14.317 pallet rate — $10.00 is all-in"),
]
# Fontana "PICK & PACK ECOM" bills EVERY pick where the MSA line is "Per
# Additional Ecom Pick" — needs an additional-only recompute from the
# supporting worksheet, so it disputes without a computable amount.
_PICK_PACK_ECOM = re.compile(r"PICK\s*&?\s*PACK\s*ECOM", re.I)


def detect_msa_conflicts(text: str, wh: str) -> list[tuple[str, Optional[float]]]:
    """Return [(description, disputed_amount_or_None), ...] for known conflicts."""
    found = []
    if not text:
        return found
    for wh_pat, rx, why in MSA_CONFLICT_RULES:
        if wh not in wh_pat.split("|"):
            continue
        for m in rx.finditer(text):
            qty = float(m.group(1).replace(",", ""))
            rate = float(m.group(2))
            # The disputed piece of a 14.317 pallet line is only the embedded
            # 4.317 wrap component; the other rules dispute the full line.
            per_unit = 4.317 if rate == 14.317 else rate
            amt = round(qty * per_unit, 2)
            found.append((f"{why} — {m.group(1)} × {per_unit} = ${amt:,.2f} disputed", amt))
    if wh == "fontana" and _PICK_PACK_ECOM.search(text):
        found.append((
            "MSA basis: PICK & PACK ECOM billed on every pick, but the MSA line is "
            "'Per Additional Ecom Pick' — recompute additional-only from the supporting "
            "worksheet (single-unit orders with a pick charge = automatic dispute)", None))
    return found


AF9_PALLET_ALL_IN = 10.00   # MSA AF-9: $10.00/pallet, pallet AND stretch wrap included

# Savannah bills pallets as VAS work orders rather than on the SP/LTL invoice:
#   "WORK ORDER 5001859 PALLETS (Savannah) - 7 PALLETS W/SHRINKWRAP @ $10.00/PALLET"
#   "WORK ORDER 5001786 PALLETS - 48 pallets w/shrinkwrap @ $14.317"
#   "WORK ORDER 5001727 PALLETS - 57 pallets @ $11.74"
# Anchored on PALLET so the work-order number can never be read as a quantity.
_VAS_PALLET_LINE = re.compile(
    r"(?<![\d.])(\d{1,5}(?:\.\d+)?)\s+PALLETS?\b[^@$]*?@\s*\$?\s*([\d,]+(?:\.\d+)?)", re.I)


def apply_vas_pallet_check(invoice: dict, result: dict) -> None:
    """Judge a Savannah VAS pallet work order: recompute, then rate vs AF-9.

    These are pallet charges wearing a VAS document. The generic VAS logic cannot
    resolve them — it has no per-unit basis to check — so they parked at
    `needs_detail` indefinitely even when billed exactly right. This reads the
    quantity and rate straight out of `notes`, which matters because SC VAS PDFs
    are scanned images: no OCR is needed to reach a verdict.

    Two stages, and the second is the one that protects the money:

    1. **Recompute.** pallets x printed rate must equal the invoice total.
    2. **Judge the rate against AF-9's $10.00 all-in.** Arithmetic alone is not
       enough — 48 x $14.317 = $687.22 recomputes perfectly, and validating on
       that would stamp an AF-9 overcharge `valid` and silently drop a live claim.

    Rate handling (Anthony, 2026-08-12): the MSA rate is the yardstick, and the
    pre-MSA $11.74 SC rate is NOT grandfathered — anything above $10.00 is
    disputed for the excess, whatever era it came from.

    Reclassifying these as SMLPRCL/LTL was considered and rejected: SP/LTL carries
    the Stedi shipping gate, these work orders have no order numbers to match, so
    reclassifying would park them at `needs_detail` permanently — the opposite of
    the goal — and would misdescribe the document in the ledger.
    """
    if (invoice.get("type_of_invoice") or "").strip().upper() != "VAS":
        return
    if result.get("_settled") or result.get("status") == "error":
        return
    m = _VAS_PALLET_LINE.search(invoice.get("notes") or "")
    if not m:
        return

    pallets = float(m.group(1))
    rate = float(m.group(2).replace(",", ""))
    amount = result.get("billed_amount")
    if amount is None:
        amount = float(invoice.get("amount") or 0)
    expected = round(pallets * rate, 2)
    payable = round(pallets * AF9_PALLET_ALL_IN, 2)

    # Marks this row as judged by the pallet rule so the generic conflict
    # detector and the PDF line pass do not re-judge the same charge.
    result["_pallet_rule"] = True

    if abs(expected - amount) > 0.01:
        result["status"] = "discrepancy"
        result["expected_amount"] = expected
        result["variance"] = round(amount - expected, 2)
        result["discrepancies"].append(
            f"{pallets:g} pallets x ${rate:,.4f} = ${expected:,.2f} but the invoice bills "
            f"${amount:,.2f} — the pallet line does not recompute")
        return

    if abs(rate - AF9_PALLET_ALL_IN) < 0.005:
        result["status"] = "valid"
        result["expected_amount"] = expected
        result["variance"] = 0.0
        result["variance_percent"] = 0.0
        result["line_report"] = (
            f"VALID vs MSA AF-9: {pallets:g} pallets x ${rate:,.2f} = ${amount:,.2f}, exact. "
            f"All-in pallet rate, wrap included — no markup, nothing disputed.")
        return

    if rate > AF9_PALLET_ALL_IN:
        over = round((rate - AF9_PALLET_ALL_IN) * pallets, 2)
        result["status"] = "disputed"
        result["variance"] = over
        result["variance_percent"] = round(over / amount * 100, 1) if amount else None
        era = (f"the pre-MSA SC pallet rate of ${rate:,.2f}"
               if abs(rate - 11.74) < 0.005 else f"${rate:,.4f}/pallet")
        result["discrepancies"].append(
            f"AF-9: {pallets:g} pallets billed at {era}; the MSA all-in rate is "
            f"${AF9_PALLET_ALL_IN:,.2f} incl. stretch wrap, so {pallets:g} x "
            f"${rate - AF9_PALLET_ALL_IN:,.4f} = ${over:,.2f} is disputed and "
            f"${payable:,.2f} is payable")
        return

    result["status"] = "discrepancy"
    result["variance"] = round((rate - AF9_PALLET_ALL_IN) * pallets, 2)
    result["discrepancies"].append(
        f"{pallets:g} pallets x ${rate:,.4f} = ${amount:,.2f}, below the AF-9 $10.00 all-in "
        f"— unrecognised pallet rate, needs a human look")


# "MAY 2026 CONSOLIDATION PROJECT - 24.49 HRS", "55 hrs @ $53.55", "2 hrs"
_VAS_HOURS = re.compile(r"(?<![\d.])(\d{1,4}(?:\.\d+)?)\s*(?:HRS?|HOURS?)\b", re.I)


# Role keywords -> the row of the MSA hourly table. Order matters: the specific
# activities are tested before general_labor, which is the catch-all the MSA itself
# defines broadly ("equipment operator, office, admin, returns, photography, floor
# loading, oversize, QA, routing").
_ROLE_WORDS = [
    ("stock_consolidation", ("consolidat",)),
    ("physical_inventory",  ("physical inventory", "inventory count", "cycle count",
                             "stock count")),
    ("salaried_supervisor", ("supervisor", "salaried")),
    ("clerical",            ("clerical",)),
    ("material_handler",    ("material handler",)),
    ("dray_admin_fee",      ("dray",)),
    ("qa",                  ("qa ", " qa", "quality assurance")),
]


def _vas_role(notes: str) -> str:
    low = (notes or "").lower()
    for role, words in _ROLE_WORDS:
        if any(w in low for w in words):
            return role
    return "general_labor"


def apply_vas_labor_check(invoice: dict, result: dict) -> None:
    """Judge an hourly VAS project against the MSA hourly table: role x site.

    A VAS job described as a project plus hours ("MAY 2026 CONSOLIDATION PROJECT -
    24.49 HRS") carries everything needed for a verdict, but parked at `needs_detail`
    because nothing derived the rate. This divides the total by the hours, works out
    which row of the MSA hourly table the work belongs to, and compares.

    **The rate depends on both the site and the kind of work**, which is why a single
    figure per warehouse was not enough. South Carolina bills general labour at
    $53.55 but physical inventory and stock consolidation at $63.00, so 755701 —
    a consolidation project at $63.00/hr — is exactly on contract, and reading it
    against a lone "SC hourly" number made a correct invoice look overbilled.

    When the derived rate matches no row for that site, it is only disputed if it is
    ABOVE every rate in the site's column; the amount claimed is the excess over the
    highest contracted rate, which is the most defensible figure. A rate at 1.5x the
    matched role is reported as apparent overtime for a human rather than disputed,
    since the MSA carries no overtime multiplier.
    """
    if (invoice.get("type_of_invoice") or "").strip().upper() != "VAS":
        return
    if result.get("_settled") or result.get("status") == "error":
        return
    if result.get("_pallet_rule"):     # a pallet work order, not a labour job
        return
    m = _VAS_HOURS.search(invoice.get("notes") or "")
    if not m:
        return
    hours = float(m.group(1))
    if hours <= 0:
        return

    wh = result.get("warehouse")
    card = ((result.get("_rates") or {}).get("admin_vas") or {}).get(wh) or {}
    roles = card.get("hourly_roles") or {}
    if not roles:
        return                          # pre-v1.6.0 snapshot: no role table to judge against

    notes = invoice.get("notes") or ""
    role = _vas_role(notes)
    msa_rate = roles.get(role) or card.get("vas_hourly")
    if not msa_rate:
        return

    amount = result.get("billed_amount")
    if amount is None:
        amount = float(invoice.get("amount") or 0)
    derived = round(amount / hours, 4)
    result["_labor_rule"] = True
    # validate() left a "provide hours from the invoice detail" placeholder because it
    # could not see the hours. We just supplied them, so drop it — leaving it in makes
    # a row read "valid" and "needs more detail" at once.
    result["discrepancies"] = [d for d in (result.get("discrepancies") or [])
                               if "hourly rate" not in str(d)]

    pretty = role.replace("_", " ")
    # Any row of this site's column is a contracted rate. Match the derived rate
    # against all of them, not just the role we guessed from the wording.
    exact = [r_ for r_, v in roles.items() if abs(derived - v) < 0.005]
    if exact:
        matched = exact[0].replace("_", " ")
        result["status"] = "valid"
        result["expected_amount"] = round(hours * derived, 2)
        result["variance"] = 0.0
        result["variance_percent"] = 0.0
        note = (f"VALID vs the MSA hourly table: {hours:g} hrs x ${derived:,.4f} = "
                f"${amount:,.2f}, exact, at the {wh} {matched} rate.")
        if exact[0] != role:
            note += (f" Wording reads as {pretty}; the rate billed is the {matched} row. "
                     f"Both are contracted for this site.")
        result["line_report"] = note
        return

    if derived > msa_rate:
        # Overtime at 1.5x is agreed (Anthony, 2026-08-12), so it is a contracted rate
        # like any other. Checked against every role in the column, not just the role
        # inferred from the wording, so OT on a specialised rate also resolves.
        mult = card.get("overtime_multiplier")
        if mult:
            ot_hits = [r_ for r_, v in roles.items() if abs(derived - round(v * mult, 4)) < 0.01]
            if ot_hits:
                base = ot_hits[0]
                result["status"] = "valid"
                result["expected_amount"] = round(hours * derived, 2)
                result["variance"] = 0.0
                result["variance_percent"] = 0.0
                result["line_report"] = (
                    f"VALID vs the MSA hourly table: {hours:g} hrs x ${derived:,.4f} = "
                    f"${amount:,.2f}, exact, at {mult:g}x overtime on the {wh} "
                    f"{base.replace('_', ' ')} rate of ${roles[base]:,.4f}. Overtime at "
                    f"{mult:g}x is agreed.")
                return
        ceiling = max(roles.values())
        if derived > ceiling:
            over = round((derived - ceiling) * hours, 2)
            result["status"] = "disputed"
            result["variance"] = over
            result["variance_percent"] = round(over / amount * 100, 1) if amount else None
            result["discrepancies"].append(
                f"{hours:g} hrs at ${derived:,.4f}/hr is above every contracted {wh} hourly "
                f"rate (highest is ${ceiling:,.4f}) — ${over:,.2f} above the ceiling; reads as "
                f"{pretty}, whose rate is ${msa_rate:,.4f}")
            return
        result["status"] = "discrepancy"
        result["variance"] = round((derived - msa_rate) * hours, 2)
        result["discrepancies"].append(
            f"{hours:g} hrs at ${derived:,.4f}/hr matches no row of the {wh} hourly table but "
            f"sits within its range; reads as {pretty} (${msa_rate:,.4f}). Identify the role "
            f"before paying")
        return

    result["status"] = "valid"
    result["variance"] = 0.0
    result["line_report"] = (
        f"{hours:g} hrs at ${derived:,.4f}/hr, below the {wh} {pretty} rate of "
        f"${msa_rate:,.4f} — ${abs(round((msa_rate - derived) * hours, 2)):,.2f} in "
        f"Americanflat's favour, nothing to dispute.")


def apply_msa_conflicts(invoice: dict, result: dict) -> None:
    """Stamp `disputed` when the invoice carries known MSA-conflict lines.

    Runs after validate(): a mathematically clean invoice can still contain
    charges the MSA doesn't allow. Doesn't downgrade a discrepancy (math/rate
    mismatches are investigated first) and skips intl warehouses — the MSA
    conflict schedule is US-domestic.
    """
    # A VAS pallet work order already got a verdict from apply_vas_pallet_check,
    # on the same charge. Running the generic detector too would re-judge it and
    # overwrite the variance with a second, differently-derived figure.
    if result.get("_pallet_rule"):
        return
    wh = result.get("warehouse")
    if wh not in ("fontana", "new_jersey", "south_carolina"):
        return
    if result["status"] in ("discrepancy", "error"):
        return
    conflicts = detect_msa_conflicts(invoice.get("notes") or "", wh)
    if not conflicts:
        return
    result["status"] = "disputed"
    total = round(sum(a for _, a in conflicts if a), 2)
    if total:
        # For disputed rows validation_variance carries the disputed $ total —
        # the dashboards render it as "⚑ Disputed $X".
        result["variance"] = total
        billed = result.get("billed_amount") or 0
        result["variance_percent"] = round(total / billed * 100, 1) if billed else None
    for desc, _amt in conflicts:
        result["discrepancies"].append(desc)


def _set_variance(result: dict, amount: float, expected: float) -> None:
    result["expected_amount"] = round(expected, 2)
    result["variance"] = round(amount - expected, 2)
    result["variance_percent"] = round((result["variance"] / expected) * 100, 1) if expected else 0.0
    # 1 cent tolerance absorbs rounding; real variances are dollars.
    result["status"] = "discrepancy" if abs(result["variance"]) > 0.01 else "valid"


VALIDATION_COLUMNS = [
    ("validated_at", "TIMESTAMP"),
    ("validation_status", "STRING"),
    ("validation_variance", "FLOAT64"),
    ("validated_by", "STRING"),
    # Payment tracking: set only on explicit user confirmation (--mark-paid).
    ("paid_at", "TIMESTAMP"),
    ("paid_marked_by", "STRING"),
    # The two-axis report card stored at approval time (audit artifact).
    ("validation_report", "STRING"),
]


def compose_report(r: dict, paid_date: str = "") -> str:
    """Build the two-axis report card text stored on the row at approval.

    Auto-composed from the validation result. When Claude has done a deeper
    document-level validation in-conversation (PDF worksheet, NL per-order
    checks), pass that richer text via --report-file instead — the stored
    report should match what the approver actually saw.
    """
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌",
            "disputed": "⚑"}
    s = r.get("status", "?")
    d = r.get("discrepancies") or []
    if s == "valid":
        math_line = (f"✅ billed ${r['billed_amount']:,.2f} = expected "
                     f"${r.get('expected_amount') or r['billed_amount']:,.2f} — exact")
        rate_line = "✅ matches contracted rate"
    elif s == "discrepancy":
        math_line = f"🚨 {d[0]}" if d else "🚨 variance vs expected"
        rate_line = f"🚨 variance ${r.get('variance', 0):,.2f} ({r.get('variance_percent', 0):+.1f}%)"
    elif s == "disputed":
        amt = r.get("variance")
        math_line = "✅ line math validated" if not d else f"⚑ {d[-1][:180]}"
        rate_line = (f"⚑ MSA-conflict charges{f' totaling ${amt:,.2f}' if amt else ''}: "
                     + "; ".join(x[:150] for x in d))
    else:
        math_line = f"{icon.get(s, '•')} {d[0][:180]}" if d else f"{icon.get(s, '•')} header total recorded"
        rate_line = "⏳ per-unit rate check needs itemized counts"
    t = (r.get("invoice_type") or "").lower()
    if t not in ("smlprcl/ltl",):
        stedi_line = "n/a (no order numbers on this type)"
    elif r.get("stedi_note"):
        # A completed order-level check was handed to us — report it rather than
        # printing the "still to do" wording over the top of a finished check.
        stedi_line = r["stedi_note"]
    else:
        stedi_line = "no order-level Stedi result recorded on this row yet"
    if s == "discrepancy":
        verdict = "Hold — discrepancy"
    elif s == "disputed":
        amt = r.get("variance")
        verdict = f"Short-pay/hold — MSA dispute{f' ${amt:,.2f}' if amt else ''}"
    else:
        verdict = "OK to pay"
    line_detail = r.get("line_report")
    lines = [
        f"Invoice {r['invoice_number']} — {r.get('invoice_type')}, {r.get('warehouse')}, {r.get('period')}",
        f"Invoice math:  {math_line}",
        f"Rate card:     {rate_line}",
        f"Stedi:         {stedi_line}",
    ]
    if paid_date:
        lines.append(f"Paid:          ✓ {paid_date}")
    if line_detail:
        lines.append(f"Line detail:   {line_detail}")
    lines.append(f"Verdict:       {verdict}")
    return "\n".join(lines)


# Every automated write stamps this name. Anything else in validated_by means a
# person recorded the verdict, which write_result() treats as sticky.
AUTO_WRITER = "yusen-invoice-validator"


def init_columns(client: bigquery.Client) -> None:
    """Add the validation tracking columns if they don't already exist.

    Idempotent (ADD COLUMN IF NOT EXISTS) and non-destructive — existing rows and
    data are untouched. Run once when pointing the skill at a fresh table so that
    --write has somewhere to record validated_at / validation_status.
    """
    adds = ",\n      ".join(f"ADD COLUMN IF NOT EXISTS {name} {typ}"
                            for name, typ in VALIDATION_COLUMNS)
    q = f"ALTER TABLE `{TABLE}`\n      {adds}"
    client.query(q).result()
    print(f"✓ Validation columns ensured on {TABLE}:")
    for name, typ in VALIDATION_COLUMNS:
        print(f"    {name} {typ}")


def _missing_columns(client: bigquery.Client) -> bool:
    """True if the validation columns are absent from the table schema."""
    table = client.get_table(TABLE)
    present = {f.name for f in table.schema}
    return not all(name in present for name, _ in VALIDATION_COLUMNS)


# One auto-composed report block lives on each row, tagged [AUTO YYYY-MM-DD].
# Re-sweeps replace the previous AUTO block instead of stacking a copy per day;
# every other block (paid report cards, [MSA DISPUTE ...] specs, human notes)
# is preserved verbatim.
_AUTO_BLOCK = re.compile(r"\n*\[AUTO \d{4}-\d{2}-\d{2}\].*?(?=\n\n\[|\Z)", re.S)


def _block_pattern(tag: str) -> "re.Pattern[str]":
    """Matcher for one dated block, e.g. [PAID 2026-08-11] ... up to the next block."""
    return re.compile(rf"\n*\[{re.escape(tag)} \d{{4}}-\d{{2}}-\d{{2}}\].*?(?=\n\n\[|\Z)", re.S)


def merge_report(prior: Optional[str], new_block: str, tag: str = "AUTO") -> str:
    """Splice `new_block` into the row's report as the single [tag <today>] block.

    Only the block carrying the same tag is replaced. Every other block survives
    verbatim — that is the whole point: a row accumulates a [MSA REVAL ...], a
    [DEEP PASS ...], a [STEDI ...] and a [PAID ...] block over its life, each
    written by a different pass, and none of them may be destroyed by the next
    one. Anything that stores report text MUST come through here.
    """
    base = _block_pattern(tag).sub("", prior or "").strip()
    tagged = f"[{tag} {date.today().isoformat()}] {new_block}"
    return f"{base}\n\n{tagged}".strip()


# Blocks written by a pass that saw more than the invoice header: itemized
# worksheet math, an order-level Stedi result, a contract-conflict spec. When one
# of these is on the row, a header-level result is the weaker reading and must
# not be presented as the current state of the invoice.
_DEEPER_BLOCK = re.compile(r"\[(DEEP PASS|STEDI|MSA DISPUTE|MSA REVAL) \d{4}-\d{2}-\d{2}\]")


def _deferral_block(r: dict, prior_report: str) -> str:
    """The AUTO block to write when a deeper review is already on the row.

    A header-only pass knows the invoice total and nothing else, so its normal
    card says "provide itemized counts" and "no order-level Stedi result
    recorded". Appending that under a completed deep pass reads as though the
    itemized and shipping work still needs doing — the exact confusion this
    replaces (755265, 2026-08-11: an [AUTO] block claiming the Stedi check was
    outstanding sat directly beneath a [DEEP PASS] block recording 289/289).
    """
    tags = sorted({m.group(1).upper() for m in _DEEPER_BLOCK.finditer(prior_report)})
    return (f"Invoice {r['invoice_number']} — header-level re-check only, no new "
            f"findings. Itemized detail is already on file above "
            f"({', '.join(tags)}); this pass does not supersede it. Header total "
            f"${r['billed_amount']:,.2f}, unchanged.")


def write_result(r: dict, client: bigquery.Client,
                 invoice: Optional[dict] = None) -> tuple[bool, str]:
    """Persist the validation outcome back onto the invoice row.

    Records validated_at = now plus the status/variance, and stores the
    auto-composed report card in validation_report on every write (replacing
    only its own previous [AUTO] block), so the dashboards always carry a
    current per-invoice spec — not just rows that went through --mark-paid.

    A `disputed` stamp is sticky: a re-sweep that comes back valid/needs_detail
    must NOT clear it (the conflict lives in the line items, which a header
    pass can't see). Disputed clears only when the invoice is re-billed/credited
    or manually cleared. The report block still refreshes.

    A **human stamp is also sticky**, for the same reason: when someone reads the
    itemized detail this header pass can't see and records a verdict, an automated
    re-sweep must not overwrite it — not the status, and not the `validated_by`
    provenance that says a person decided it. Any prior stamp whose `validated_by`
    is not AUTO_WRITER counts as human. Real escalations still win: a sweep that
    finds `disputed`/`discrepancy` overrides a human `valid`, because that is new
    information rather than the absence of information.

    Returns (ok, message). A freshly-ingested row may still be in BigQuery's
    streaming buffer, where UPDATE is not allowed; that's reported, not fatal —
    re-run once the buffer flushes (typically well under an hour).
    """
    if r.get("_settled"):
        return True, f"kept {r['_settled']} — settled row, not re-judged"
    prior_status = ((invoice or {}).get("validation_status") or "").strip()
    preserve = prior_status == "disputed" and r["status"] in ("valid", "needs_detail")
    # A paid row explicitly stamped valid (mark-paid user policy) is settled;
    # a later header-level pass coming back needs_detail adds nothing and
    # must not un-check it. Real escalations (discrepancy/disputed) still win.
    if (prior_status == "valid" and (invoice or {}).get("paid_at")
            and r["status"] == "needs_detail"):
        preserve = True
    # A stamp set by a person beats this automated header pass, paid or not: they
    # had the itemized detail (hours, unit counts) that the header lacks, which is
    # exactly why the row reads valid instead of needs_detail. Only escalations
    # get through — see the docstring.
    prior_by = ((invoice or {}).get("validated_by") or "").strip()
    if (prior_status and prior_by and prior_by != AUTO_WRITER
            and r["status"] in ("valid", "needs_detail")):
        preserve = True

    prior_report = (invoice or {}).get("validation_report") or ""
    # Never let a header-level pass talk over a completed deeper review. The
    # status is already protected above; the report text needs the same guard,
    # because the AUTO block is written last and therefore reads as the current
    # verdict on the dashboards.
    if r["status"] == "needs_detail" and _DEEPER_BLOCK.search(prior_report):
        new_block = _deferral_block(r, prior_report)
    else:
        new_block = compose_report(r)
    report = merge_report(prior_report, new_block)
    params = [
        bigquery.ScalarQueryParameter("report", "STRING", report),
        bigquery.ScalarQueryParameter("inv", "STRING", r["invoice_number"]),
    ]
    if preserve:
        # Refresh the timestamp + report only; status/variance/validated_by keep
        # their disputed values.
        setter = "validated_at = CURRENT_TIMESTAMP(), validation_report = @report"
    else:
        setter = ("validated_at = CURRENT_TIMESTAMP(), validation_status = @status, "
                  "validation_variance = @variance, validated_by = @by, "
                  "validation_report = @report")
        params += [
            bigquery.ScalarQueryParameter("status", "STRING", r["status"]),
            bigquery.ScalarQueryParameter("variance", "FLOAT64", r["variance"]),
            bigquery.ScalarQueryParameter("by", "STRING", AUTO_WRITER),
        ]
    q = f"UPDATE `{TABLE}` SET {setter} WHERE invoice_number = @inv"
    cfg = bigquery.QueryJobConfig(query_parameters=params)
    try:
        client.query(q, job_config=cfg).result()
        return True, f"written ({prior_status} stamp preserved)" if preserve else "written"
    except Exception as e:
        msg = str(e)
        if "streaming buffer" in msg:
            return False, "row still in streaming buffer — re-run later"
        if "validation_status" in msg or "validated_at" in msg or "Unrecognized name" in msg:
            return False, "validation columns missing — run once with --init"
        return False, f"write failed: {msg.splitlines()[0][:120]}"


def mark_paid(invoice_number: str, client: bigquery.Client, paid: bool = True,
              report_text: Optional[str] = None) -> tuple[bool, str]:
    """Set or clear the paid stamp on an invoice row.

    Only call this after the USER has explicitly confirmed the invoice was paid
    (or that a paid mark was a mistake) — payment status is a human fact the
    validator cannot infer. When marking paid, the approval-time report card is
    stored on the row as its own [PAID <date>] block.

    The report card is **merged, never substituted**. Through v1.4.0 this wrote
    `validation_report = COALESCE(@report, validation_report)`, which replaced the
    entire field with the payment card and silently discarded every other block on
    the row. On 2026-08-11 that destroyed the [MSA REVAL] and [DEEP PASS] history
    on 754891 and 755265 — including their itemized line math and 106/106 and
    289/289 Stedi order matches — recoverable only because BigQuery keeps 7 days
    of table history. Both rows were `valid` and paid, so no later sweep would
    ever have rebuilt them. If the prior report cannot be read, the field is left
    untouched rather than overwritten.

    Subject to the same streaming-buffer limitation as write_result.
    """
    params = [bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)]
    if not paid:
        setter = "paid_at = NULL, paid_marked_by = NULL"
    else:
        merged = None
        if report_text:
            try:
                cfg0 = bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)])
                rows = list(client.query(
                    f"SELECT validation_report FROM `{TABLE}` WHERE invoice_number = @inv "
                    f"LIMIT 1", job_config=cfg0).result())
                if rows:
                    merged = merge_report(rows[0][0], report_text, tag="PAID")
            except Exception:
                # Could not read what is already there — decline to write the
                # report rather than risk replacing history we never saw.
                merged = None
        setter = ("paid_at = CURRENT_TIMESTAMP(), "
                  "paid_marked_by = 'user-confirmed via yusen-invoice-validator', "
                  "validation_report = COALESCE(@report, validation_report)")
        params.append(bigquery.ScalarQueryParameter("report", "STRING", merged))
    q = f"UPDATE `{TABLE}` SET {setter} WHERE invoice_number = @inv"
    cfg = bigquery.QueryJobConfig(query_parameters=params)
    try:
        job = client.query(q, job_config=cfg)
        job.result()
        if job.num_dml_affected_rows == 0:
            return False, "no matching invoice row"
        return True, f"marked {'paid' if paid else 'unpaid'} ({job.num_dml_affected_rows} row(s))"
    except Exception as e:
        msg = str(e)
        if "streaming buffer" in msg:
            return False, "row still in streaming buffer — retry later"
        return False, f"update failed: {msg.splitlines()[0][:120]}"


def fetch_invoice(invoice_number: str, client: bigquery.Client) -> Optional[dict]:
    cfg = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)]
    )
    base = ("SELECT invoice_number, type_of_invoice, warehouse, amount, date, bill_period, notes{extra} "
            f"FROM `{TABLE}` WHERE invoice_number = @inv LIMIT 1")
    # Tracking columns ride along so --write can preserve a disputed stamp and
    # merge the report instead of clobbering it.
    # validated_by rides along so write_result() can tell a human stamp from an
    # automated one and leave the human's verdict alone.
    tracked = (", paid_at, validation_status, validation_variance, validation_report,"
               " validated_by")
    try:
        rows = list(client.query(base.format(extra=tracked), job_config=cfg).result())
    except Exception as e:
        if not any(c in str(e) for c in ("paid_at", "validation_", "Unrecognized name")):
            raise
        # Table not yet provisioned with tracking columns (run --init) — degrade gracefully.
        rows = list(client.query(base.format(extra=""), job_config=cfg).result())
    return dict(rows[0]) if rows else None


def print_report(r: dict) -> None:
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌",
            "disputed": "⚑"}.get(r["status"], "•")
    print(f"\n{'='*78}")
    print(f"RATE CARD VALIDATION — Invoice {r['invoice_number']}  {icon} {r['status'].upper()}")
    print(f"{'='*78}")
    print(f"Type:       {r['invoice_type']}")
    print(f"Warehouse:  {r['warehouse_raw']}" + (f"  ->  {r['warehouse']}" if r['warehouse'] else ""))
    print(f"Period:     {r['period']}")
    print(f"{'-'*78}")
    print(f"Billed:     ${r['billed_amount']:,.2f}")
    if r["expected_amount"] is not None:
        print(f"Expected:   ${r['expected_amount']:,.2f}")
        print(f"Variance:   ${r['variance']:,.2f} ({r['variance_percent']:+.1f}%)")
    # Show the Paid line only when marked — "not marked paid" is noise; the
    # ask-if-paid step covers the unpaid case (user preference, 2026-07-09).
    if r.get("paid_at"):
        print(f"Paid:       ✓ {r['paid_at'][:16]}")
    for d in r["discrepancies"]:
        print(f"\n  → {d}")
    if r.get("line_report"):
        print(f"\n  → [line pass] {r['line_report']}")
    if r.get("_settled"):
        print(f"\n  → settled: already {r['_settled']} — not re-judged")
    print(f"{'='*78}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate Yusen/Taylored invoices against the rate card.")
    ap.add_argument("invoice_number", nargs="?", help="Invoice number to validate")
    ap.add_argument("--rates", help="Path to a rates JSON pulled live from Notion (recommended)")
    ap.add_argument("--list-all", action="store_true", help="Validate the 20 most recent invoices")
    ap.add_argument("--limit", type=int, default=20, help="How many invoices for --list-all")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a text report")
    ap.add_argument("--write", action="store_true",
                    help="Persist the result to validated_at/validation_status on the invoice row")
    ap.add_argument("--init", action="store_true",
                    help="Add the validation tracking columns if missing, then continue/exit")
    ap.add_argument("--mark-paid", action="store_true",
                    help="Mark the invoice paid (only after the user explicitly confirms payment)")
    ap.add_argument("--unmark-paid", action="store_true",
                    help="Clear a paid mark set by mistake")
    ap.add_argument("--report-file",
                    help="With --mark-paid: store this file's text as the approval report "
                         "(use when a richer document-level validation was performed); "
                         "omitted → a report is auto-composed from the validation result")
    ap.add_argument("--no-pdf", action="store_true",
                    help="Skip the PDF line-level pass (header-level validation only)")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR),
                    help=f"Invoice-PDF cache directory (default {DEFAULT_PDF_DIR}; "
                         "also settable via YUSEN_PDF_CACHE)")
    args = ap.parse_args()
    pdf_dir = Path(args.pdf_dir)

    client = bigquery.Client(project=PROJECT)

    if args.mark_paid or args.unmark_paid:
        if not args.invoice_number:
            ap.error("--mark-paid/--unmark-paid require an invoice_number")
        if _missing_columns(client):
            init_columns(client)
        report = None
        if args.mark_paid:
            if args.report_file:
                report = Path(args.report_file).read_text().strip()
            else:
                inv = fetch_invoice(args.invoice_number, client)
                if inv:
                    rates0, _ = load_rates(args.rates)
                    from datetime import date as _d
                    prior = inv.get("validation_report") or ""
                    if _DEEPER_BLOCK.search(prior):
                        # A deeper review is on file — the payment card cites it
                        # instead of restating what a header pass cannot see.
                        tags = sorted({m.group(1).upper()
                                       for m in _DEEPER_BLOCK.finditer(prior)})
                        report = (f"Payment confirmed by the user on "
                                  f"{_d.today().isoformat()}. Basis: the "
                                  f"{', '.join(tags)} review already on this row; "
                                  f"header total ${float(inv['amount']):,.2f}. No "
                                  f"re-validation performed at payment time.")
                    else:
                        report = compose_report(validate(inv, rates0),
                                                paid_date=_d.today().isoformat())
        ok, msg = mark_paid(args.invoice_number, client, paid=args.mark_paid, report_text=report)
        print(f"{'✓' if ok else '⚠️ '} {args.invoice_number}: {msg}"
              + (" + report stored" if (ok and report) else ""))
        if not (args.write or args.list_all):
            return

    # Provision the tracking columns. Explicit via --init; also auto-run if a
    # --write was requested but the columns aren't there yet (self-provisioning).
    if args.init:
        init_columns(client)
        if not (args.invoice_number or args.list_all):
            return
    elif args.write and _missing_columns(client):
        print("ℹ️  Validation columns missing — adding them (one-time setup)…")
        init_columns(client)

    rates, source = load_rates(args.rates)
    if "SNAPSHOT" in source and not args.json:
        print(f"⚠️  Using {source}.\n   Pull the live Notion rate card for an authoritative check (see SKILL.md).")

    if args.list_all:
        q = f"SELECT DISTINCT invoice_number FROM `{TABLE}` ORDER BY invoice_number DESC LIMIT {args.limit}"
        results = []
        for row in client.query(q).result():
            inv = fetch_invoice(row["invoice_number"], client)
            if inv:
                r = validate(inv, rates)
                apply_vas_pallet_check(inv, r)
                apply_vas_labor_check(inv, r)
                apply_msa_conflicts(inv, r)
                if not args.no_pdf:
                    _line_pass_keeping_disputes(inv, r, pdf_dir)
                if args.write:
                    r["_written"], r["_write_msg"] = write_result(r, client, inv)
                results.append(r)
                if not args.json:
                    print_report(r)
        if args.json:
            print(json.dumps({"rate_source": source, "results": results}, indent=2))
        else:
            _print_rollup(results)
        return

    if not args.invoice_number:
        ap.error("provide an invoice_number or --list-all")

    inv = fetch_invoice(args.invoice_number, client)
    if not inv:
        msg = {"invoice_number": args.invoice_number, "status": "error",
               "error": "Invoice not found in yusen_invoices"}
        print(json.dumps(msg, indent=2) if args.json else f"❌ Invoice {args.invoice_number} not found.")
        sys.exit(1)

    r = validate(inv, rates)
    apply_vas_pallet_check(inv, r)
    apply_vas_labor_check(inv, r)
    apply_msa_conflicts(inv, r)
    if not args.no_pdf:
        _line_pass_keeping_disputes(inv, r, pdf_dir)
    if args.write:
        ok, msg = write_result(r, client, inv)
        r["_written"], r["_write_msg"] = ok, msg
    if args.json:
        print(json.dumps({"rate_source": source, **r}, indent=2))
    else:
        print_report(r)
        if args.write:
            print(f"{'✓ Written to' if r['_written'] else '⚠️  Not written ('+r['_write_msg']+') —'} "
                  f"validated_at / validation_status on the invoice row.")


def _print_rollup(results: list) -> None:
    by = {"valid": 0, "discrepancy": 0, "disputed": 0, "needs_detail": 0, "error": 0}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"\n{'='*78}\nSUMMARY: {len(results)} invoices")
    print(f"  ✅ valid {by['valid']}   🚨 discrepancy {by['discrepancy']}   "
          f"⚑ disputed {by['disputed']}   ⏳ needs detail {by['needs_detail']}   "
          f"❌ error {by['error']}\n{'='*78}")
    flagged = [r for r in results if r["status"] == "discrepancy"]
    if flagged:
        print("\nDISCREPANCIES:")
        for r in flagged:
            print(f"  🚨 {r['invoice_number']} ({r['invoice_type']}, {r['warehouse']}): "
                  f"${r['variance']:,.2f} ({r['variance_percent']:+.1f}%)")
    disputed = [r for r in results if r["status"] == "disputed"]
    if disputed:
        print("\nMSA DISPUTES (short-pay/hold):")
        for r in disputed:
            amt = f"${r['variance']:,.2f}" if r.get("variance") else "amount needs worksheet recompute"
            print(f"  ⚑ {r['invoice_number']} ({r['invoice_type']}, {r['warehouse']}): {amt}")

    if any("_written" in r for r in results):
        wrote = sum(1 for r in results if r.get("_written"))
        buffered = [r["invoice_number"] for r in results if r.get("_written") is False]
        print(f"\nPERSISTED: {wrote} written to BigQuery.")
        if buffered:
            print(f"  ⚠️  {len(buffered)} still in streaming buffer (re-run later): "
                  f"{', '.join(buffered)}")


if __name__ == "__main__":
    main()
