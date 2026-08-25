# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``piecewise:`` blocks into plain variables and constraints.

A ``piecewise:`` block becomes ordinary affine declarations before anything
reads the model. The λ convex-combination method needs only the breakpoint
parameters themselves, no derived data. For a block

    piecewise:
      curve:
        over: bp
        links:
          - [power, power_bp]
          - [fuel * eff, fuel_bp, "<="]

with F = the union of the links' dims, it emits:

    variables:
      curve_lam(F, bp)  in [0, 1]
      curve_seg(F, bp)  binary                            (method: adjacency)
    constraints:
      curve_convexity(F):     sum(curve_lam, over=bp) == 1
      curve_pick(F):          sum(curve_seg, over=bp) == 1        (method: adjacency)
      curve_adjacency(F, bp): curve_lam <= curve_seg + shift(curve_seg, over=bp, offset=1, edge=0)
      curve_link0(F):         (power) == sum(curve_lam * power_bp, over=bp)
      curve_link1(F):         (fuel * eff) <= sum(curve_lam * fuel_bp, over=bp)

**Only the restriction on λ varies** (:data:`~math_spec.model.PIECEWISE_METHODS`):
every method emits the weights, the convexity row and the links; ``adjacency``
adds the binaries above, ``sos2`` states the same restriction as a ``sos:``
block, ``convex`` adds nothing and leaves λ over the hull.

A link expression is judged against the language before expansion, so ``p * p``
is named against the link the user wrote rather than ``curve_link0``.
Curvature is a property of the breakpoint *values*, so it is not decided here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from math_spec.degree import check_expression
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError, PiecewiseExpansionError
from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import ComparisonNode
from math_spec.model import Buildable, Model, PiecewiseBlock
from math_spec.resolution import Namespace, resolve_expression

if TYPE_CHECKING:
    from collections.abc import Sequence


def mask_of(block: str, pw: PiecewiseBlock) -> str | None:
    """The parameter a block masks its weights with, or ``None`` for a whole curve.

    ``points:`` may name the mask itself, or one of the block's own values
    parameters — "the curve runs as far as this does" — in which case the
    mask is derived from that parameter when data binds, under the name this
    returns.
    """
    if pw.points is None:
        return None
    return f'{block}_points' if pw.points in {link.values for link in pw.links} else pw.points


def _gate_rows(schema: Model, pw: PiecewiseBlock) -> tuple[tuple[str, str | None, str], ...]:
    """What the weights sum to, as ``(name suffix, where, right-hand side)``.

    One row where the gate exists at every coordinate the block builds a curve
    for, and **two** where it does not. A gate is a variable, so a masked one
    has coordinates where it does not exist — and there the block is ungated,
    which is the ``1`` a block with no ``activity:`` gets. Written as a single
    row it would instead be *no row*: absence does not spread out of a
    reduction, so the right-hand side would take the row with it and leave the
    weights without the convexity that makes them a curve at all (#1158).

    ``absence: zero`` is the other reading and stays one row — the gate is 0
    where it does not exist, so the curve is pinned off there.
    """
    if pw.activity is None:
        return (('', None, '1'),)
    gate = schema.variables[pw.activity]
    if gate.where is None or gate.absence == 'zero':
        return (('', None, f'({pw.activity})'),)
    return (('', pw.activity, f'({pw.activity})'), ('_ungated', f'NOT {pw.activity}', '1'))


