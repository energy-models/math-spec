<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Pin a variable

Use one model for two studies. In one study, the solver chooses a quantity,
such as the size of a plant. In the other, the data gives it. The model file
stays the same, and only the data changes.

1. **Declare the quantity as a variable, with named bounds.**

   ```yaml
   dimensions:
     plant: { dtype: str }
   parameters:
     size_min: { dims: [plant] }
     size_max: { dims: [plant] }
   variables:
     size:
       dims: [plant]
       bounds: { lower: size_min, upper: size_max }
   ```

2. **Write every rule against the variable.** `rate - relmax * size <= 0` is
   one equation, whether the solver chooses `size` or the data gives it.

3. **Pin it in the data.** For a plant with a known size, attach the same value
   as `size_min` and `size_max`. Equal bounds pin a variable
   ([variables](../reference/language/declarations.md#variables)).

??? note "The whole file"

    ```yaml
    dimensions:
      plant: { dtype: str }
      time: { dtype: int }

    parameters:
      size_min: { dims: [plant] }
      size_max: { dims: [plant] }
      relmax: { dims: [plant, time] }
      demand: { dims: [time] }
      size_cost: { dims: [plant] }

    variables:
      size:
        dims: [plant]
        bounds: { lower: size_min, upper: size_max }
      rate:
        dims: [plant, time]
        bounds: { lower: 0 }

    constraints:
      within_size:
        dims: [plant, time]
        expression: rate - relmax * size <= 0
      meet_demand:
        dims: [time]
        expression: sum(rate, over=plant) == demand

    objective:
      sense: minimize
      expression: sum(size * size_cost)
    ```

## Limits

A pinned variable is still a variable:

- **`size * on` is `variable * variable`**, which is quadratic.
- **`size` cannot be a bound of another variable.** Where a bound comes from
  the size, also declare the size as a parameter, and attach it as data.
