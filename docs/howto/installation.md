<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Install

Install mathspec to check a model file and print it as math. You need Python
3.12 or above.

## Install from git

mathspec is not on PyPI yet. Install it from the repository:

```bash
pip install git+https://github.com/energy-models/mathspec
```

Make sure that it runs:

```bash
python -m mathspec --help
```

To change mathspec itself, follow
[contributing](../contributing.md#setting-up-a-development-environment)
instead.

## Editor completion and offline checking

mathspec ships its YAML keys as a JSON Schema,
[`schema/mathspec.schema.json`](https://github.com/energy-models/mathspec/blob/main/schema/mathspec.schema.json).
Your editor reads it to complete keys as you type. A CI job with no Python
reads it to check the structure of a file.

### Map the schema in VS Code

Install the
[Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml).
Then map the schema for the whole workspace:

```jsonc
// .vscode/settings.json
"yaml.schemas": { "https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json": ["*.model.yaml"] }
```

Or map it for one file, with a modeline on its first line:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json
```

### Check a file without Python

Use this in a pre-commit hook or a CI job that has no Python:

```bash
uvx check-jsonschema --schemafile https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json model.yaml
```

The schema checks the structure only. It does not read the math inside
`expression:` and `where:`. [`to_spec`](../reference/language/errors.md#what-to_spec-checks)
checks that.
