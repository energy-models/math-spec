<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Installation

`mathspec` needs Python 3.12 or above. Nothing is published yet, so install it
from git:

```bash
pip install git+https://github.com/energy-models/mathspec
```

To develop against a clone instead, follow
[contributing](../contributing.md#setting-up-a-development-environment).

## Editor completion and offline checking

The YAML keys ship as a JSON Schema,
[`schema/mathspec.schema.json`](https://github.com/energy-models/mathspec/blob/main/schema/mathspec.schema.json).
An editor reads it for key completion, and a job with no Python reads it for a
structure check.

### Map the schema in VS Code

Install the
[Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml),
then map the schema per workspace:

```jsonc
// .vscode/settings.json
"yaml.schemas": { "https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json": ["*.model.yaml"] }
```

or per file, with a modeline on its first line:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json
```

### Check a file without Python

For a pre-commit hook or a non-Python CI job:

```bash
uvx check-jsonschema --schemafile https://raw.githubusercontent.com/energy-models/mathspec/main/schema/mathspec.schema.json model.yaml
```

The schema validates structure only. The math inside `expression:` and
`where:` is checked by [`to_spec`](../reference/language/errors.md#what-to_spec-checks).