def expand_piecewise(schema: Model) -> Buildable:
    """Return *schema* as a :class:`Buildable` — every ``piecewise:`` block expanded away.

    The adjacency constraint shifts with ``edge=0`` rather than a bare
    ``shift``: at the first breakpoint the vacated term must contribute zero,
    giving ``lam <= seg``. Left absent it would propagate and drop that row,
    leaving the first lambda unconstrained by segment selection — a wrong MILP
    with no error, which is why #289 kept the escape hatch.

    ``points:`` masks the *declarations* — the weights and the segment binaries
    — and no constraint. Every emitted row either reduces over the breakpoint
    axis, where absence does not spread, or carries a masked weight, which
    takes the row with it: a second ``where:`` on the adjacency row builds the
    same model down to the column.

    Building the expanded model validates it, so the result is memoised on
    *schema* — a validated schema already carries the expansion its own
    validation built (:class:`Model` expands as a check on the way in), and
    asking again returns it rather than validating a second copy. Idempotent:
    a :class:`Buildable` is its own expansion and comes straight back, so a
    consumer unsure whether it has expanded yet can simply ask.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """
    if isinstance(schema, Buildable):
        return schema
    if schema._expansion is not None:
        return schema._expansion
    if not schema.piecewise:
        schema._expansion = _retyped(schema)
        return schema._expansion

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, pw in schema.piecewise.items():
        frame = _validate_block(schema, name, pw)
        mask, nominated = mask_of(name, pw), pw.points
        if mask is not None and nominated is not None and mask != nominated:
            raw.setdefault('parameters', {})[mask] = {
                'dims': list(schema.parameters[nominated].dims),
                'dtype': 'bool',
                'description': f"where '{nominated}' has a row, and so where the curve runs",
            }
        if pw.method == 'lp':
            _expand_lp(raw, name, pw, frame, mask, schema.parameters[pw.points].dims if pw.points else ())
            continue
        lam = f'{name}_lam'

        raw['variables'][lam] = {
            'foreach': [*frame, pw.over],
            **({'where': mask} if mask else {}),
            'bounds': {'lower': 0.0, 'upper': 1.0},
            'description': 'convex-combination weight on a breakpoint',
        }
        gated = _gate_rows(schema, pw)
        for suffix, where, rhs in gated:
            raw['constraints'][f'{name}_convexity{suffix}'] = {
                'foreach': list(frame),
                **({'where': where} if where else {}),
                'expression': f'sum({lam}, over={pw.over}) == {rhs}',
            }
        for i, link in enumerate(pw.links):
            raw['constraints'][f'{name}_link{i}'] = {
                'foreach': list(frame),
                'expression': (f'({link.expression}) {link.sign} sum({lam} * {link.values}, over={pw.over})'),
            }
        if pw.method == 'sos2':
            raw.setdefault('sos', {})[name] = {'variable': lam, 'over': pw.over, 'type': 2}
        elif pw.method == 'adjacency':
            seg = f'{name}_seg'
            raw['variables'][seg] = {
                'foreach': [*frame, pw.over],
                **({'where': mask} if mask else {}),
                'domain': 'binary',
                'bounds': {},
            }
            for suffix, where, rhs in gated:
                raw['constraints'][f'{name}_pick{suffix}'] = {
                    'foreach': list(frame),
                    **({'where': where} if where else {}),
                    'expression': f'sum({seg}, over={pw.over}) == {rhs}',
                }
            raw['constraints'][f'{name}_adjacency'] = {
                'foreach': [*frame, pw.over],
                'expression': f'{lam} <= {seg} + shift({seg}, over={pw.over}, offset=1, edge=0)',
            }

    raw['piecewise'].clear()
    expanded = Buildable.model_validate(raw)
    schema._expansion = expanded
    return expanded


def _retyped(schema: Model) -> Buildable:
    """*schema* as the type of a model with nothing to expand, unvalidated.

    Reached only where ``piecewise:`` is already empty, which is the whole of
    what :class:`Buildable` promises — the fields are the ones a validating
    construction would arrive at, so a second pass over them would buy the
    caller nothing and cost every curve-free model a copy of its own checks.
    """
    return Buildable.model_construct(**dict(schema))


