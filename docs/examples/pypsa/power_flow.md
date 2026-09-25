<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Power flow

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: Kirchhoff's voltage law around each cycle. It declares `Cycle_angle_sum` as a sum with a frame and no body, which the lines and transformers add to.

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  cycle:
    description: independent cycles of the passive network graph — the cycle basis, data prep

expressions:
  Cycle_angle_sum:
    dims: [scenario, snapshot, cycle]
    description: >-
      the voltage angle differences around a cycle: every branch flow times
      its cycle weight, and every transformer phase shift

constraints:
  Kirchhoff_Voltage_Law:
    description: >-
      `Kirchhoff-Voltage-Law` — around every independent cycle the
      impedance-weighted flows sum to nothing, which is what makes the linear
      power flow physical rather than transport. A transformer's flow weighs its
      effective reactance, and its phase shift enters the cycle sum too: a
      constant where the shift is fixed, or the shift decision times its cycle
      weight where the shift is a phase-shifting transformer's to choose
    dims: [scenario, snapshot, cycle]
    expression: Cycle_angle_sum == 0
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{C}`$ | index $`c`$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{Cycle\_angle\_sum}`$ | `Cycle_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$, a sum other files add terms to — the voltage angle differences around a cycle: every branch flow times its cycle weight, and every transformer phase shift |

#### Subject to

**`Kirchhoff_Voltage_Law`**

```math
\mathit{Cycle\_angle\_sum}_{\xi,t,c} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```
<!-- gallery:end -->
