<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing

How to report a problem, set up a checkout, change the docs, and name what you
add to the code.

## How to contribute

Report a problem, request a change or ask a question through these links:

<div class="grid cards" markdown>

- [:material-bug: Report a bug](https://github.com/energy-models/math-spec/issues/new?template=BUG-REPORT.yml)
- [:material-file-document: Report a docs issue](https://github.com/energy-models/math-spec/issues/new?template=DOCS.yml)
- [:material-lightbulb-on: Request a change](https://github.com/energy-models/math-spec/issues/new?template=FEATURE-REQUEST.yml)
- [:material-chat-question: Ask a question](https://github.com/energy-models/math-spec/discussions)

</div>

## Developing `math-spec`

Beginner-friendly bugs and feature requests are the
[good first issues](https://github.com/energy-models/math-spec/contribute).

### Setting up a development environment

The development environment is [pixi](https://pixi.prefix.dev/).

1. Install pixi following the [official instructions](https://pixi.prefix.dev/latest/installation/).
1. In your clone of the `math-spec` repository, install the environment:

```sh
pixi install
```

While you work:

- `pixi run pre-commit-install` installs the checks that run on every commit.
  `ruff` lints and formats the Python files to the [PEP8 standard](https://peps.python.org/pep-0008/),
  [pyrefly](https://pyrefly.org/) type-checks the package, and prettier,
  `typos` and `reuse` check the rest. `pixi run lint` runs the same checks on
  the whole tree.
- `pixi run test` runs the test suite.
- `pixi run test-coverage` runs it with coverage.
- `pixi run compile-tex` renders every model in the tree to standalone LaTeX
  and compiles it, which proves the typeset output is a real document.
- `pixi run ci` runs the four gates CI runs (lint, tests, a strict docs build
  and the LaTeX compile) in the order a failure is cheapest to read. It takes
  about fifteen seconds; run it before you push.

## Documentation

The docs are Markdown under `docs/`, built by [MkDocs](https://www.mkdocs.org/)
with the [Material](https://squidfunk.github.io/mkdocs-material/) theme. A
change updates its page in the same contribution. The cases that come up:

??? question "I have updated the README.md"

    Sections of the README are pulled into the site by name: the homepage includes the badges, the diagram, the model, the load snippet, the development install and the status note.
    A section is delimited in the README by `:::md <!--- --8<-- [start:name] -->` and `:::md <!--- --8<-- [end:name] -->`, and `docs/index.md` pulls it in with `:::md --8<-- "README.md:name"`.
    Edit inside the markers and the site follows.
    Keep a section link-free or absolutely linked: a relative link inside one resolves against `docs/index.md` on the site and against the repository root on GitHub, and only one of those can be right.

??? question "I have changed what a model prints"

    The model in the README and the math block under it on the homepage both come out of `examples/dispatch.yaml` and its symbol table, so the page shows what the typesetter prints and the model shown cannot drift from the model rendered:

    ```bash
    pixi run python -m tools.home_math           # rewrite the block
    pixi run python -m tools.home_math --check   # fail if it has drifted
    ```

    `tools/notation.py` does the same for `docs/reference/notation.md`, out of `tests/typesetting/golden/model.yaml` and the four `piecewise:` models under `examples/`.
    `tests/test_docs.py` fails when either page has drifted from its generator.

??? question annotate "I want to add a new page"

    Decide what the page is for first: a tutorial, a how-to guide, reference or
    explanation, the four kinds of [Diátaxis](https://diataxis.fr). The kind
    decides the folder under `docs/` and the nav section of the same name in
    `mkdocs.yml`, and [the docs-writing skill](https://github.com/energy-models/math-spec/blob/main/.claude/skills/docs-writing/SKILL.md)
    holds the rules each kind has to meet. Then add the file under its section
    in the `nav` key, e.g.:

    ```yaml
    nav:
    - How-to guides:
        - Installation: howto/installation.md
        - My recipe: howto/my-recipe.md
    ```

    Or leave the nav title to the page's own heading:
    `my-page.md`

    ```md
    # My Page
    ...
    ```

    `mkdocs.yml`

    ```yaml
    nav:
    ...
    - my-page.md
    ...
    ```

??? question "I want to add images to my docs"

    Put new images in the top-level `resources/` directory and reference them from Markdown:

    ``` html
    <figure>
    <img src="../resources/filename.png", width="100%", style="background-color:white;", alt="accessible alternative text">
    <figcaption>My caption.</figcaption>
    </figure>
    ```

    Or:

    ``` md
    ![accessible alternative text](../resources/filename.png)
    ```

    The first form takes a caption.

??? question "I want to update the Python API docs"

    They are built from the docstrings at build time, so a new class or module appears on the next build.

??? question "I want to automatically process a number of files into pages in the docs"

    Add the workflow to `docs/static/hooks.py`, which already builds the Python API pages that way.

??? question "I want to view my documentation changes locally"

    `pixi run docs-serve` builds the site, serves it at a link it prints (most likely <http://127.0.0.1:8000>), and rebuilds on every change.

??? question "I want to do something else"

    The [MkDocs](https://www.mkdocs.org/) and [Material](https://squidfunk.github.io/mkdocs-material/) documentation covers the rest.

## Naming across the layers

The same construct passes through three layers, and each names it in full. The
layer is the suffix, which keeps the three vocabularies from colliding:

| Layer                           | Suffix               | Example                                   |
| ------------------------------- | -------------------- | ----------------------------------------- |
| YAML block (`math_spec.model`)  | `Block`              | `VariableBlock`, `PiecewiseBlock`         |
| Core AST (`math_spec.*_parser`) | `Node`               | `VariableNode`, `DimensionComparisonNode` |
| Program (`math_spec.program`)   | none / `Declaration` | `Variable`, `VariableDeclaration`         |

Two rules follow, and a PR that adds a construct keeps them:

- **A node names the coordinate map, not a surface spelling.** The translation
  node is `Translate`; its surface spelling is `shift(…, edge=)`.
- **Nothing is abbreviated.** `ParameterComparison`, not `Cmp`;
  `variable_type`, not `vtype`.

## Adding an operator

Grammar first, which is usually free because `f(x, k=v)` already parses. Then
its signature in `operators.BUILTINS`, which holds the arity and which
arguments name dimensions; resolution, validation and lowering all read it
from there. Then its dimension rule in `dimensions.py`, its degree verdict in
`degree.py`, the plan node it lowers to in `program.py`, and its page in the
[language reference](reference/language/operators.md).

The operator lands and is tagged here before any consumer's half, because a
consumer cannot lower an operator the version it pins does not parse. A
consumer owns only the query or call it makes for the node.

## Submitting changes

--8<-- "CONTRIBUTING.md:docs"
