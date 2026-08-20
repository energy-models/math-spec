"""Expand ``piecewise:`` blocks into plain variables and constraints.

This is schema-level expansion (the piecewise rules): a ``piecewise:`` block becomes
ordinary affine declarations *before* anything is built, so both backends —
eager and relational — receive identical schemas and stay differential-
testable. Formulations never enter the plan as expression nodes.

The λ convex-combination method is used because it is expansion-pure: it
needs only the breakpoint coordinate parameters themselves, no derived data
(no slopes, intercepts, or segment lengths). For a block

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

**Only the restriction on λ varies**, which is why it is one ``method:`` key
and not three formulations (:data:`~lpspec.language.model.PIECEWISE_METHODS`).
Every method emits the weights, the convexity row and the links. Then
``adjacency`` adds the binaries above, so at most two *neighbouring* λ are
nonzero and the linked expressions lie on the curve exactly; ``sos2`` states
that same restriction as a ``sos:`` block over the same weights, leaving a
sink that branches on a set to do so; and ``convex`` adds nothing, leaving λ
over the hull of the breakpoints — the correct relaxation for a convex or
concave curve under optimisation pressure.

``sos2`` is the one method emitting a declaration this module does not expand
away, and that is what lets the choice reach a solver at all: an expansion is
unconditional where a capability is per sink, so the *formulation* stays the
file's and the *encoding* stays the sink's (``relational/sinks/sos.py``).

A link expression is judged against the *language* before expansion — resolved,
degree-checked, dims from :mod:`~lpspec.language.dimensions` — which keeps
``p * p`` named against the link the user wrote rather than ``curve_link0``, a
declaration they never saw.

Two verdicts are deliberately elsewhere: what a plan node can represent is the
consuming lane's business, and curvature is a property of the breakpoint
*values*, so it needs data and lives in :mod:`lpspec.sources`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpspec.errors import LanguageError, PiecewiseExpansionError
from lpspec.language.degree import check_expression
from lpspec.language.dimensions import dims_of
from lpspec.language.expression_parser import ComparisonNode, parse_expression
from lpspec.language.model import Model, PiecewiseBlock
from lpspec.language.resolution import Namespace, resolve_expression

if TYPE_CHECKING:
    from collections.abc import Sequence


def expand_piecewise(schema: Model) -> Model:
    """Return *schema* with every ``piecewise:`` block expanded away.

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

    Building the expanded ``Model`` validates it, so the result is memoised
    on *schema* — a validated schema already carries the expansion its own
    validation built (:class:`Model` expands as a check on the way in), and
    asking again returns it rather than validating a second copy.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """
    if not schema.piecewise:
        return schema
    if schema._expansion is not None:
        return schema._expansion

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, pw in schema.piecewise.items():
        frame = _validate_block(schema, name, pw)
        if pw.method == 'lp':
            _expand_lp(raw, name, pw, frame, schema.parameters[pw.points].dims if pw.points else ())
            continue
        lam, seg = f'{name}_lam', f'{name}_seg'

        raw['variables'][lam] = {
            'foreach': [*frame, pw.over],
            **({'where': pw.points} if pw.points else {}),
            'bounds': {'lower': 0.0, 'upper': 1.0},
            'description': 'convex-combination weight on a breakpoint',
        }
        rhs = f'({pw.active})' if pw.active else '1'
        raw['constraints'][f'{name}_convexity'] = {
            'foreach': list(frame),
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
            raw['variables'][seg] = {
                'foreach': [*frame, pw.over],
                **({'where': pw.points} if pw.points else {}),
                'domain': 'binary',
                'bounds': {},
            }
            raw['constraints'][f'{name}_pick'] = {
                'foreach': list(frame),
                'expression': f'sum({seg}, over={pw.over}) == {rhs}',
            }
            raw['constraints'][f'{name}_adjacency'] = {
                'foreach': [*frame, pw.over],
                'expression': f'{lam} <= {seg} + shift({seg}, over={pw.over}, offset=1, edge=0)',
            }

    raw['piecewise'].clear()
    expanded = Model.model_validate(raw)
    schema._expansion = expanded
    return expanded


def _expand_lp(
    raw: dict[str, Any], name: str, pw: PiecewiseBlock, frame: tuple[str, ...], schema_dims: Sequence[str]
) -> None:
    """Emit the segment-line form: a row per segment, and the two domain rows.

    Three things a change here could break unknowingly:

    The chord is written at the *later* of the two breakpoints it joins, so the
    first has no predecessor and its row must not exist. The ``where:`` and
    ``edge=0`` travel together — without the exclusion the vacated position
    reads as a zero, which is a spurious line through the origin.

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
    interior = f'{d} != index({d}, 0)'
    raw['constraints'][f'{name}_chord'] = {
        'foreach': [*frame, d],
        'where': f'{pw.points} AND {interior}' if pw.points else interior,
        'expression': (
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}'
        ),
    }
    edges = (('domain_lo', '>=', f'{name}_starts'), ('domain_hi', '<=', f'{name}_ends'))
    axis = (('domain_lo', '>=', f'{d} == index({d}, 0)'), ('domain_hi', '<=', f'{d} == index({d}, -1)'))
    for suffix, sense, at in edges if pw.points else axis:
        if pw.points:
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

    if pw.active is not None:
        if pw.active in schema.variables and schema.variables[pw.active].domain != 'binary':
            raise PiecewiseExpansionError(f"{ctx}: active variable '{pw.active}' must be binary")
        for d in _declared_order(schema, _expr_dims(schema, pw.active, f'{ctx} active')):
            if d == pw.over:
                raise PiecewiseExpansionError(f"{ctx}: active expression must not carry the breakpoint dim '{pw.over}'")
            if d not in frame:
                frame.append(d)

    if pw.points is not None:
        if pw.points not in schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: points references undeclared parameter '{pw.points}'")
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
        f'{name}_pick',
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
    declared = [d for d in schema.dimensions if d in dims]
    return declared + sorted(dims.difference(declared))


def _expr_dims(schema: Model, text: str, ctx: str) -> frozenset[str]:
    """Dims of an affine link expression.

    The frame a block is emitted over is the union of its links' dims, so the
    dim set has to be known *here*, before any declaration exists to carry it.
    ``dimensions`` is the one implementation of that question, and asking it
    is the whole of what this needs: whether the engine has a plan node for
    the expression is a different question, asked later by whichever lane
    builds a plan.
    """
    ast = parse_expression(text)
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
