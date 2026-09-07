"""Step 1 spike: can we replace a CV bullet with a LONGER sentence and keep the styling?

This is the question that decides whether "edit in place, layout preserved" is
buildable. Reflow is the risk: a rewritten bullet is almost always longer than
the one it replaces.

Two ways to write the replacement back:

  plain text   the default. One uniform run, taking the look of the bullet's
               dominant run. Right when the bullet is a single run; lossy when
               it has, say, a bold lead-in — the script prints WARN in that case.

  --segments   the replacement is a list of {text, bold, italic} pieces, spliced
               back run by run so a bold lead-in stays bold and the rest stays
               regular. This is the shape the rewriter should emit for any bullet
               where the plain path would WARN.

Usage:
    python3 spike/docx_roundtrip.py <cv.docx> [--match "text to find"] [--no-pdf]
    python3 spike/docx_roundtrip.py <cv.docx> --segments [--match "text to find"]

It prints a per-check verdict and writes the edited file to spike/out/.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn

OUT_DIR = "spike/out"

# Deliberately much longer than a typical weak bullet — this is the stress test.
REPLACEMENT = (
    "Built the ordering backend (Node + Postgres) serving roughly 4,000 orders a day, "
    "and cut checkout errors from 3.1% to 0.4% by adding idempotent retries and a "
    "dead-letter queue for failed payment callbacks."
)

# The same rewrite, but as pieces — a bold lead-in and a regular remainder. This
# is what --segments splices in, and the shape a real rewriter would return for a
# bullet that starts with a bold verb.
REPLACEMENT_SEGMENTS = [
    {"text": "Rebuilt the ordering backend", "bold": True},
    {
        "text": (
            " (Node + Postgres) to serve roughly 4,000 orders a day, cutting checkout "
            "errors from 3.1% to 0.4% with idempotent retries and a dead-letter queue "
            "for failed payment callbacks."
        ),
        "bold": False,
    },
]


def fingerprint(p):
    """Everything about a paragraph we expect to survive the edit."""
    r = p.runs[0] if p.runs else None
    pf = p.paragraph_format
    return {
        "style": p.style.name if p.style else None,
        "font_name": r.font.name if r else None,
        "font_size": r.font.size.pt if (r and r.font.size) else None,
        "bold": r.bold if r else None,
        "italic": r.italic if r else None,
        "color": str(r.font.color.rgb) if (r and r.font.color and r.font.color.type is not None) else None,
        "left_indent": pf.left_indent.pt if pf.left_indent else None,
        "space_after": pf.space_after.pt if pf.space_after else None,
        # numbering can come from the paragraph itself or from its style
        "is_list": (
            p._p.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr") is not None
            or bool(p.style and "list" in p.style.name.lower())
        ),
    }


def run_layout(p):
    """(text, bold, italic) per run — for checking a segmented rewrite survived."""
    return [(r.text, bool(r.bold), bool(r.italic)) for r in p.runs]


def dominant_run(runs):
    """The run carrying most of the paragraph's text — the look a rewrite inherits.

    Better than always taking runs[0]: a bullet like "**Led** the migration ..."
    has a tiny bold run first, and flattening the whole line to *that* would make
    it all bold. The longest run is almost always the body text.
    """
    return max(runs, key=lambda r: len(r.text)) if runs else None


def set_text_keep_format(p, text):
    """Replace paragraph text with one run, keeping the dominant run's formatting.

    Returns True if the paragraph had mixed formatting across runs (meaning some
    of it is being flattened — use set_runs_from_segments to keep a bold lead-in).
    """
    runs = p.runs
    if not runs:
        p.add_run(text)
        return False
    mixed = len({(r.bold, r.italic, r.underline, r.font.name, r.font.size) for r in runs}) > 1
    keep = dominant_run(runs)
    keep.text = text
    for r in list(runs):
        if r is not keep:
            r._element.getparent().remove(r._element)
    return mixed


def set_runs_from_segments(p, segments):
    """Rebuild the paragraph's runs from [{text, bold?, italic?, underline?}, ...].

    Every new run starts as a copy of the dominant run's character formatting
    (font, size, colour), then applies the per-segment overrides. So a bold
    lead-in stays bold and the body stays regular, while both keep the bullet's
    font — and the paragraph keeps its style, indent and numbering, which never
    lived on the runs.
    """
    template = dominant_run(p.runs)
    template_rpr = template._element.find(qn("w:rPr")) if template is not None else None

    for r in list(p.runs):
        r._element.getparent().remove(r._element)

    for seg in segments:
        run = p.add_run(seg["text"])
        if template_rpr is not None:
            run._element.insert(0, deepcopy(template_rpr))  # rPr must be the first child of w:r
        for prop in ("bold", "italic", "underline"):
            if prop in seg:
                setattr(run, prop, seg[prop])


def pick_target(doc, match=None, prefer_mixed=False):
    """The bullet we will rewrite: a match, else the first list paragraph.

    prefer_mixed skips single-run bullets, so --segments lands on one that
    actually has a lead-in to preserve.
    """
    for i, p in enumerate(doc.paragraphs):
        if match:
            if match.lower() in p.text.lower():
                return i, p
            continue
        if not (fingerprint(p)["is_list"] and len(p.text.strip()) > 20):
            continue
        if prefer_mixed and len(p.runs) < 2:
            continue
        return i, p
    return None, None


def to_pdf(path):
    if not shutil.which("soffice"):
        return None
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", OUT_DIR, path],
        check=False, capture_output=True, timeout=120,
    )
    pdf = os.path.join(OUT_DIR, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def page_count(pdf):
    if not pdf:
        return None
    try:
        out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=30).stdout
        m = re.search(r"Pages:\s+(\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    with open(pdf, "rb") as f:
        return len(re.findall(rb"/Type\s*/Page[^s]", f.read())) or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cv")
    ap.add_argument("--match", help="substring of the bullet to replace")
    ap.add_argument("--segments", action="store_true",
                    help="splice the replacement in run by run, preserving a bold lead-in")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    doc = Document(a.cv)
    idx, target = pick_target(doc, a.match, prefer_mixed=a.segments)
    if target is None:
        sys.exit("Found no bullet to rewrite. Pass --match with text from a real bullet.")

    before = fingerprint(target)
    before_layout = run_layout(target)
    old_text = target.text

    if a.segments:
        set_runs_from_segments(target, REPLACEMENT_SEGMENTS)
        new_text = "".join(s["text"] for s in REPLACEMENT_SEGMENTS)
        mixed = False
    else:
        new_text = REPLACEMENT
        mixed = set_text_keep_format(target, new_text)

    out_docx = os.path.join(OUT_DIR, "edited_" + os.path.basename(a.cv))
    doc.save(out_docx)

    reloaded = Document(out_docx).paragraphs[idx]
    after = fingerprint(reloaded)
    after_layout = run_layout(reloaded)

    print(f"\n  original : {old_text}")
    print(f"  rewritten: {new_text}")
    print(f"  length   : {len(old_text)} -> {len(new_text)} chars "
          f"(+{len(new_text) - len(old_text)})")
    if a.segments:
        print(f"  runs     : {before_layout}")
        print(f"          -> {after_layout}")
    print()

    checks = []
    for k in before:
        checks.append((k, before[k], after[k], before[k] == after[k]))
    if a.segments:
        expected = [(s["text"], bool(s.get("bold")), bool(s.get("italic"))) for s in REPLACEMENT_SEGMENTS]
        checks.append(("run_formatting", expected, after_layout, after_layout == expected))

    width = max(len(k) for k, *_ in checks)
    for k, b, af, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {k.ljust(width)}  {b!r} -> {af!r}")

    if mixed:
        print("\n  WARN  the paragraph had mixed formatting across runs and the plain "
              "path flattened it to one look. Re-run with --segments to keep the lead-in.")

    if not a.no_pdf:
        p1, p2 = to_pdf(a.cv), to_pdf(out_docx)
        c1, c2 = page_count(p1), page_count(p2)
        print(f"\n  pages    : {c1} -> {c2}" + ("  (grew — check the last page)" if c1 and c2 and c2 > c1 else ""))
        print(f"  pdfs     : {p1}  |  {p2}")

    failed = [k for k, _, _, ok in checks if not ok]
    if failed:
        verdict = f"styling changed: {', '.join(failed)}"
    elif mixed:
        verdict = ("the paragraph's own style survived, but its internal formatting was "
                   "flattened to one look — fine for a plain bullet, not for one with a "
                   "bold lead-in. --segments handles that case.")
    else:
        verdict = "styling survived — option B is buildable"
    print("\n  VERDICT  " + verdict)
    print("  Automated checks cannot see layout. Open both PDFs before you trust this.\n")


if __name__ == "__main__":
    main()
