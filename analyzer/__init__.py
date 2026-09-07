"""Step 2: the CV analyzer — structured, anchored findings, no prose.

    from analyzer.analyze import analyze_cv
    result = analyze_cv("my_cv.docx")

CLI: python -m analyzer <cv.docx> [--model ...] [--dry-run] [--json]
"""
from .schema import Analysis, Finding, NeedFromUser, Severity

__all__ = ["Analysis", "Finding", "NeedFromUser", "Severity"]
