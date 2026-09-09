---
name: docs-writing
description: House rules for writing documentation prose in this project — what a page is for, how it is shaped, and the sentence-level bar. Use when writing a new documentation page or section, or when adding prose to an existing one.
---

# Writing docs here

These are the rules a page has to meet. They apply to prose you write now and
to prose already on the page: a page that does not meet them is not finished,
whoever wrote it.

The reader knows the domain — optimisation models, YAML, a bit of maths — and
knows nothing about this project. Write for that person.

## The voice

Plain, direct, professional. Explain to a smart adult who does not work on
this project. They are not stupid, they are unfamiliar.

- **Say the answer first**, then why. A section that builds to its point makes
  the reader hold everything until the end.
- **Short sentences, short words.** "Use" not "utilise", "before" not "prior
  to", "so" not "in order that". A term the language owns — `piecewise`, a
  coordinate, a `where`, a macro — is never swapped for a plainer word, but
  everything around it is.
- **Snappy is short, not clipped.** A four-word fragment that costs a re-read
  is worse than the ten-word sentence it replaced.
- **Confident and flat.** State the rule. Do not hedge with "generally",
  "typically", "in most cases" unless the exception is real, and then name the
  exception instead.
- **No enthusiasm, no marketing.** No "powerful", "seamless", "elegant",
  "simply", "just", "of course", "as you can see", "note that". Each of these
  either tells the reader their confusion is their fault, or says nothing.
- **No jokes and no asides.** A reader hitting this page is stuck, and reads
  it in a hurry.
- **No apology and no warning voice.** "Unfortunately", "be careful",
  "beware" — say what happens and what to write instead.
- **One spelling convention per page.** The tree is mixed and this skill does
  not settle it: match the page you are on.

## 1. Decide what the page is before writing a sentence

Two questions decide it, and they work on a paragraph as well as a page:

1. Does it inform **action** or **cognition**?
2. Does it serve **acquiring** a skill or **applying** one?

| Kind        | Informs   | Serves  | Answers                                               | Nav section · folder                                           |
| ----------- | --------- | ------- | ----------------------------------------------------- | -------------------------------------------------------------- |
| Tutorial    | action    | acquire | "Get me a first file that loads and prints"           | Tutorials · `docs/`                                            |
| How-to      | action    | apply   | "I have this task"                                    | How-to guides · `docs/howto/`                                  |
| Reference   | cognition | apply   | "What exactly does X accept, and what does it print?" | Reference · `docs/reference/`, model pages in `docs/examples/` |
| Explanation | cognition | acquire | "Why is it like this?"                                | About · `docs/about/`                                          |

The nav and the tree are both arranged by kind. A new page goes in the folder
of its kind and under the nav section of the same name; the first tutorial
opens the `Tutorials:` section, above the how-to guides. The model pages sit at
the end of the Reference section, after the pages a reader looks things up in.
A worked example is neither a tutorial nor a how-to: it teaches no path and
names no task, it shows that the language says a model.

Each kind has one job, and one thing it must not do:

- **A tutorial is a lesson.** One path, every step shows a result, and the
  reader finishes with a file that loads and prints. It explains nothing and
  offers no choice: a choice is a how-to leaking in.
- **A how-to is a recipe.** The title names the goal, the body is the steps,
  and the reader is assumed competent. It neither teaches nor explains.
- **Reference describes, and only describes.** One consistent format, and a
  structure that mirrors what it describes: the language pages follow the
  file's keys, the typeset page follows the three formats and their options.
  No rationale, no instruction.
- **Explanation is the one place for why.** Context, alternatives and opinion
  live here and nowhere else, within what `AGENTS.md` sends to the PR.

**A model page is reference in its own form.** It answers "can the language
say my model, and what does the file mean?", and its shape is a witness rather
than a table: a paragraph of the page's own, then the file verbatim and the
math the typesetter prints from it. The block is written by `tools/gallery.py`
between `<!-- gallery:begin -->` and `<!-- gallery:end -->`; the paragraph is
the only prose on the page, and it says what the model is and the one or two
things worth reading for, which the `description:` line in the file does not.
The PyPSA pages add a generated block per rung, holding the reference script
and what PyPSA solved it to. Every model is a file under `examples/`, loaded
by the suite and compiled by the LaTeX gate, and `tests/test_docs.py` holds
each block to its generator byte for byte. The catalogue in
`docs/examples/index.md` is hand-written: one bullet per page, saying why a
reader would open it.

**The Python API pages are built, not written.** mkdocs renders
`reference/math_spec/` from the docstrings at build time, so their prose is
the docstring rules in `AGENTS.md`.

Mixing kinds is the most common failure. Rationale inside a reference section
makes the rules unskimmable, and rules inside an explanation page make the
argument unreadable. Most rationale belongs in the PR, per `AGENTS.md`; what
survives into an explanation page is the part a user needs to make decisions.

