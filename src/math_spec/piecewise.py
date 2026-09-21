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

from typing import TYPE_CHECKING

from math_spec._expression_parser import ComparisonNode
from math_spec.degree import check_expression
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError, PiecewiseExpansionError
from math_spec.expansion import parse_and_expand
from math_spec.model import Curvature, ExpandedPiecewise, PiecewiseBlock, Spec, undeclared_dimension
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
from math_spec.sos import Emitted, emit

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def _nominated(pw: PiecewiseBlock) -> str | None:
    """The block's own values parameter ``points:`` names, so the mask is derived from it — or ``None``."""
    return pw.points if pw.points in {link.values for link in pw.links} else None


#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


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
    """The curve of one expanded block, as a program carries it."""
    pw = expanded.block
    return PiecewiseDeclaration(
        over=pw.over,
        method=pw.method,
        breakpoints=tuple(link.values for link in pw.links),
    )


def assumptions_of(block: str, pw: PiecewiseBlock) -> dict[str, Check]:
    """What *block* assumes of its numbers, by the name the document prints and a refusal quotes.

    A curve has an x-axis only where two links tie it, so the increasing
    condition — and the shape it is checked with — exist only there; ``lp``
    alone needs a segment to state a line for; a mask must be one run.

    Read off the block rather than off an expansion, so a model states what it
    assumes whether or not its curves have been written out. A mask is the
    parameter the file named, which is the one that exists in both readings:
    the derived column the expansion emits marks the same breakpoints.

    The space in each name is what keeps these apart from the file's own
    ``assumptions:`` entries in one mapping: a declaration is named as an
    expression writes it, so no file can write one of these.
    """
    checks: dict[str, Check] = {}
    curvature = _curvature_required(pw)
    if curvature is not None:
        x, y = pw.curve
        checks[f'{block} increasing'] = Increasing(block, pw.method, x.values, pw.over)
        checks[f'{block} curvature'] = Curved(block, pw.method, x.values, y.values, pw.over, curvature)
    if pw.method == 'lp':
        checks[f'{block} breakpoints'] = AtLeastTwo(block, pw.over, pw.points)
    if pw.points is not None:
        checks[f'{block} points'] = Contiguous(block, pw.points, _nominated(pw))
    return checks


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


