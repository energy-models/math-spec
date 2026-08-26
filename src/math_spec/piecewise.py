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

Only the restriction on λ varies (:data:`~math_spec.model.PIECEWISE_METHODS`);
``lp`` emits no weights at all. A link expression is judged before expansion,
so ``p * p`` is refused against the link the user wrote rather than
``curve_link0``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from math_spec.degree import check_expression
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError, PiecewiseExpansionError
from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import ComparisonNode
from math_spec.model import Buildable, Model, PiecewiseBlock, undeclared_dimension
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


def curvature_required(pw: PiecewiseBlock) -> str | None:
    """The curvature *pw*'s method is only exact for, or ``None`` if any shape works.

    ``convex`` relaxes the weights onto the hull, which cuts the corners of a
    *mixed* curve and nothing else, so it answers ``'either'``. ``lp`` states
    one side of the curve as its segment lines and the bounded link's sign says
    which side, so the opposite bend is silently wrong rather than merely loose.

    The breakpoints decide whether a model meets the condition, and they arrive
    with the data rather than with the schema — so this names what to check,
    and the caller holding the numbers does the checking.

    Args:
        pw: The block whose method is in question.

    Returns:
        ``'convex'``, ``'concave'``, ``'either'`` for a method that constrains
        the shape, or ``None`` for one that does not.
    """
    if pw.method == 'convex':
        return 'either'
    if pw.method != 'lp':
        return None
    return 'convex' if pw.curve[1].sign == '>=' else 'concave'


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

    The adjacency row shifts with ``edge=0``: a bare ``shift`` would drop the
    first breakpoint's row and leave its weight unconstrained, a wrong MILP
    with no error (#289). ``points:`` masks the weights and the segment
    binaries and no constraint — every emitted row reduces over the breakpoint
    axis or carries a masked weight. The result is memoised on *schema*, and a
    :class:`Buildable` comes straight back; a model with no ``piecewise:`` is
    retyped with ``model_construct``, its validation already done on the way in.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """
    if isinstance(schema, Buildable):
        return schema
    if schema._expansion is not None:
        return schema._expansion
    if not schema.piecewise:
        schema._expansion = Buildable.model_construct(**dict(schema))
        return schema._expansion

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, pw in schema.piecewise.items():
        frame = _validate_block(schema, name, pw)
        mask, nominated = mask_of(name, pw), pw.points
        if nominated is not None and mask != nominated:
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


def _expand_lp(
    raw: dict[str, Any],
    name: str,
    pw: PiecewiseBlock,
    frame: tuple[str, ...],
    mask: str | None,
    schema_dims: Sequence[str],
) -> None:
    """Emit the segment-line form: a row per segment, and the two domain rows.

    The chord sits at the later breakpoint, so the first has none and its
    ``where:`` and ``edge=0`` travel together — without the exclusion the
    vacated position is a spurious line through the origin; under a mask the
    first breakpoint is the curve's own, which is what ``_starts`` names. The
    row is multiplied through by the run rather than dividing, which keeps its
    sense only because the breakpoints are strictly monotone. The domain rows
    are ``linopy``'s ``_add_lp`` rows under its names; under ``points:`` they
    sit on the derived ``_starts``/``_ends`` flags, which is why the mask has to
    be a prefix.
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

    A values parameter is checked against the frame in a second pass, since
    the last link's expression widens the frame as readily as the first; left
    to the emitted declarations the refusal would name ``<block>_link0``, a
    constraint the author never wrote.
    """
    ctx = f"piecewise '{name}'"
    if pw.over not in schema.dimensions:
        raise PiecewiseExpansionError(undeclared_dimension('piecewise', name, pw.over))

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
                f"{ctx}: activity '{pw.activity}' is not a declared variable. A gate is a binary variable; "
                f'declare it, or drop activity: for weights that sum to 1.'
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

    if pw.points is not None and mask_of(name, pw) == pw.points:
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
    derived = (f'{name}_points',) if mask_of(name, pw) != pw.points else ()
    for kind, emitted, declared in (
        ('variable', (f'{name}_lam', f'{name}_seg'), schema.variables),
        ('parameter', (f'{name}_starts', f'{name}_ends', *derived), schema.parameters),
        ('constraint', emitted_constraints, schema.constraints),
        ('sos', (name,), schema.sos),
    ):
        for one in emitted:
            if one in declared:
                raise PiecewiseExpansionError(f"{ctx}: emitted {kind} '{one}' collides with a declared {kind}")
    return tuple(frame)


def _declared_order(schema: Model, dims: frozenset[str]) -> list[str]:
    """*dims* in declaration order — iterating the set varies the emitted ``foreach``, and every column index behind it, per process."""
    return [d for d in schema.dimensions if d in dims]


def _expr_dims(schema: Model, text: str, ctx: str) -> frozenset[str]:
    """Dims of an affine link expression, asked of ``dimensions`` before any declaration exists to carry it."""
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