The language is documented here and only here. A page says what a file may
contain, what it means, what the loader refuses, and what the typesetter
prints from it. What a consumer does with a spec — the data it binds, how it
solves, what it reads back — is that consumer's page, not this tree's
([what counts as language](../../../docs/about/what-counts-as-language.md)).
A rule about a consumer says only what the file guarantees it
([reading a loaded model](../../../docs/reference/language/reading.md)).

Answer the two questions before starting. If a page needs two kinds, it is
two sections with two headings, or two pages.

## 2. Open with the purpose

One sentence, above the first rule, saying what the page is for and who needs
it. No throat-clearing, no restating the title, no "in this section we will".

Then the shape a reader needs, in this order:

1. **Shape** — the smallest thing they can write that works.
2. **Rules** — what is accepted, and what is refused.
3. **Rationale** — only where it changes what they write.

The subtlest rule gets the most support: a list, a worked example, a table.
The obvious rule gets one sentence.

## 3. Every rule carries an example, and the example is real

- **Show the input and its result side by side.** YAML next to the maths it
  renders, a call next to its output. Never in a later subsection.
- **Every generated block is checked; a hand-written fence is not.** The
  model on an example page, the notation page, the operator table and the
  home model come from a generator, and `tests/test_docs.py` holds them to
  it. `reading.md` is run by `tests/test_reading_page.py`, which checks every
  `expression  # value` line. The `NAME` production on the expressions page
  is compared to the parser's. A YAML fence anywhere else is read by nothing,
  so load it before committing: write it to a file and run
  `pixi run python -m math_spec check model.yaml`. Write the fragment as a
  whole model where the page allows it; a fragment that cannot stand alone is
  one the reader cannot run either.
- **Quote error messages whole.** This language's messages name the rewrite,
  and a truncated quote drops exactly the half that teaches.
- **Prefer the smallest example that still shows the point.** A model with two
  dimensions and one variable teaches; a realistic one hides the rule in
  scenery.
- **Show the refused form too**, where the refusal is the lesson, with the
  message it produces.

## 4. Headings are the table of contents

- **Topic nouns, sentence case.** "Quadratic expressions", not "Degree 2 in
  the math, degree 1 beside it". The test: a reader who types the subject into
  the search box should land on this heading.
- **Never a conclusion the reader cannot parse yet.** A heading is read before
  the section, so it cannot depend on it.
- **One `##` per idea.** A section that needs a paragraph of preamble before
  its first rule is two sections.

## 5. Bold lead-ins are the skim layer

A reader who reads only the bold lead-ins of a list must come away correct and
complete. Write them that way deliberately: each is a claim, not a label.

```markdown
- **Absence spreads through arithmetic.** A sum with one absent term is absent.
```

not

```markdown
- **Arithmetic.** ...
```

## 6. Vocabulary

- **Gloss house vocabulary at first use** — _spec_, _program_, _declaration_,
  _dimension_, _coordinate_, _frame_, _lookup_, _absence_, _macro_, _named
  expression_, _reported expression_, _escape_. One clause with a concrete
  instance: "one point of it, one generator in one snapshot, is a coordinate".
- **Gloss every acronym and domain term at first use**, in parentheses, six
  words or fewer.
- **One word per concept, for the whole page.** _dims_, _dimensions_ and
  _axis_ are three words, and a reader counts three ideas. Vary nothing for
  rhythm.
- **No overloaded words** — do not write "the case in point" beside a `cases:`
  keyword.
- **Gloss where the term is used**, and link the reference page that owns it
  rather than redefine it. The ten-rules table on the
  [language index](../../../docs/reference/language/index.md) says which page
  owns which rule; a second definition drifts.
- **Link the reference section at a construct's first mention** on the page.
  A construct links to its page under `docs/reference/language/`; a verb —
  `to_spec`, `to_latex` — links to `docs/reference/typeset.md` or the API
  page.

## 7. Sentences

The bar, and it is checkable:

1. **One idea per sentence.** Median at or under 20 words; over 25 is where a
   newcomer re-reads.
2. **Active voice, with a real subject.** "The loader refuses it before any
   data binds", not "the refusal comes before any data binds". An abstract
   noun as subject is the single biggest reason technical prose reads
   expert-only.
3. **State the rule in things, then in abstractions.** "One generator at one
   snapshot cannot have two previous statuses" before "two values at one
   coordinate is not a quantity".
4. **Address the reader for what they do.** "Close such a hole in one of three
   ways". A rule about the language is about the language, not about "the
   modeller".
5. **A full stop, not an em dash, between two independent clauses.** Both
   halves having a subject and a verb is the test. Keep the dash for an aside
   inside one clause, and use few.
6. **No fronted participles** that suspend the subject: "Having no mask to
   narrow its frame, it is the one that…".
7. **No elided possessives**: "The dims of a cased one cannot", not "A cased
   one's cannot".
8. **A pronoun names its subject again** once a clause has intervened.
9. **No double negatives, no metaphor stacked on metaphor, no relative clauses
   stacked without _that_.**
