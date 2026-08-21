<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# Golden output

One model, rendered in every format, committed and asserted byte for byte.

The same trade `examples/walkthrough.out` makes: reading the file is the same
as running the generator, and a format that starts saying something different
shows up as a diff here rather than as nothing at all.

Fragment assertions cannot do this job. They pin the constructs someone
thought to pin, and they survive anything that leaves those substrings intact
— a stray prefix, a lost space, a changed separator. Perturbing
`TypstFormat.summation` to emit `~sum_(...)` failed **no test** before these
files existed.

`model.yaml` is synthetic on purpose: it reaches every rendering path — each
operator, every translation, every bound shape, every `where` predicate, both
constant masks, and a set carried to the solver rather than rows. A real model
exercises a handful of those and reads better on a gallery page; this one is
here to be complete rather than to be read.

**Complete is asserted, not claimed.** Three checks in `tests/typeset/test_typeset.py`
hold this file to the language: every operator a format spells is asked for
while rendering it, every node kind the parsers produce reaches the walk, and
every line of `walk.py` runs. A construct added to the language lands with a
case here or one of them goes red — where before, "every rendering path" was a
sentence in this README, and the symbols no model printed stayed unprinted.

Regenerate after an intended change, then **read the diff** — that is the
review, and it is the whole point:

    pixi run python -m tests.typeset.golden
