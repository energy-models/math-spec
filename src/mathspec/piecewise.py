# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``piecewise:`` blocks into plain variables and constraints.

A block becomes ordinary affine declarations when a caller asks
[`expand`][mathspec.model.Spec.expand] for them, under names prefixed with the
block's own; what each method emits is tabled in
``docs/reference/language/piecewise.md``. Every rule a block is held to is
decided at load, before this runs: the names it references in
[`Spec`][], its links where every expression is typed, and
its frame in [`curve_frame`][].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import mathspec.sos as sos
from mathspec.dimensions import dims_of
from mathspec.errors import DimensionError
from mathspec.model import AssumptionBlock, Curvature, PiecewiseBlock, Spec, VariableBlock
from mathspec.program import PiecewiseDeclaration, PiecewiseMethod, VariableDeclaration, carries_variable
from mathspec.resolution import resolve_expression_text

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mathspec.program import Expression
    from mathspec.resolution import Namespace


#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


def _curvature_required(pw: PiecewiseDeclaration) -> Curvature | None:
    """The curvature *pw*'s method is only exact for, or ``None`` if any shape works.

    A bounded link binds from one side, and that side is the hull boundary the
    weights are driven onto: ``>=`` reaches the lower one, which is the curve
    itself only where the curve is convex. ``lp`` states that boundary as its
    segment lines and ``convex`` relaxes the weights onto it, so the two rest
    on the same shape and read the same sign for it. The opposite bend is
    silently wrong rather than merely loose.

    With both links pinned the weights range over the whole hull, and what
    drives them within it is the objective rather than the block. There the
    most a method states is ``'either'``: a mixed curve is wrong whichever way
    the pressure runs, and a single bend is exact one of the two ways.
    """
    if pw.method not in ('convex', 'lp'):
        return None
    if (sign := pw.curve[1].sign) == '==':
        return 'either'
    return 'convex' if sign == '>=' else 'concave'


def resolve_links(name: str, pw: PiecewiseBlock, ns: Namespace, errors: list[str]) -> tuple[Expression, ...] | None:
    """Block *name*'s link expressions typed, in link order, or ``None`` once one failed, its refusal appended.

    A link is read affinely, so it is held to degree 1 where it is read.
    """
    links = [
        resolve_expression_text(link.expression, ns, f"piecewise '{name}' link {i}", errors, ceiling=1)
        for i, link in enumerate(pw.links)
    ]
    if any(link is None for link in links):
        return None
    return tuple(link for link in links if link is not None)


def lp_domain_refusal(name: str, pw: PiecewiseBlock, links: tuple[Expression, ...]) -> str | None:
    """The refusal for a ``method: lp`` curve whose x-link carries no variable, or ``None``.

    The method bounds the curve's domain with two rows comparing the x-link
    against the first and the last breakpoint, and a row with no variable
    decides nothing. Decided on the link the file wrote, rather than on the
    row the expansion would write under a name the file never declared.
    """
    x = pw.curve[0]
    i = next(i for i, link in enumerate(pw.links) if link is x)
    if carries_variable(links[i]):
        return None
    return (
        f"piecewise '{name}' link {i}: method: lp bounds the curve's domain by rows comparing this link's expression "
        f'against its first and last breakpoint, and {x.expression!r} carries no variable, so those rows decide '
        f'nothing. Name a variable in the link, or use method: convex, sos2 or adjacency, whose weights pin the '
        f'domain themselves.'
    )


