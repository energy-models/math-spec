<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing guidelines

We're glad you're reading this; we welcome all contributors!

Some of the resources to look at if you're interested in contributing:

- Look at open issues tagged with ["help wanted"](https://github.com/energy-models/math-spec/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) and ["good first issue"](https://github.com/energy-models/math-spec/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- Look at the [contributing guide in our documentation](https://energy-models.github.io/math-spec/contributing)

## Licensing

Copyright (c) 2026 math-spec contributors.
By contributing to math-spec, i.e. through opening a pull request, you represent that your contributions are your own original work and that you have the right to license them, and you agree that your contributions are licensed under the .

## Reporting bugs and requesting features

You can open an issue on GitHub to report bugs or request new math-spec features.
Follow these links to submit your issue:

- [Report bugs or other problems while running math-spec](https://github.com/energy-models/math-spec/issues/new?template=BUG-REPORT.yml).
  If reporting an error, please include a full traceback in your issue.

- [Request features that math-spec does not already include](https://github.com/energy-models/math-spec/issues/new?template=FEATURE-REQUEST.yml).

- [Report missing or inconsistent information in our documentation](https://github.com/energy-models/math-spec/issues/new?template=DOCS.yml).

- [Any other issue](https://github.com/energy-models/math-spec/issues/new).

## Submitting changes

Look at the [development guide in our documentation](https://energy-models.github.io/math-spec/contributing) for information on how to get set up for development.

<!--- the "--8<--" html comments define what part of this file to add to the index page of the documentation -->
<!--- --8<-- [start:docs] -->

To contribute changes:

1. Fork the project on GitHub.
1. Create a feature branch to work on in your fork (`git checkout -b new-fix-or-feature`).
1. Test your changes using `pixi run test`, or `pixi run ci` for everything CI will check.
1. Commit your changes to the feature branch (you should have `pre-commit` installed to ensure your code is correctly formatted when you commit changes).
1. Push the branch to GitHub (`git push origin new-fix-or-feature`).
1. On GitHub, create a new [pull request](https://github.com/energy-models/math-spec/pull/new/main) from the feature branch.

When you contribute for the first time, ensure your reviewer [adds you as a contributor](https://allcontributors.org/en/bot/)!

### Pull requests

Before submitting a pull request, check whether you have:

- Written the PR title as a conventional commit subject (see below) — this, not a hand-written entry, is what appears in `CHANGELOG.md`.
- Added or updated documentation for your changes.
- Added tests if you implemented new functionality.

When opening a pull request, please provide a clear summary of your changes!

### Commit messages

Merges are squashed, and the resulting subject on `main` is what
[release-please](https://github.com/googleapis/release-please) reads to build
the changelog. So the **PR title** must be a
[conventional commit](https://www.conventionalcommits.org) subject:

```text
<type>[(scope)]: <subject>

feat: AST parsing for indexed constraints
fix(parser): where clauses with a trailing comma
docs: describe the two expression tiers
```

Types are `feat`, `fix`, `perf`, `refactor`, `docs`, `chore`, `test`, `ci`,
`build`, `style` and `revert`; the first five appear in the changelog and the
rest are hidden. A subject the parser cannot read is not an error — the entry
simply never appears — so the `Conventional commit subject` check enforces the
format on every pull request.

While the version is pinned to the alpha stream, a breaking marker (`!`, or a
`BREAKING CHANGE:` footer) is refused, because it moves the base version rather
than the alpha counter. Describe the break in the PR body instead. See
[RELEASING.md](https://github.com/energy-models/math-spec/blob/main/RELEASING.md).

Beyond the subject line, write whatever body the change deserves — a paragraph
or bullet list covering what changed and its impact.

### Code conventions

Start reading our code and you'll get the hang of it.

We mostly follow the official [Style Guide for Python Code (PEP8)](https://www.python.org/dev/peps/pep-0008/).

We have chosen to use the uncompromising code formatter and linter [`ruff`](https://beta.ruff.rs/docs/).
When run from the root directory of this repo, `pyproject.toml` should ensure that formatting and linting fixes are in line with our custom preferences (e.g., maximum line length).
To make this a smooth experience, you should run `pixi run pre-commit-install` after setting up your development environment.
If you prefer, you can also set up your IDE to run these two tools whenever you save your files, and to have `ruff` highlight erroneous code directly as you type.
Take a look at their documentation for more information on configuring this.

We require all new contributions to have docstrings for all modules, classes and methods.
When adding docstrings, we request you use the [Google docstring style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

## Releases

Nothing here is done by hand. release-please opens a release PR from the
conventional-commit subjects on `main`; merging it tags the release, and the tag
is what builds and publishes the package. While the project is on the alpha
stream that release PR is merged automatically, so every merge to `main` cuts a
version.

The version is never written down in the source tree — it comes from the git
tag at build time, and `math_spec.__version__` reads it back from the installed
package metadata.

See [RELEASING.md](https://github.com/energy-models/math-spec/blob/main/RELEASING.md) for the full pipeline, the alpha-stream rules,
and the one-time repository setup it still needs.

<!--- --8<-- [end:docs] -->
