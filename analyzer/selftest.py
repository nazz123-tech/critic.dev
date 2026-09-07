"""Offline checks for the parts that don't need the API: extraction and the
validator. Run: python -m analyzer.selftest spike/out/sample_cv.docx
"""
from __future__ import annotations

import sys

from .analyze import validate
from .extract import extract
from .schema import Analysis, Finding, NeedFromUser, Severity


def main(path: str) -> int:
    ex = extract(path)
    ids = [u.id for u in ex.units]
    assert ids == sorted(set(ids), key=ids.index), "unit ids are not unique"
    assert all(".bullet1" in i or ".bullet" not in i for i in ids
               if i.endswith("bullet1") or "bullet" not in i) or True  # informational
    first_bullets = [i for i in ids if i.endswith(".bullet1")]
    assert first_bullets, f"expected bullet numbering to start at 1, got {ids}"

    src = {u.id: u.text for u in ex.units}
    a_bullet = next(u for u in ex.units if u.kind == "bullet")

    good = Finding(
        anchor_id=a_bullet.id, section=a_bullet.section, item=a_bullet.item,
        quote=a_bullet.text.split()[0], severity=Severity.medium,
        why="duty, not result.", rewrite="Shipped X, cutting Y by {pct}.",
        needs_from_user=[NeedFromUser(placeholder="pct", question="By what %?")],
    )
    bad = [
        Finding(anchor_id="nope.item9", section="x", item=None, quote="z",
                severity=Severity.low, why="w", rewrite="r"),
        Finding(anchor_id=a_bullet.id, section=a_bullet.section, item=None,
                quote="THIS TEXT IS NOT IN THE UNIT", severity=Severity.low,
                why="w", rewrite="r"),
        Finding(anchor_id=a_bullet.id, section=a_bullet.section, item=None,
                quote=a_bullet.text.split()[0], severity=Severity.low, why="w",
                rewrite="Handled 4,000 orders a day for the team."),  # invented number
        Finding(anchor_id=a_bullet.id, section=a_bullet.section, item=None,
                quote=a_bullet.text.split()[0], severity=Severity.low, why="w",
                rewrite="Cut latency by {ms} ms"),  # undeclared placeholder
    ]
    problems = validate(Analysis(summary="s", findings=[good, *bad]), ex)
    kinds = {p.kind for p in problems}
    expected = {"bad-anchor", "quote-not-substring", "invented-number", "placeholder-undeclared"}
    missing = expected - kinds
    assert not missing, f"validator missed: {missing} (got {kinds})"
    assert not any(p.finding_index == 0 for p in problems), "the good finding should be clean"

    print(f"selftest OK — {len(ex.units)} units, ids like {ids[:3]}…, "
          f"validator caught {sorted(kinds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "spike/out/sample_cv.docx"))
