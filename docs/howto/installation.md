<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Installation

!!! warning "Not published yet"

    math-spec is on the alpha stream, and nothing is published yet. The
    commands below are what the first release will look like. Until then,
    install from a checkout or a git reference.

`math-spec` needs Python 3.12 or above. Install it into a dedicated
environment:

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

To develop against a clone instead:

--8<-- "README.md:docs-install-dev"

[Contributing](../contributing.md) has the rest.

## Editor completion and offline checking

The YAML keys ship as a JSON Schema,
[`schema/math-spec.schema.json`](https://github.com/energy-models/math-spec/blob/main/schema/math-spec.schema.json).
An editor reads it for key completion, and a job with no Python reads it for a
structure check.

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

### Check a file without Python

For a pre-commit hook or a non-Python CI job:

```bash
uvx check-jsonschema --schemafile https://raw.githubusercontent.com/energy-models/math-spec/main/schema/math-spec.schema.json model.yaml
```

The schema validates structure only. The math inside `expression:` and
`where:` is checked by [`to_spec`](../reference/language/errors.md#what-to_spec-checks).
