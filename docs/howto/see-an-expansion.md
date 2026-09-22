<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# See what a curve or a set expands to

A [`piecewise:`](../reference/language/piecewise.md) block and a `sos:` block
each stand for plain variables and constraints. Write them out to review a
formulation, to teach one, or to hand the model to an engine that has no
concept of a set.

## 1. Write the formulation out

`expand()` returns the same math with its formulations stated as plain
declarations. `to_yaml()` prints the result as a file.

=== "Python"

    ```python
    from math_spec import to_spec

    spec = to_spec('before.yaml')
    print(spec.expand().to_yaml())
    ```

=== "Command line"

    ```bash
    python -m math_spec markdown before.yaml --expand
    ```

The command line prints the expansion as math rather than as YAML.

## 2. Read a set

The `sos:` block below says that at most one `p` is nonzero. Its expansion
adds one binary per member, a row that picks at most one binary, and a row that
holds an unpicked member at zero. The coefficient `10.0` is the upper bound of
`p`.

=== "Before"

    ```yaml
    --8<-- "tests/expand/set-type1/before.yaml"
    ```

=== "`expand()`"

    ```yaml
    --8<-- "tests/expand/set-type1/after.yaml"
    ```

Every name the expansion adds starts with the name of the block, so `pick_seg`
is the binary of the set `pick`. A file that already declares one of these
names is refused at load.

## 3. Read a curve

The `piecewise:` block below ties `x` and `y` to a curve through the
breakpoints in `x_bp` and `y_bp`. A `method: sos2` curve states a set, so it
writes out in two steps. Compare the tabs from left to right:

- **`expand('piecewise')` writes the curve out and leaves its set.** It adds a
  weight per breakpoint and one link row per tied variable. An `sos:` block
  over the weights keeps at most two neighbouring weights nonzero.
- **`expand()` writes the set out too.** The `sos:` block becomes one binary
  per segment and the rows that keep the two nonzero weights next to each
  other.

=== "Before"

    ```yaml
    --8<-- "tests/expand/curve-sos2/before.yaml"
    ```

=== "`expand('piecewise')`"

    ```yaml
    --8<-- "tests/expand/curve-sos2-piecewise/after.yaml"
    ```

=== "`expand()`"

    ```yaml
    --8<-- "tests/expand/curve-sos2/after.yaml"
    ```

Both expansions also write an
[`assumptions:`](../reference/language/assumptions.md) row. A missing
breakpoint row reads as a zero, not as a shorter curve, so the curve states
that its breakpoints are there.

## 4. Write out one kind at a time

Pass a kind to keep the other construct. `expand('piecewise')` keeps the sets,
and `expand('sos')` keeps the curves. `expand()` with no argument writes the
curves out first, because a curve can state a set and a set never states a
curve.

## Every method, before and after

The repository keeps one before and after pair for each `method:` and each
`type:`, in
[`tests/expand/`](https://github.com/energy-models/math-spec/tree/main/tests/expand).
The test suite expands every `before.yaml` and compares the result to its
`after.yaml` in full. This page shows those same files, so a pair here cannot
differ from what `expand()` returns.

## Two things to know

**An expansion is a file like any other.** A curve emits variables,
constraints and assumptions over the parameters the file declared, and no
parameter of its own, so `to_yaml()` writes every expansion and the same data
binds it.

**A method states what it assumes of the data.** A `method: lp` or
`method: convex` curve is exact only for breakpoints of the right shape. The
expansion writes those conditions into `assumptions:` beside the rows. The
`method: sos2` curve above states nothing about the shape, because it takes a
curve of any shape.

What `expand()` accepts, and what each `method:` emits, is under
[piecewise curves and SOS](../reference/language/piecewise.md#writing-a-formulation-out).
