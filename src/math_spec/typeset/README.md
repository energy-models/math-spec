# `typeset/` — the model, printed

A third consumer of the resolved core AST. It builds no model, binds no data
and never reaches the plan; it walks the same typed tree both lanes consume and
prints it.

| Module | Role |
|---|---|
| `__init__.py` | `typeset` / `to_latex` / `to_markdown` / `to_typst`, and the `FORMATS` registry |
| `walk.py` | resolved AST → `Line`s. Every decision about the **math**, written once |
| `format.py` | the seam: what a format must spell, and the operator vocabulary |
| `symbols.py` | which symbol a name gets, and the `SymbolTable` sidecar that overrides it |
| `latex.py` | amsmath — the format that lands in a journal |
| `typst.py` | Typst — the format that compiles without a toolchain |
| `markdown.py` | GitHub-flavoured Markdown — LaTeX math, Markdown document layer |

## The split, and why it is here

`walk.py` decides where a bracket changes the reading, which dimension a
reduction binds, that a mask belongs on the ∀ rather than in the equation, and
that a translation shows at the leaf it re-indexes. A `Format` decides that a
sum is `\sum_{…}` or `sum_(…)`.

Those are different questions, and the reason they are in different files is
the same reason `relational/sinks/` exists: with one module the second format
becomes a *copy of the walk*, and two copies of a walk are two walks that can
disagree about what the model says. This is the same divergence hard rule 3
spends its budget preventing at the other end of the pipeline — and it matters
more here than it looks, because a typeset model is what a reader checks the
math against.

Two rules keep it honest:

- **A walk emits bare math** — no `$`, no environment. The format wraps it with
  `math()` when embedding in prose, so the walk never knows which mode it is in.
- **A format spells; it never decides.** No method in `format.py` takes an AST
  node or a schema. If a format had to look at the model to answer, the
  question belongs in the walk.

## Notation

Symbols are derived by default, so a model prints with no setup at all. A
`SymbolTable` overrides that, and `symbols=` takes it in whichever form the
caller already has — the CLI's `--symbols` is the path case:

```python
lps.to_latex('dispatch.yaml', symbols='dispatch.symbols.yaml')  # a path
lps.to_latex('dispatch.yaml', symbols={'notation': 'latex', 'names': {'load': r'\ell'}})  # a dict
lps.to_latex('dispatch.yaml', symbols=lps.SymbolTable.load(table))  # the object
```

The dict is the same sections as the file (`notation`, `dimensions`, `names`) —
it is what the YAML parses to, not a flat `{name: symbol}` map. Whichever form,
the table is checked against the model: a key naming nothing is an error with
the near miss, because a silent typo is a symbol that never applies and a reader
who never finds out.

Every value is a spelling, printed verbatim — nothing parses or translates it.
`notation` says which language the table is written in; a format that reads the
other one refuses. Everything past that comparison is the caller's.

The table carries **notation only**. What a declaration *is* — the prose in the
legend's right-hand column — is the model's own `description:`, read straight
off the block, because it is the model talking about itself rather than a reader
choosing symbols. It travels with the file, survives a rename and needs no
sidecar; the price is that it must be plain prose, since the same words are set
by every format.

## Adding a format

1. A module here with a class satisfying `Format` — atoms, structure, document,
   and a spelling for every name in `OPERATOR_NAMES`.
2. A row in `FORMATS` in `__init__.py`. The CLI verb comes from the key.
3. Nothing in `walk.py`. If you need to change it, either the walk is making a
   syntax decision it should not, or the seam is missing a method — fix that
   rather than special-casing.

`markdown.py` is the cheap case worth knowing about: Markdown has no math of
its own, so it *forwards* every math method to `LatexFormat` and writes only
the document layer. Forwarding, not subclassing — inheritance would silently
absorb any method later added to `LatexFormat`, and since the two differ
exactly in the document methods, the silent case is a `\paragraph` in a
Markdown file.

`tests/typeset/test_typeset.py` runs the shared expectations against **every** entry in
`FORMATS`, so a new format inherits the suite. Two of them are the point: every
operator name is spelled, and no format leaks another's syntax.

## Verified, not assumed

LaTeX and Typst are **compiled** in CI, not just string-matched. LaTeX needs a
two-package apt install; Typst is a pip wheel, so the suite compiles it
in-process. Structural checks (brace balance, environment nesting,
`\left`/`\right` pairing) run too — they are what a *generator* gets wrong —
but they are not a compile, and a malformed `\mathcal` passes every one of them.
