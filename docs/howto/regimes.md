<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Vary a rule by regime

Give some members of a dimension a different rule, in one model file. The
usual case is a fleet of generators where only some are committable: those
have an on/off state, and the others do not.

## Put the regime in the data

A `bool` parameter says which members are in the regime. A `str` parameter
names one of several regimes:

```yaml
parameters:
  committable: { dims: [generator], dtype: bool }
```

## Write one block per regime

Put each block under its own [`where:`](../reference/language/absence.md). A
block builds rows only where its mask holds, so a regime that needs no row gets
none:

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  capacity: { dims: [generator] }
  min_output: { dims: [generator] }
  committable: { dims: [generator], dtype: bool }

variables:
  dispatch: { dims: [snapshot, generator], bounds: { lower: 0, upper: capacity } }
  on: { dims: [snapshot, generator], where: committable, domain: binary }

constraints:
  floor_committed:
    dims: [snapshot, generator]
    where: committable
    expression: dispatch >= min_output * on
  ceiling_committed:
    dims: [snapshot, generator]
    where: committable
    expression: dispatch <= capacity * on
```

??? example "Rendered output"

    **`floor_committed`**

    ```math
    \mathit{dispatch}_{t,g} \ge \mathrm{min\_output}_{g} \cdot \mathit{on}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{committable}_{g}
    ```

    **`ceiling_committed`**

    ```math
    \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \cdot \mathit{on}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{committable}_{g}
    ```

Here the variable's `bounds:` limit a non-committable generator to
`capacity`. To give the other regime a rule of its own, write a third block
under `where: "NOT committable"`.

## Vary a quantity with `cases:`

Sometimes the regime changes a quantity, not a rule. Then name the quantity
with [`cases:`](../reference/language/named.md#cases), and write the rule once
against it:

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  capacity: { dims: [generator] }
  committable: { dims: [generator], dtype: bool }

variables:
  dispatch: { dims: [snapshot, generator], bounds: { lower: 0 } }
  on: { dims: [snapshot, generator], where: committable, domain: binary }

expressions:
  available:
    dims: [snapshot, generator]
    cases:
      committed:
        when: committable
        expression: capacity * on
    otherwise: capacity

constraints:
  ceiling:
    dims: [snapshot, generator]
    expression: dispatch <= available
```

`otherwise:` takes every coordinate that the cases leave.

## Check the file

```bash
python -m mathspec check model.yaml
```

The check refuses two masks that can both hold, and a `cases:` block with no
`otherwise:`. The message names the rewrite.
