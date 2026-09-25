<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Write a curve by hand

Use this when the number of flows on one curve comes from the data. For
example, a boiler ties two flows to its curve and a CHP (combined heat and
power) unit ties three, in the same model. A
[`piecewise:`](../reference/language/piecewise.md) block lists its links in
the file, so it cannot do this. Write the formulation out instead.

1. **Declare the weights as a variable over the breakpoint dimension.** Mask
   them to how far each curve runs:

   ```yaml
   variables:
     weight: # the convex combination, one per converter and period
       dims: [converter, time, bp]
       where: bp_present # how far each curve runs
       bounds: { lower: 0, upper: 1 }
   ```

2. **Restrict the weights with an `sos:` block.** `type: 2` states the same
   restriction that `method: sos2` emits:

   ```yaml
   sos:
     on_one_segment: { variable: weight, along: bp, type: 2 }
   ```

3. **Write the convexity row, and one row per flow.** A relation from each flow
   to its converter carries the number of flows:

   ```yaml
   constraints:
     one_operating_point:
       dims: [converter, time]
       expression: sum(weight, over=bp) == 1
     on_the_curve: # one row per flow
       dims: [flow, time]
       expression: rate == sum(at(weight, by=converter_of, over=converter, into=flow) * bp_rate, over=bp)
   ```

A converter with a fourth flow is then one more row in the data for
`converter_of`. The model file does not change.

??? note "The whole file"

    ```yaml
    dimensions:
      converter: { dtype: str }
      flow: { dtype: str }
      time: { dtype: int }
      bp: { dtype: int }

    relations:
      converter_of: { key: flow, values: converter }

    parameters:
      bp_present: { dims: [converter, bp], dtype: bool }
      bp_rate: { dims: [flow, bp] }

    variables:
      rate: { dims: [flow, time] }
      weight:
        dims: [converter, time, bp]
        where: bp_present
        bounds: { lower: 0, upper: 1 }

    sos:
      on_one_segment: { variable: weight, along: bp, type: 2 }

    constraints:
      one_operating_point:
        dims: [converter, time]
        expression: sum(weight, over=bp) == 1
      on_the_curve:
        dims: [flow, time]
        expression: rate == sum(at(weight, by=converter_of, over=converter, into=flow) * bp_rate, over=bp)
    ```
