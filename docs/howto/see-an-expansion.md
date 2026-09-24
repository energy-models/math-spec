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

`expand()` writes each formulation out as plain declarations, and `to_yaml()`
prints the result as a file.

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

The command line prints the expansion as math rather than as YAML. Pass
`'piecewise'` or `'sos'` to write out one kind and keep the other.

## 2. Read a set

The `sos:` block below says that at most one `p` is nonzero. Its expansion
adds one binary per member, a row that picks at most one binary, and a row that
holds an unpicked member at zero. The coefficient `10.0` is the upper bound of
`p`.

<!-- prettier-ignore-start -->
<!-- expansion:set:begin -->

=== "Before"

    === "YAML"

        ```yaml
        dimensions:
          g: { dtype: str }

        variables:
          p:
            dims: [g]
            bounds: { lower: 0, upper: 10 }

        sos:
          pick:
            variable: p
            along: g
            type: 1
        ```

    === "Math"

        _Variable domains_

        **`p`**

        ```math
        0 \le p_{g} \le 10 \qquad \forall\, g \in \mathcal{G}
        ```

        **`pick`**

        ```math
        \left( p_{g} \right)_{g \in \mathcal{G}} \in \mathrm{SOS}1
        ```

=== "`expand()`"

    === "YAML"

        ```yaml
        dimensions:
          g: { dtype: str }

        variables:
          p:
            dims: [g]
            bounds: { lower: 0, upper: 10 }
          pick_seg:
            dims: [g]
            domain: binary
            description: a binary per member, 1 where that member may be nonzero

        constraints:
          pick_pick:
            dims: []
            expression: sum(pick_seg, over=g) <= 1
          pick_nonzero:
            dims: [g]
            expression: p <= 10.0 * (pick_seg)
        ```

    === "Math"

        _Subject to_

        **`pick_pick`**

        ```math
        \sum_{g \in \mathcal{G}} \mathit{pick\_seg}_{g} \le 1
        ```

        **`pick_nonzero`**

        ```math
        p_{g} \le 10 \cdot \mathit{pick\_seg}_{g} \qquad \forall\, g \in \mathcal{G}
        ```

        _Variable domains_

        **`p`**

        ```math
        0 \le p_{g} \le 10 \qquad \forall\, g \in \mathcal{G}
        ```

        **`pick_seg`**

        ```math
        \mathit{pick\_seg}_{g} \in \{0, 1\} \qquad \forall\, g \in \mathcal{G}
        ```

<!-- expansion:set:end -->
<!-- prettier-ignore-end -->

Every name the expansion adds starts with the name of the block, so `pick_seg`
is the binary of the set `pick`.

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

<!-- prettier-ignore-start -->
<!-- expansion:curve:begin -->

=== "Before"

    === "YAML"

        ```yaml
        dimensions:
          bp: { dtype: int }

        parameters:
          x_bp: { dims: [bp] }
          y_bp: { dims: [bp] }

        variables:
          x: { dims: [], bounds: { lower: 0 } }
          y: { dims: [], bounds: { lower: 0 } }

        piecewise:
          curve:
            over: bp
            method: sos2
            links:
              - [x, x_bp]
              - [y, y_bp]
        ```

    === "Math"

        _Subject to_

        **`curve`**

        ```math
        \left( x,\ y \right) \in \mathrm{pwl}_{b \in \mathcal{B}}(\mathrm{x}^{\mathrm{bp}}_{b},\ \mathrm{y}^{\mathrm{bp}}_{b})
        ```

        _Variable domains_

        **`x`**

        ```math
        x \ge 0
        ```

        **`y`**

        ```math
        y \ge 0
        ```

        _Assumptions_

        **`curve_complete`**

        ```math
        \mathrm{x}^{\mathrm{bp}}_{b} \text{ is defined} \wedge \mathrm{y}^{\mathrm{bp}}_{b} \text{ is defined} \qquad \forall\, b \in \mathcal{B}
        ```

