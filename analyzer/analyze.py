"""extract -> ask Claude -> validate. The orchestration layer.

The validator is doing the real work of the quality gate: the schema guarantees
shape, but only checking quotes against the source text catches the model
drifting, paraphrasing, or inventing a number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import Extraction, extract, reviewable
from .prompt import SYSTEM, build_user_message
from .schema import Analysis

DEFAULT_MODEL = "claude-opus-5"

_PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")
_NUMBER = re.compile(r"\b\d[\d,.]*\b")


@dataclass
class Problem:
    finding_index: int   # -1 for analysis-level problems
    kind: str
    detail: str


def validate(analysis: Analysis, ex: Extraction) -> list[Problem]:
    """Everything a well-formed-but-wrong analysis can still get wrong."""
    problems: list[Problem] = []
    text_by_id = {u.id: u.text for u in ex.units}

    for i, f in enumerate(analysis.findings):
        unit_text = text_by_id.get(f.anchor_id)
        if unit_text is None:
            problems.append(Problem(i, "bad-anchor", f"anchor_id {f.anchor_id!r} is not a real unit"))
            continue

        if f.quote not in unit_text:
            problems.append(Problem(i, "quote-not-substring",
                                    f"quote {f.quote!r} is not a verbatim substring of unit {f.anchor_id}"))

        ph_in_rewrite = set(_PLACEHOLDER.findall(f.rewrite))
        ph_declared = {n.placeholder for n in f.needs_from_user}
        for missing in ph_in_rewrite - ph_declared:
            problems.append(Problem(i, "placeholder-undeclared",
                                    f"{{{missing}}} used in rewrite with no needs_from_user entry"))
        for unused in ph_declared - ph_in_rewrite:
            problems.append(Problem(i, "placeholder-unused",
                                    f"needs_from_user declares {unused!r} but the rewrite never uses it"))

        # A number in the rewrite that is neither in the quoted source nor wrapped
        # in a placeholder is a likely fabrication — the one thing the brief bans.
        rewrite_wo_ph = _PLACEHOLDER.sub("", f.rewrite)
        new_numbers = set(_NUMBER.findall(rewrite_wo_ph)) - set(_NUMBER.findall(unit_text))
        if new_numbers:
            problems.append(Problem(i, "invented-number",
                                    f"rewrite adds number(s) {sorted(new_numbers)} not in the source and not a placeholder"))

    return problems


@dataclass
class Result:
    analysis: Analysis
    problems: list[Problem]
    extraction: Extraction
    usage: object | None
    model: str


def analyze_cv(path: str, model: str = DEFAULT_MODEL, max_tokens: int = 16000) -> Result:
    import anthropic  # imported here so extract / dry-run work without the SDK

    ex = extract(path)
    units = reviewable(ex.units)
    if not units:
        raise SystemExit("No reviewable lines found — is this a CV .docx with text in the body?")

    client = anthropic.Anthropic()
    resp = client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_user_message(units)}],
        output_format=Analysis,
    )
    analysis = resp.parsed_output
    return Result(
        analysis=analysis,
        problems=validate(analysis, ex),
        extraction=ex,
        usage=getattr(resp, "usage", None),
        model=model,
    )
