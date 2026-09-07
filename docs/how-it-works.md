# How this project works

Written for someone who is new to Python. Nothing here assumes you have seen a library,
an object, or a decorator before. Every example is real code from this repository, so
when you finish reading you will have read the whole project.

---

## 1. The single idea behind the whole app

A CV is a document. To a human it is a page with headings and bullet points. To a
computer it is just a long soup of characters — unless you give it structure.

So the app does three things, in this order:

```
    a Word file            structured data           a Word file again
   ┌───────────┐          ┌──────────────┐          ┌───────────┐
   │  cv.docx  │  ──────► │  sections,   │  ──────► │  cv.docx  │
   │           │  read    │  bullets,    │  write   │  (better) │
   └───────────┘          │  as data     │          └───────────┘
                          └──────────────┘
                                 ▲
                                 │ the agent reads this
                                 │ and says what is weak
```

**Read it. Criticise the structure. Write the changes back into the same file.**

That last part — *back into the same file* — is the hard bit, and it is what the spike
script exists to test. Everything else in the project sits on top of it.

---

## 2. Python you need, taught from our own code

### A script is a file you run

`spike/make_sample_cv.py` is a script. You run it by typing:

```bash
python3 spike/make_sample_cv.py
```

Python starts at the top of the file and goes down, doing what each line says. That is
the whole model. There is no magic entry point (well — there is one line that looks like
magic, and we explain it at the end of this section).

### Importing: using code other people wrote

```python
from docx import Document
```

Read this as: *"from the toolbox called `docx`, bring in the tool called `Document`."*

`docx` is a **library** — a pile of code someone else wrote and published so you do not
have to figure out the Word file format yourself. You installed it with
`pip install python-docx`. The library is called `python-docx`, but inside your code you
type `docx`. That mismatch is annoying and normal.

### Objects: things that know how to do things

```python
d = Document()
```

`Document()` creates a new, empty Word document and `d` is now a name for it. `d` is an
**object**: a thing that holds data *and* knows how to do things to itself.

You do things to an object with a dot:

```python
d.add_paragraph("Nazar Ismailov")   # d, please add a paragraph
d.save("cv.docx")                   # d, please save yourself to this file
```

`add_paragraph` and `save` are **methods** — functions that belong to the object. The dot
means "belonging to". You will type a lot of dots.

### Values that come back

Notice this line from `make_sample_cv.py`:

```python
name = d.add_paragraph("Nazar Ismailov")
```

`add_paragraph` does something *and hands something back*: the paragraph it just made. We
catch it in the name `name` so we can keep working on it:

```python
name.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

Some methods hand something back, some do not. `d.save(...)` hands back nothing, because
there is nothing useful to say after saving a file.

### Setting properties

```python
r = name.runs[0]
r.bold = True
r.font.size = Pt(22)
```

A property is a value living on an object. You read it and you set it with `=`, like an
ordinary variable. `r.font.size` is a property on a property — `r` has a `font`, and the
font has a `size`. Dots all the way down.

`Pt(22)` means "22 points". Word does not measure text in plain numbers, so python-docx
makes you say which unit you mean. `Pt` came from an import at the top of the file.

### Lists and loops

```python
for b in [
    "Responsible for the backend of the ordering system.",
    "Worked with the frontend team on the checkout flow.",
    "Helped maintain the deployment pipeline.",
]:
    d.add_paragraph(b, style="List Bullet")
```

The square brackets make a **list** — three strings in a row. `for b in [...]` means: *do
the indented part once for each item, calling the current item `b`.* So this adds three
bullet paragraphs, and you wrote the adding code once instead of three times.

**Indentation is not decoration in Python.** The indented line is "inside" the loop. If
you unindent it, it stops being part of the loop and the program changes meaning. This
trips up everyone at first.

### Functions: naming a piece of work

```python
def to_pdf(path):
    ...
    return pdf
```

`def` defines a **function**: a chunk of work with a name, so you can do it repeatedly
without re-typing it. `path` is a **parameter** — a blank that gets filled in when you
call it:

```python
p1 = to_pdf("spike/out/sample_cv.docx")
p2 = to_pdf("spike/out/edited_sample_cv.docx")
```

Same function, two different files. `return` hands a value back to whoever called it.

### Dictionaries: labelled boxes

This is the `fingerprint` function from `docx_roundtrip.py`, slightly trimmed:

```python
def fingerprint(p):
    r = p.runs[0] if p.runs else None
    return {
        "style": p.style.name,
        "bold": r.bold if r else None,
        "is_list": ...,
    }
