<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Errors and limits

This page says when a model fails to load, what the message tells you, and what
the language refuses to say at all.

## `to_spec` is the check

There is one entry point, and it binds no data. Before `ms.to_spec('model.yaml')`
returns a `Spec`, it does all of the following:

- parses the file;
- expands every `piecewise:` block;
- resolves every name;
- checks every dimension rule and every degree;
- reads every `where` string and every macro template, including the templates
  that nothing calls.

Anything the language refuses is refused there. So you can validate a whole
repository of models in CI, with no data and no solver. It also means the worst
error a downstream consumer could hand you cannot come from this package. That
worst error is an opaque array, or a solver exception with no pointer back to a
declaration.

Every message names what went wrong and what to do about it. Where it helps, the
message also lists the valid options:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['p', 'soc']
  Parameters: ['p_max', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

When you use a construct that is outside the language, the error names the
construct and its rewrite. You never get a silent fallback.

## `advice` reports what is decidable but not an error

Two more things can be decided without data, and each one is advice rather than
a refusal.

`ms.advice(model)` returns both as a tuple of `ms.Advice`. Each `Advice` carries
a `kind`, which is one of `ms.ADVICE_KINDS`, so either `never-an-axis` or
`unbounded`. It also carries the `subject` declaration it is about, and its
`text`. Calling `str()` on one gives you the sentence.

A consumer either prints these, or filters on the two fields. The sentences
belong to the language, so no consumer writes its own.

From a shell, `python -m math_spec check model.yaml` runs the two together. A
refusal prints its message on stderr and exits with status 1. Advice is printed
and the status is 0.

The first kind of advice is about an axis. A dimension that nothing is indexed
by, and that nothing aggregates into, is never an axis. If a lookup targets it,
then it is a label space wearing a dimension's declaration, and the note says
how to declare it as a label space. If nothing reaches it at all, then it is
unused.

The second kind is about an unbounded variable. Take a variable that no
constraint names, and whose bounds leave open the side that its objective term
improves toward. That variable runs to infinity for every dataset there is. A
solver reports this with a bare `unbounded` that names nothing. The note reports
it with the variable and the side:

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is -inf, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

This is advice rather than an error because a half-written model has the same
shape. A variable declared before the constraint that will hold it looks exactly
like this, and `to_spec` stays open to a half-written model.

So advice is a list that a consumer asks for, not an error that it is handed. If
you build straight from the model, the solver's bare answer is still the first
word you get.

Both halves of the condition are needed, and neither half alone is wrong. A
variable held by nothing but its own `bounds:` is ordinary. So is an unbounded
variable that a constraint names.

Nothing is said where the sign that a variable enters the objective with is
_data_. That happens with a parameter coefficient, which may be zero or either
sign. A note against a model that solves would be the worse error.

There is also a per-coordinate case, where a `where:` mask leaves one slice of a
variable with no constraint row. That case cannot be decided from the file
([#229](https://github.com/fluxopt/lpspec/issues/229)).

## Which error you get

|                           |                                                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MathSpecError`           | The root of the tree. Everything below it is an instance of it                                                                   |
| `LanguageError`           | Something in the model: a construct outside the language, a dimension set that does not compose, or a name that nothing declares |
| `SchemaError`             | Something in the file: an unknown key, a malformed declaration, or a bad symbol table                                            |
| `DimensionError`          | Dimensions that disagree, such as a constraint whose expression does not equal its `foreach`                                     |
| `PiecewiseExpansionError` | a `piecewise:` block that cannot be expanded                                                                                     |

Every one of these means the _file_ is wrong, and every one is reproducible from
the YAML alone, with no data and no solver.

That is the whole tree that this package raises. A consumer that binds numbers
or calls a solver adds its own errors below `MathSpecError`, and says so in its
own documentation.

## What the language will not say

This section lists the refusals, and what to reach for instead. None of these is
an unimplemented feature. Each one is a boundary that the design keeps on
purpose, and [the limits](../../about/limits.md) is the argument for where the
boundary sits.

| Not here                                                                       | Instead                                                                                                                                                                              |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| variable × variable in a **bound, a named expression or a `piecewise:` link**  | The objective and the constraints take it. Everywhere else, use a parameter coefficient ([expressions](expressions.md#where-a-product-of-two-variables-is-allowed))                  |
| `sum(x, over=d) * sum(y, over=d)`                                              | Multiply before you reduce, or name the reduction with a variable. A product of two sums is a cross join                                                                             |
| degree 3 (`x * y * z`)                                                         | a variable constrained to equal one product, then multiplied by the third                                                                                                            |
| `**`                                                                           | `x * x` ([expressions](expressions.md#where-a-product-of-two-variables-is-allowed))                                                                                                  |
| arithmetic in `bounds:`                                                        | a name or a number; ship the derived column as data ([#31](https://github.com/fluxopt/lpspec/issues/31))                                                                             |
| time-series processing (resample, cluster, interpolate, align), file IO, units | data prep; pass a parameter                                                                                                                                                          |
| indicator constraints                                                          | This is not a language question. What a consumer can take is its own axis, and that is the axis `sos:` landed on ([#220](https://github.com/fluxopt/lpspec/issues/220))              |
| multi-objective                                                                | There is one `objective:` block, and a second one cannot be said. Weight the goals into one expression                                                                               |
| arbitrary array ops (`merge`, `reindex`, `apply_ufunc`)                        | Data preparation. The closed operator set is what makes streaming possible                                                                                                           |
| filling a missing value (`.fillna`)                                            | Data preparation, or a `where` if you meant the coordinate not to exist. Fill inside the language only where the data cannot reach, with `shift(..., edge=)` ([absence](absence.md)) |
| schema migrations                                                              | —                                                                                                                                                                                    |

A model built partly in Python has no readable `.yaml` representation, and it
will not get one. The _math_ side of such a round trip is feasible. But
expression strings and `where` strings come back as anonymous arrays, so the
round trip would be functional and not reviewable, and being reviewable is the
whole point of the file. A framework that wants to _emit_ declarations passes a
dict, and gets `to_yaml()` back.

Where the language genuinely cannot say the math, the escape hatch is a declared
`escape:` island. An island is named in the file, bounded by the `where` mask in
front of it, terminal, and billed against a label budget before any Python runs.
It is [#38](https://github.com/fluxopt/lpspec/issues/38), and it has not
shipped.
