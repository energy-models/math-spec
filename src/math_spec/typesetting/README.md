<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# `typeset/` — the model, printed

A consumer of the resolved core AST. It builds no model and binds no data; it
walks the typed tree `to_spec` validates and prints it.

| Module        | Role                                                                            |
| ------------- | ------------------------------------------------------------------------------- |
| `__init__.py` | `typeset` / `to_latex` / `to_markdown` / `to_typst`, and the `FORMATS` registry |
| `walk.py`     | resolved AST → `Line`s. Every decision about the **math**, written once         |
| `format.py`   | the seam: what a format must spell, and the operator vocabulary                 |
| `symbols.py`  | which symbol a name gets, and the `SymbolTable` sidecar that overrides it       |
| `latex.py`    | amsmath — the format that lands in a journal                                    |
| `typst.py`    | Typst — the format that compiles without a toolchain                            |
| `markdown.py` | GitHub-flavoured Markdown — LaTeX math, Markdown document layer                 |

## The split, and why it is here

`walk.py` decides where a bracket changes the reading, which dimension a
reduction binds, that a mask belongs on the ∀ rather than in the equation, and
that a translation shows at the leaf it re-indexes. A `Format` decides that a
sum is `\sum_{…}` or `sum_(…)`.

Those are different questions, and they are in different files because with
one module the second format becomes a _copy of the walk_, and two copies of a
walk are two walks that can disagree about what the model says. That matters
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
math_spec.to_latex('dispatch.yaml', symbols='dispatch.symbols.yaml')  # a path
math_spec.to_latex('dispatch.yaml', symbols={'notation': 'latex', 'names': {'load': r'\ell'}})  # a dict
math_spec.to_latex('dispatch.yaml', symbols=math_spec.SymbolTable.load(table))  # the object
```

The dict is the same sections as the file (`notation`, `dimensions`, `names`) —
it is what the YAML parses to, not a flat `{name: symbol}` map. Whichever form,
the table is checked against the model: a key naming nothing is an error with
the near miss, because a silent typo is a symbol that never applies and a reader
who never finds out.

Every value is a spelling, printed verbatim — nothing parses or translates it.
`notation` says which language the table is written in; a format that reads the
other one refuses. Everything past that comparison is the caller's.

The table carries **notation only**. What a declaration _is_ — the prose in the
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

`markdown.py` is the cheap case: Markdown has no math of its own, so it
subclasses `LatexFormat` and overrides only the document layer.

`tests/typesetting/test_typeset.py` runs the shared expectations against **every** entry in
`FORMATS`, so a new format inherits the suite. Two of them are the point: every
operator name is spelled, and no format leaks another's syntax.

## Verified, not assumed

LaTeX and Typst are **compiled** in CI, not just string-matched. LaTeX needs a
two-package apt install; Typst is a pip wheel, so the suite compiles it
in-process. Structural checks (brace balance, environment nesting,
`\left`/`\right` pairing) run too — they are what a _generator_ gets wrong —
but they are not a compile, and a malformed `\mathcal` passes every one of them.
