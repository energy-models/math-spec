<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing

## How to contribute

<div class="grid cards" markdown>

- [:material-bug: Report a bug](https://github.com/energy-models/math-spec/issues/new?template=BUG-REPORT.yml)
- [:material-file-document: Report a docs issue](https://github.com/energy-models/math-spec/issues/new?template=DOCS.yml)
- [:material-lightbulb-on: Request a change](https://github.com/energy-models/math-spec/issues/new?template=FEATURE-REQUEST.yml)
- [:material-chat-question: Ask a question](https://github.com/energy-models/math-spec/discussions)

</div>

The [good first issues](https://github.com/energy-models/math-spec/contribute)
are the bugs and feature requests to start with.

## Setting up a development environment

The project runs in [pixi](https://pixi.prefix.dev/).

1. Install pixi following the
   [official instructions](https://pixi.prefix.dev/latest/installation/).
1. In your clone of the repository, install the environment and the commit hooks:

```sh
pixi install
pixi run pre-commit-install
```

The hooks run on every commit. They format Python, Markdown, YAML and TOML,
lint and type-check the Python, and check the licence headers. These commands run
the same checks and the rest of the gate by hand:

- `pixi run lint`: every commit hook, over every file.
- `pixi run test`: the test suite. `pixi run test-coverage` adds coverage.
- `pixi run compile-tex`: print every model in the tree to standalone LaTeX and
  compile it.
- `pixi run ci`: lint, tests, a strict docs build and the LaTeX compile. This is
  what CI runs. Run it before you push.

## Documentation

The pages under `docs/` are Markdown, built by [MkDocs](https://www.mkdocs.org/)
with the [Material](https://squidfunk.github.io/mkdocs-material/) theme. The
build is strict: a page with no `nav` entry in `mkdocs.yml`, a dead link or a
stale anchor fails it. `pixi run docs-serve` builds the site and serves it at
<http://127.0.0.1:8000>, rebuilding when a page changes.

??? question "I have updated the README.md"

    The home page includes named sections of the README rather than a copy: the
    badges, the model and the status note. A section
    is delimited in the README by `:::md <!--- --8<-- [start:name] -->` and
    `:::md <!--- --8<-- [end:name] -->`, and `docs/index.md` pulls it in with
    `:::md --8<-- "README.md:name"`. Edit inside the markers, and the site
    follows.

    Keep the sections link-free, or link absolutely. A relative link resolves
    against `docs/index.md` on the site and against the repository root on GitHub,
    and only one of those can be right.

??? question "I have changed what a model prints"

    Every page that carries a block a tool writes is listed in
    `tests/test_docs.py`'s `GENERATED` table, and a test compares each block to
    its generator. Regenerate rather than edit, and read the diff:

    ```bash
    pixi run python -m tools.home_math   # docs/index.md and README.md, from examples/dispatch.yaml
    pixi run python -m tools.notation    # docs/reference/notation.md, from tests/typesetting/golden/model.yaml
    pixi run python -m tools.spec_math   # the operator table on docs/reference/language/operators.md
    pixi run python -m tools.gallery     # the example pages, from examples/
    ```

    Each tool takes `--check` to report drift without writing.

??? question "I want to add a new page"

    Add a Markdown file under `docs/`, then add it to the `nav` key in
    `mkdocs.yml`:

    ```yaml
    nav:
      - Home: index.md
      - My Page: my-page.md
    ```

    The module pages under Development are generated from the docstrings, so a
    new module appears in the next build. A new public name also needs its own
    `:::` entry on the [Python API](reference/api.md) page.

## Naming across the layers

The same construct passes through three layers, and each names it in full. The
suffix says which layer:

| Layer                          | Suffix               | Example                                |
| ------------------------------ | -------------------- | -------------------------------------- |
| YAML block (`math_spec.model`) | `Block`              | `VariableBlock`, `PiecewiseBlock`      |
| Syntax (`math_spec.*_parser`)  | `Node`               | `NameNode`, `UnresolvedComparisonNode` |
| Program (`math_spec.program`)  | none / `Declaration` | `Variable`, `VariableDeclaration`      |

A node names the operation, not the verb a file writes. One verb can resolve
to two nodes, so the file's spelling cannot decide the name.

| File verb          | Node                | What the node names                                  |
| ------------------ | ------------------- | ---------------------------------------------------- |
| `sum(over=)`       | `Sum`               | axes removed from the result                         |
| `sum(by=)`         | `Sum` over a `Join` | a join, and the sum over the axes it opens           |
| `at(by=)`          | `Join`              | a join whose groups are one row, with no sum over it |
| `shift(along=)`    | `Translate`         | a re-index along one dimension                       |
| `sum_back(along=)` | `WindowSum`         | a sum over a trailing window                         |

Nothing is abbreviated.

## Adding an operator

Start with the grammar, which is usually free because `f(x, k=v)` already
parses. Then declare the signature in `operators.BUILTINS`. It holds the number
of arguments and says which arguments name dimensions, and resolution reads it
from there. Then write the node in `program.py` and how resolution builds it,
the dimension rule in `dimensions.py`, the degree verdict in `degree.py`, and
the entry in the [language reference](reference/language/operators.md).

## Submitting changes

--8<-- "CONTRIBUTING.md:docs"