def assumptions_of(block: str, pw: PiecewiseDeclaration) -> dict[str, AssumptionBlock]:
    """What *block* assumes of its numbers, by the name the document prints and a refusal quotes.

    Every curve assumes its breakpoints are there: a missing parameter row is
    not absence, it is a zero, so an undeclared breakpoint sits the curve on
    the origin rather than shortening it. A curve has an x-axis only where two
    links tie it, so the increasing condition — and the shape it is checked
    with — exist only there; ``lp`` alone needs a segment to state a line for;
    a mask must be one run.

    Read off the block rather than off an expansion, so a model states what it
    assumes whether or not its curves have been written out. Each condition is
    an ``assumptions:`` entry over the parameters the file declared, its
    ``description`` naming the method and the rewrite that takes a curve of any
    shape: the expansion writes them into the model, and a model that still
    declares the block resolves the same entries at load.
    """
    d, mask = pw.over, pw.points
    assumed: dict[str, AssumptionBlock] = {}
    assumed[f'{block}_complete'] = AssumptionBlock(
        holds=' AND '.join(dict.fromkeys(link.values for link in pw.links)),
        where=mask,
        description=f"piecewise '{block}': every breakpoint the curve runs through needs a row in "
        f'{_quoted(link.values for link in pw.links)} — a missing row is read as a zero rather than as a '
        f'shorter curve, so it sits the curve on the origin. '
        + (
            f"Attach the rows, or narrow points: '{mask}' to where the curve runs."
            if mask is not None
            else 'Attach the rows, or declare points: to say how far the curve runs.'
        ),
    )
    curvature = _curvature_required(pw)
    if curvature is not None:
        x, y = (link.values for link in pw.curve)
        assumed[f'{block}_increasing'] = AssumptionBlock(
            holds=f'{_back(x, d, 1)} < {x}',
            where=_neighbours(d, mask),
            description=f"piecewise '{block}': method: {pw.method} requires strictly increasing breakpoints in '{x}' along '{d}'",
        )
        assumed[f'{block}_curvature'] = _bends(block, pw, x, y, curvature)
    if pw.method == 'lp':
        assumed[f'{block}_breakpoints'] = AssumptionBlock(
            holds=f'count({mask or pw.curve[0].values}, over={d}) >= 2',
            description=f"piecewise '{block}': method: lp needs at least two breakpoints per curve — the method *is* its "
            f'segment lines, so a curve with no segment states nothing and leaves the bounded link on its own '
            f'bound. Use method: adjacency, sos2 or convex, which pin it to the points it does have.',
        )
    if mask is not None:
        assumed[f'{block}_contiguous'] = AssumptionBlock(
            holds=f'count({_edge(d, mask, "first")}, over={d}) == 1',
            description=f"piecewise '{block}': points: '{mask}' must mark a consecutive run of at least one breakpoint per "
            f'curve — {_GAP[pw.method]}.',
        )
    return assumed


#: Why a gap in ``points:`` breaks each method, in the rows that method writes.
_GAP: dict[PiecewiseMethod, str] = {
    'adjacency': 'the weights are nonzero only on two neighbouring breakpoints, and a gap leaves no neighbour across it',
    'sos2': 'the weights are nonzero only on two neighbouring breakpoints, and a gap leaves no neighbour across it',
    'convex': 'the checks on the shape compare a breakpoint with its neighbours, so a bend across a gap goes unchecked',
    'lp': "the chord row joins a breakpoint to the one before it, and the domain rows sit on the curve's own first "
    'and last',
}


def _quoted(names: Iterable[str]) -> str:
    """Parameter names as a refusal lists them, in link order and without repeats."""
    return ', '.join(f"'{name}'" for name in dict.fromkeys(names))


def _back(parameter: str, over: str, offset: int) -> str:
    """One breakpoint along *over* from here, the vacated row filled with zero and excluded by the ``where``.

    ``edge=0`` is what the language admits over data, and the mask beside it
    is what keeps the invented zero from ever being read.
    """
    return f'shift({parameter}, along={over}, offset={offset}, edge=0)'


def _neighbours(over: str, mask: str | None) -> str:
    """Where a breakpoint and the one before it are both there: the rows a claim about a segment is true of."""
    if mask is None:
        return f'position({over}) > 0'
    return f'{mask} AND shift({mask}, along={over}, offset=1)'


