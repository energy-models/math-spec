<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# State a rule that differs by regime

Write one model in which a rule takes a different form for some members of a
dimension. Committable and non-committable generators are the usual case, and
the recipe needs no second model file.

1. **Put the regime in the data.** A `bool` parameter says which members are
   in it; a `str` parameter names one of several:

   ```yaml
   parameters:
     committable: { dims: [generator], dtype: bool }
   ```

2. **Write one block per regime, each under its own `where:`.** The block
   builds rows only where its mask holds, so a regime that needs no row gets
   none:

   ```yaml
   dimensions:
     snapshot: { dtype: int }
     generator: { dtype: str }

   parameters:
     p_max: { dims: [generator] }
     p_min: { dims: [generator] }
     committable: { dims: [generator], dtype: bool }

   variables:
     p: { dims: [snapshot, generator], bounds: { lower: 0, upper: p_max } }
     on: { dims: [snapshot, generator], where: committable, domain: binary }

   constraints:
     floor_committed:
       dims: [snapshot, generator]
       where: committable
       expression: p >= p_min * on
     ceiling_committed:
       dims: [snapshot, generator]
       where: committable
       expression: p <= p_max * on
   ```

   Here a non-committable generator is bounded by `p_max` alone, through the
   variable's `bounds:`. Where the other regime has a rule of its own, write
   it as a third block under `where: "NOT committable"`.

3. **Where the regime changes a quantity rather than a rule, name the
   quantity with `cases:`** and write the rule once against it:

   ```yaml
   dimensions:
     snapshot: { dtype: int }
     generator: { dtype: str }

   parameters:
     p_max: { dims: [generator] }
     committable: { dims: [generator], dtype: bool }

   variables:
     p: { dims: [snapshot, generator], bounds: { lower: 0 } }
     on: { dims: [snapshot, generator], where: committable, domain: binary }

   expressions:
     available:
       dims: [snapshot, generator]
       cases:
         committed:
           when: committable
           expression: p_max * on
       otherwise: p_max

   constraints:
     ceiling:
       dims: [snapshot, generator]
       expression: p <= available
   ```

   The loader proves at load that no two cases can hold at one coordinate,
   and `otherwise:` takes every coordinate they leave.

4. **Check it** with `python -m math_spec check model.yaml`. A pair of masks
   that can both hold, or a case with no `otherwise:`, is refused there with
   the rewrite named.

What a `where:` means is under [absence](../reference/language/absence.md);
what a `cases:` block accepts is under
[named expressions](../reference/language/expressions.md#cases--one-quantity-a-value-per-region).