```

The curly braces make a **dictionary**: values with labels attached, instead of a bare
list where you have to remember that position 2 was the bold flag. You look things up by
label:

```python
before = fingerprint(target)
print(before["style"])       # 'List Bullet'
```

A dictionary is the right shape here because we want to compare a paragraph's look before
and after an edit, label by label. That is exactly what the script prints out.

### Conditions, and the compact form

```python
r = p.runs[0] if p.runs else None
```

Read right to left-ish: *if `p.runs` has anything in it, use the first one; otherwise use
`None`.* This is the short form of:

```python
if p.runs:
    r = p.runs[0]
else:
    r = None
```

`None` is Python's word for "nothing here". An empty list counts as false, which is why
`if p.runs:` means "if there are any runs".

### The magic-looking last line

```python
if __name__ == "__main__":
    main()
```

Every Python file gets a hidden variable called `__name__`. If you *run* the file
directly, Python sets it to the text `"__main__"`. If some other file *imports* your file,
it gets set to the file's name instead.

So this line means: **"only actually do the work if someone ran this file on purpose."**
It lets a file be both a program and a toolbox. Copy the pattern; it becomes obvious after
you have written a few files that import each other.

---

## 3. How Word documents are really built

This is the mental model that makes the rest of the project make sense. Get this and
everything else is detail.

A Word document is a tree:

```
Document
├── Paragraph  "Nazar Ismailov"
├── Paragraph  "Trondheim, Norway · nazar@example.com"
├── Paragraph  "Experience"                       (style: Heading 1)
├── Paragraph  "Backend Developer, Kvikk AS  Jun 2025 – present"
│   ├── Run  "Backend Developer, Kvikk AS"        bold
│   └── Run  "   Jun 2025 – present"              italic
├── Paragraph  "Responsible for the backend…"     (style: List Bullet)
└── Table
    ├── Cell "Languages" │ Cell "Python, JavaScript, SQL"
    └── Cell "Tools"     │ Cell "Git, Docker, Postgres"
```

Two levels matter:

**A paragraph** is a block of text with block-level properties: which style it uses
(`Heading 1`, `List Bullet`, `Normal`), how far it is indented, how much space follows it,
and whether it is part of a numbered or bulleted list.

**A run** is a stretch of text *inside* a paragraph that all looks the same. The moment
formatting changes mid-sentence, Word starts a new run. That is why the job title line
above is two runs: the bold part and the italic part.

This is why the code says `p.runs[0]` so often. `p.text` gives you the words, but the
*look* lives on the runs.

---

## 4. Walking through `make_sample_cv.py`

Its only job is to produce a CV to experiment on, so we are not testing against nothing.

```python
d = Document()                      # a blank Word document

normal = d.styles["Normal"]         # the default style everything inherits
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
```

Change the base style once and every paragraph follows, because styles cascade. Same idea
as CSS if you have met that.

```python
name = d.add_paragraph("Nazar Ismailov")
name.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = name.runs[0]
r.bold = True
r.font.size = Pt(22)
```

Add the paragraph, centre it (a paragraph-level property), then reach into its first run
to make the text big and bold (run-level properties). Paragraph properties and run
properties, exactly as in the tree above.

```python
job = d.add_paragraph()
job.add_run("Backend Developer (part-time), Kvikk AS").bold = True
job.add_run("   Jun 2025 – present").italic = True
```

Here we deliberately build a paragraph with **two runs of different formatting** —
because that is the case that breaks naive editing, and we want our test document to
contain the hard case rather than only easy ones. Note the trick on those lines:
`add_run(...)` hands back the new run, and we set `.bold` on it immediately, in one line.

```python
d.add_heading("Skills", level=1)
t = d.add_table(rows=2, cols=2)
t.style = "Table Grid"
t.cell(0, 0).text = "Languages"
```

Tables are in there on purpose too: real CVs use them constantly, often invisibly, to
line things up. `cell(0, 0)` is row 0, column 0 — counting starts at zero in Python, so
the first row is row 0. You will forget this and be off by one. Everyone does.

---

## 5. Walking through `docx_roundtrip.py` — the real experiment

### The question

Rewritten bullets are *longer* than the ones they replace. "Responsible for the backend
of the ordering system" (51 characters) becomes a sentence with a stack, a scale and a
result (205 characters). Does the document survive that?

### The trick, and why it works

```python
def set_text_keep_format(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text)
        return False
    mixed = len({(r.bold, r.italic, r.underline, r.font.name, r.font.size) for r in runs}) > 1
    runs[0].text = text
    for r in runs[1:]:
        r._element.getparent().remove(r._element)
    return mixed
