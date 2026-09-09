<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a function

This page says which functions may join the public API. It exists so that the
API stays small while the language grows.

A function may join when both of these hold:

> Everything the function decides, the language has already written down. And
> the function needs nothing but the file to decide it.

The first half refuses a function that carries a rule of its own. If
`to_program` decided that a masked variable reads as zero, and no page said so,
then an engine written in another language could not know it. The second half
refuses a function that needs data, a solver, the network or a clock. Its answer
would change from one run to the next, so it cannot be part of what the file
means.

## What makes this package more useful

This package builds nothing and solves nothing. Its value is what other programs
build on it, so a small API that a dozen programs read is worth more than a wide
one that one program uses.

The largest gain available is not a function. It is writing a `Program` out in a
format another language can read. Then an engine in Julia or Rust reads the
resolved tree instead of re-implementing the parser and every rule behind it.

## New capability arrives as a declaration

`cases:`, `piecewise:` and `sos:` each added a capability and no function. A
declaration can be read, printed, diffed and written back out, because it is
part of the file. A callback or a plugin cannot be reviewed in a diff, cannot be
printed as math, and cannot cross into another language. So a feature that can
be a declaration is one.

## What every function keeps

- **No state.** No registry, no plugin, and no setting that changes what a
  model means. `symbols=` on the typesetter is the shape a legitimate option
  takes: it changes how `load` prints and nothing about what `load` is.
- **A value or an error, and nothing between.** `to_spec` either returns a
  `Spec` or raises an error that names the rewrite. It never returns a
  half-built value with a warning attached. `advice()` is separate: it talks
  about a file the language accepts, and changes nothing.
- **Safe to call again.** `to_program(program)` returns `program` unchanged, so
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
