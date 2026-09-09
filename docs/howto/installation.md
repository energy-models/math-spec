<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Installation

## Installing a user environment

!!! warning "Not published yet"

    math-spec is on the alpha stream and the publish job is off until it leaves
    it — see [RELEASING.md](https://github.com/energy-models/math-spec/blob/main/RELEASING.md).
    The commands below are what the first release will look like; until then,
    install from a checkout or a git reference.

!!! hint

    If it is your first time using Python, we recommend [pixi](https://pixi.prefix.dev/), [conda](https://docs.conda.io/projects/conda), or [uv](https://docs.astral.sh/uv/) as easy-to-use package managers.
    They are available for Windows, macOS, and GNU/Linux.
    It is always helpful to use dedicated environments.

You can install `math-spec` via all common package managers:

=== "pixi"

    ``` bash
    pixi add --pypi math_spec
    ```

=== "uv"

    ``` bash
    uv add math_spec
    ```

=== "conda"

    ``` bash
    conda create -n math-spec "python>=3.12" "pip"
    conda activate math-spec
    pip install math_spec
    ```

=== "pip"

    ``` bash
    pip install math_spec
    ```

`math-spec` is written and tested to be compatible with Python 3.12 and above.
We recommend to use the latest version with active support (see [endoflife.date](https://endoflife.date/python)).

## Installing a development environment

The install instructions are slightly different to create a development environment compared to a user environment:

--8<-- "README.md:docs-install-dev"

For more detailed installation instructions specific to developing the `math-spec` codebase, see our [development documentation][setting-up-a-development-environment].

## Editor completion and offline checking

The YAML surface ships as a JSON Schema,
[`schema/math-spec.schema.json`](https://github.com/energy-models/math-spec/blob/main/schema/math-spec.schema.json),
generated from the same declarations `to_spec` validates against. An editor
reads it for key completion, and a job with no Python reads it for a
structure check. The examples below read it over the network; a vendored copy
takes a path in the same slot.

### Map the schema in VS Code

Install the
[Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml),
then map the schema per workspace:

```jsonc
// .vscode/settings.json
"yaml.schemas": { "https://raw.githubusercontent.com/energy-models/math-spec/main/schema/math-spec.schema.json": ["*.model.yaml"] }
```

or per file, with a modeline on its first line:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/energy-models/math-spec/main/schema/math-spec.schema.json
```

That gives key completion, hover docs, the closed vocabulary behind
`dtype:`, `domain:` and `sense:`, and a squiggle on a misspelled key.

### Check a file without Python

For a pre-commit hook or a non-Python CI job:

```bash
uvx check-jsonschema --schemafile https://raw.githubusercontent.com/energy-models/math-spec/main/schema/math-spec.schema.json model.yaml
```

The schema validates structure only. `expression:` and `where:` are strings
to it; the math inside them is checked by
[`to_spec`](../reference/language/errors.md#to_spec-is-the-check).
