<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Errors and limits

## What `to_spec` checks

`to_spec` attaches no data. Before it returns a `Spec`, it parses the file,
resolves every name, checks every dimension rule and every degree, and reads
every `where` string and every macro template, including the templates that
nothing calls. A `piecewise:` block is checked against every rule its expansion
would be held to. Anything the language refuses is refused there.

Every message names what went wrong and what to do about it:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['dispatch', 'soc']
  Parameters: ['capacity', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

## What `advice` warns about

`ms.advice(model)` returns a tuple of `ms.Advice`, one per warning, and
`python -m mathspec check model.yaml` prints them. Advice is a warning: the file
loads.

| `kind`          | The file has…                                                                                                     | The advice says…                                                      |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `never-an-axis` | a dimension nothing is indexed by, nothing aggregates into and no relation targets                                | remove it, or keep it knowingly if its declarations are still to come |
| `unbounded`     | a variable that no constraint, set or curve uses, whose objective term pushes it towards a bound it does not have | give it a finite bound, or the constraint that was meant to define it |

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is open, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

`advice` is silent where the answer depends on the data: an objective
coefficient that is a parameter, or a `where:` that leaves one slice of a
variable with no constraint row.

## Which error you get

| Class            | Subclass of     |                                                                                                                                  |
| ---------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MathSpecError`  | `ValueError`    | The root                                                                                                                         |
| `LanguageError`  | `MathSpecError` | Something in the model: a construct outside the language, a dimension set that does not compose, or a name that nothing declares |
| `SchemaError`    | `LanguageError` | Something in the file: an unknown key, a malformed declaration, or a bad symbol table                                            |
| `DimensionError` | `LanguageError` | Dimensions that disagree, such as a constraint whose expression does not equal its `dims`                                        |

Every one of these is reproducible from the YAML alone.

## What the language will not express

What the language refuses, and what to write instead, is in
[the limits](../../about/limits.md#deliberate-non-primitives).
