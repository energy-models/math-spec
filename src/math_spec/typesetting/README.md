<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# `typeset/` — the model, printed

This package is a consumer of the resolved core syntax tree. It builds no model
and binds no data. It walks the typed tree that `to_spec` validates, and prints
it.

| Module        | Role                                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------------------ |
| `__init__.py` | `typeset` / `to_latex` / `to_markdown` / `to_typst`, `typeset_declaration`, and the `FORMATS` registry |
| `walk.py`     | resolved syntax tree to `Line`s. Every decision about the **math**, written once                       |
| `format.py`   | the boundary: what a format must spell, and the operator vocabulary                                    |
| `symbols.py`  | which symbol a name gets, and the `SymbolTable` sidecar that overrides it                              |
| `latex.py`    | amsmath, the format that lands in a journal                                                            |
| `typst.py`    | Typst, the format that compiles without a toolchain                                                    |
| `markdown.py` | GitHub-flavoured Markdown: LaTeX math, with a Markdown document layer                                  |

## Why the walk and the formats are separate files

`walk.py` makes the decisions about the math. It decides where a bracket changes
the reading, which dimension a reduction binds, that a mask belongs on the ∀
rather than in the equation, and that a translation shows at the leaf it
re-indexes.

A `Format` makes a much smaller decision: that a sum is written `\sum_{…}` or
`sum_(…)`.

Those are different questions, and they live in different files. With one
module, the second format becomes a _copy of the walk_. Two copies of a walk are
two walks that can disagree about what the model says. That matters more here
than it looks, because a typeset model is what a reader checks the math against.

Two rules keep the split honest:

- **A walk emits bare math.** No `$`, and no environment. The format wraps the
  math with `math()` when it embeds it in prose, so the walk never knows which
  mode it is in.
- **A format spells; it never decides.** No method in `format.py` takes a
  syntax-tree node or a schema. If a format had to look at the model to answer a
  question, that question belongs in the walk.

## Notation

Symbols are derived by default, so a model prints with no setup at all.

A `SymbolTable` overrides the derived symbols. `symbols=` takes the table in
whichever form the caller already has. The `--symbols` flag on the command line
is the path case:

```python
math_spec.to_latex('dispatch.yaml', symbols='dispatch.symbols.yaml')  # a path
math_spec.to_latex('dispatch.yaml', symbols={'notation': 'latex', 'names': {'load': r'\ell'}})  # a dict
math_spec.to_latex('dispatch.yaml', symbols=math_spec.SymbolTable.load(table))  # the object
```

The dict has the same sections as the file, which are `notation`, `dimensions`
and `names`. It is what the YAML parses to, and not a flat `{name: symbol}` map.

Whichever form you use, the table is checked against the model. A key that names
nothing is an error, and the message gives the near miss. Without that check, a
silent typo would be a symbol that never applies, and a reader who never finds
out.

Every value is a spelling, and it is printed exactly as written. Nothing parses
or translates it. `notation` says which language the table is written in, and a
format that reads the other language refuses the table. Everything past that
comparison is the caller's business.

The table carries **notation only**. What a declaration _is_, which is the prose
in the right-hand column of the legend, comes from the model's own
`description:`, read straight off the block. That is the model talking about
itself, rather than a reader choosing symbols.

A description travels with the file, survives a rename, and needs no sidecar.
The price is that it has to be plain prose, because every format sets the same
words.

## Adding a format

1. Add a module here with a class that satisfies `Format`. That means atoms,
   structure, document, and a spelling for every name in `OPERATOR_NAMES`.
2. Add a row to `FORMATS` in `__init__.py`. The command-line verb comes from the
   key.
3. Change nothing in `walk.py`. If you find that you need to, then either the
   walk is making a syntax decision that it should not make, or `format.py` is
   missing a method. Fix that, rather than adding a special case.

`markdown.py` is the cheap case. Markdown has no math of its own, so it
subclasses `LatexFormat` and overrides only the document layer.

`tests/typesetting/test_typeset.py` runs the shared expectations against
**every** entry in `FORMATS`, so a new format inherits the whole suite. Two of
those expectations are the point: every operator name is spelled, and no format
leaks another format's syntax.

## What CI checks, and what it cannot

LaTeX and Typst are **compiled** in CI, not just matched as strings. LaTeX needs
a two-package apt install. Typst is a pip wheel, so the suite compiles it
in-process.

The structural checks run as well. Those check brace balance, environment
nesting, and `\left` and `\right` pairing, which are the things a _generator_
gets wrong. But a structural check is not a compile. A malformed `\mathcal`
passes every one of them.
