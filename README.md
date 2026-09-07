# critic.dev

CV review that is specific enough to act on.

You upload your CV. An agent tells you which exact bullet is weak and why. You fix it
right there — in your own document, keeping your own layout — and export it again.

Most CV tools give you a score and some general advice. This one points at line 3 of
your second job and says: *that sentence describes a duty, not a result, and here is the
version that describes a result.*

## Status

Spike stage. No app yet — one experiment, answered.

| Step | What it answers | State |
|---|---|---|
| 1. DOCX round-trip | Can we edit a CV without wrecking its layout? | done — passes |
| 2. Analyzer prompt + schema | Is the feedback actually good? | next, and it is the gate |
| 3. Thinnest loop | Does the upload → fix → export flow work at all? | not started |
| 4. Limits, privacy, delete | Safe to put a public link on it? | not started |
| 5. Accounts + payments | Free review, paid fix | not started |
| 6. First hundred users | Does anyone want it? | not started |

Each step can invalidate the next one, so they happen in order. Step 2 is the real gate:
if the findings are not visibly sharper than what a friend would say over coffee, no
amount of interface saves the product.

## Getting set up

You need Python 3.10 or newer, and LibreOffice if you want PDF output.

```bash
python3 -m pip install python-docx     # reads and writes Word files
soffice --version                      # should print a version; used for DOCX -> PDF
```

## Running the spike

```bash
python3 spike/make_sample_cv.py                             # makes a test CV
python3 spike/docx_roundtrip.py spike/out/sample_cv.docx    # edits it, checks the damage
```

Try it on a real CV too — that is the test that counts:

```bash
python3 spike/docx_roundtrip.py ~/Documents/my_cv.docx --match "responsible for"
```

## Layout

```
critic.dev/
├── README.md              you are here
├── docs/
│   └── how-it-works.md    the long, beginner-friendly explanation of the code
└── spike/
    ├── README.md          what the experiment proved and what it did not
    ├── make_sample_cv.py  builds a Word CV to experiment on
    ├── docx_roundtrip.py  the experiment itself
    └── out/               generated files, not in git
```

New to Python? Start with `docs/how-it-works.md` — it walks through both scripts line
by line and has exercises at the end.