10. **Say it once.** The same claim in three paragraphs is load-bearing in
    none.

Measure before committing, and put the numbers in the commit body. The number
is evidence, not a target: a list-shaped sentence may be long and clear.

````bash
pixi run python - docs/reference/language/absence.md <<'PY'
import re, sys

SKIP = ('#', '$$', '|', '>', '    ')
ABBREV = re.compile(r'(?:\b[A-Za-z]|\d|\be\.g|\bi\.e|\betc|\bcf|\bFig|\bvs)\.$')


def blocks(path: str) -> list[str]:
    """Prose blocks: one per paragraph and one per list item, code stripped.

    Inline code is stripped per line, so a code span reflowed across a line
    break cannot pair backticks across the whole page and eat the prose
    between them.
    """
    out, buf, incode, incomment = [], [], False, False
    for line in open(path).read().split('\n'):
        if incomment:
            incomment = '-->' not in line
            continue
        if line.startswith('<!--') and '-->' not in line:
            incomment = True
            continue
        if line.startswith('```'):
            incode = not incode
            continue
        line = re.sub(r'`[^`]*`', 'X', line)
        if incode or line.startswith(SKIP):
            continue
        item = re.match(r'\s*(?:[-*+]|\d+\.)\s+(.*)', line)
        if not line.strip() or item:
            if buf:
                out.append(' '.join(buf))
            buf = [item.group(1)] if item else []
            continue
        buf.append(line.strip())
    if buf:
        out.append(' '.join(buf))
    return [b for b in out if b.strip()]


def sentences(block: str) -> list[str]:
    """Split on terminal punctuation, rejoining across `1.5`, `e.g.` and initials."""
    parts, cur = [], ''
    for chunk in re.split(r'(?<=[.!?])\s+', block):
        cur = f'{cur} {chunk}'.strip()
        if not ABBREV.search(cur):
            parts.append(cur)
            cur = ''
    if cur:
        parts.append(cur)
    return [p for p in parts if p.strip()]


w = sorted(len(s.split()) for b in blocks(sys.argv[1]) for s in sentences(b))
print('n', len(w), 'avg', round(sum(w) / len(w), 1), 'median', w[len(w) // 2], 'over25', sum(x > 25 for x in w))
PY
````

## 8. What does not go on the page

- **History.** "Previously this used to…", "renamed from…" — that is git.
- **Argument for a settled decision.** That is the PR.
- **A promise about the future.** "Will support…" ages into a lie.
- **Anything that duplicates another page.** One fact, one home; link instead.
  A second copy drifts silently. The README is pulled into `docs/index.md` as
  snippets, so a sentence that appears on both is edited once, in the README.
- **A rule of an engine.** How a spec is bound to data, solved, or read back
  is a consumer's page. Here a consumer is named only for what the file
  guarantees it.
- **Generated content.** The model and its math on every example page and the
  rung blocks on the PyPSA pages (`tools/gallery.py`), the table on
  `docs/reference/notation.md` (`tools/notation.py`), the operator table on
  `docs/reference/language/operators.md` (`tools/spec_math.py`), and the home
  model on `docs/index.md` and in the README (`tools/home_math.py`) are
  written by a tool between `<!-- …:begin -->` and `<!-- …:end -->` markers.
  Change the generator, then read the diff. `tests/test_docs.py`'s
  `GENERATED` table is the list.

## 9. Mechanics

- **A new page needs a nav entry in `mkdocs.yml`.** The docs build is
  `--strict`, so a page without one fails it, as do a dead cross-link and a
  stale anchor.
- **A new page carries the SPDX header** — `math-spec contributors`,
  `CC-BY-4.0` — in an HTML comment at the top, or as YAML comments inside the
  front matter where the page has one, as `docs/index.md` does. `reuse lint`
  is part of `pixi run lint`.
- **Inside `docs/`, link relatively; outside it, write the full GitHub URL.**
  A relative link above `docs/` renders in the repo and fails the strict
  build. Anchors follow GitHub's slug rules on the site too, so an anchor that
  works in the repo works on the site.
- **A card body is indented four spaces**, under `<!-- prettier-ignore -->`,
  or the card falls out of its list and `tests/test_docs.py` says so.
- **A generated block lands with its plumbing**: the page in
  `.prettierignore`, with a comment naming the tool, and the tool in
  `tests/test_docs.py`'s `GENERATED` table.
- **A diagram carries alt text**, and no rule is stated in colour alone.
- **Tables for what varies along one axis** — accepted keys, the operators,
  the formats. Prose for what has an order or a reason.

## 10. Gates

```bash
pixi run docs-build                                               # --strict, so a dead anchor is a failure
pixi run pytest tests/test_docs.py tests/test_reading_page.py -q  # the generated blocks, and the page that is run
pixi run lint                                                     # prettier, typos, reuse
```

`pixi run compile-tex` too when a model under `examples/` changed. Say which
gate ran and what was left unrun.
