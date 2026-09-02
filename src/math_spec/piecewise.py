# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``piecewise:`` blocks into plain variables and constraints.

A block becomes ordinary affine declarations before anything reads the model,
under names prefixed with the block's own; what each method emits is tabled in
``docs/reference/language/piecewise.md``. A link expression is judged before
expansion, so a refusal names the link the file wrote rather than an emitted
constraint.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from math_spec.degree import check_expression
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError, PiecewiseExpansionError
from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import ComparisonNode
from math_spec.model import Curvature, ExpandedPiecewise, PiecewiseBlock, Spec, _ExpandedSpec, undeclared_dimension
from math_spec.program import (
    AtLeastTwo,
    Check,
    Contiguous,
    Curved,
    Derivation,
    FirstOf,
    Increasing,
    LastOf,
    MaskOf,
    PiecewiseDeclaration,
)
from math_spec.resolution import Namespace, resolve_expression


def _nominated(pw: PiecewiseBlock) -> str | None:
    """The block's own values parameter ``points:`` names, so the mask is derived from it — or ``None``."""
    return pw.points if pw.points in {link.values for link in pw.links} else None


#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


class _Emitted(NamedTuple):
    """Every name one block's expansion may write — the emitters and the collision check read one spelling.

    ``points`` is the derived mask, written only where ``nominated`` names the
    values parameter it is derived from.
    """

    lam: str
    seg: str
    starts: str
    ends: str
    points: str
    nominated: str | None
    convexity: str
    pick: str
    adjacency: str
    chord: str
    domain_lo: str
    domain_hi: str
    links: tuple[str, ...]
    sos: str

    @classmethod
    def of(cls, block: str, pw: PiecewiseBlock) -> _Emitted:
        return cls(
            lam=f'{block}_lam',
            seg=f'{block}_seg',
            starts=f'{block}_starts',
            ends=f'{block}_ends',
            points=f'{block}_points',
            nominated=_nominated(pw),
            convexity=f'{block}_convexity',
            pick=f'{block}_pick',
            adjacency=f'{block}_adjacency',
            chord=f'{block}_chord',
            domain_lo=f'{block}_domain_lo',
            domain_hi=f'{block}_domain_hi',
            links=tuple(f'{block}_link{i}' for i in range(len(pw.links))),
            sos=block,
        )

    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The names by the kind of declaration each would collide with."""
        return (
            ('variable', (self.lam, self.seg)),
            ('parameter', (self.starts, self.ends, *((self.points,) if self.nominated is not None else ()))),
            (
                'constraint',
                (
                    self.convexity,
                    self.convexity + _UNGATED,
                    self.pick,
                    self.pick + _UNGATED,
                    self.adjacency,
                    self.chord,
                    self.domain_lo,
                    self.domain_hi,
                    *self.links,
                ),
            ),
            ('sos', (self.sos,)),
        )


def _curvature_required(pw: PiecewiseBlock) -> Curvature | None:
    """The curvature *pw*'s method is only exact for, or ``None`` if any shape works.

    ``convex`` relaxes the weights onto the hull, which cuts the corners of a
    *mixed* curve and nothing else, so it answers ``'either'``. ``lp`` states
    one side of the curve as its segment lines and the bounded link's sign says
    which side, so the opposite bend is silently wrong rather than merely loose.
    """
    if pw.method == 'convex':
        return 'either'
    if pw.method != 'lp':
        return None
    return 'convex' if pw.curve[1].sign == '>=' else 'concave'


def declaration_of(expanded: ExpandedPiecewise) -> PiecewiseDeclaration:
    """The facts of one expanded block, as a program carries them.

    A curve has an x-axis only where two links tie it, so the increasing
    condition — and the shape it is checked with — exist only there; ``lp``
    alone needs a segment to state a line for; a mask must be one run.
    """
    pw = expanded.block
    checks: list[Check] = []
    curvature = _curvature_required(pw)
    if curvature is not None:
        x, y = pw.curve
        checks.append(Increasing(x.values, pw.over))
        checks.append(Curved(x.values, y.values, pw.over, curvature))
    if pw.method == 'lp':
        checks.append(AtLeastTwo(pw.over, expanded.points))
    if expanded.points is not None:
        checks.append(Contiguous(expanded.points, _nominated(pw)))
    return PiecewiseDeclaration(
        over=pw.over,
        method=pw.method,
        breakpoints=tuple(link.values for link in pw.links),
        checks=tuple(checks),
    )


def derivations_of(block: str, expanded: ExpandedPiecewise) -> dict[str, Derivation]:
    """How each parameter *block*'s expansion emitted is filled, by name.

    Everything emitted hangs off the mask, so a block masking nothing emits
    nothing for the caller to be told about.
    """
    if (mask := expanded.points) is None:
        return {}
    derivations: dict[str, Derivation] = {}
    if (values := _nominated(expanded.block)) is not None:
        derivations[mask] = MaskOf(block, values)
    if expanded.starts is not None:
        derivations[expanded.starts] = FirstOf(block, mask)
    if expanded.ends is not None:
        derivations[expanded.ends] = LastOf(block, mask)
    return derivations


def _gate_rows(schema: Spec, pw: PiecewiseBlock) -> tuple[tuple[str, str | None, str], ...]:
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
    return (('', pw.activity, f'({pw.activity})'), (_UNGATED, f'NOT {pw.activity}', '1'))


def expand_piecewise(schema: Spec) -> _ExpandedSpec:
    """Return *schema* as a :class:`_ExpandedSpec` — every ``piecewise:`` block expanded away.

    Memoised on *schema*.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """
    if isinstance(schema, _ExpandedSpec):
        return schema
    if schema._expansion is not None:
        return schema._expansion
    if not schema.piecewise:
        schema._expansion = _ExpandedSpec.model_construct(**dict(schema))
        return schema._expansion

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    records: dict[str, dict[str, Any]] = {}
    raw['expanded_piecewise'] = records
    for name, pw in schema.piecewise.items():
        emitted = _Emitted.of(name, pw)
        frame = _validate_block(schema, name, pw, emitted)
        mask = emitted.points if emitted.nominated is not None else pw.points
        record = records[name] = {'block': raw['piecewise'][name], 'points': mask}
        if emitted.nominated is not None:
            _emit_parameter(
                raw,
                emitted.points,
                list(schema.parameters[emitted.nominated].dims),
                f"where '{emitted.nominated}' has a row, and so where the curve runs",
            )
        if pw.method == 'lp':
            _expand_lp(raw, record, emitted, pw, frame, mask)
            continue

        raw['variables'][emitted.lam] = {
            'foreach': [*frame, pw.over],
            **({'where': mask} if mask else {}),
            'bounds': {'lower': 0.0, 'upper': 1.0},
            'description': 'convex-combination weight on a breakpoint',
        }
        gated = _gate_rows(schema, pw)
        for suffix, where, rhs in gated:
            raw['constraints'][emitted.convexity + suffix] = {
                'foreach': list(frame),
                **({'where': where} if where else {}),
                'expression': f'sum({emitted.lam}, over={pw.over}) == {rhs}',
            }
        for cname, link in zip(emitted.links, pw.links, strict=True):
            raw['constraints'][cname] = {
                'foreach': list(frame),
                'expression': (f'({link.expression}) {link.sign} sum({emitted.lam} * {link.values}, over={pw.over})'),
            }
        if pw.method == 'sos2':
            raw.setdefault('sos', {})[emitted.sos] = {'variable': emitted.lam, 'over': pw.over, 'type': 2}
        elif pw.method == 'adjacency':
            raw['variables'][emitted.seg] = {
                'foreach': [*frame, pw.over],
                **({'where': mask} if mask else {}),
                'domain': 'binary',
                'bounds': {},
            }
            for suffix, where, rhs in gated:
                raw['constraints'][emitted.pick + suffix] = {
                    'foreach': list(frame),
                    **({'where': where} if where else {}),
                    'expression': f'sum({emitted.seg}, over={pw.over}) == {rhs}',
                }
            raw['constraints'][emitted.adjacency] = {
                'foreach': [*frame, pw.over],
                'expression': (
                    f'{emitted.lam} <= {emitted.seg} + shift({emitted.seg}, over={pw.over}, offset=1, edge=0)'
                ),
            }

    raw['piecewise'].clear()
    expanded = _ExpandedSpec.model_validate(raw)
    schema._expansion = expanded
    return expanded


def _expand_lp(
    raw: dict[str, Any],
    record: dict[str, Any],
    emitted: _Emitted,
    pw: PiecewiseBlock,
    frame: tuple[str, ...],
    mask: str | None,
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
    interior = f'{mask} AND NOT {emitted.starts}' if mask else f'position({d}) != 0'
    raw['constraints'][emitted.chord] = {
        'foreach': [*frame, d],
        'where': interior,
        'expression': (
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}'
        ),
    }
    edges = ((emitted.domain_lo, '>=', emitted.starts), (emitted.domain_hi, '<=', emitted.ends))
    axis = ((emitted.domain_lo, '>=', f'position({d}) == 0'), (emitted.domain_hi, '<=', f'position({d}) == -1'))
    for cname, sense, at in edges if mask else axis:
        if mask:
            record['starts' if sense == '>=' else 'ends'] = at
            _emit_parameter(
                raw,
                at,
                raw['parameters'][mask]['dims'],
                f'the {"first" if sense == ">=" else "last"} breakpoint of each curve',
            )
        raw['constraints'][cname] = {
            'foreach': [*frame, d],
            'where': at,
            'expression': f'({x_link.expression}) {sense} {x_link.values}',
        }


def _validate_block(schema: Spec, name: str, pw: PiecewiseBlock, emitted: _Emitted) -> tuple[str, ...]:
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

    if pw.points is not None and emitted.nominated is None:
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

    declared = {
        'variable': schema.variables,
        'parameter': schema.parameters,
        'constraint': schema.constraints,
        'sos': schema.sos,
    }
    for kind, names in emitted.by_kind():
        for one in names:
            if one in declared[kind]:
                raise PiecewiseExpansionError(f"{ctx}: emitted {kind} '{one}' collides with a declared {kind}")
    return tuple(frame)


def _emit_parameter(raw: dict[str, Any], name: str, dims: list[str], description: str) -> None:
    """Write a ``bool`` parameter the expansion derives."""
    raw.setdefault('parameters', {})[name] = {'dims': dims, 'dtype': 'bool', 'description': description}


def _declared_order(schema: Spec, dims: frozenset[str]) -> list[str]:
    """*dims* in declaration order — iterating the set varies the emitted ``foreach``, and every column index behind it, per process."""
    return [d for d in schema.dimensions if d in dims]


def _expr_dims(schema: Spec, text: str, ctx: str) -> frozenset[str]:
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
