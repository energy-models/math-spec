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

Wherever a feature can be a key in the file, it is one: a key shows up in a git
diff, the typesetter prints it, and an engine in another language reads it.

## What every function keeps

- **No state.** No registry, no plugin, and no setting that changes what a
  model means. `symbols=` on the typesetter is the shape a legitimate option
  takes: it changes how `load` prints and nothing about what `load` is.
- **A value or an error, and nothing between.** `to_spec` either returns a
  `Spec` or raises an error that names the rewrite. `advice()` is separate: it
  talks about a file the language accepts, and changes nothing.
- **Nothing is written out unasked.** A `piecewise:` or `sos:` block stays the
  block until a caller calls
  [`spec.expand()`](../reference/reading.md#formulations-written-out).

What a solver or file format can take, how the numbers attach to the names, and
which solver runs are each engine's to decide
([what counts as language](what-counts-as-language.md#what-each-tool-decides-for-itself)).
