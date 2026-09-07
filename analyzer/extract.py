"""Turn a CV .docx into a flat list of anchored text units.

A "unit" is the smallest thing a finding can point at: one line or one bullet,
tagged with the section it sits under and the role/item it belongs to, and given
a stable id. The analyzer only ever refers to a unit by its id, and every quote
it makes has to be a substring of that unit's text — see analyzer/analyze.py.

Reused idea from the spike: style and list membership live on the paragraph, so
we can read structure straight off python-docx without rendering anything.

Tables: real CVs routinely put everything inside a layout table (a sidebar
column, or one big invisible grid). We walk the document in reading order and
recurse into every cell, so table content flows into the same section / item /
bullet tracking as body text. Cell reading order is row-major, which is also the
visual order for the sidebar layouts CVs use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from docx import Document
from docx.document import Document as _DocumentClass
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Unit:
    id: str            # stable anchor, e.g. "experience.item2.bullet1"
    kind: str          # "line" | "bullet"  (headings are not reviewed, only used for context)
    section: str       # nearest Heading above, e.g. "Experience"; "" before the first heading
    item: str | None   # nearest non-bullet line under that heading, e.g. "Backend Developer, Kvikk AS"
    text: str          # the paragraph's text, stripped
    in_table: bool = False  # came from inside a table cell

    def as_prompt_line(self) -> str:
        return f"[{self.id}] {self.text}"


@dataclass
class Extraction:
    units: list[Unit]
    para_by_id: dict = field(default_factory=dict)  # id -> docx paragraph, for the apply step later
    tables: int = 0                                  # tables walked (including nested)


@dataclass
class _State:
    section: str = ""
    section_slug: str = "intro"
    item: str | None = None
    item_index: int = 0
    bullet_counters: dict = field(default_factory=dict)


def _iter_block_items(parent):
    """Yield Paragraph and Table children of a document or a cell, in reading order."""
    if isinstance(parent, _DocumentClass):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise TypeError(f"cannot iterate blocks of {type(parent)!r}")
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


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


def _unique(ex: Extraction, uid: str) -> str:
    """Odd table shapes can collide ids; keep them distinct without losing the base."""
    if uid not in ex.para_by_id:
        return uid
    n = 2
    while f"{uid}.{n}" in ex.para_by_id:
        n += 1
    return f"{uid}.{n}"


def _add_paragraph(p, ex: Extraction, st: _State, in_table: bool) -> None:
    text = p.text.strip()
    if not text:
        return

    if _is_heading(p):
        st.section = text
        st.section_slug = _slug(text)
        st.item = None
        st.item_index = 0
        return

    if _is_bullet(p):
        kind = "bullet"
        bkey = (st.section_slug, st.item_index)
        st.bullet_counters[bkey] = st.bullet_counters.get(bkey, 0) + 1
        n = st.bullet_counters[bkey]
        uid = f"{st.section_slug}.item{st.item_index}.bullet{n}" if st.item_index else f"{st.section_slug}.bullet{n}"
    else:
        # A non-bullet line directly under a heading is treated as the "item"
        # (a job title, a degree, a project name) and becomes context for the
        # bullets beneath it. It is still reviewable in its own right.
        kind = "line"
        st.item = text
        st.item_index += 1
        uid = f"{st.section_slug}.item{st.item_index}"

    uid = _unique(ex, uid)
    unit = Unit(
        id=uid,
        kind=kind,
        section=st.section,
        item=st.item if kind == "bullet" else None,
        text=text,
        in_table=in_table,
    )
    ex.units.append(unit)
    ex.para_by_id[uid] = p


def _walk(blocks, ex: Extraction, st: _State, in_table: bool) -> None:
    for block in blocks:
        if isinstance(block, Table):
            ex.tables += 1
            seen = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc in seen:  # merged cells repeat in row.cells
                        continue
                    seen.add(cell._tc)
                    _walk(_iter_block_items(cell), ex, st, in_table=True)
        else:
            _add_paragraph(block, ex, st, in_table)


def extract(path: str) -> Extraction:
    doc = Document(path)
    ex = Extraction(units=[])
    _walk(_iter_block_items(doc), ex, _State(), in_table=False)
    return ex


def reviewable(units: list[Unit]) -> list[Unit]:
    """Units worth sending to the analyzer: skip anything too short to carry a claim."""
    return [u for u in units if len(u.text) >= 12]
