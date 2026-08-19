# Errors and limits

## Everything decidable without data is decided without data

Anything detectable before building is detected before building. The worst
error this language could hand you is an opaque solver or array exception with
no pointer back to a YAML declaration, so a model is parsed, expanded, resolved
and dim-checked — including *uncalled* macro templates and every `where` string
— before a single source is read.

`lps.check('model.yaml')` runs exactly that and binds nothing, which is why it
is the CI verb: a model repository can be validated on every commit without
shipping the data.

Every message names what went wrong, what to do about it, and where it helps,
the valid options:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['p', 'soc']
  Parameters: ['p_max', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

A construct outside the language names the construct and its rewrite, never a
silent fallback.

## One answer is decidable without data too

A variable that no constraint names, and whose bounds leave open the side its
objective term improves toward, runs to infinity for every dataset there is. A
solver says that with a bare `unbounded` naming nothing; `check` says it with
the variable and the side, as advice:

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is -inf, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

Advice and not a refusal, because the same shape is what a half-written model
looks like — a variable declared before the constraint that will hold it — and
`build` and `solve` stay open to one. The price is that only `check` says it:
go straight to `solve` and the solver's bare answer is still the first word.

Both halves of the conjunction are needed, and neither alone is wrong: a
variable held by nothing but its own `bounds:` is ordinary, and so is an
unbounded one that a constraint names. Where the sign a variable enters the
objective with is *data* — a parameter coefficient, which may be zero or either
sign — nothing is said, because a note against a model that solves is the worse
error. The per-coordinate case, where a `where:` mask leaves one slice of a
variable with no constraint row, still reaches you from the solver
([#229](https://github.com/fluxopt/lpspec/issues/229)).

## Which error you get

| | |
|---|---|
| `LpspecError` | the root of the tree; everything below is an instance of it |
| `LanguageError` | the model: a construct outside the language, a dim set that does not compose, a name nothing declares |
| `SchemaError` | the file: an unknown key, a malformed declaration, a bad symbol table |
| `DimensionError` | dims that disagree — a constraint whose expression does not equal its `foreach` |
| `PiecewiseExpansionError` | a `piecewise:` block that cannot be expanded |
| `LaneError` | the lane: a model both accept, that this one cannot build — the other route can ([lanes](../../about/linopy.md)) |
| `DataError` | what was bound: a missing source, an unreadable one, a coordinate outside the master index |
| `NoSolutionError` | the answer: reading values off a solve that returned none — infeasible, unbounded, errored |

The split is the useful one for a caller: `LanguageError` and its subclasses
are the *file* being wrong, and are reproducible from the YAML alone;
`DataError` is the numbers being wrong for a file that is fine; `LaneError` is
neither wrong, and names the route that builds it.

`check` also issues an `LpspecWarning` for advice short of an error — a
declared dimension nothing uses as an axis, say. It is the only place warnings
come from.

## What the language will not say

Refusals, and what to reach for instead. None of them is an unimplemented
feature list: each is a boundary the design keeps on purpose, and
[the ceiling](../../about/ceiling.md) is the argument for where it sits.

| Not here | Instead |
|---|---|
| variable × variable, or `**` | nothing — degree 1 is the ceiling ([expressions](expressions.md#degree-1-always)) |
| arithmetic in `bounds:` | a name or a number; ship the derived column as data ([#31](https://github.com/fluxopt/lpspec/issues/31)) |
| time-series processing (resample, cluster, interpolate, align), file IO, units | data prep; pass a parameter |
| solver breadth | two solvers — HiGHS, which ships, and Gurobi via the `[gurobi]` extra — chosen at the call and never in the file; LP files for everything else ([#106](https://github.com/fluxopt/lpspec/issues/106)) |
| indicator constraints | planned as a *solver capability* rather than a language question, the same axis `sos:` landed on ([#220](https://github.com/fluxopt/lpspec/issues/220)) |
| multi-objective | one `objective:` block — a second is unsayable; weight them into one expression |
| arbitrary array ops (`merge`, `reindex`, `apply_ufunc`) | data prep — the closed operator set is what makes streaming possible |
| filling a missing value (`.fillna`) | data prep, or a `where` if you meant the coordinate not to exist. In the language only where the data cannot reach: `shift(..., edge=)` ([absence](absence.md)) |
| schema migrations | — |

A model built partly in Python has no readable `.yaml` representation and will
not get one: the *math* side is feasible, but expression and `where` strings
come back as anonymous arrays, so the round trip would be functional and not
reviewable — which is the whole point of the file. A framework that wants to
*emit* declarations passes a dict, and gets `to_yaml()` back
([Python API](../api.md#a-model-four-ways)).

Where the language genuinely cannot say the math, the escape hatch is a
declared `escape:` island — named in the file, bounded by the preceding `where`
mask, terminal, and billed against a label budget before any Python runs. It is
[#38](https://github.com/fluxopt/lpspec/issues/38) and not shipped.