def _expand_lp(
    raw: dict[str, Any],
    name: str,
    pw: PiecewiseBlock,
    frame: tuple[str, ...],
    mask: str | None,
    schema_dims: Sequence[str],
) -> None:
    """Emit the segment-line form: a row per segment, and the two domain rows.

    Three things a change here could break unknowingly:

    The chord is written at the *later* of the two breakpoints it joins, so the
    first has no predecessor and its row must not exist. The ``where:`` and
    ``edge=0`` travel together — without the exclusion the vacated position
    reads as a zero, which is a spurious line through the origin. Under a mask
    the first is the *curve's*, not the axis', which is what the derived
    ``_starts`` flag names: a curve may sit anywhere along the breakpoints as
    long as it sits on consecutive ones.

    The row is multiplied through by the run rather than written as
    ``rise / run``: the sense survives only because the run is positive, which
    is the strict monotonicity the method already requires of its breakpoints,
    and a difference is outside the plan's divisor rule anyway.

    A segment line does not stop where its segment does, so the two domain rows
    are what keeps the formulation inside the curve's own range. They are
    ``linopy``'s ``_add_lp`` rows under its own names.

    Under ``points:`` the upper one moves off the breakpoint axis: the last
    breakpoint is then each curve's own, and ``where:`` takes no operators to
    find it with. ``points - shift(points, offset=-1)`` is 1 exactly where a
    curve ends, so the bound is read as a sum over the axis instead of a row
    sitting on one coordinate of it — which is why the mask has to be a prefix.
    """
    x_link, y_link = pw.curve
    d = pw.over
    run = f'({x_link.values} - shift({x_link.values}, over={d}, offset=1, edge=0))'
    rise = f'({y_link.values} - shift({y_link.values}, over={d}, offset=1, edge=0))'
    interior = f'{mask} AND NOT {name}_starts' if mask else f'position({d}) != 0'
    raw['constraints'][f'{name}_chord'] = {
        'foreach': [*frame, d],
        'where': interior,
        'expression': (
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}'
        ),
    }
    edges = (('domain_lo', '>=', f'{name}_starts'), ('domain_hi', '<=', f'{name}_ends'))
    axis = (('domain_lo', '>=', f'position({d}) == 0'), ('domain_hi', '<=', f'position({d}) == -1'))
    for suffix, sense, at in edges if mask else axis:
        if mask:
            raw.setdefault('parameters', {})[at] = {
                'dims': list(schema_dims),
                'dtype': 'bool',
                'description': f'the {"first" if sense == ">=" else "last"} breakpoint of each curve',
            }
        raw['constraints'][f'{name}_{suffix}'] = {
            'foreach': [*frame, d],
            'where': at,
            'expression': f'({x_link.expression}) {sense} {x_link.values}',
        }


