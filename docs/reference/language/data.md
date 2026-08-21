<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Data binding

The YAML declares shapes; `sources` supplies the numbers, keyed by the names
the file declared:

```python
import math_spec as lps

result = lps.solve(
    'dispatch.yaml',
    {'load': 'load.parquet', 'cost': cost_frame, 'p_max': p_max_frame},
)
```

## What a parameter accepts

For a parameter declared `dims: [d1, d2]`:

- a **parquet path**;
- **any table exposing the Arrow PyCapsule protocol** — polars, pandas,
  pyarrow, duckdb — with columns `d1, d2, value`;
- an **`int` or `float`**, standing for every coordinate the parameter covers;
- a **`dict`** of label to value, for a parameter over one dimension;
- a **sequence** — list, tuple, `np.ndarray` — for a parameter over one
  dimension, positional against that dimension's index.

The last three are for models written out in Python. Each is dense, so each is
materialised at bind: one number over `(snapshot, generator)` becomes a row per
pair, and a value that really is constant is better declared `dims: []`. A
sequence is positional, so the dimension's labels have to come from somewhere
other than this parameter — one of the three sources below, which is what fixes
the order it is positional against.

`pd.Series` keeps its one dim in an _index_ rather than in a column, so it is
unwrapped first — but only if pandas is already imported, never by importing
it. An unnamed index binds to the declared dim; a named one binds by that name,
and a name outside the declared dims raises rather than being overwritten.

**One dimension only.** A `MultiIndex` is refused: an index is a pandas idea
with no counterpart in the frames both lanes build, and its _depth_ is a second
claim about what the parameter is over, free to disagree with the declaration
with nothing able to say which was meant. A parameter over two dims arrives as
a frame carrying both as columns — `series.reset_index()` is the whole change,
and columns are what the other five shapes on this list already use.

**Tables in, arrays out.** An `xr.DataArray` is a dense n-dimensional array
rather than a table, and neither lane reads one: pass
`array.to_series().reset_index()`. `Result.to_dataarray()` is the way back
out.

