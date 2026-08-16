# Data binding

The YAML declares shapes; `sources` supplies the numbers, keyed by the names
the file declared:

```python
import lpspec as lps

result = lps.solve(
    'dispatch.yaml',
    {'load': 'load.parquet', 'cost': cost_frame, 'p_max': p_max_frame},
    coords={'snapshot': range(24)},
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

`pd.Series` keeps its dims in an *index* rather than in columns, so it is
unwrapped first — but only if pandas is already imported, never by importing
it. An unnamed index binds positionally to the declared `dims`; a named one
binds by name in any order, and a name outside the declared dims raises rather
than being overwritten.

**Tables in, arrays out.** An `xr.DataArray` is a dense n-dimensional array
rather than a table, and neither lane reads one: pass `array.to_series()`,
whose index binds by name on both. `Result.to_dataarray()` is the way back out.

Everything on this list is read by the [linopy lane](../../about/linopy.md#3-it-is-a-lane)
too, so one `sources` mapping goes to either.

Nothing on this path imports pandas, xarray or linopy on your behalf.

## Where coordinates come from

**Master coordinates are resolved per dimension before any parameter loads**,
highest precedence first:

1. **a key in `sources`** — a table carrying a column of that name, or a
   parquet path. The first occurrence of each value is its position;
2. **`coords=`** — anything `pd.Index()` accepts, or a table carrying the label
   column plus one column per [lookup](dimensions.md#lookups) over the
   dimension, each named after it;
3. **`values:` in the YAML** — the dimension's own, plus any
   [lookup](dimensions.md#values-puts-a-small-map-in-the-file) over it that
   declares one, assembled into the index a caller would otherwise pass.

There is no fourth step. A dimension none of the three supplies raises, and
labels are never read out of the parameters: they would *be* the definition,
so a mistyped label could not be told from a new one, and the index is also
what fixes label **order**, which [`shift`](operators.md#shift) reads
positionally.

## The data contract

Both lanes bind by these rules.

### Refused

| | |
|---|---|
| a declared parameter with no data | names the parameter |
| a key naming neither a parameter nor a dimension | names the near miss |
| a table missing a declared dim column, or `value` | names the columns needed |
| a label outside the dimension's index | names the parameter and the strays |
| two rows for one coordinate | |
| a lookup with two values for one label | |
| a lookup value that is not a label of its target | |
| a dimension carrying lookups with no index | |
| a dimension nothing can supply labels for | names both ways to fix it |

### Accepted

| | |
|---|---|
| an undeclared column in a table | ignored |
| a coordinate with no row | sparse data gives sparse variables; what a missing row means where it is read is [absence](absence.md) |
| values that are wrong but well-formed | not read |

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
