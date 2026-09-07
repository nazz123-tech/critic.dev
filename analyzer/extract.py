"""Turn a CV .docx into a flat list of anchored text units.

A "unit" is the smallest thing a finding can point at: one line or one bullet,
tagged with the section it sits under and the role/item it belongs to, and given
a stable id. The analyzer only ever refers to a unit by its id, and every quote
it makes has to be a substring of that unit's text — see analyzer/analyze.py.

Reused idea from the spike: style and list membership live on the paragraph, so
we can read structure straight off python-docx without rendering anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from docx import Document

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Unit:
    id: str            # stable anchor, e.g. "experience.item2.bullet1"
    kind: str          # "line" | "bullet"  (headings are not reviewed, only used for context)
    section: str       # nearest Heading above, e.g. "Experience"; "" before the first heading
    item: str | None   # nearest non-bullet line under that heading, e.g. "Backend Developer, Kvikk AS"
    text: str          # the paragraph's text, stripped

    def as_prompt_line(self) -> str:
        return f"[{self.id}] {self.text}"


@dataclass
class Extraction:
    units: list[Unit]
    para_by_id: dict = field(default_factory=dict)  # id -> docx paragraph, for the apply step later
    skipped_tables: int = 0                          # paragraphs inside tables we did not look at


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def _is_heading(p) -> bool:
    name = (p.style.name or "") if p.style else ""
    return name.startswith("Heading") or name == "Title"


def _is_bullet(p) -> bool:
    if p._p.find(f".//{WORD_NS}numPr") is not None:
        return True
    name = (p.style.name or "").lower() if p.style else ""
    return "list" in name or "bullet" in name


def extract(path: str) -> Extraction:
    doc = Document(path)

    ex = Extraction(units=[])
    section = ""
    section_slug = "intro"
    item: str | None = None
    bullet_counters: dict[tuple[str, int], int] = {}
    item_index = 0

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        if _is_heading(p):
            section = text
            section_slug = _slug(text)
            item = None
            item_index = 0
            continue

        if _is_bullet(p):
            kind = "bullet"
        else:
            # A non-bullet line directly under a heading is treated as the "item"
            # (a job title, a degree, a project name) and becomes context for the
            # bullets beneath it. It is still reviewable in its own right.
            kind = "line"
            item = text
            item_index += 1

        if kind == "line":
            uid = f"{section_slug}.item{item_index}"
        else:
            bkey = (section_slug, item_index)
            bullet_counters[bkey] = bullet_counters.get(bkey, 0) + 1
            n = bullet_counters[bkey]
            uid = f"{section_slug}.item{item_index}.bullet{n}" if item_index else f"{section_slug}.bullet{n}"

        unit = Unit(id=uid, kind=kind, section=section, item=item if kind == "bullet" else None, text=text)
        ex.units.append(unit)
        ex.para_by_id[uid] = p

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                ex.skipped_tables += sum(1 for cp in cell.paragraphs if cp.text.strip())

    return ex


def reviewable(units: list[Unit]) -> list[Unit]:
    """Units worth sending to the analyzer: skip anything too short to carry a claim."""
    return [u for u in units if len(u.text) >= 12]