Everything on this list is read by the [linopy lane](../../about/linopy.md#3-it-is-a-lane)
too, so one `sources` mapping goes to either.

Nothing on this path imports pandas, xarray or linopy on your behalf.

## Where coordinates come from

**Master coordinates are resolved per dimension before any parameter loads**,
from exactly one of:

1. **a key in `sources`** — a table carrying a column of that name, or a
   parquet path. The first occurrence of each value is its position;
2. **`dimensions.<d>.values` in the YAML** — the labels written out in the file.

**The two are exclusive, not ranked.** A dimension the file declares and the
caller also supplies is refused at bind, naming the declaration and the key that
collided with it. The file owns that dimension's labels or the caller does,
never both — so there is no precedence to remember, and no way for the file a
reviewer reads to describe a model the caller quietly replaced. A model whose
label set varies from run to run should not declare one.

**A [map](dimensions.md#lookups) is not on that list either.** It says how
labels map, never which ones exist: a map is a partial relation over the
dimension, free to omit members and written in whatever order someone typed,
and neither may decide an extent nor an order that
[`shift`](operators.md#shift) reads positionally. A map is instead _read
against_ whichever of the two supplied the labels. Each has **one author out of
two** — `lookups.<x>.values` in the file, or its own source key — and both of
them, or neither, is a refusal. Which leaves one index with two authors, one
fact each: **labels from the caller, maps from wherever each map lives.**

Reading a map against labels is **not symmetric**, because the two directions
mean different things. A label no map mentions is **unmapped** — the partial
case, and what a relation over a dimension is entitled to be. A key matching no
label is a **typo**, and refused: dropping it would place its terms nowhere
while the model built and solved. Where the file declares the labels too, that
same refusal happens at load with no data at all.

**A map supplied as data is a
[`(over, <label space>)` table](dimensions.md#otherwise-it-is-supplied-under-the-lookups-own-name)
of the rows it has**, so an unmapped label is one with no row — the absence rule
everything else obeys — and a null in the value column is refused for saying
both at once. A column of the index named after a lookup over it is refused
too: every other stray column is a dump's extra, and that one is a map.

There is no third step. A dimension neither of the two supplies raises, and
labels are never read out of the parameters: they would _be_ the definition,
so a mistyped label could not be told from a new one, and the index is also
what fixes label **order**, which [`shift`](operators.md#shift) reads
positionally.

## The data contract

Both lanes bind by these rules, and `tests/test_data_parity.py` is what holds
them to it: the same malformed source, checked for the same verdict and — where
one defect has one repair — the same sentence.

**A coordinate has a value, or it has no row.** A row whose value is null or
NaN says both at once, and is refused at bind naming the parameter and the
coordinates. The pair is one rule because the spelling is the source's rather
than the model's: polars and parquet write a hole as a null, pandas has only
NaN, and `None` in a pandas column _is_ NaN by the time either lane sees it.
Sparsity is the absent row.

### Refused

|                                                                         |                                                                                    |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| a declared parameter with no data                                       | names the parameter                                                                |
| a source nothing can be read as a table from                            | names the shapes that are read                                                     |
| an `xr.DataArray`                                                       | names `to_series().reset_index()`, this being a lane's output rather than an input |
| a `pd.Series` with a `MultiIndex`                                       | names the tidy frame, and the `reset_index()` that gets there                      |
| a `dims: []` parameter whose source has more than one row               | one value broadcast everywhere has one row                                         |
| a dict or a sequence for a parameter over more than one dim             | each runs along one dimension                                                      |
| a sequence whose length is not the dimension's                          | positional, so one entry per label                                                 |
| a sequence for a dimension nothing else supplies labels for             | names the three ways to supply them                                                |
| a key naming neither a parameter, a dimension nor a lookup              | names the near miss                                                                |
| a lookup relation short of either column                                | names the pair, and what each is                                                   |
| a lookup relation with a null in its value column                       | a map is partial by omitting a row                                                 |
| a lookup relation mapping one label twice                               | a lookup is single-valued                                                          |
| a map with both authors, or neither                                     | names them, and says which way out                                                 |
| an index carrying a column named after a lookup over it                 | names the key it belongs under                                                     |
| a table missing a declared dim column, or `value`                       | names the columns needed                                                           |
| a `value` column carrying a null or a NaN                               | names the parameter and the coordinates                                            |
| a label outside the dimension's index                                   | names the parameter and the strays                                                 |
| two rows for one coordinate                                             |                                                                                    |
| a lookup with two values for one label                                  |                                                                                    |
| a lookup value that is not a label of its target                        | one wording, checked once for both lanes                                           |
| a dimension carrying lookups with no index                              |                                                                                    |
| a dimension nothing can supply labels for                               | names both ways to fix it                                                          |
| a dimension the file declares and the caller also supplies              | names the declaration and the colliding key                                        |
| a lookup whose map the file declares and the caller also supplies       | names the map and the colliding column                                             |
| a declared map whose labels nothing supplies                            | names the map, and asks only for the labels                                        |
| a declared map keyed by something the labels do not carry               | names the lookup and the strays                                                    |
| a column that is not the declared `dtype`                               | names both, and the declaration the data would satisfy                             |
| a divisor with no value where the model divides by it                   | names the parameter and how many rows ([absence](absence.md))                      |
| a comparison's whole constant side with no value where the row is built | the same, naming the constraint                                                    |
| a bound parameter with no value where the variable exists               | names both models the two repairs build                                            |

### Accepted

|                                    |                                                                                                                                                                                                                                                               |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| an undeclared column in a table    | ignored                                                                                                                                                                                                                                                       |
| a coordinate with no row           | sparse data gives sparse variables; what a missing row means where it is read is [absence](absence.md). `diagnostics().sparse_parameters` says which parameters arrived short of their dims, so a lost row is at least visible ([api](../api.md#diagnostics)) |
| a value that is readable and wrong | bound as given; no number is second-guessed                                                                                                                                                                                                                   |

### The index is what makes a stray label a stray

```python
cost = {'wind': 1.0, 'gsa': 2.0}  # 'gas' misspelled — refused by name
```

A dimension whose labels came from the parameters instead would read that as a
third generator, and answer a different question.

## Growing or replacing the data

A model that is already built takes new numbers with
[`rebind`](../api.md#re-solving-with-new-numbers), and a sweep over slices of
one dimension is [`solve_over`](../sweeps.md). Both bind through the rules
above.

The opt-in [linopy lane](../../about/linopy.md#the-same-language-and-the-same-data)
binds by these same rules, refusals included.