def _validate_block(schema: Model, name: str, pw: PiecewiseBlock) -> tuple[str, ...]:
    """Check references and infer the frame (union of the links' dims).

    Every name the expansion will emit is checked against what the file
    already declares — one list per kind rather than one loop per name family,
    so a new emitted declaration is a name here, not a fourth loop to
    remember.

    A values parameter is checked against the frame in a **second pass**, since
    any link's expression may be the one that carries the dim, and the last of
    them widens the frame as readily as the first. Left to the emitted
    declarations the same file is still refused, but by a dimension error
    naming ``<block>_chord`` or ``<block>_link0`` — a constraint the author
    never wrote, and a different one per method.
    """
    ctx = f"piecewise '{name}'"
    if pw.over not in schema.dimensions:
        raise PiecewiseExpansionError(f"{ctx}: over references undeclared dimension '{pw.over}'")

    frame: list[str] = []
    for i, link in enumerate(pw.links):
        values = link.values
        if values not in schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: link {i} values references undeclared parameter '{values}'")
        if pw.over not in schema.parameters[values].dims:
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} values parameter '{values}' must carry dim "
                f"'{pw.over}' (has {schema.parameters[values].dims})"
            )
        for d in _declared_order(schema, _expr_dims(schema, link.expression, f'{ctx} link {i}')):
            if d == pw.over:
                raise PiecewiseExpansionError(
                    f"{ctx}: link {i} expression already carries the breakpoint dim '{pw.over}'"
                )
            if d not in frame:
                frame.append(d)

    if pw.activity is not None:
        if pw.activity not in schema.variables:
            raise PiecewiseExpansionError(
                f"{ctx}: activity '{pw.activity}' is not a declared variable. A gate is a variable or it is "
                f'nothing — with no `activity:` at all the weights sum to 1, so what a gate adds is a column '
                f'the solver decides, and only a declaration says what its absence means.'
            )
        if schema.variables[pw.activity].domain != 'binary':
            raise PiecewiseExpansionError(f"{ctx}: activity variable '{pw.activity}' must be binary")
        for d in _declared_order(schema, _expr_dims(schema, pw.activity, f'{ctx} activity')):
            if d == pw.over:
                raise PiecewiseExpansionError(f"{ctx}: activity must not carry the breakpoint dim '{pw.over}'")
            if d not in frame:
                frame.append(d)

    for i, link in enumerate(pw.links):
        if stray := [d for d in schema.parameters[link.values].dims if d != pw.over and d not in frame]:
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} values parameter '{link.values}' carries {stray}, which no link "
                f'expression does — the block builds one curve per coordinate of {frame}, so a curve '
                f'varying along {stray} has nothing to vary against. Declare a link expression over '
                f"it, or drop it from '{link.values}'."
            )

    if pw.points is not None and mask_of(name, pw) != pw.points:
        if f'{name}_points' in schema.parameters:
            raise PiecewiseExpansionError(
                f"{ctx}: emitted parameter '{name}_points' collides with a declared parameter"
            )
    elif pw.points is not None:
        if pw.points not in schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: points references undeclared parameter '{pw.points}'")
        if (dtype := schema.parameters[pw.points].dtype) != 'bool':
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' is {dtype}, and a mask is a bool parameter — one "
                f'saying, per breakpoint, whether the curve reaches it. Declare it dtype: bool.'
            )
        mask = schema.parameters[pw.points].dims
        if pw.over not in mask:
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' must carry dim '{pw.over}' — "
                f'it says how far each curve runs along it (has {mask})'
            )
        if stray := [d for d in mask if d != pw.over and d not in frame]:
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' carries {stray}, which the links do not — "
                f"a mask says which of the block's own coordinates exist, and cannot add coordinates"
            )

    emitted_constraints = (
        f'{name}_convexity',
        f'{name}_convexity_ungated',
        f'{name}_pick',
        f'{name}_pick_ungated',
        f'{name}_adjacency',
        f'{name}_chord',
        f'{name}_domain_lo',
        f'{name}_domain_hi',
        *(f'{name}_link{i}' for i in range(len(pw.links))),
    )
    for kind, emitted, declared in (
        ('variable', (f'{name}_lam', f'{name}_seg'), schema.variables),
        ('parameter', (f'{name}_starts', f'{name}_ends'), schema.parameters),
        ('constraint', emitted_constraints, schema.constraints),
        ('sos', (name,), schema.sos),
    ):
        for one in emitted:
            if one in declared:
                raise PiecewiseExpansionError(f"{ctx}: emitted {kind} '{one}' collides with a declared {kind}")
    return tuple(frame)


def _declared_order(schema: Model, dims: frozenset[str]) -> list[str]:
    """*dims* in the order the file declares them.

    An emitted ``foreach`` is a *language* object and inherits the label
    contract in ARCHITECTURE — row-major over the coordinate product, the same
    run to run. Iterating the dim *set* instead spends string hashing, which is
    randomised per process, so the emitted order and every solver column index
    behind it varied between builds of the same model. Declaration order is
    what a hand-written ``foreach`` gets, so it is what an emitted one gets.
    """
    return [d for d in schema.dimensions if d in dims]


def _expr_dims(schema: Model, text: str, ctx: str) -> frozenset[str]:
    """Dims of an affine link expression.

    The frame a block is emitted over is the union of its links' dims, so the
    dim set has to be known *here*, before any declaration exists to carry it.
    ``dimensions`` is the one implementation of that question, and asking it
    is the whole of what this needs: whether the engine has a plan node for
    the expression is a different question, asked later by whichever lane
    builds a plan.
    """
    ast = parse_and_expand(text, schema, ctx)
    if isinstance(ast, ComparisonNode):
        raise PiecewiseExpansionError(f'{ctx}: link expressions must not contain a comparison, got {text!r}')
    errors: list[str] = []
    resolved = resolve_expression(ast, Namespace.of(schema), ctx, errors)
    if resolved is None:
        raise PiecewiseExpansionError('\n'.join(errors))
    assert not isinstance(resolved, ComparisonNode)
    try:
        check_expression(resolved, ctx)
        return dims_of(resolved, schema, ctx)
    except LanguageError as exc:
        raise PiecewiseExpansionError(
            f'{ctx}: link expression {text!r} is not a valid affine expression: {exc}'
        ) from exc
