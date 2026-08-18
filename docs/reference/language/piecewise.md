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

A block **expands before building** into plain variables and constraints via a
λ convex combination — weights in `[0,1]` with a convexity row, and one link
row per tuple. That expansion is what the rest of the model, and the
[typeset output](../typeset.md), sees.

**`method` is the one thing that varies**, and it varies in exactly one place:
how the weights are restricted, once they exist.

| `method` | What it adds | |
|---|---|---|
| `adjacency` *(default)* | a binary per segment, and `lam <= seg + shift(seg, over=bp, offset=1, edge=0)` | the curve, built |
| `sos2` | an [`sos:`](#sos) block over the same weights | the curve, *said* — for a solver that branches on the set itself |
| `convex` | nothing | the hull, which is a pure LP |

`adjacency` and `sos2` state the same restriction and reach the same optimum;
they differ in what the solver is handed, so which is faster is a property of
the solver and not of the model.

`convex` is a **different model** — exact only for a curve of matching
curvature under optimisation pressure, which is checked against the breakpoint
*values* when data binds. It takes exactly two links and no `active`.

linopy's tangent-line formulation, `method: lp`, is
[#695](https://github.com/fluxopt/lpspec/issues/695) and not here.

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