def _edge(over: str, mask: str | None, end: Literal['first', 'last']) -> str:
    """The first or last breakpoint of each curve: where the mask holds and does not one step outward.

    The vacated edge of a ``shift`` in a ``where`` is false, which is what
    makes the head and the tail of the axis their own edge.
    """
    if mask is None:
        return f'position({over}) == {0 if end == "first" else -1}'
    return f'{mask} AND NOT shift({mask}, along={over}, offset={1 if end == "first" else -1})'


def _interior(over: str, mask: str | None) -> str:
    """Where a breakpoint has one on either side: the rows a claim about a bend is true of."""
    if mask is None:
        return f'position({over}) > 0 AND position({over}) != -1'
    return f'{mask} AND shift({mask}, along={over}, offset=1) AND shift({mask}, along={over}, offset=-1)'


def _bends(block: str, pw: PiecewiseDeclaration, x: str, y: str, curvature: Curvature) -> AssumptionBlock:
    """The curve bends the way *curvature* says, as a comparison of the two slopes at each breakpoint.

    The slopes are compared as a cross-product rather than as two quotients,
    so nothing divides by a run the increasing condition is what rules out.
    ``either`` is one bend in *some* direction, which is a claim about the
    whole axis rather than about a breakpoint: it counts the bends that go the
    wrong way and asks that one of the two directions has none.
    """
    d, mask = pw.over, pw.points
    rise, run = f'({y} - {_back(y, d, 1)})', f'({x} - {_back(x, d, 1)})'
    next_rise, next_run = f'({_back(y, d, -1)} - {y})', f'({_back(x, d, -1)} - {x})'
    bend = f'{rise} * {next_run} {{}} {next_rise} * {run}'
    interior = _interior(d, mask)
    shape = 'a single bend' if curvature == 'either' else f'a {curvature} curve'
    description = (
        f"piecewise '{block}': method: {pw.method} is exact only for {shape}, and '{y}' over '{x}' along "
        f"'{d}' is not one, so the answer is wrong rather than loose. Use method: adjacency "
        f'or sos2, which take a curve of any shape.'
    )
    if curvature == 'either':
        up, down = bend.format('>'), bend.format('<')
        return AssumptionBlock(
            holds=f'count({up} AND {interior}, over={d}) == 0 OR count({down} AND {interior}, over={d}) == 0',
            description=description,
        )
    return AssumptionBlock(
        holds=bend.format('<=' if curvature == 'convex' else '>='), where=interior, description=description
    )


