<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What renders where

Each line should show `a > b` or `a < b` as an equation. Where it shows
`a &gt; b` or `a &lt; b` instead, GitHub escaped the character twice.

## Top level, outside a fold

1. fence, `>`

```math
a > b
```

2. verbatim inline pair, `>`: $`a > b`$

3. verbatim inline pair, `\gt`: $`a \gt b`$

4. verbatim inline pair, `<`: $`a < b`$

5. verbatim inline pair, `\lt`: $`a \lt b`$

<details>
<summary>Inside a fold</summary>

6. fence, `>`

```math
a > b
```

7. verbatim inline pair, `>`: $`a > b`$

8. verbatim inline pair, `\gt`: $`a \gt b`$

9. a table cell

| Symbol | Meaning |
|---|---|
| $`a > b`$ | with `>` |
| $`a \gt b`$ | with `\gt` |

</details>