```

Line by line:

- `if not runs:` — an empty paragraph has no runs to reuse, so just add one and leave.
- The `mixed = ...` line asks: *do the runs in this paragraph look different from each
  other?* It builds a set (curly braces, no labels = a **set**, which throws away
  duplicates) of each run's formatting. If more than one distinct look survives, the
  paragraph had mixed formatting. We do not fail on this — we warn, because we are about
  to flatten it.
- `runs[0].text = text` — **the whole trick.** Keep the first run and write new words
  into it. It keeps its font, size, bold and colour, so the new text inherits the old
  look. The paragraph keeps its style, indent and bullet, because those never lived on
  the run in the first place.
- `for r in runs[1:]:` — `runs[1:]` means "everything except the first". Delete them, or
  the old words would still be sitting there after our new text.
- `r._element.getparent().remove(r._element)` — the ugly line. python-docx has no
  `delete_run()`, so we drop below it to the raw XML that a .docx is really made of and
  remove the element by hand. **The leading underscore is a convention meaning "internal,
  not part of the promised API"** — using it is a small risk we take knowingly, and a
  thing to check if a future library version breaks.

### Proving it worked

```python
before = fingerprint(target)
...edit...
after = fingerprint(Document(out_docx).paragraphs[idx])
```

Note what happens in the middle: we save the file and **open it again from disk**. We
check the saved document, not the in-memory one, because the round trip through the file
format is exactly what we are testing. Checking the object we just edited would prove
nothing.

Then the script prints every property side by side:

```
  PASS  style        'List Bullet' -> 'List Bullet'
  PASS  is_list      True -> True
  ...
  pages : 1 -> 1
  VERDICT  styling survived — option B is buildable
```

### The honest limit

The script says this itself, at the end:

> Automated checks cannot see layout. Open both PDFs before you trust this.

Our checks compare properties. They cannot see that a table now overlaps the footer or
that the last line fell onto page two. That is why the script also converts both files to
PDF with LibreOffice — so a human can look. **Write checks for what a machine can judge,
and put a human in front of the rest.** That is a general lesson, not a Python one.

---

## 6. Try it yourself

Small changes, in rising order of difficulty. Break things on purpose; the file is
regenerated by running the script again.

1. **Make the rewrite short.** In `docx_roundtrip.py`, change `REPLACEMENT` to
   `"Built the ordering backend."` and re-run. Watch the character count and page count
   change in the output.
2. **Make it absurdly long.** Paste the same sentence in five times. Does the CV spill
   onto page two? That is the regression the real app has to warn about.
3. **Hit the mixed-formatting case.** Run with
   `--match "Backend Developer"`. That paragraph is the bold + italic one. You should get
   the `WARN` line — read it and look at the resulting PDF to see what was lost.
4. **Print what is in a document.** Write a new file, `spike/inspect.py`:

   ```python
   from docx import Document

   d = Document("spike/out/sample_cv.docx")
   for i, p in enumerate(d.paragraphs):
       print(i, p.style.name, "|", len(p.runs), "runs |", p.text[:60])
   ```

   `enumerate` gives you the position *and* the item, so you get numbered output. Run it
   on your own CV and you will immediately see how Word actually structured it — this one
   tiny script is the most useful debugging tool in the project.
5. **Rewrite two bullets in one pass.** Change `pick_target` so it returns a list of
   matching paragraphs, then loop over them. This is the step that turns the experiment
   into something the app could actually use, because a real review produces many findings
   at once.

---

## 7. Words you will keep meeting

| Word | What it means here |
|---|---|
| library / package | Code someone else wrote that you install and import. `python-docx` is one. |
| object | A thing that holds data and knows how to act on itself. `Document`, `Paragraph`, `Run`. |
| method | A function belonging to an object. You call it with a dot: `d.save(...)`. |
| property | A value belonging to an object: `run.bold`, `paragraph.style`. |
| list / dict / set | Ordered items `[...]`, labelled items `{"k": v}`, unique unlabelled items `{...}`. |
| run | A stretch of text inside a paragraph that all looks the same. The unit of formatting in Word. |
| style | A named bundle of formatting (`Heading 1`, `List Bullet`) that many paragraphs share. |
| XML | The tagged text format a .docx is actually made of. A .docx is a zip of XML files — rename one to .zip and look inside. |
| headless | Running an app with no window. `soffice --headless` converts files without opening LibreOffice on screen. |
| spike | A throwaway experiment written to answer one risky question before committing to a plan. |

---

## 8. What comes next, and what you will need for it

Step 2 is the analyzer: send a CV's structure to a model and get back findings that name
the exact weak bullet. For that you will meet:

- **JSON** — the same shape as a Python dictionary, written as text, used to send data
  between programs. If you understand dicts, you understand JSON.
- **Talking to an API** — sending a request over the internet and getting a reply, using
  a library like `httpx` or the model provider's own.
- **Schemas** — telling the model the exact shape of the answer you will accept, so you
  get data you can rely on instead of a paragraph of prose you have to parse.

Everything in this document — dicts, functions, loops, objects — is what that is built
out of. There is nothing new coming that is harder than what you have just read.
