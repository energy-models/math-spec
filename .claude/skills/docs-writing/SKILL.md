---
# SPDX-FileCopyrightText: math-spec contributors
# SPDX-License-Identifier: CC-BY-4.0
name: docs-writing
description: House rules for writing documentation prose in this project — what a page is for, how it is shaped, and the sentence-level bar. Use when writing a new documentation page or section, or when adding prose to an existing one.
---

# Writing docs here

These are the rules a page has to meet. They apply to prose you write now and
to prose already on the page: a page that does not meet them is not finished,
whoever wrote it.

The reader knows the domain — optimization models, YAML, a bit of maths — and
knows nothing about this project. Write for that person.

## The voice

Plain, direct, professional. Explain to a smart adult who does not work on
this project. They are not stupid, they are unfamiliar.

- **Say the answer first**, then why. A section that builds to its point makes
  the reader hold everything until the end.
- **Short sentences, short words.** "Use" not "utilise", "before" not "prior
  to", "so" not "in order that". A term the language owns — `piecewise`, a
  coordinate, a frame — is never swapped for a plainer word, but everything
  around it is.
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

Four kinds of page, and one page is one kind:

| Kind        | Answers                        | Lives in                      |
| ----------- | ------------------------------ | ----------------------------- |
| Tutorial    | "Get me a first working model" | `docs/index.md`, installation |
| How-to      | "I have this task"             | `docs/examples/`              |
| Reference   | "What exactly does X accept?"  | `docs/reference/`             |
| Explanation | "Why is it like this?"         | `docs/about/`                 |

Mixing them is the most common failure. Rationale inside a reference section
makes the rules unskimmable, and rules inside an explanation page make the
argument unreadable. Most rationale belongs in the PR, per `AGENTS.md`; what
survives into an explanation page is the part a user needs to make decisions.

Say the kind out loud before starting. If a page needs two kinds, it is two
sections with two headings, or two pages.

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
- **Every YAML example loads.** Paste it through `to_spec` before committing.
  Parse with `math_spec._yaml.parse_yaml`, not `yaml.safe_load` — a key like
  `on:` is a boolean under YAML 1.1, and the stock loader fails on a page that
  is correct. Most examples are fragments; complete them from the prose around
  them and load the whole thing.
- **Quote error messages whole.** This project's messages name the rewrite,
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

- **Gloss house vocabulary at first use** — _coordinate_, _frame_, _mask_,
  _dims_, _region_, _row_, _broadcast_. One clause with a concrete instance:
  "one point of it, one snapshot for one generator, is a coordinate".
- **Gloss every acronym and domain term at first use**, in parentheses, six
  words or fewer.
- **One word per concept, for the whole page.** _dims_, _dimensions_ and
  _frame_ are three words, and a reader counts three ideas. Vary nothing for
  rhythm.
- **No overloaded words** — do not write "the case in point" beside a `cases:`
  keyword.
- **Gloss where the term is used.** Do not invent a glossary page.
- **Link the reference section at a construct's first mention** on the page.

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
pixi run python - docs/reference/language/expressions.md <<'PY'
import re, sys

SKIP = ('#', '$$', '|', '>', '    ')
ABBREV = re.compile(r'(?:\b[A-Za-z]|\d|\be\.g|\bi\.e|\betc|\bcf|\bFig|\bvs)\.$')


def blocks(path: str) -> list[str]:
    """Prose blocks: one per paragraph and one per list item, code stripped.

    Inline code is stripped per line, because prettier reflows a code span
    across a line break and a document-wide regex then pairs backticks across
    the whole page and eats the prose between them.
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
  A second copy drifts silently.
- **Generated content.** Anything between `<!-- gallery:begin -->` and
  `<!-- gallery:end -->`, the pages in `tests/test_docs.py`'s `GENERATED`
  table, the golden `.out` files and the schema are written by a tool. Change
  the generator.

## 9. Mechanics

- **A new page needs a nav entry in `mkdocs.yml`.** The docs build is
  `--strict`, so a page without one fails it, as do a dead cross-link and a
  stale anchor.
- **A new file needs an SPDX header** or an entry in `REUSE.toml`.
- **A generated page belongs in `.prettierignore`**, or the formatter and its
  generator fight over it.
- **A diagram carries alt text**, and no rule is stated in colour alone.
- **Tables for what varies along one axis** — accepted keys, operator
  precedence. Prose for what has an order or a reason.

## 10. Gates

```bash
pixi run lint         # prettier reflows markdown; run it before reading the diff
pixi run docs-build   # --strict, so a dead anchor is a failure
pixi run pytest tests/test_docs.py -q
```

Say which gate ran and what was left unrun.
