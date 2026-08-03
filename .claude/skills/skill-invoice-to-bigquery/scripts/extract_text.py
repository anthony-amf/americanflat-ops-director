#!/usr/bin/env python3
"""Extract the text layer from one or more invoice PDFs.

These invoices are digitally generated (not scanned), so a plain text
extraction with PyMuPDF is fast, deterministic, and faithful to the
original layout - which is exactly what the model needs to map the
invoice onto the canonical schema.

Usage:
    python extract_text.py invoice1.pdf [invoice2.pdf ...]
    python extract_text.py *.pdf --json        # machine-readable output

Plain mode prints each file's text under a clear header so the model can
read it straight from the tool output. --json emits a list of
{"file", "pages", "text"} objects instead.

If a PDF has no extractable text (i.e. it's a scanned image), the script
says so explicitly rather than returning empty output - that's the signal
to fall back to an OCR path (the `pdf` skill) for that file.
"""
import argparse
import json
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit(
        "PyMuPDF is required. Install it with:\n"
        "    python -m pip install pymupdf\n"
    )


def extract_one(path: str) -> dict:
    doc = fitz.open(path)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages).strip()
    return {"file": path, "pages": len(pages), "text": text}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdfs", nargs="+", help="PDF file path(s)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    results = []
    for path in args.pdfs:
        try:
            results.append(extract_one(path))
        except Exception as exc:  # noqa: BLE001 - surface any read error per file
            results.append({"file": path, "pages": 0, "text": "", "error": str(exc)})

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    for r in results:
        print("=" * 72)
        print(f"FILE: {r['file']}  |  pages: {r['pages']}")
        print("=" * 72)
        if r.get("error"):
            print(f"[ERROR reading file: {r['error']}]")
        elif not r["text"]:
            print(
                "[NO TEXT LAYER FOUND - this PDF is likely scanned. "
                "Use the `pdf` skill to OCR it, then feed that text in.]"
            )
        else:
            print(r["text"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
