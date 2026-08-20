# Piecewise curves and SOS

Two blocks for the shapes a purely affine language cannot state directly: a
curve through breakpoints, and a family of variables of which only one — or two
neighbours — may be nonzero.

## `piecewise`

N expressions jointly pinned to a breakpoint-indexed piecewise-linear curve.

<!-- doctest: wrap=piecewise -->
```yaml
chp:
  over: bp  # breakpoint dimension
  links:
    - [power, power_bp]  # [expression, values-parameter]
    - [fuel, fuel_bp]
    - [heat, heat_bp]
  method: adjacency  # how the weights are restricted — below
  active: null  # optional gating expression: formulation pinned to 0

# a two-link block may bound one side instead of pinning it
fuel_cap:
  over: bp
  links:
    - [power, power_bp]
    - [fuel, fuel_bp, "<="]
```

| Part of a link | |
|---|---|
| *expression* | any affine expression — a bare variable name being the simplest |
| *values* | a parameter carrying the `over` dim, so curves may vary along other dims (per generator, say) |
| *sign* | `<=` or `>=`, at most one per block and only with exactly two links: bounds the link instead of pinning it |

`points:` says how far each curve runs where they are not all the same length —
below. `active:` is a different question: whether a curve *applies*, gated by a
variable, rather than how long it is.

A block **expands before building** into plain variables and constraints, for
three of the four methods via a λ convex combination — weights in `[0,1]` with
a convexity row, and one link row per tuple. That expansion is what the rest of
the model, and the [typeset output](../typeset.md), sees.

**A curve is supplied everywhere it is built.** The expansion emits one weight
per breakpoint over the whole product of its dims and masks none of them, so a
values parameter short of a row does not build a shorter curve: the
[absence rules](absence.md#what-creates-absence) read the missing row as a zero
coefficient, which is a breakpoint at the origin the file never declared. Such a
table is refused when data binds.

**A curve with fewer breakpoints than the dimension holds masks its tail**, with
`points:` — a boolean parameter over the curve's own coordinates and `over`,
true up to each curve's last breakpoint:

<!-- doctest: wrap=piecewise -->
```yaml
cost_curve:
  over: bp
  points: bp_present  # true where this curve still runs
  links:
    - [p, bp_x]
    - [op_cost, bp_y]
```

The masked breakpoint declares no weight and no segment binary, and its values
are not asked for. The mask is ordinary data — a model that keeps a
length per curve crosses it with the breakpoints and compares, wherever the rest
of its tables are prepared. **The mask is a prefix**: a curve runs from the first
breakpoint to its own last one, and a gap — or a curve marked nowhere — is
refused when data binds, because the chord row joins a breakpoint to the one
before it and the domain row is written where the mask stops.

Where the *arity* is data, and one component ties three expressions where
another ties two, the λ formulation is written out directly rather than through
this block ([#1101](https://github.com/fluxopt/lpspec/issues/1101)).

**`method` is the one thing that varies**, and for those three it varies in
exactly one place: how the weights are restricted, once they exist.

| `method` | What it adds | |
|---|---|---|
| `adjacency` *(default)* | a binary per segment, and `lam <= seg + shift(seg, over=bp, offset=1, edge=0)` | the curve, built |
| `sos2` | an [`sos:`](#sos) block over the same weights | the curve, *said* — for a solver that branches on the set itself |
| `convex` | nothing | the hull, which is a pure LP |
| `lp` | no weights at all — a row per segment line, and two holding the domain | the curve as its own lines |

`adjacency` and `sos2` state the same restriction and reach the same optimum;
they differ in what the solver is handed, so which is faster is a property of
the solver and not of the model.

`convex` is a **different model** — exact only for a curve of matching
curvature under optimisation pressure, which is checked against the breakpoint
*values* when data binds. It takes exactly two links and no `active`.

### `lp`, the one that declares nothing

`lp` states the curve as its **segment lines** instead of interpolating between
its breakpoints, so it declares no auxiliary variable at all — where the others
carry one weight per breakpoint per frame row. It needs exactly two links, one
of them bounded (`<=` or `>=`), and no `active:` — there are no weights for a
gate to pin down.

<!-- doctest: wrap=piecewise -->
```yaml
cost_curve:
  over: bp
  method: lp
  links:
    - [p, bp_x]
    - [op_cost, bp_y, ">="]   # cost bounded below by the curve
```

The trade is **columns for rows**: one row per segment plus the two domain
rows, against K weight columns. On a 20-generator, 48-snapshot, 6-breakpoint
dispatch it is 7680 → 1920 columns and 2928 → 6768 rows, at the same optimum
([#926](https://github.com/fluxopt/lpspec/pull/926)).

Two things follow from stating lines rather than weights:

- **The curvature has to match the sign**, and getting it wrong is silent —
  lines that envelope a convex curve *cut* a concave one, and the solve comes
  back optimal with a wrong answer. `>=` requires a convex curve and `<=` a
  concave one, checked against the values when data binds. This is stricter
  than `convex`'s check, which only refuses a *mixed* curve.
- **A line does not stop where its segment does**, so the block emits the two
  domain rows that hold the pinned link inside the breakpoint range. Without
  them the formulation would extrapolate along the end segments, where the
  weight forms cannot go. They are the rows `linopy`'s own `lp` method emits.

## `sos`

A **special-ordered set**: one dimension of one variable, and how many of that
family may be nonzero at once.

<!-- doctest: wrap=sos -->
```yaml
pick_one_size:
  variable: build  # the variable the set is over
  over: size  # the dim it runs along — one set per coordinate of the rest
  type: 1  # 1: at most one nonzero; 2: at most two, and consecutive
  big_m: 500  # optional, and only read by a solver that has to reformulate
```

`type: 1` is a **choice** — at most one member of the family is nonzero.
`type: 2` is an **interpolation** — at most two, and those two *consecutive*,
which is what makes it the native spelling of a piecewise-linear curve.

**A set is over one variable, and a variable holds one set.** A second block
naming the same variable is a load error.

**Membership is the variable's own.** Its `where` decides which coordinates
exist, so a masked-out member is not in the set — and for `type: 2`,
consecutive means consecutive *among the members present*, leaving no hole
where a coordinate was masked away.

**Order is the `over` dimension's declared order** — the same order `shift`
walks ([data binding](data.md)) — so reordering the set means reordering that
index. There is no per-set weight to supply.

### What a solver without SOS does with it

Where the chosen solver has no SOS concept, the set is handed over as binaries
and big-M rows instead. Two consequences reach the model, so neither is silent:

- that rewrite is **mixed-integer**, so a set on an otherwise continuous model
  gives up its [duals](../api.md#reading-a-result) there;
- **M has to be finite**, so every member needs `bounds.upper` or a `big_m:`,
  and a negative `bounds.lower` is refused. `big_m` caps a loose bound — the
  *tighter* of the two is used, tighter being a better relaxation.

Both are conditions of the *rewrite*, so a model that fails them still solves
on a solver that takes the set, and the message says so. HiGHS, which ships
with the package, reformulates; Gurobi branches on the set itself.
