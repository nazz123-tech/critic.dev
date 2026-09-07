"""python -m analyzer <cv.docx> [--dry-run] [--json] [--check FILE] [--apply FILE]

--dry-run  print exactly what would be sent to the model; no API call, no key.
--check    read an Analysis as JSON (FILE, or - for stdin), validate it against
           the CV, and print the report. Lets findings produced any way — by a
           real call, or by hand while iterating on the prompt — go through the
           same validator and formatter for free.
--apply    apply an Analysis JSON's rewrites to the CV and write a new .docx.
           --fill K=V (repeatable) supplies values for {placeholder} tokens;
           --only I,J restricts to those finding indices; --out sets the path.
"""
from __future__ import annotations

import argparse
import sys

from .extract import extract, reviewable
from .prompt import SYSTEM, build_user_message
from .schema import Analysis

# Opus 5 list price, for a rough running cost only.
PRICE_IN_PER_MTOK = 5.0
PRICE_OUT_PER_MTOK = 25.0

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEV_MARK = {"critical": "!!", "high": "! ", "medium": "~ ", "low": ". "}


def _dry_run(path: str) -> int:
    ex = extract(path)
    units = reviewable(ex.units)
    msg = build_user_message(units)
    print("=== SYSTEM ===\n" + SYSTEM)
    print("=== USER ===\n" + msg)
    print("=== EXTRACTION ===")
    in_table = sum(1 for u in ex.units if u.in_table)
    print(f"{len(ex.units)} units, {len(units)} reviewable, "
          f"{ex.tables} table(s) walked ({in_table} unit(s) from cells)")
    for u in ex.units:
        flag = "-" if u not in units else ("T" if u.in_table else " ")
        print(f"  {flag} {u.id:<34} {u.kind:<7} {u.text[:70]}")
    return 0


def _print_report(result) -> None:
    a = result.analysis
    print(f"\nSUMMARY  {a.summary}\n")

    orig_index = {id(f): i for i, f in enumerate(a.findings)}
    findings = sorted(a.findings, key=lambda f: (SEV_ORDER.get(f.severity.value, 9), f.anchor_id))
    for f in findings:
        head = (f"{SEV_MARK.get(f.severity.value, '  ')}#{orig_index[id(f)]} "
                f"[{f.severity.value.upper()}] {f.anchor_id}")
        if f.item:
            head += f"  ({f.item})"
        print(head)
        print(f"    quote  : {f.quote}")
        print(f"    why    : {f.why}")
        print(f"    rewrite: {f.rewrite}")
        for n in f.needs_from_user:
            print(f"    ask    : {{{n.placeholder}}} — {n.question}")
        print()

    if result.problems:
        print(f"VALIDATION — {len(result.problems)} problem(s) the output did not satisfy:")
        for p in result.problems:
            where = "analysis" if p.finding_index < 0 else f"finding #{p.finding_index}"
            print(f"    {where}: [{p.kind}] {p.detail}")
        print()
    else:
        print("VALIDATION — clean: every quote is verbatim, every anchor real, no invented numbers.\n")

    u = result.usage
    if u:
        cost = (getattr(u, "input_tokens", 0) / 1e6) * PRICE_IN_PER_MTOK \
             + (getattr(u, "output_tokens", 0) / 1e6) * PRICE_OUT_PER_MTOK
        print(f"USAGE    {result.model}: in={getattr(u, 'input_tokens', '?')} "
              f"out={getattr(u, 'output_tokens', '?')}  ~${cost:.3f}")


def _check(cv_path: str, src: str) -> int:
    from .analyze import Result, validate

    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    analysis = Analysis.model_validate_json(raw)
    ex = extract(cv_path)
    problems = validate(analysis, ex)
    _print_report(Result(analysis=analysis, problems=problems, extraction=ex, usage=None, model="(offline --check)"))
    return 1 if problems else 0


def _apply(cv_path: str, src: str, out: str | None, fills: list[str], only: str | None) -> int:
    from .apply import apply_findings

    fill_map: dict[str, str] = {}
    for pair in fills:
        if "=" not in pair:
            sys.exit(f"--fill expects K=V, got {pair!r}")
        k, v = pair.split("=", 1)
        fill_map[k.strip()] = v
    only_idx = [int(x) for x in only.split(",")] if only else None

    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    analysis = Analysis.model_validate_json(raw)
    report = apply_findings(cv_path, analysis, out_path=out, fills=fill_map, only=only_idx)

    for a in report.applied:
        note = "  (bold lead-in flattened — needs a segmented rewrite)" if a.flattened_bold else ""
        print(f"APPLIED  {a.anchor_id} [{a.how}]{note}")
        print(f"    - {a.old}")
        print(f"    + {a.new}")
    for s in report.skipped:
        print(f"SKIPPED  {s.anchor_id}: {s.reason}")

    print(f"\nwrote {report.out_path}")
    if report.pages_before is not None:
        arrow = f"{report.pages_before} -> {report.pages_after}"
        print(f"pages    {arrow}" + ("   ⚠ grew — the CV gained a page" if report.grew else ""))
    else:
        print("pages    not checked (LibreOffice not installed)")
    return 0 if report.applied else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analyzer")
    ap.add_argument("cv", help="path to a CV .docx")
    ap.add_argument("--model", default=None, help="override the model id")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt and extraction, make no API call")
    ap.add_argument("--json", action="store_true", help="print the raw Analysis as JSON")
    ap.add_argument("--check", metavar="FILE", help="validate + render an Analysis JSON (FILE or -), no API call")
    ap.add_argument("--apply", metavar="FILE", help="apply an Analysis JSON's rewrites to the CV, write a new .docx")
    ap.add_argument("--out", metavar="PATH", help="output path for --apply")
    ap.add_argument("--fill", action="append", metavar="K=V", default=[], help="value for a {placeholder}; repeatable")
    ap.add_argument("--only", metavar="I,J", help="with --apply, restrict to these finding indices")
    a = ap.parse_args(argv)

    if a.dry_run:
        return _dry_run(a.cv)
    if a.check:
        return _check(a.cv, a.check)
    if a.apply:
        return _apply(a.cv, a.apply, a.out, a.fill, a.only)

    try:
        from .analyze import DEFAULT_MODEL, analyze_cv
    except ImportError:
        sys.exit("The 'anthropic' package is not installed. `pip install -r requirements.txt` (or use --dry-run).")

    try:
        result = analyze_cv(a.cv, model=a.model or DEFAULT_MODEL)
    except Exception as e:  # anthropic raises at client construction when no key is resolvable
        name = type(e).__name__
        if "api_key" in str(e).lower() or name in ("AuthenticationError",):
            sys.exit("No Anthropic credentials found. Set ANTHROPIC_API_KEY (or use --dry-run / --check).")
        raise

    if a.json:
        print(result.analysis.model_dump_json(indent=2))
    else:
        _print_report(result)
    return 1 if result.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