=== "`expand('piecewise')`"

    === "YAML"

        ```yaml
        dimensions:
          bp: { dtype: int }

        parameters:
          x_bp: { dims: [bp] }
          y_bp: { dims: [bp] }

        variables:
          x: { dims: [], bounds: { lower: 0 } }
          y: { dims: [], bounds: { lower: 0 } }
          curve_lam:
            dims: [bp]
            bounds: { lower: 0, upper: 1 }
            description: convex-combination weight on a breakpoint

        constraints:
          curve_convexity:
            dims: []
            expression: sum(curve_lam, over=bp) == 1
          curve_link0:
            dims: []
            expression: (x) == sum(curve_lam * x_bp, over=bp)
          curve_link1:
            dims: []
            expression: (y) == sum(curve_lam * y_bp, over=bp)

        sos:
          curve:
            variable: curve_lam
            along: bp
            type: 2

        assumptions:
          curve_complete:
            holds: x_bp AND y_bp
            description: >-
              piecewise 'curve': every breakpoint the curve runs through needs a row in
              'x_bp', 'y_bp' — a missing row is read as a zero rather than as a shorter
              curve, so it sits the curve on the origin. Bind the rows, or declare
              points: to say how far the curve runs.
        ```

    === "Math"

        _Subject to_

        **`curve_convexity`**

        ```math
        \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} = 1
        ```

        **`curve_link0`**

        ```math
        x = \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} \cdot \mathrm{x}^{\mathrm{bp}}_{b}
        ```

        **`curve_link1`**

        ```math
        y = \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} \cdot \mathrm{y}^{\mathrm{bp}}_{b}
        ```

        _Variable domains_

        **`x`**

        ```math
        x \ge 0
        ```

        **`y`**

        ```math
        y \ge 0
        ```

        **`curve_lam`**

        ```math
        0 \le \mathit{curve\_lam}_{b} \le 1 \qquad \forall\, b \in \mathcal{B}
        ```

        **`curve`**

        ```math
        \left( \mathit{curve\_lam}_{b} \right)_{b \in \mathcal{B}} \in \mathrm{SOS}2
        ```

        _Assumptions_

        **`curve_complete`**

        ```math
        \mathrm{x}^{\mathrm{bp}}_{b} \text{ is defined} \wedge \mathrm{y}^{\mathrm{bp}}_{b} \text{ is defined} \qquad \forall\, b \in \mathcal{B}
        ```

=== "`expand()`"

    === "YAML"

        ```yaml
        dimensions:
          bp: { dtype: int }

        parameters:
          x_bp: { dims: [bp] }
          y_bp: { dims: [bp] }

        variables:
          x: { dims: [], bounds: { lower: 0 } }
          y: { dims: [], bounds: { lower: 0 } }
          curve_lam:
            dims: [bp]
            bounds: { lower: 0, upper: 1 }
            description: convex-combination weight on a breakpoint
          curve_seg:
            dims: [bp]
            domain: binary
            description: a binary per segment, 1 where the two members it spans may be nonzero

        constraints:
          curve_convexity:
            dims: []
            expression: sum(curve_lam, over=bp) == 1
          curve_link0:
            dims: []
            expression: (x) == sum(curve_lam * x_bp, over=bp)
          curve_link1:
            dims: []
            expression: (y) == sum(curve_lam * y_bp, over=bp)
          curve_pick:
            dims: []
            expression: sum(curve_seg, over=bp) <= 1
          curve_adjacency:
            dims: [bp]
            expression: curve_lam <= (curve_seg + shift(curve_seg, along=bp, offset=1, edge=0))

        assumptions:
          curve_complete:
            holds: x_bp AND y_bp
            description: >-
              piecewise 'curve': every breakpoint the curve runs through needs a row in
              'x_bp', 'y_bp' — a missing row is read as a zero rather than as a shorter
              curve, so it sits the curve on the origin. Bind the rows, or declare
              points: to say how far the curve runs.
        ```

    === "Math"

        _Subject to_

        **`curve_convexity`**

        ```math
        \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} = 1
        ```

        **`curve_link0`**

        ```math
        x = \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} \cdot \mathrm{x}^{\mathrm{bp}}_{b}
        ```

        **`curve_link1`**

        ```math
        y = \sum_{b \in \mathcal{B}} \mathit{curve\_lam}_{b} \cdot \mathrm{y}^{\mathrm{bp}}_{b}
        ```

        **`curve_pick`**

        ```math
        \sum_{b \in \mathcal{B}} \mathit{curve\_seg}_{b} \le 1
        ```

        **`curve_adjacency`**

        ```math
        \mathit{curve\_lam}_{b} \le \mathit{curve\_seg}_{b} + \mathit{curve\_seg}_{b \boxminus_{0} 1} \qquad \forall\, b \in \mathcal{B}
        ```

        _Variable domains_

        **`x`**

        ```math
        x \ge 0
        ```

        **`y`**

        ```math
        y \ge 0
        ```

        **`curve_lam`**

        ```math
        0 \le \mathit{curve\_lam}_{b} \le 1 \qquad \forall\, b \in \mathcal{B}
        ```

        **`curve_seg`**

        ```math
        \mathit{curve\_seg}_{b} \in \{0, 1\} \qquad \forall\, b \in \mathcal{B}
        ```

        _Assumptions_

        **`curve_complete`**

        ```math
        \mathrm{x}^{\mathrm{bp}}_{b} \text{ is defined} \wedge \mathrm{y}^{\mathrm{bp}}_{b} \text{ is defined} \qquad \forall\, b \in \mathcal{B}
        ```

<!-- expansion:curve:end -->
<!-- prettier-ignore-end -->

The [`assumptions:`](../reference/language/assumptions.md) rows state what
the curve needs of its data.
[`Spec.expand()`](../reference/reading.md#formulations-written-out) lists what
the call accepts.
[Writing a formulation out](../reference/language/piecewise.md#writing-a-formulation-out)
says what each block emits.
