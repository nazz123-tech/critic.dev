"""The finding schema — the whole point of step 2.

The analyzer returns an Analysis and nothing else: no prose, no chat. Every
field here is something the app will render or act on directly. If a field is
hard for the model to fill reliably, that is a signal the schema is wrong, not
that the field should become free text.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"   # a recruiter bins the CV over this
    high = "high"           # clearly weakens the application
    medium = "medium"       # worth fixing, not fatal
    low = "low"             # minor wording / consistency


class NeedFromUser(BaseModel):
    """A number or fact the rewrite needs and the CV does not contain.

    The rewrite carries the matching token as `{placeholder}`. The app collects
    answers, substitutes them, and only then offers the rewrite. The model must
    never guess the value.
    """
    placeholder: str = Field(description="snake_case token used verbatim in the rewrite, e.g. orders_per_day")
    question: str = Field(description="the specific question to put to the user, answerable in a few words")


class Finding(BaseModel):
    anchor_id: str = Field(description="id of the unit this refers to, copied exactly from the input")
    section: str = Field(description="the unit's section, e.g. Experience")
    item: str | None = Field(default=None, description="the role/item the unit sits under, if any")
    quote: str = Field(description="the exact span of the unit's text that is weak — a verbatim substring")
    severity: Severity
    why: str = Field(description="why it is weak — concrete, at most two sentences, no generic advice")
    rewrite: str = Field(description="the improved line; may contain {placeholder} tokens for missing facts")
    needs_from_user: list[NeedFromUser] = Field(
        default_factory=list,
        description="one entry per {placeholder} in the rewrite; empty if the rewrite invents nothing",
    )


class Analysis(BaseModel):
    summary: str = Field(description="one or two sentences naming the single biggest recurring problem")
    findings: list[Finding]
