<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as public API

This page says which functions may join the package's public API, such as
`to_spec` and `to_latex`. It is not about the operators a model may use; those
are [the limits](limits.md).

A function may join the public API when both of these hold:

1. **Same file in, same answer out.** `to_spec('model.yaml')` returns the same
   `Spec` today, tomorrow, and on a machine with no data and no solver. A
   function whose answer depends on data, a solver, the network or the clock
   cannot join.
2. **No rule lives only in the code.** Every rule the function applies is written
   on a page of this reference, so somebody could rewrite the function in another
   language from the pages alone and get the same answer.

## Where a new feature lands

When the language gained piecewise-linear curves, it gained a `piecewise:` key
in the YAML. A key in the file
shows up in a git diff, the typesetter prints it as math, and an engine written
in another language can read it. So wherever a feature can be a key in the
file, it is one.

## What every function keeps

- **No state.** No registry, no plugin, and no setting that changes what a
  model means. `symbols=` on the typesetter is the shape a legitimate option
  takes: it changes how `load` prints and nothing about what `load` is.
- **A value or an error, and nothing between.** `to_spec` either returns a
  `Spec` or raises an error that names the rewrite. `advice()` is separate: it
  talks about a file the language accepts, and changes nothing.
- **Safe to call again.** `spec.program` is one object, however often it is
  asked for.
- **Nothing is written out unasked.** A `piecewise:` or `sos:` block is the
  block until a caller writes it out with `spec.expand(...)`. No door, verb or
  check expands a model on the caller's behalf: `spec.program` mirrors the
  file, `advice` reads a block as the rows it states, and `--expand` on a
  typeset verb is how the shell asks for the rows as a document of their own.
  A program's `footprint`, `separability` and `roots` answer for the rows it
  holds, so a curve counts there once it is written out.
  An engine that writes curves out at its
  own door makes that choice for its users, not for the language.

## Three things a function never decides

- What one solver or file format can take. That is the engine's question.
- How the numbers bind to the names. That is the engine's too.
- Which solver runs.

## What this refuses

| Asked for                                        | Why                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------- |
| A Python API for building models                 | The model is the file you review and diff                           |
| A hook, a callback, a registry, a plugin         | Cannot be diffed, printed or read from another language             |
| A function that binds data or calls a solver     | Needs more than the file                                            |
| A setting that changes what a file means         | Two callers would read one file two ways                            |
| A function whose answer a declaration could give | A declaration can be diffed, printed and read from another language |
