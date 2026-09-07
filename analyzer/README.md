# Step 2 — the analyzer

**Question:** is the feedback actually good, across real CVs? Structure and
round-tripping (step 1) don't matter if the findings aren't sharper than what a
friend says over coffee. This step is the quality gate.

## What it produces

One `Analysis` per CV, and nothing else — no prose. Each `Finding`:

| field | what it holds |
|---|---|
| `anchor_id` | the unit the finding points at, e.g. `experience.item1.bullet1` |
| `quote` | a **verbatim substring** of that unit — the weak span |
| `severity` | `critical` / `high` / `medium` / `low` |
| `why` | why it's weak, ≤ 2 sentences, specific to this line |
| `rewrite` | the improved line; may contain `{placeholder}` tokens |
| `needs_from_user[]` | one `{placeholder, question}` per token in the rewrite |

The rewriter never invents a number, name, date, tech, or scale. If a stronger
line needs a figure the CV doesn't give, the figure becomes a `{placeholder}` and
a matching question — the app collects the answer before offering the rewrite.

## Run it

```bash
pip install -r requirements.txt

# With a key — the automated run:
export ANTHROPIC_API_KEY=...
python -m analyzer path/to/cv.docx                 # review, print findings
python -m analyzer path/to/cv.docx --json          # raw Analysis as JSON
python -m analyzer path/to/cv.docx --model claude-sonnet-5

# No key, $0 — iterate on the prompt and schema:
python -m analyzer path/to/cv.docx --dry-run       # print the exact prompt + extraction
python -m analyzer path/to/cv.docx --check FILE     # validate + render an Analysis JSON (FILE or -)
python -m analyzer.selftest spike/out/sample_cv.docx   # extraction + validator

# Worked example (findings written by hand against the sample, then checked):
python -m analyzer spike/out/sample_cv.docx --check analyzer/examples/sample_cv.analysis.json

# Apply the rewrites and write a new .docx:
python -m analyzer spike/out/sample_cv.docx \
  --apply analyzer/examples/sample_cv.analysis.json \
  --fill orders_per_day="4,000" --fill checkout_metric="checkout errors" \
  --fill improvement="38%" --fill failed_deploy_reduction="around half" \
  --fill assignments_count="60"
```

`--check` runs any `Analysis` — from a real call, a hand-written draft, or a
free model — through the same validator and formatter. Useful for tuning the
prompt before spending anything, and as a fixture for step 3's UI.

## Applying findings — `--apply`

`analyzer/apply.py` turns an `Analysis` into an edited `.docx`, reusing the
spike's in-place technique (`analyzer/docxedit.py`):

- `{placeholder}` tokens in a rewrite are filled from `--fill K=V` (repeatable).
  A rewrite with an **unfilled** placeholder is skipped and reported — the app's
  cue to ask the user, never to guess.
- Whole-line quotes → the paragraph's text is replaced, keeping the dominant
  run's formatting; style, list numbering and indent survive.
- Part-of-line quotes → replaced inside the single run that contains them.
- A quote that **spans several runs** (e.g. a date that starts mid-run) is
  skipped: `partial replacement not supported yet`.
- `--only I,J` restricts to those finding indices (shown as `#N` by `--check`);
  `--out` sets the path (default `edited_<name>.docx` beside the input).
- If LibreOffice is installed, the report shows the page count before/after and
  warns when the CV gained a page.

`--check` and `--apply` are the whole loop, no key: extract → findings (by hand
or model) → validate → apply → re-check the output.

Default model is `claude-opus-5` (quality gate — worth it). Production cost
tuning is a later step, not this one.

## How it works

1. `extract.py` — walk the DOCX in reading order, emit one `Unit` per line/bullet,
   each tagged with its section and the role it sits under, each given a stable
   id. Recurses into table cells (row-major, which matches the visual order of
   the sidebar layouts CVs use) and nested tables; cell-sourced units carry
   `in_table=True`.
2. `prompt.py` — a system prompt that defines what counts as a finding and the
   no-invention rule; the CV goes in as `[id] text` lines grouped by section.
3. `analyze.py` — `client.messages.parse(..., output_format=Analysis)`, then
   `validate()`:
   - every `anchor_id` is a real unit
   - every `quote` is a verbatim substring of its unit
   - every `{placeholder}` has a `needs_from_user` entry and vice versa
   - no number appears in a rewrite that isn't in the source or a placeholder

   The schema guarantees shape; `validate()` is what actually catches the model
   drifting or fabricating.

## The quality gate — pass criteria

Run against **≥ 20 real CVs** (varied: students, career-changers, senior, non-native
English). For each, record:

| criterion | bar |
|---|---|
| Parses | 100% — `messages.parse` returns a valid `Analysis` |
| Anchors clean | 0 `bad-anchor` / `quote-not-substring` problems |
| No fabrication | 0 `invented-number` problems; missing figures show up as `needs_from_user` |
| Signal | ≥ 90% of findings are ones a good human reviewer would also flag |
| Not padded | roughly 5–12 findings; no nitpicking of already-strong lines |
| Catches the obvious | every clear duty-not-result / unquantified bullet is found |

Step 3 does not start until this holds. Collect the 20 CVs first (consent +
delete after — see the pre-launch legal note), then log a row per CV.

## Known gaps

- **Bold pseudo-headings.** A sidebar that uses a bold line ("Skills", "Contact")
  instead of a real Heading style is not recognised as a section break — its
  content lands under whatever section preceded it. Only styled headings
  (`Heading 1`…) start a new section.
- **Strict-schema optionals.** `Finding.item` is nullable; if the API's strict
  json-schema mode rejects it, make it a plain `str` (empty when absent).
- **Cross-run partial quotes.** `--apply` skips a quote that spans multiple runs.
  Handling it means splicing at run level; `docxedit.set_runs_from_segments` is
  the hook, but the analyzer would need to emit segmented rewrites.
- **Bold lead-in flattening.** A whole-line rewrite of a bullet like
  `**Led** the migration…` flattens it to one look; `--apply` flags this
  (`bold lead-in flattened`). Same fix as above.
