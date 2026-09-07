"""Offline checks for the parts that don't need the API: extraction, the
validator, and the apply layer.
Run: python -m analyzer.selftest spike/out/sample_cv.docx
"""
from __future__ import annotations

import os
import sys
import tempfile

from .analyze import validate
from .apply import apply_findings
from .extract import extract
from .schema import Analysis, Finding, NeedFromUser, Severity


def main(path: str) -> int:
    ex = extract(path)
    ids = [u.id for u in ex.units]
    assert len(ids) == len(set(ids)), "unit ids are not unique"
    first_bullets = [i for i in ids if i.endswith(".bullet1")]
    assert first_bullets, f"expected bullet numbering to start at 1, got {ids}"
    assert ex.tables > 0, "sample CV has a table; extractor reported none"
    assert any(u.in_table for u in ex.units), "expected some units to come from table cells"

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

    # apply layer: a fillable whole-bullet rewrite lands; an unfilled one is skipped
    whole = Finding(
        anchor_id=a_bullet.id, section=a_bullet.section, item=a_bullet.item,
        quote=a_bullet.text, severity=Severity.high, why="w",
        rewrite="Rebuilt the thing, handling {n} requests/day.",
        needs_from_user=[NeedFromUser(placeholder="n", question="how many?")],
    )
    unfilled = Finding(
        anchor_id=ex.units[-1].id, section=ex.units[-1].section, item=None,
        quote=ex.units[-1].text, severity=Severity.low, why="w",
        rewrite="Something with {a_missing_value} in it.",
        needs_from_user=[NeedFromUser(placeholder="a_missing_value", question="?")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "edited.docx")
        rep = apply_findings(path, Analysis(summary="s", findings=[whole, unfilled]),
                             out_path=out, fills={"n": "4,000"}, check_pages=False)
        assert os.path.exists(out), "apply wrote no file"
        assert [x.anchor_id for x in rep.applied] == [a_bullet.id], rep.applied
        assert any("a_missing_value" in s.reason for s in rep.skipped), rep.skipped
        assert "4,000" in extract(out).para_by_id[a_bullet.id].text, "rewrite not in output"

    print(f"selftest OK — {len(ex.units)} units, ids like {ids[:3]}…, "
          f"validator caught {sorted(kinds)}, apply wrote + skipped as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "spike/out/sample_cv.docx"))