class _Block:
    """One ``piecewise:`` block being expanded into the raw model it writes.

    Every name the expansion may write is spelled once here, so the emitters
    and the collision check read the same table — ``set`` is the one a method
    that states a set writes through :func:`math_spec.sos.emit`. ``points`` is
    the derived mask, written only where ``nominated`` names the values
    parameter it is derived from; ``mask`` is whichever parameter masks the
    weights, or ``None`` for a whole curve.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """

    def __init__(self, schema: Spec, raw: dict[str, object], name: str, pw: PiecewiseBlock) -> None:
        self.schema = schema
        self.raw = raw
        self.name = name
        self.pw = pw
        self.nominated = _nominated(pw)
        self.lam = f'{name}_lam'
        self.starts = f'{name}_starts'
        self.ends = f'{name}_ends'
        self.points = f'{name}_points'
        self.convexity = f'{name}_convexity'
        self.set = Emitted.of(name, 2)
        self.chord = f'{name}_chord'
        self.domain_lo = f'{name}_domain_lo'
        self.domain_hi = f'{name}_domain_hi'
        self.links = tuple(f'{name}_link{i}' for i in range(len(pw.links)))
        self.mask = self.points if self.nominated is not None else pw.points
        self.ns = Namespace(schema)
        self.context = f"piecewise '{name}'"
        self.frame = self._validated_frame()
        self.record: dict[str, object] = {'block': self._section('piecewise')[name], 'points': self.mask}

    def expand(self) -> dict[str, object]:
        """Write the block's declarations, and return the record ``expanded_piecewise`` keeps for it."""
        if self.nominated is not None:
            self._parameter(
                self.points,
                list(self.schema.parameters[self.nominated].dims),
                f"where '{self.nominated}' has a row, and so where the curve runs",
            )
        if self.pw.method == 'lp':
            self._segment_lines()
        else:
            self._weights()
        return self.record

    # -- emitters ----------------------------------------------------------

    def _section(self, name: str) -> dict[str, object]:
        """The *name* section of the raw model, created empty where the file declares none."""
        section = self.raw.setdefault(name, {})
        assert isinstance(section, dict), f'{name}: is a mapping in a validated model'
        return section

    def _mask_dims(self, mask: str) -> list[str]:
        """The dims of *mask*, the parameter masking the weights: the nominated values parameter's where it is derived from one."""
        return list(self.schema.parameters[self.nominated if self.nominated is not None else mask].dims)

    def _parameter(self, name: str, dims: list[str], description: str) -> None:
        """A ``bool`` parameter the expansion derives."""
        self._section('parameters')[name] = {'dims': dims, 'dtype': 'bool', 'description': description}

    def _weight(self, name: str, **fields: object) -> None:
        """A variable over the frame and the breakpoint dim, masked as the block is."""
        self._section('variables')[name] = {
            'dims': [*self.frame, self.pw.over],
            **({'where': self.mask} if self.mask else {}),
            **fields,
        }

    def _constraint(self, name: str, dims: list[str], expression: str, where: str | None = None) -> None:
        self._section('constraints')[name] = {
            'dims': dims,
            **({'where': where} if where else {}),
            'expression': expression,
        }

    def _weights(self) -> None:
        """The convex-combination form: weights, their convexity, a row per link, and the method's restriction."""
        d = self.pw.over
        self._weight(
            self.lam,
            bounds={'lower': 0.0, 'upper': 1.0},
            description='convex-combination weight on a breakpoint',
        )
        gated = self._gate_rows()
        for suffix, where, rhs in gated:
            self._constraint(self.convexity + suffix, list(self.frame), f'sum({self.lam}, over={d}) == {rhs}', where)
        for cname, link in zip(self.links, self.pw.links, strict=True):
            self._constraint(
                cname,
                list(self.frame),
                f'({link.expression}) {link.sign} sum({self.lam} * {link.values}, over={d})',
            )
        if self.pw.method in ('sos2', 'adjacency'):
            self._section('sos')[self.name] = {'variable': self.lam, 'over': d, 'type': 2}

    def _gate_rows(self) -> tuple[tuple[str, str | None, str], ...]:
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
        activity = self.pw.activity
        if activity is None:
            return (('', None, '1'),)
        gate = self.schema.variables[activity]
        if gate.where is None or gate.absence == 'zero':
            return (('', None, f'({activity})'),)
        return (('', activity, f'({activity})'), (_UNGATED, f'NOT {activity}', '1'))

    def _segment_lines(self) -> None:
        """The segment-line form: a row per segment, and the two domain rows.

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
        x_link, y_link = self.pw.curve
        d = self.pw.over
        mask = self.mask
        run = f'({x_link.values} - shift({x_link.values}, along={d}, offset=1, edge=0))'
        rise = f'({y_link.values} - shift({y_link.values}, along={d}, offset=1, edge=0))'
        interior = f'{mask} AND NOT {self.starts}' if mask else f'position({d}) != 0'
        self._constraint(
            self.chord,
            [*self.frame, d],
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}',
            interior,
        )
        edges = ((self.domain_lo, '>=', self.starts), (self.domain_hi, '<=', self.ends))
        axis = ((self.domain_lo, '>=', f'position({d}) == 0'), (self.domain_hi, '<=', f'position({d}) == -1'))
        for cname, sense, at in edges if mask else axis:
            if mask:
                self.record['starts' if sense == '>=' else 'ends'] = at
                self._parameter(
                    at, self._mask_dims(mask), f'the {"first" if sense == ">=" else "last"} breakpoint of each curve'
                )
            self._constraint(cname, [*self.frame, d], f'({x_link.expression}) {sense} {x_link.values}', at)

    # -- checks ------------------------------------------------------------

    def _emitted_by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Every name this block may write, by the kind of declaration each would collide with.

        The set a block states writes names of its own, and they are reserved
        whichever method the block declares: which of the two write them is the
        method's business, and a collision is the file's either way.
        """
        return (
            ('variable', (self.lam, self.set.seg)),
            ('parameter', (self.starts, self.ends, *((self.points,) if self.nominated is not None else ()))),
            (
                'constraint',
                (
                    self.convexity,
                    self.convexity + _UNGATED,
                    self.set.pick,
                    self.set.link,
                    self.chord,
                    self.domain_lo,
                    self.domain_hi,
                    *self.links,
                ),
            ),
            ('sos', (self.name,)),
        )

    def _validated_frame(self) -> tuple[str, ...]:
        """Check every name the block writes and infer its frame: the union of the links' and the gate's dims.

        A values parameter is checked against the frame in a second pass, since
        the last link's expression widens the frame as readily as the first; left
        to the emitted declarations the refusal would name ``<block>_link0``, a
        constraint the author never wrote.
        """
        if self.pw.over not in self.schema.dimensions:
            raise PiecewiseExpansionError(undeclared_dimension('piecewise', self.name, self.pw.over))
        frame: list[str] = []
        self._widen(frame, self._link_dims())
        self._widen(frame, self._activity_dims())
        self._values_fit(frame)
        self._points_fit(frame)
        self._nothing_collides()
        return tuple(frame)

    def _widen(self, frame: list[str], dims: Iterable[tuple[str, frozenset[str]]]) -> None:
        """Add each labelled dim set to *frame* in declaration order, refusing the breakpoint dim.

        Declaration order, because iterating a set would vary the emitted
        ``dims`` — and every column index behind it — per process.
        """
        for what, found in dims:
            for d in (d for d in self.schema.dimensions if d in found):
                if d == self.pw.over:
                    raise PiecewiseExpansionError(
                        f"{self.context}: {what} already carries the breakpoint dim '{self.pw.over}'"
                    )
                if d not in frame:
                    frame.append(d)

    def _link_dims(self) -> Iterator[tuple[str, frozenset[str]]]:
        """Each link's expression dims, its values parameter checked to exist and to run along the breakpoint dim."""
        schema, pw = self.schema, self.pw
        for i, link in enumerate(pw.links):
            values = link.values
            if values not in schema.parameters:
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} values references undeclared parameter '{values}'"
                )
            if pw.over not in schema.parameters[values].dims:
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} values parameter '{values}' must carry dim "
                    f"'{pw.over}' (has {schema.parameters[values].dims})"
                )
            yield f'link {i} expression', self._expr_dims(link.expression, f'{self.context} link {i}')

    def _activity_dims(self) -> Iterator[tuple[str, frozenset[str]]]:
        """The gate's dims, if the block names one: a declared binary variable."""
        activity = self.pw.activity
        if activity is None:
            return
        if activity not in self.schema.variables:
            raise PiecewiseExpansionError(
                f"{self.context}: activity '{activity}' is not a declared variable. A gate is a binary variable; "
                f'declare it, or drop activity: for weights that sum to 1.'
            )
        if self.schema.variables[activity].domain != 'binary':
            raise PiecewiseExpansionError(f"{self.context}: activity variable '{activity}' must be binary")
        yield 'activity', self._expr_dims(activity, f'{self.context} activity')

    def _values_fit(self, frame: list[str]) -> None:
        """A values parameter varies along the frame and the breakpoint dim, and nothing else."""
        for i, link in enumerate(self.pw.links):
            if stray := [d for d in self.schema.parameters[link.values].dims if d != self.pw.over and d not in frame]:
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} values parameter '{link.values}' carries {stray}, which no link "
                    f'expression does — the block builds one curve per coordinate of {frame}, so a curve '
                    f'varying along {stray} has nothing to vary against. Declare a link expression over '
                    f"it, or drop it from '{link.values}'."
                )

    def _points_fit(self, frame: list[str]) -> None:
        """A ``points:`` naming a parameter of its own is a bool mask along the breakpoint dim, inside the frame."""
        pw, ctx = self.pw, self.context
        if pw.points is None or self.nominated is not None:
            return
        if pw.points not in self.schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: points references undeclared parameter '{pw.points}'")
        if (dtype := self.schema.parameters[pw.points].dtype) != 'bool':
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' is {dtype}, and a mask is a bool parameter — one "
                f'saying, per breakpoint, whether the curve reaches it. Declare it dtype: bool.'
            )
        mask = self.schema.parameters[pw.points].dims
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

    def _nothing_collides(self) -> None:
        """No name the block writes is one the file already declares."""
        declared = {
            'variable': self.schema.variables,
            'parameter': self.schema.parameters,
            'constraint': self.schema.constraints,
            'sos': self.schema.sos,
        }
        for kind, names in self._emitted_by_kind():
            for one in names:
                if one in declared[kind]:
                    raise PiecewiseExpansionError(
                        f"{self.context}: emitted {kind} '{one}' collides with a declared {kind}"
                    )

    def _expr_dims(self, text: str, ctx: str) -> frozenset[str]:
        """Dims of an affine link expression, asked of ``dimensions`` before any declaration exists to carry it."""
        ast = parse_and_expand(text, self.schema, ctx)
        if isinstance(ast, ComparisonNode):
            raise PiecewiseExpansionError(f'{ctx}: link expressions must not contain a comparison, got {text!r}')
        errors: list[str] = []
        resolved = resolve_expression(ast, self.ns, ctx, errors)
        if resolved is None:
            raise PiecewiseExpansionError('\n'.join(errors))
        assert not isinstance(resolved, ComparisonNode)
        try:
            check_expression(resolved, ctx)
            return dims_of(resolved, self.schema, ctx)
        except LanguageError as exc:
            raise PiecewiseExpansionError(
                f'{ctx}: link expression {text!r} is not a valid affine expression: {exc}'
            ) from exc


def expand_piecewise(schema: Spec) -> Spec:
    """*schema* with every ``piecewise:`` block written out — *schema* itself where it declares none.

    A ``method: adjacency`` block states its restriction as the set
    ``method: sos2`` states, and then that set is written out here too: the
    binaries are what the method *is*, so the model that comes back carries no
    set of its own (:func:`math_spec.sos.emit` is where they are spelled).

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """
    if not schema.piecewise:
        return schema

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    records = {name: _Block(schema, raw, name, pw).expand() for name, pw in schema.piecewise.items()}
    raw['piecewise'].clear()
    for name, pw in schema.piecewise.items():
        if pw.method == 'adjacency':
            emit(raw, name)
    expanded = Spec.model_validate(raw)
    expanded._expanded_piecewise = {name: ExpandedPiecewise.model_validate(record) for name, record in records.items()}
    return expanded
