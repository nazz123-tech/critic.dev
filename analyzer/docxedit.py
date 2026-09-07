"""Editing a paragraph in place while keeping the document's own formatting.

The productised version of the technique proved in spike/docx_roundtrip.py: the
style, list numbering and indentation live on the paragraph, not the run, so
rewriting run text leaves the document looking like the user's own.

Three ways in, in order of how much of the paragraph they touch:
- replace_span      — swap one substring; used when a finding quotes part of a line
- replace_paragraph — swap the whole line for one uniform run
- set_runs_from_segments — rebuild the line from [{text, bold, ...}] pieces, so a
  bold lead-in survives (the analyzer does not emit segmented rewrites yet, but
  the apply layer is ready for when it does)
"""
from __future__ import annotations

from copy import deepcopy

from docx.oxml.ns import qn


def dominant_run(runs):
    """The run carrying most of the paragraph's text — the look a rewrite inherits."""
    return max(runs, key=lambda r: len(r.text)) if runs else None


def paragraph_is_mixed(p) -> bool:
    """True if the runs don't all look the same (e.g. a bold lead-in)."""
    runs = p.runs
    return len({(r.bold, r.italic, r.underline, r.font.name, r.font.size) for r in runs}) > 1


def replace_paragraph(p, text: str) -> bool:
    """Replace the whole paragraph's text with one run, keeping the dominant run's
    formatting. Returns True if run formatting was mixed and is now flattened."""
    runs = p.runs
    if not runs:
        p.add_run(text)
        return False
    mixed = paragraph_is_mixed(p)
    keep = dominant_run(runs)
    keep.text = text
    for r in list(runs):
        if r is not keep:
            r._element.getparent().remove(r._element)
    return mixed


def replace_span(p, old: str, new: str) -> str:
    """Replace the first `old` with `new` inside paragraph p, keeping formatting.

    Returns which path was taken:
      "whole"     old was the entire paragraph text  -> replace_paragraph
      "run"       old sat inside a single run         -> edited that run
      "cross-run" old spans two or more runs          -> not changed
      "not-found" old is not in the paragraph         -> not changed
    """
    full = p.text
    if old == full or old == full.strip():
        replace_paragraph(p, new)
        return "whole"
    if old not in full:
        return "not-found"
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new, 1)
            return "run"
    return "cross-run"


def set_runs_from_segments(p, segments) -> None:
    """Rebuild the paragraph's runs from [{text, bold?, italic?, underline?}, ...].

    Every new run starts as a copy of the dominant run's character formatting,
    then applies the per-segment overrides.
    """
    template = dominant_run(p.runs)
    template_rpr = template._element.find(qn("w:rPr")) if template is not None else None
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    for seg in segments:
        run = p.add_run(seg["text"])
        if template_rpr is not None:
            run._element.insert(0, deepcopy(template_rpr))  # rPr must be first child of w:r
        for prop in ("bold", "italic", "underline"):
            if prop in seg:
                setattr(run, prop, seg[prop])
