<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Relations as linear maps

This page says what a [relation](../reference/language/relations.md) is in the
language of linear algebra. It then shows that the dimension rule on that page
and the join an engine runs are one computation. Read it if "the dimensions a call
consumes, produces and joins on" reads as bookkeeping and you want the math it
stands for.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  zone: { dtype: str }
relations:
  gen_zone: { key: [generator, snapshot], values: zone }
parameters:
  zone_cap: { dims: [snapshot, zone] }
variables:
  p: { dims: [snapshot, generator] }
constraints:
  zonal:
    dims: [snapshot, zone]
    expression: sum(p, by=gen_zone, over=generator, into=zone) <= zone_cap
  pulled:
    dims: [snapshot, generator]
    where: gen_zone
    expression: p <= at(zone_cap, by=gen_zone, over=zone, into=generator)
objective:
  sense: minimize
  expression: sum(p)
```

## A relation is an indicator

A relation with columns over the dimensions $`D_1, \dots, D_n`$ is a set of
rows, so it is a subset $`R \subseteq D_1 \times \dots \times D_n`$. Its
**indicator** $`\mathbf{1}_R`$ is $`1`$ at a row of the table and $`0`$
everywhere else. `key:` is a claim about the shape of that set: one row per key
tuple. So a relation with `key: K` and `values: V` is the graph of a function
$`f: K \to V`$, and

```math
\mathbf{1}_R(k, v) = [\, f(k) = v \,].
```

The function is partial where a key tuple has no row. A bare relation is a
subset and nothing more. Above, `gen_zone` is the graph of
$`f: \mathcal{G} \times \mathcal{T} \to \mathcal{Z}`$. The
[data contract](../reference/language/relations.md#the-data-contract) makes it
one: the loader checks one row per key tuple when the data binds.

## A sum is a contraction

`sum(p, by=gen_zone, over=generator, into=zone)` is the product of two arrays,
summed over the one index they share and the call names:

```math
y_{t,z} = \sum_{g} \mathbf{1}_R(g, t, z) \cdot p_{t,g} = \sum_{g \,:\, f(g,\,t) = z} p_{t,g}
```

The right-hand form is what the typesetter
[prints](../reference/notation.md). The left-hand form is a tensor contraction,
and each kind of dimension on the relations page is one position an index can
take in it:

| The relations page says | In the formula                                              |
| ----------------------- | ----------------------------------------------------------- |
| consumed (`over=`)      | $`g`$ is on both factors and summed. It leaves.             |
| produced (`into=`)      | $`z`$ is on the indicator alone and not summed. It arrives. |
| joined on               | $`t`$ is on both factors and not summed. It stays.          |
| passes through          | on the operand alone and not summed. It stays.              |

**The result carries the free indices.** Those are the indices of the operand
and the indicator together, less the summed one, which is
`(dims(x) − consumed) ∪ produced`. That is the rule in the [expressions
reference](../reference/language/expressions.md#how-dimensions-combine),
and `_read_dims` in `src/math_spec/dimensions.py` computes it as
`(inner - consumed) | produced`. The three refusals beside it are the three
things the formula needs:

- **The operand carries every consumed dimension**, or there is nothing to sum.
- **The operand carries every joined dimension.** Otherwise $`t`$ would sit on
  the indicator alone, which is the produced position, and the call names a
  produced column with `into=`.
- **The operand carries no produced dimension.** Otherwise $`z`$ would sit on
  both factors and not be summed. That ties the two occurrences together
  instead of adding an axis. The language makes you write that tie outside the
  operator: `load * sum(p, by=gen_bus, over=generator, into=bus)`.

So "the indices an operation carries, adds and takes away" is the free-index
rule of a summation convention, applied to one product. Nothing on the relations
page is a separate rule.

**The joined dimension makes the matrix block-diagonal.** At each $`t`$,
$`M_t[z, g] = \mathbf{1}_R(g, t, z)`$ is a $`|\mathcal{Z}| \times |\mathcal{G}|`$
matrix of zeros and ones, and $`y_t = M_t\, p_t`$. A relation keyed by one
column has one block.

## A read is the transpose

`at(zone_cap, by=gen_zone, over=zone, into=generator)` reads the same table with
the other index bound:

```math
w_{t,g} = \sum_{z} \mathbf{1}_R(g, t, z) \cdot \mathrm{zone\_cap}_{t,z} = \mathrm{zone\_cap}_{t,\, f(g,\,t)}
```

Same indicator, same contraction, so the same free-index rule gives the result's
dimensions. As a matrix it is $`M_t^{\mathsf{T}}`$. Because $`R`$ is the graph
of $`f`$, the sum over $`z`$ has exactly one term where $`(g, t)`$ is in the
domain of $`f`$, and none elsewhere. So the contraction is the composition
$`\mathrm{zone\_cap} \circ f`$, which is a pullback.

**That one term is the whole difference between `at` and `sum`**, and
resolution decides it from the key alone. A call lands on the columns it names
in `into=` and the columns it joins on. Where those hold the whole key, each
output coordinate meets at most one row, and the call is a read. `_direction`
in `src/math_spec/resolution.py` names this `single_valued`. A `sum` that is
single-valued adds up nothing and is refused toward `at`. An `at` that is not
would have several terms and is refused toward `sum`. The
[relations page](../reference/language/relations.md#aggregates-and-reads)
quotes both messages.

**The two are adjoint.** For `gen_bus: { key: generator, values: bus }`,
$`x`$ over generators and $`y`$ over buses,

```math
\langle M x, y \rangle = \sum_{b} y_b \sum_{g} \mathbf{1}_R(g, b)\, x_g = \sum_{g} x_g \sum_{b} \mathbf{1}_R(g, b)\, y_b = \langle x, M^{\mathsf{T}} y \rangle,
```

which is what the program means by calling `Pullback` the adjoint of
`GroupSum`. A bare relation has the same matrix without the functional claim.
A column of $`M`$ may hold several ones, so the sum fans out and there is no
read. That is why `at` through a bare relation is refused.

## The join and the aggregate

The language fixes the formula, and an engine decides how to evaluate it. A
table stores $`\mathbf{1}_R`$ as its support: the rows where it is $`1`$.
Multiplying a matrix stored that way by a vector takes two steps.

1. **Pair each row of the table with each row of the operand that agrees on
   every shared index**, here $`g`$ and $`t`$. That is an inner equi-join on
   the consumed and joined columns. Each pair is one nonzero product
   $`1 \cdot p_{t,g}`$, relabelled by the produced column $`z`$.
2. **Add the pairs that agree on the free indices**, here $`(t, z)`$. That is a
   group-by on the result's dimensions with a sum.

lpspec, the reference engine, runs exactly these two steps. `walk_join` in
`src/lpspec/relational/engines/polars/relations.py` is step 1. It runs one inner
join on the consumed and joined dimensions. A select then drops the consumed
dimensions and renames the landing column to the produced one. Step 2 is the
terminal aggregate in `assembly.py`, a `group_by` over the row's coordinates
with `sum`, run once per constraint after every term has landed. Until then a
sum of linear terms is a list of terms, and adding is concatenation. `at` runs
step 1 against the same table and needs no step 2: single-valued means no two
pairs land on one coordinate. Where several $`(g, t)`$ share one $`z`$ the
join fans out, which is a column of $`M^{\mathsf{T}}`$ holding several ones.

So the two pictures are one. The join is the multiplication by an entry of
$`\mathbf{1}_R`$, which is $`1`$ or absent. The group-by is the $`\sum`$.

## Where the built model departs from the map

Two positions of the formula have no variable to build, and there the model a
consumer builds is not the matrix.

- **An empty fibre is the empty sum.** A zone no generator maps to at $`t`$ has
  $`y_{t,z} = 0`$, and the row reads $`0 \le \mathrm{zone\_cap}_{t,z}`$. It
  names no variable, so an engine [does not build
  it](../reference/language/absence.md#rows-with-no-variable-terms) and reports
  the omission. With `>=` the omitted row would have been infeasible.
- **Off the domain there is no value.** $`\mathrm{zone\_cap} \circ f`$ is
  undefined where $`f`$ is, so `at` is absent there and [absence
  spreads](../reference/language/absence.md#how-absence-travels) to the row.
  `where: gen_zone` on `pulled` writes the domain of $`f`$ on the page, so a
  reader sees which rows exist without opening the data.

## Partitions and tests

The other two uses of a relation do not contract against $`\mathbf{1}_R`$.

- **A partition steps inside a fibre.** `shift(x, along=snapshot, offset=1,
by=season_of, within=season)` reads the neighbour $`t'`$ of $`t`$ with
  $`f(t') = f(t)`$. The fibres of $`f`$ partition the axis, and the frame does
  not change.
- **A test is the indicator itself.** A relation's name in a `where` evaluates
  $`\mathbf{1}_R`$ at the frame's own coordinate, and keeps the coordinate where
  it is $`1`$.
