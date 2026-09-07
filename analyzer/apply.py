"""Analysis -> edited .docx.

Takes the findings, fills any {placeholder} tokens from values the user supplied,
and rewrites the anchored paragraphs in place using analyzer/docxedit.py. Anything
it cannot safely do — a missing value, a quote that spans runs — is skipped and
reported, never guessed at.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from docx import Document

from .docxedit import paragraph_is_mixed, replace_span
from .extract import extract_doc
from .pages import delta as page_delta
from .schema import Analysis

_PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")


@dataclass
class Applied:
    anchor_id: str
    how: str            # "whole" | "run"
    old: str
    new: str
    flattened_bold: bool


@dataclass
class Skipped:
    anchor_id: str
    reason: str


@dataclass
class ApplyReport:
    out_path: str
    applied: list[Applied] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    pages_before: int | None = None
    pages_after: int | None = None

    @property
    def grew(self) -> bool:
        return bool(self.pages_before and self.pages_after and self.pages_after > self.pages_before)


def _default_out(cv_path: str) -> str:
    d, name = os.path.split(cv_path)
    return os.path.join(d, "edited_" + name)


def _fill(text: str, fills: dict[str, str]) -> tuple[str, list[str]]:
    missing = [ph for ph in _PLACEHOLDER.findall(text) if ph not in fills]
    for k, v in fills.items():
        text = text.replace("{" + k + "}", v)
    return text, missing


def apply_findings(
    cv_path: str,
    analysis: Analysis,
    out_path: str | None = None,
    fills: dict[str, str] | None = None,
    only: list[int] | None = None,
    check_pages: bool = True,
) -> ApplyReport:
    fills = fills or {}
    doc = Document(cv_path)
    ex = extract_doc(doc)
    report = ApplyReport(out_path=out_path or _default_out(cv_path))

    indices = list(range(len(analysis.findings))) if only is None else only
    edited_anchors: set[str] = set()

    for i in indices:
        if i < 0 or i >= len(analysis.findings):
            report.skipped.append(Skipped(f"#{i}", "no finding with that index"))
            continue
        f = analysis.findings[i]
        p = ex.para_by_id.get(f.anchor_id)
        if p is None:
            report.skipped.append(Skipped(f.anchor_id, "anchor not found in this document"))
            continue
        if f.anchor_id in edited_anchors:
            report.skipped.append(Skipped(f.anchor_id, "an earlier finding already edited this line"))
            continue

        new_text, missing = _fill(f.rewrite, fills)
        if missing:
            report.skipped.append(Skipped(
                f.anchor_id, "needs a value for " + ", ".join("{%s}" % m for m in missing)))
            continue

        was_mixed = paragraph_is_mixed(p)
        how = replace_span(p, f.quote, new_text)
        if how == "not-found":
            report.skipped.append(Skipped(f.anchor_id, "quote is not in the paragraph as written"))
            continue
        if how == "cross-run":
            report.skipped.append(Skipped(
                f.anchor_id, "quote spans multiple runs — partial replacement not supported yet"))
            continue

        edited_anchors.add(f.anchor_id)
        report.applied.append(Applied(
            anchor_id=f.anchor_id, how=how, old=f.quote, new=new_text,
            flattened_bold=(how == "whole" and was_mixed),
        ))

    doc.save(report.out_path)
    if check_pages:
        report.pages_before, report.pages_after = page_delta(cv_path, report.out_path)
    return report
