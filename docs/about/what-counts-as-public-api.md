<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as public API

This page says which functions may join the package's public API, such as
`to_spec` and `to_latex`. It is not about the operators a model may use, such as
`sum` and `shift`; those are [the limits](limits.md). The page exists so that the
API stays small while the language grows.

A function may join the public API when both of these hold:

1. **Same file in, same answer out.** `to_spec('model.yaml')` returns the same
   `Spec` today, tomorrow, and on a machine with no data and no solver. A
   function whose answer depends on data, a solver, the network or the clock
   cannot join, because its answer would change from one run to the next.
2. **No rule lives only in the code.** Every rule the function applies is written
   on a page of this reference, so somebody could rewrite the function in another
   language from the pages alone and get the same answer. If `to_program` treated
   a masked variable as zero, and no page said so, an engine written in Julia
   could not know it.

## What makes this package more useful

This package builds nothing and solves nothing. Its value is what other tools
build on it, so a small API that a dozen tools read is worth more than a wide
one that one tool uses.

The largest gain available is not a function. It is writing a `Program` out in a
format another language can read. Then an engine - whether in Python, Julia, Rust, etc. -
reads the resolved tree instead of re-implementing the parser and every rule behind it.

## Where a new feature lands

When the language gained piecewise-linear curves, it gained a `piecewise:` key
in the YAML, not a call such as `ms.add_curve(spec, ...)`. The same holds for
`cases:` and `sos:`. A key in the file shows up in a git diff, the typesetter
prints it as math, and an engine written in Julia can read it. A Python call does
none of these: the curve would exist only in the script that made the call, and
only for Python. So wherever a feature can be a key in the file, it is one.

## What every function keeps

- **No state.** No registry, no plugin, and no setting that changes what a
  model means. `symbols=` on the typesetter is the shape a legitimate option
  takes: it changes how `load` prints and nothing about what `load` is.
- **A value or an error, and nothing between.** `to_spec` either returns a
  `Spec` or raises an error that names the rewrite. It never returns a
  half-built value with a warning attached. `advice()` is separate: it talks
  about a file the language accepts, and changes nothing.
- **Safe to call again.** `to_program(tool)` returns `program` unchanged, so
  a caller that does not know whether it holds a `Spec` or a `Program` can call
  it either way.

## Three things a function never decides

- What one solver or file format can take. That is the engine's question.
- How the numbers bind to the names. That is the engine's too.
- Which solver runs.

A function that answered any of these would push one engine's limits onto every
other.

## What this refuses

| Asked for                                        | Why                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------- |
| A Python API for building models                 | The model is the file you review and diff                           |
| A hook, a callback, a registry, a plugin         | Cannot be diffed, printed or read from another language             |
| A function that binds data or calls a solver     | Needs more than the file                                            |
| A setting that changes what a file means         | Two callers would read one file two ways                            |
| A function whose answer a declaration could give | A declaration can be diffed, printed and read from another language |

If somebody needs a capability, this test refuses it, and it cannot be written
as a declaration, then this page is wrong and should change.
