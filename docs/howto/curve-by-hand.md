<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Write a piecewise curve out by hand

Tie a number of flows to one curve where that number is data: a boiler ties two
flows and a CHP unit ties three, in one model. A
[`piecewise:`](../reference/language/piecewise.md) block lists its links in the
file, so it cannot say this. The formulation written out can.

1. **Declare the weights as a variable over the breakpoint dimension**, masked
   to how far each curve runs:

   ```yaml
   variables:
     weight: # the convex combination, one per converter and period
       dims: [converter, time, bp]
       where: bp_present # how far each curve runs
       bounds: { lower: 0, upper: 1 }
   ```

2. **Restrict the weights with an `sos:` block.** `type: 2` states the
   restriction that `method: sos2` emits:

   ```yaml
   sos:
     on_one_segment: { variable: weight, over: bp, type: 2 }
   ```

3. **Write the convexity row, and one row per flow.** The row per flow is where
   the count goes, and a relation carries it:

   ```yaml
   constraints:
     one_operating_point:
       dims: [converter, time]
       expression: sum(weight, over=bp) == 1
     on_the_curve: # one row per flow
       dims: [flow, time]
       expression: rate == sum(at(weight, by=converter_of[converter]) * bp_rate, over=bp)
   ```

A converter with a fourth flow is then a row in a table.
