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
    badges, the model, the development install and the status note. A section
    is delimited in the README by `:::md <!--- --8<-- [start:name] -->` and
    `:::md <!--- --8<-- [end:name] -->`, and `docs/index.md` pulls it in with
    `:::md --8<-- "README.md:name"`. Edit inside the markers, and the site
    follows.

    Keep the sections link-free, or link absolutely. A relative link resolves
    against `docs/index.md` on the site and against the repository root on GitHub,
    and only one of those can be right.

??? question "I have changed what a model prints"

    Six pages carry a block that a tool writes, and a test compares each block
    to its generator. Regenerate rather than edit, and read the diff:

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

    The Python API pages are generated from the docstrings, so a new class or
    module appears in the next build.

## Naming across the layers

The same construct passes through three layers, and each names it in full. The
suffix says which layer:

| Layer                           | Suffix               | Example                                   |
| ------------------------------- | -------------------- | ----------------------------------------- |
| YAML block (`math_spec.model`)  | `Block`              | `VariableBlock`, `PiecewiseBlock`         |
| Core AST (`math_spec.*_parser`) | `Node`               | `VariableNode`, `DimensionComparisonNode` |
| Program (`math_spec.program`)   | none / `Declaration` | `Variable`, `VariableDeclaration`         |

A node names the coordinate map: the translation
node is `Translate`, whatever `shift` is spelled. Nothing is abbreviated.

## Adding an operator

Start with the grammar, which is usually free because `f(x, k=v)` already
parses. Then declare the signature in `operators.BUILTINS`. It holds the number
of arguments and says which arguments name dimensions, and resolution,
validation and lowering all read it from there. Then write the dimension rule in
`dimensions.py`, the degree verdict in `degree.py`, the node it lowers to in
`program.py`, and the entry in the
[language reference](reference/language/operators.md).

## Submitting changes

--8<-- "CONTRIBUTING.md:docs"