@dataclass(frozen=True)
class Emitted:
    """Every name one block's expansion may write, spelled once for the emitter and the collision check.

    The set a block states writes names of its own, and they are reserved
    whichever method the block declares: which of the two write them is the
    method's business, and a collision is the file's either way.
    """

    name: str
    lam: str
    convexity: str
    set: sos.Emitted
    chord: str
    domain_lo: str
    domain_hi: str
    links: tuple[str, ...]
    assumptions: tuple[str, ...]

    @classmethod
    def of(cls, name: str, pw: PiecewiseDeclaration) -> Emitted:
        """The names block *name* writes."""
        return cls(
            name,
            f'{name}_lam',
            f'{name}_convexity',
            sos.Emitted.of(name, 2),
            f'{name}_chord',
            f'{name}_domain_lo',
            f'{name}_domain_hi',
            tuple(f'{name}_link{i}' for i in range(len(pw.links))),
            tuple(assumptions_of(name, pw)),
        )

    def written(self, method: PiecewiseMethod, *, ungated: bool) -> tuple[str, ...]:
        """The variables and constraints [`expand`][mathspec.model.Spec.expand] declares for a block of *method*.

        *ungated* is [`leaves_ungated`][] of the block's gate. The set a
        ``sos2`` or ``adjacency`` block states is written out too, since
        ``expand()`` writes every set.
        """
        if method == 'lp':
            return (self.chord, self.domain_lo, self.domain_hi)
        convexity = (self.convexity, self.convexity + _UNGATED) if ungated else (self.convexity,)
        restriction = (self.set.seg, self.set.pick, self.set.link) if method in ('sos2', 'adjacency') else ()
        return (self.lam, *convexity, *self.links, *restriction)

    @property
    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each name by the kind of declaration it would collide with."""
        return (
            ('variable', (self.lam, self.set.seg)),
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
            ('assumption', self.assumptions),
        )


def leaves_ungated(gate: VariableBlock | VariableDeclaration | None) -> bool:
    """Whether a curve gated by *gate* runs ungated where the gate does not exist, which takes a second convexity row.

    A masked gate is absent off its mask, and there the curve sums to 1;
    ``absence: zero`` reads the gate as 0 there instead, which one row states.
    """
    return gate is not None and gate.where is not None and gate.absence != 'zero'


def curve_frame(schema: Spec, name: str, pw: PiecewiseBlock, links: Iterable[Expression]) -> tuple[str, ...]:
    """The dimensions block *name* builds one curve per coordinate of: every one its links and its gate carry.

    In declaration order, because iterating a set would vary the emitted
    ``dims`` — and every column index behind it — per process. *links* are the
    block's link expressions typed, as [`resolve_links`][] answers.

    Raises:
        DimensionError: A link or the gate carries the breakpoint dimension, or
            a values or ``points:`` parameter varies along a dimension no link
            expression carries.
    """
    context = f"piecewise '{name}'"
    carried = [(f'link {i} expression', dims_of(node, schema, f'{context} link {i}')) for i, node in enumerate(links)]
    if pw.activity is not None:
        carried.append(('activity', frozenset(schema.variables[pw.activity].dims)))
    frame: list[str] = []
    for what, found in carried:
        for d in (d for d in schema.dimensions if d in found):
            if d == pw.over:
                raise DimensionError(f"{context}: {what} already carries the breakpoint dim '{pw.over}'")
            if d not in frame:
                frame.append(d)
    for i, link in enumerate(pw.links):
        if stray := [d for d in schema.parameters[link.values].dims if d != pw.over and d not in frame]:
            raise DimensionError(
                f"{context}: link {i} values parameter '{link.values}' carries {stray}, which no link "
                f'expression does — the block builds one curve per coordinate of {frame}, so a curve '
                f'varying along {stray} has nothing to vary against. Declare a link expression over '
                f"it, or drop it from '{link.values}'."
            )
    if pw.points is not None and pw.nominated is None:
        mask = schema.parameters[pw.points].dims
        if stray := [d for d in mask if d != pw.over and d not in frame]:
            raise DimensionError(
                f"{context}: points parameter '{pw.points}' carries {stray}, which the links do not — "
                f"a mask says which of the block's own coordinates exist, and cannot add coordinates"
            )
    return tuple(frame)


class _Block:
    """One ``piecewise:`` block being expanded into the raw model it writes.

    ``mask`` is the parameter masking the weights, or ``None`` for a whole
    curve: the ``bool`` the file named, or one of the block's own values
    parameters, which as a bare name in a ``where`` is true wherever it has a
    row. Nothing here can fail: every rule a block is held to was decided when
    *schema* loaded.
    """

    def __init__(
        self, schema: Spec, raw: dict[str, object], name: str, pw: PiecewiseBlock, curve: PiecewiseDeclaration
    ) -> None:
        self.schema = schema
        self.raw = raw
        self.name = name
        #: The block as the file wrote it, for the link text the rows repeat.
        self.pw = pw
        #: The block as the program carries it, for its frame and the names it writes.
        self.curve = curve
        self.emitted = Emitted.of(name, curve)
        self.mask = pw.points
        self.frame = curve.frame

    def expand(self) -> None:
        """Write the block's declarations into the raw model."""
        if self.pw.method == 'lp':
            self._segment_lines()
        else:
            self._weights()
        self._assumptions()

    def _assumptions(self) -> None:
        """What the method assumes of the numbers, written into the model the expansion returns.

        A formulation states its conditions the way it states its rows, so a
        model that has been written out carries them as language rather than
        as something a consumer has to know to ask for.
        """
        assumptions = sos.section(self.raw, 'assumptions')
        for name, assumed in assumptions_of(self.name, self.curve).items():
            assumptions[name] = assumed.model_dump()

    # -- emitters ----------------------------------------------------------

    def _weight(self, name: str, **fields: object) -> None:
        """A variable over the frame and the breakpoint dim, masked as the block is."""
        sos.section(self.raw, 'variables')[name] = {
            'dims': [*self.frame, self.pw.over],
            **({'where': self.mask} if self.mask else {}),
            **fields,
        }

    def _constraint(self, name: str, dims: list[str], expression: str, where: str | None = None) -> None:
        sos.section(self.raw, 'constraints')[name] = {
            'dims': dims,
            **({'where': where} if where else {}),
            'expression': expression,
        }

    def _weights(self) -> None:
        """The convex-combination form: weights, their convexity, a row per link, and the method's restriction."""
        d = self.pw.over
        self._weight(
            self.emitted.lam,
            bounds={'lower': 0.0, 'upper': 1.0},
            description='convex-combination weight on a breakpoint',
        )
        gated = self._gate_rows()
        for suffix, where, rhs in gated:
            self._constraint(
                self.emitted.convexity + suffix, list(self.frame), f'sum({self.emitted.lam}, over={d}) == {rhs}', where
            )
        for cname, link in zip(self.emitted.links, self.pw.links, strict=True):
            self._constraint(
                cname,
                list(self.frame),
                f'({link.expression}) {link.sign} sum({self.emitted.lam} * {link.values}, over={d})',
            )
        if self.pw.method in ('sos2', 'adjacency'):
            sos.section(self.raw, 'sos')[self.name] = {'variable': self.emitted.lam, 'along': d, 'type': 2}

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
        if not leaves_ungated(self.schema.variables[activity]):
            return (('', None, f'({activity})'),)
        return (('', activity, f'({activity})'), (_UNGATED, f'NOT {activity}', '1'))

    def _segment_lines(self) -> None:
        """The segment-line form: a row per segment, and the two domain rows.

        The chord sits at the later breakpoint, so the first has none and its
        ``where:`` and ``edge=0`` travel together — without the exclusion the
        vacated position is a spurious line through the origin; under a mask the
        first breakpoint is the curve's own. The row is multiplied through by the
        run rather than dividing, which keeps its sense only because the
        breakpoints are strictly monotone. The domain rows are ``linopy``'s
        ``_add_lp`` rows under its names, each sitting on the edge of the curve
        the mask marks, which is why the mask has to be one run.
        """
        x_link, y_link = self.pw.curve
        d = self.pw.over
        run = f'({x_link.values} - shift({x_link.values}, along={d}, offset=1, edge=0))'
        rise = f'({y_link.values} - shift({y_link.values}, along={d}, offset=1, edge=0))'
        self._constraint(
            self.emitted.chord,
            [*self.frame, d],
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}',
            _neighbours(d, self.mask),
        )
        edges = ((self.emitted.domain_lo, '>=', 'first'), (self.emitted.domain_hi, '<=', 'last'))
        for cname, sense, end in edges:
            self._constraint(
                cname, [*self.frame, d], f'({x_link.expression}) {sense} {x_link.values}', _edge(d, self.mask, end)
            )


def expand_piecewise(schema: Spec) -> Spec:
    """*schema* with every ``piecewise:`` block written out — *schema* itself where it declares none.

    A ``method: adjacency`` block states its restriction as the set
    ``method: sos2`` states, and then that set is written out here too: the
    binaries are what the method *is*, so the model that comes back carries no
    set of its own ([`mathspec.sos.emit`][] is where they are spelled).
    Each block's frame and names are read off the program *schema* lowered to.
    """
    if not schema.piecewise:
        return schema
    program = schema.program
    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, pw in schema.piecewise.items():
        _Block(schema, raw, name, pw, program.piecewise[name]).expand()
    raw['piecewise'].clear()
    for name, pw in schema.piecewise.items():
        if pw.method == 'adjacency':
            sos.emit(raw, name)
    return Spec.model_validate(raw)
