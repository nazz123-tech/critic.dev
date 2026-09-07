"""Page count before/after an edit, via LibreOffice if it's installed.

A longer rewrite can push a one-page CV onto a second page — a regression the
user did not ask for. The apply layer reports the delta so the app can warn
before the edit is accepted. Without `soffice` this degrades to (None, None).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile


def _pdf_pages(pdf: str) -> int | None:
    if shutil.which("pdfinfo"):
        try:
            out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=30).stdout
            m = re.search(r"Pages:\s+(\d+)", out)
            if m:
                return int(m.group(1))
        except Exception:
            pass
    try:
        with open(pdf, "rb") as f:
            hits = len(re.findall(rb"/Type\s*/Page[^s]", f.read()))
        return hits or None
    except OSError:
        return None


def page_count(docx_path: str) -> int | None:
    if not shutil.which("soffice"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
            check=False, capture_output=True, timeout=120,
        )
        pdf = os.path.join(tmp, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        return _pdf_pages(pdf) if os.path.exists(pdf) else None


def delta(before_docx: str, after_docx: str) -> tuple[int | None, int | None]:
    return page_count(before_docx), page_count(after_docx)
