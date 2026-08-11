"""Expand ``piecewise:`` blocks into plain variables and constraints.

This is schema-level expansion (SPEC §12.4): a ``piecewise:`` block becomes
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
      curve_seg(F, bp)  binary                            (omitted when convex)
    constraints:
      curve_convexity(F):     sum(curve_lam, over=bp) == 1
      curve_pick(F):          sum(curve_seg, over=bp) == 1        (when not convex)
      curve_adjacency(F, bp): curve_lam <= curve_seg + shift(curve_seg, over=bp, by=1, edge=0)
      curve_link0(F):         (power) == sum(curve_lam * power_bp, over=bp)
      curve_link1(F):         (fuel * eff) <= sum(curve_lam * fuel_bp, over=bp)

With adjacency, at most two *neighbouring* λ are nonzero, so the linked
expressions lie on the piecewise curve exactly. Without it (``convex:
true``), they range over the convex hull of the breakpoints — the correct
relaxation for convex/concave curves under optimisation pressure.

A link expression is judged against the *language* before expansion —
resolved, degree-checked (:mod:`~lpspec.language.degree`), dims from
:mod:`~lpspec.language.dimensions`. Judging it here keeps ``p * p`` named
against the link the user wrote rather than against ``curve_link0``, a
declaration they never saw.

Two verdicts are deliberately elsewhere. What a plan node can represent is the
consuming lane's business — this module runs in lanes that build no plan
(docs/ARCHITECTURE.md, "What counts as language"). Curvature is a property of
the breakpoint *values*, so it needs data and lives in :mod:`lpspec.sources`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lpspec.errors import LanguageError, PiecewiseExpansionError
from lpspec.language.degree import check_expression
from lpspec.language.dimensions import dims_of
from lpspec.language.expression_parser import ComparisonNode, parse_expression
from lpspec.language.model import Model, PiecewiseBlock
from lpspec.language.resolution import Namespace, resolve_expression

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def expand_piecewise(
    schema: Model,
    *,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> Model:
    """Return *schema* with every ``piecewise:`` block expanded away.

    The adjacency constraint shifts with ``edge=0`` rather than a bare
    ``shift``: at the first breakpoint the vacated term must contribute zero,
    giving ``lam <= seg``. Left absent it would propagate and drop that row,
    leaving the first lambda unconstrained by segment selection — a wrong MILP
    with no error, which is why #289 kept the escape hatch.

    ``known_variables`` widens the variable set the same way it does for any
    other expression: a link may name a variable the model being extended
    already has, and the frame is the union of the links' dims, so resolution
    has to see those names to compute it.

    Building the expanded ``Model`` validates it, so the result is memoised
    on *schema* keyed by the namespace it was expanded against — a validated
    schema already carries the expansion its own validation built
    (:class:`Model` expands as a check on the way in), and asking again
    returns it rather than validating a second copy.
    """
    if not schema.piecewise:
        return schema
    key = expansion_key(known_variables)
    if schema._expansion is not None and schema._expansion[0] == key:
        return schema._expansion[1]

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, pw in schema.piecewise.items():
        frame = _validate_block(schema, name, pw, known_variables)
        lam, seg = f'{name}_lam', f'{name}_seg'

        raw['variables'][lam] = {
            'foreach': [*frame, pw.over],
            'bounds': {'lower': 0.0, 'upper': 1.0},
        }
        rhs = f'({pw.active})' if pw.active else '1'
        raw['constraints'][f'{name}_convexity'] = {
            'foreach': list(frame),
            'expression': f'sum({lam}, over={pw.over}) == {rhs}',
        }
        for i, link in enumerate(pw.links):
            expr, values = link[0], link[1]
            sign = link[2] if len(link) == 3 else '=='
            raw['constraints'][f'{name}_link{i}'] = {
                'foreach': list(frame),
                'expression': (f'({expr}) {sign} sum({lam} * {values}, over={pw.over})'),
            }
        if not pw.convex:
            raw['variables'][seg] = {
                'foreach': [*frame, pw.over],
                'binary': True,
                'bounds': {},
            }
            raw['constraints'][f'{name}_pick'] = {
                'foreach': list(frame),
                'expression': f'sum({seg}, over={pw.over}) == {rhs}',
            }
            raw['constraints'][f'{name}_adjacency'] = {
                'foreach': [*frame, pw.over],
                'expression': f'{lam} <= {seg} + shift({seg}, over={pw.over}, by=1, edge=0)',
            }

    raw['piecewise'].clear()
    expanded = Model.model_validate(raw, context={'known_variables': known_variables})
    schema._expansion = (key, expanded)
    return expanded


def expansion_key(known_variables: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    """*known_variables* normalised for equality, however its sequences are typed."""
    return {name: tuple(dims) for name, dims in known_variables.items()}


def _validate_block(
    schema: Model,
    name: str,
    pw: PiecewiseBlock,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> tuple[str, ...]:
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
        expr_text, values = link[0], link[1]
        if values not in schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: link {i} values references undeclared parameter '{values}'")
        if pw.over not in schema.parameters[values].dims:
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} values parameter '{values}' must carry dim "
                f"'{pw.over}' (has {schema.parameters[values].dims})"
            )
        for d in _declared_order(schema, _expr_dims(schema, expr_text, f'{ctx} link {i}', known_variables)):
            if d == pw.over:
                raise PiecewiseExpansionError(
                    f"{ctx}: link {i} expression already carries the breakpoint dim '{pw.over}'"
                )
            if d not in frame:
                frame.append(d)

    if pw.active is not None:
        if pw.active in schema.variables and not schema.variables[pw.active].binary:
            raise PiecewiseExpansionError(f"{ctx}: active variable '{pw.active}' must be binary")
        for d in _declared_order(schema, _expr_dims(schema, pw.active, f'{ctx} active', known_variables)):
            if d == pw.over:
                raise PiecewiseExpansionError(f"{ctx}: active expression must not carry the breakpoint dim '{pw.over}'")
            if d not in frame:
                frame.append(d)

    emitted_constraints = (
        f'{name}_convexity',
        f'{name}_pick',
        f'{name}_adjacency',
        *(f'{name}_link{i}' for i in range(len(pw.links))),
    )
    for kind, emitted, declared in (
        ('variable', (f'{name}_lam', f'{name}_seg'), schema.variables),
        ('constraint', emitted_constraints, schema.constraints),
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


def _expr_dims(
    schema: Model,
    text: str,
    ctx: str,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> frozenset[str]:
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
    resolved = resolve_expression(ast, Namespace.of(schema, known_variables), ctx, errors)
    if resolved is None:
        raise PiecewiseExpansionError('\n'.join(errors))
    assert not isinstance(resolved, ComparisonNode)
    try:
        check_expression(resolved, ctx)
        return dims_of(resolved, schema, ctx, known_variables)
    except LanguageError as exc:
        raise PiecewiseExpansionError(
            f'{ctx}: link expression {text!r} is not a valid affine expression: {exc}'
        ) from exc
