<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Check a model

Find the errors in a model file before you attach data or start a solver. The
check reads the file alone, so it runs in seconds on your machine and in CI.

## Check one file

```bash
python -m mathspec check model.yaml
```

The result is one of three:

- **Nothing printed, exit status 0.** The model is correct.
- **Advice on stdout, exit status 0.** The model loads, but something in it is
  probably not what you meant:

  ```text
  Variable 'slack' makes this model unbounded: no constraint names it, and bounds.lower is open, which is the direction a +slack term improves a minimize objective in. No data can change that, so the solve would answer `unbounded` and name nothing.
  Give it a finite bounds.lower, or the constraint that was meant to define it.
  ```

- **An error on stderr, exit status 1.** The language refuses the file. The
  message names the fix:

  ```text
  variables.p: unknown key 'boundz' in a variable declaration. Did you mean 'bounds'?
  ```

## Check every model in CI

The exit status is the gate. A shell loop is the whole job:

```bash
for model in models/*.yaml; do python -m mathspec check "$model" || exit 1; done
```

## Check from Python

Use this where the check is one step of a longer script.
[`to_spec`](../reference/api.md#loading) raises a `MathSpecError` for anything
the language refuses. [`advice`](../reference/api.md#advice) returns the advice
that the command line prints:

```python
import mathspec as ms

for note in ms.advice('model.yaml'):
    print(note)
```

## Check without Python

The JSON schema checks the structure of a file, but not the math inside an
`expression:` or `where:` string. See
[editor completion and offline checking](installation.md#editor-completion-and-offline-checking).
