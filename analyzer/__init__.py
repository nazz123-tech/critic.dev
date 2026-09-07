"""Step 2: the CV analyzer — structured, anchored findings, no prose.

    from analyzer.analyze import analyze_cv
    result = analyze_cv("my_cv.docx")           # extract -> Claude -> validate

    from analyzer.apply import apply_findings
    apply_findings("my_cv.docx", result.analysis, fills={...})   # -> edited .docx

CLI: python -m analyzer <cv.docx> [--dry-run] [--json] [--check FILE] [--apply FILE]
"""
from .schema import Analysis, Finding, NeedFromUser, Severity

__all__ = ["Analysis", "Finding", "NeedFromUser", "Severity"]
