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
- an **`int` or `float`** for a 0-D parameter.

`pd.Series` keeps its dims in an *index* rather than in columns, so it is
unwrapped first — but only if pandas is already imported, never by importing
it. An unnamed index binds positionally to the declared `dims`; a named one
binds by name in any order, and a name outside the declared dims raises rather
than being overwritten.

**Tables in, arrays out.** An `xr.DataArray` is a dense n-dimensional array
rather than a table, and neither lane reads one: pass `array.to_series()`,
whose index binds by name on both. `Result.to_dataarray()` is the way back out.

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
   declares one, assembled into the index a caller would otherwise pass;
4. **derived from the parameter tables** that carry the dim, as **sorted**
   distinct values.

Step 4 is unavailable to a dimension carrying lookups whose maps the file does
not declare: it reads index columns only, so it cannot supply a lookup column.
Otherwise it exists because a dim some parameter already spans needs no second
declaration — but it costs the **declared order**, which
[`shift`](operators.md#shift) reads positionally, so pass an explicit index
whenever order matters. It also costs a full pass — a
scan plus a dedup — over *every* parameter carrying the dim before building
starts, where an explicit index is read as one dim-sized table.

A dim that no source names and no parameter carries raises.

## What is checked

- **Coordinate values in the data must be a subset of the master coordinate.**
  Values outside it raise rather than being dropped silently.
- **Every declared parameter must be provided, and every provided key must be
  declared** — the YAML is the source of truth.
- Validation order: lookup columns → parameter presence → dim names →
  coordinate values → unknown keys.

The loader deliberately does **not** check that values are sensible, that a
parameter is used, or that coordinates *cover* the master index. Missing
coordinates produce no rows — sparse data gives sparse variables, and what a
missing row means where the model reads it is [absence](absence.md).

## Growing or replacing the data

A model that is already built takes new numbers with
[`rebind`](../api.md#re-solving-with-new-numbers), and a sweep over slices of
one dimension is [`solve_over`](../sweeps.md). Both bind through the rules
above.

The opt-in [linopy shim](../../about/linopy.md#the-same-language-different-data-inputs)
accepts the same *language* but a different set of data inputs, and has no
step 4.
