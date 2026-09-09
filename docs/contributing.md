<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing

math-spec is actively maintained and used.

## How to contribute

To report an issue, request a feature, or talk to the community, follow the links below.

<div class="grid cards" markdown>

- [:material-bug: Report a bug](https://github.com/energy-models/math-spec/issues/new?template=BUG-REPORT.yml)
- [:material-file-document: Report a docs issue](https://github.com/energy-models/math-spec/issues/new?template=DOCS.yml)
- [:material-lightbulb-on: Request a change](https://github.com/energy-models/math-spec/issues/new?template=FEATURE-REQUEST.yml)
- [:material-chat-question: Ask a question](https://github.com/energy-models/math-spec/discussions)

</div>

## Developing `math-spec`

Our [good first issues](https://github.com/energy-models/math-spec/contribute) are the bugs and feature requests to start out with.

### Setting up a development environment

To create a development environment for `math-spec`, use [pixi](https://pixi.prefix.dev/).

1. Install pixi following the [official instructions](https://pixi.prefix.dev/latest/installation/).
1. Install the development environment in your local clone of the `math-spec` repository:

```sh
pixi install
```

If you plan to change the code, use these tools while you work:

- `pre-commit`: run `pixi run pre-commit-install` in your command line to load inbuilt checks that will run every time you commit your changes.
  The checks include:
  1. check no large files have been staged
  2. lint python files for major errors
  3. format python files to conform with the [PEP8 standard](https://peps.python.org/pep-0008/)
  4. type-check the package with [pyrefly](https://pyrefly.org/).
     You can also run these checks yourself at any time to ensure the tree is clean by calling `pixi run lint`.
- `pixi run test` - run the unit test suite.
- `pixi run test-coverage` - the same, with test coverage.
- `pixi run compile-tex` - render every model in the tree to standalone LaTeX and compile it, which is how the typeset output is proven to be a real document.
- `pixi run ci` - the four gates CI runs: lint, tests, a strict docs build and the LaTeX compile, in the order a failure is cheapest to read. Run it before you push.

## Documentation

A contribution may need the documentation in the `docs` directory updated with it.
The pages are Markdown, built by [MkDocs](https://www.mkdocs.org/) with the [Material](https://squidfunk.github.io/mkdocs-material/) theme.

These are the cases that come up:

??? question "I have updated the README.md"

    Sections of the README are piped into the site rather than copied wholesale: the homepage includes the badges, the diagram, the model, the load snippet, the development install and the status note, each by name.
    A section is delimited in the README by `:::md <!--- --8<-- [start:name] -->` and `:::md <!--- --8<-- [end:name] -->`, and `docs/index.md` pulls it in with `:::md --8<-- "README.md:name"`.
    Edit inside the markers and the site follows.
    Keep the sections themselves link-free or absolutely linked: a relative link inside one resolves against `docs/index.md` on the site and against the repository root on GitHub, and only one of those can be right.

??? question "I have changed what a model prints"

    The model in the README and the math block under it on the homepage both come out of `examples/dispatch.yaml` and its symbol table, so the page shows what the typesetter prints rather than what somebody typed — and the model shown cannot drift from the model rendered:

    ```bash
    pixi run python -m tools.home_math           # rewrite the block
    pixi run python -m tools.home_math --check   # fail if it has drifted
    ```

    `tools/notation.py` does the same for `docs/reference/notation.md`, out of `tests/typesetting/golden/model.yaml`.
    It also wants the four `piecewise:` models one section of that page is built from, which the extraction from lpspec has not brought over yet — so it raises `FileNotFoundError` until they arrive, and the committed page is the last one lpspec generated.

??? question annotate "I want to add a new page"

    Add a Markdown file to the top-level in `docs`, e.g. `docs/my-page.md`.
    Then, add a reference to that file within the `nav` key in `mkdocs.yml`, e.g.:

    ```yaml
    nav:
    - Home: index.md
    - Installation: installation.md
    - Getting started: getting_started.md
    - My Page: my-page.md
    ```

    You can also just rely on your document header to define the name in the navigation:
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

    You should add any new images to the top-level `resources/` directory.
    Within your Markdown, you will be able to reference these as follows:

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

    The first approach gives you a bit more power, including having a figure caption.

??? question "I want to update the Python API docs"

    These pages are generated.
    A new class or module appears in the next documentation build.

??? question "I want to automatically process a number of files into pages in the docs"

    You may have configuration files you want to add to the documentation for reference.
    You should add your workflow to process these files to `docs/hooks.py`.
    In that file, you can find examples of how we do it for other files (e.g. the python API docs).

??? question "I want to view my documentation changes locally"

    You can serve your documentation locally by calling `pixi run docs-serve` from the command line.
    Once the documentation has been built you will see a link to navigate to in your browser, most likely <http://127.0.0.1:8000>.
    When you make changes to your documentation, `mkdocs` will automatically rebuild everything so that you can check the effects of your changes without needing to rerun manually.

??? question "I want to do something else"

    The [MkDocs](https://www.mkdocs.org/) and [Material](https://squidfunk.github.io/mkdocs-material/) documentation answers what this page does not.

## Submitting changes

--8<-- "CONTRIBUTING.md:docs"
