# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``piecewise:`` blocks into plain variables and constraints.

A block becomes ordinary affine declarations before anything reads the model,
under names prefixed with the block's own; what each method emits is tabled in
``docs/reference/language/piecewise.md``. Everything the language decides
about a block against its model is decided once, in :func:`check`, and the
emitters write rows from the facts it settled. A refusal names the link or key
the file wrote rather than an emitted declaration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from math_spec._expression_parser import NAME
from math_spec.dimensions import dims_of
from math_spec.errors import PiecewiseExpansionError
from math_spec.model import AssumptionBlock, Curvature, PiecewiseBlock, PiecewiseLink, PiecewiseMethod, Spec
from math_spec.program import Mask, PiecewiseDeclaration
from math_spec.sos import Emitted, emit

if TYPE_CHECKING:
    from collections.abc import Iterable

# ---------------------------------------------------------------------------
# the mask
# ---------------------------------------------------------------------------


class CurveMask:
    """A block's ``where:``, as each shape of row the expansion writes reads it.

    Built from the block and its resolved mask, to answer the one question the
    expansion asks of it: whether it reads the breakpoint dim. Such a where is
    **ragged** — it says how far each curve runs, not only which curves exist
    — so a row over the frame and the breakpoint dim takes it as written, the
    rows on a curve's edges shift it, and a row over the frame alone, which
    cannot read that dim, takes the count of breakpoints it admits. A where
    over the frame alone reaches every row as written.
    """

    def __init__(self, block: PiecewiseBlock, resolved: Mask | None) -> None:
        self.text = block.where
        self.along = block.along
        self.dims: frozenset[str] = resolved.dims if resolved is not None else frozenset()

    @property
    def ragged(self) -> bool:
        """Whether the where reads the breakpoint dim, and so says how far each curve runs."""
        return self.along in self.dims

    @property
    def frame(self) -> str | None:
        """The where as a row over the frame and the breakpoint dim conjoins it onto a position test — none where ragged."""
        return None if self.ragged else self.text

    @property
    def exists(self) -> str | None:
        """What a row over the frame alone takes: the where, or the count of breakpoints a ragged one admits."""
        if not self.ragged:
            return self.text
        return f'count({self.text}, over={self.along}) > 0'

    def neighbours(self) -> str:
        """Where a breakpoint and the one before it are both there: the rows a claim about a segment is true of."""
        if not self.ragged:
            return f'position({self.along}) > 0'
        return f'{self._atom} AND {self._shifted(1)}'

    def edge(self, end: Literal['first', 'last']) -> str:
        """The first or last breakpoint of each curve: where the mask holds and does not one step outward.

        The vacated edge of a ``shift`` in a ``where`` is false, which is what
        makes the head and the tail of the axis their own edge.
        """
        if not self.ragged:
            return f'position({self.along}) == {0 if end == "first" else -1}'
        return f'{self._atom} AND NOT {self._shifted(1 if end == "first" else -1)}'

    def interior(self) -> str:
        """Where a breakpoint has one on either side: the rows a claim about a bend is true of."""
        if not self.ragged:
            return f'position({self.along}) > 0 AND position({self.along}) != -1'
        return f'{self._atom} AND {self._shifted(1)} AND {self._shifted(-1)}'

    @property
    def _atom(self) -> str:
        """The where as one operand of a connective: a bare name as it is, anything else parenthesised."""
        assert self.text is not None, 'a ragged where is written'
        return self.text if re.fullmatch(NAME, self.text) else f'({self.text})'

    def _shifted(self, offset: int) -> str:
        """The where read *offset* breakpoints back, false where that vacates."""
        return f'shift({self.text}, along={self.along}, offset={offset})'


def _all_of(*clauses: str | None) -> str | None:
    """The where admitting a row only where every clause given does, or ``None`` where none of them speaks.

    A lone clause passes through as it was written, so a block with no
    ``where:`` emits exactly the string it always did. Joined clauses are
    parenthesised, because a disjunction inside one of them would otherwise
    bind only its last operand to the ``AND``.
    """
    kept = [clause for clause in clauses if clause]
    if len(kept) <= 1:
        return kept[0] if kept else None
    return ' AND '.join(f'({clause})' for clause in kept)


# ---------------------------------------------------------------------------
# what a block assumes of its numbers
# ---------------------------------------------------------------------------


def _curvature_required(block: PiecewiseBlock) -> Curvature | None:
    """The curvature *block*'s method is only exact for, or ``None`` if any shape works.

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
    if block.method not in ('convex', 'lp'):
        return None
    if (sign := block.curve[1].sign) == '==':
        return 'either'
    return 'convex' if sign == '>=' else 'concave'


def declaration_of(block: PiecewiseBlock, where: Mask | None = None) -> PiecewiseDeclaration:
    """The curve of one expanded block, as a program carries it.

    Args:
        block: The block as written.
        where: Which coordinates of the frame have a curve, lowered — and so
            which ones what the block assumes is asked at.
    """
    return PiecewiseDeclaration(
        along=block.along,
        method=block.method,
        breakpoints=tuple(link.values for link in block.links),
        where=where,
    )


def assumptions_of(name: str, block: PiecewiseBlock, where: CurveMask) -> dict[str, AssumptionBlock]:
    """What *block* assumes of its numbers, by the name the document prints and a refusal quotes.

    Every curve assumes its breakpoints are there: a missing parameter row is
    not absence, it is a zero, so an undeclared breakpoint sits the curve on
    the origin rather than shortening it. A curve has an x-axis only where two
    links tie it, so the increasing condition — and the shape it is checked
    with — exist only there; ``lp`` alone needs a segment to state a line for;
    a ragged ``where:`` must mark one run.

    Read off the block rather than off an expansion, so a model states what it
    assumes whether or not its curves have been written out. Each condition is
    a where string over the parameters the file declared: the expansion writes
    them into ``assumptions:``, and a model that still declares the block
    derives the same text at load. A ``where:`` over the frame alone is not
    written into them: a program carries it on the declaration, and asks each
    condition only where it holds.
    """
    d = block.along
    mask = where.text if where.ragged else None
    values = [link.values for link in block.links]
    assumed = {
        f'{name}_complete': AssumptionBlock(
            holds=' AND '.join(dict.fromkeys(values)),
            where=mask,
            description=f"piecewise '{name}': every breakpoint the curve runs through needs a row in "
            f'{_quoted(values)} — a missing row is read as a zero rather than as a shorter curve, so it sits '
            f'the curve on the origin. '
            + (
                f'Bind the rows, or narrow where: {mask!r} to where the curve runs.'
                if mask is not None
                else 'Bind the rows, or declare where: to say how far the curve runs.'
            ),
        )
    }
    curvature = _curvature_required(block)
    if curvature is not None:
        x, y = (link.values for link in block.curve)
        assumed[f'{name}_increasing'] = AssumptionBlock(
            holds=f'{_neighbour(x, d, 1)} < {x}',
            where=where.neighbours(),
            description=f"piecewise '{name}': method: {block.method} requires strictly increasing breakpoints "
            f"in '{x}' along '{d}'",
        )
        assumed[f'{name}_curvature'] = _bends(name, block, where, x, y, curvature)
    if block.method == 'lp':
        assumed[f'{name}_breakpoints'] = AssumptionBlock(
            holds=f'count({mask or block.curve[0].values}, over={d}) >= 2',
            description=f"piecewise '{name}': method: lp needs at least two breakpoints per curve — the method "
            f'*is* its segment lines, so a curve with no segment states nothing and leaves the bounded link on '
            f'its own bound. Use method: adjacency, sos2 or convex, which pin it to the points it does have.',
        )
    if mask is not None:
        assumed[f'{name}_contiguous'] = AssumptionBlock(
            holds=f'count({where.edge("first")}, over={d}) == 1',
            description=f"piecewise '{name}': where: {mask!r} must mark a consecutive run of at least one "
            f'breakpoint per curve — {_GAP[block.method]}.',
        )
    return assumed


#: Why a gap in a ragged ``where:`` breaks each method, in the rows that method writes.
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


def _neighbour(parameter: str, along: str, offset: int) -> str:
    """*parameter* read *offset* breakpoints back, the vacated row filled with zero and excluded by the ``where``.

    ``edge=0`` is what the language admits over data, and the mask beside it
    is what keeps the invented zero from ever being read.
    """
    return f'shift({parameter}, along={along}, offset={offset}, edge=0)'


def _bends(name: str, block: PiecewiseBlock, where: CurveMask, x: str, y: str, curvature: Curvature) -> AssumptionBlock:
    """The curve bends the way *curvature* says, as a comparison of the two slopes at each breakpoint.

    The slopes are compared as a cross-product rather than as two quotients,
    so nothing divides by a run the increasing condition is what rules out.
    ``either`` is one bend in *some* direction, which is a claim about the
    whole axis rather than about a breakpoint: it counts the bends that go the
    wrong way and asks that one of the two directions has none.
    """
    d = block.along
    rise, run = f'({y} - {_neighbour(y, d, 1)})', f'({x} - {_neighbour(x, d, 1)})'
    next_rise, next_run = f'({_neighbour(y, d, -1)} - {y})', f'({_neighbour(x, d, -1)} - {x})'
    bend = f'{rise} * {next_run} {{}} {next_rise} * {run}'
    interior = where.interior()
    shape = 'a single bend' if curvature == 'either' else f'a {curvature} curve'
    description = (
        f"piecewise '{name}': method: {block.method} is exact only for {shape}, and '{y}' over '{x}' along "
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


# ---------------------------------------------------------------------------
# the checked block
# ---------------------------------------------------------------------------

#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


#: What a block may assume of its numbers, by suffix — the names
#: :func:`assumptions_of` writes, reserved whether or not the method states each.
ASSUMED = ('complete', 'increasing', 'curvature', 'breakpoints', 'contiguous')


@dataclass(frozen=True)
class Names:
    """Every name one block's expansion writes, spelled once for the emitters and the collision check.

    Every name is reserved whichever method the block declares: which method
    writes which is the method's business, and a collision is the file's
    either way. ``sos`` holds the names a method that states a set writes
    through :func:`math_spec.sos.emit`.
    """

    name: str
    weights: str
    convexity: str
    chord: str
    domain_lo: str
    domain_hi: str
    links: tuple[str, ...]
    sos: Emitted

    @classmethod
    def of(cls, name: str, links: int) -> Names:
        """The names block *name* with *links* links writes."""
        return cls(
            name=name,
            weights=f'{name}_lam',
            convexity=f'{name}_convexity',
            chord=f'{name}_chord',
            domain_lo=f'{name}_domain_lo',
            domain_hi=f'{name}_domain_hi',
            links=tuple(f'{name}_link{i}' for i in range(links)),
            sos=Emitted.of(name, 2),
        )

    @property
    def ungated(self) -> str:
        """The second gate row, where the gate variable does not exist."""
        return self.convexity + _UNGATED

    @property
    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each name by the kind of declaration it would collide with."""
        rows = (self.convexity, self.ungated, self.sos.pick, self.sos.link, self.chord, self.domain_lo, self.domain_hi)
        return (
            ('variable', (self.weights, self.sos.seg)),
            ('constraint', (*rows, *self.links)),
            ('sos', (self.name,)),
            ('assumption', tuple(f'{self.name}_{what}' for what in ASSUMED)),
        )


#: One row making the weights sum to what they sum to: ``(name suffix, where, right-hand side)``.
GateRow = tuple[str, str | None, str]


@dataclass(frozen=True)
class Curve:
    """One ``piecewise:`` block held to its model: every fact the rows it writes read.

    :func:`check` is the only thing that builds one, so holding one is the
    proof that the block is inside the language, and nothing after it decides
    anything.

    Attributes:
        name: The block's key.
        block: The block as written.
        frame: The dims the block builds one curve per coordinate of.
        rows: Each link's row frame — the frame, or its refinement through the
            link's relation.
        mask: The block's ``where:``, as each shape of row reads it.
        gates: The rows the weights sum under, one or two.
        names: Every name the expansion writes.
    """

    name: str
    block: PiecewiseBlock
    frame: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    mask: CurveMask
    gates: tuple[GateRow, ...]
    names: Names


def check(schema: Spec, name: str, block: PiecewiseBlock) -> Curve:
    """*block* held to everything the language decides about it against its model, as the facts its rows read.

    What the block names by key — dimensions, parameters, relations, the gate
    — and the names it writes are checked as the file loads, with every other
    cross-declaration rule (:class:`~math_spec.model.Spec`); the link
    expressions and the where are typed with the rest of the model
    (:attr:`~math_spec.model.Spec.resolved`), so a fault in one is named
    against the link there. What is left is what needs those typed forms: the
    frame, declared by ``dims:`` or read off the links; each link's row; that
    each link's expression and values fit its row; and that the ``where:``
    fits the frame.

    Raises:
        PiecewiseExpansionError: A link that does not fit its row, a frame
            that reaches the breakpoint dim, or a where outside the frame.
    """
    ctx = f"piecewise '{name}'"
    links, where = schema.resolved.piecewise[name]
    expressions = tuple(dims_of(node, schema, f'{ctx} link {i}') for i, node in enumerate(links))
    frame = _frame(schema, block, expressions, ctx)
    rows = tuple(_row(schema, block, i, link, frame, ctx) for i, link in enumerate(block.links))
    _links_fit(block, expressions, rows, ctx)
    _values_fit(schema, block, rows, ctx)
    mask = CurveMask(block, where)
    _where_fits(block, mask, frame, ctx)
    return Curve(name, block, frame, rows, mask, _gate_rows(schema, block), Names.of(name, len(block.links)))


def _frame(schema: Spec, block: PiecewiseBlock, expressions: tuple[frozenset[str], ...], ctx: str) -> tuple[str, ...]:
    """The dims the block builds one curve per: ``dims:`` as written, or the union of the link expressions' dims.

    Declared order where ``dims:`` states it — the same key a variable and a
    constraint carry, and there the file's order is the emitted one — and
    declaration order where it is read off the links, because iterating a set
    would vary the emitted ``dims``, and every column index behind it, per
    process. The gate's dims widen either, and neither may carry the
    breakpoint dim: the frame is what the block builds one curve per, and
    every curve runs along the breakpoints.
    """
    frame: list[str] = list(block.dims) if block.dims is not None else []
    if block.dims is None:
        for i, found in enumerate(expressions):
            _widen(schema, block, frame, f'link {i} expression', found, ctx)
    if block.activity is not None:
        _widen(schema, block, frame, 'activity', frozenset(schema.variables[block.activity].dims), ctx)
    return tuple(frame)


def _widen(schema: Spec, block: PiecewiseBlock, frame: list[str], what: str, found: frozenset[str], ctx: str) -> None:
    """Add *found* to *frame* in declaration order, refusing the breakpoint dim."""
    for d in (d for d in schema.dimensions if d in found):
        if d == block.along:
            raise PiecewiseExpansionError(f"{ctx}: {what} already carries the breakpoint dim '{block.along}'")
        if d not in frame:
            frame.append(d)


def _row(
    schema: Spec, block: PiecewiseBlock, i: int, link: PiecewiseLink, frame: tuple[str, ...], ctx: str
) -> tuple[str, ...]:
    """The dims one link's row is built over: the curve's frame, or its refinement through the link's relation.

    The produced dims stand where the consumed ones did, so a refined row
    reads in the shape of the curve it ties rather than in relation order.
    """
    if not link.refined:
        return frame
    consumed, produced = _walk(schema, link) if link.walks else (frozenset(), _spans(link, frame, f'{ctx} link {i}'))
    if missing := sorted(consumed - set(frame)):
        raise PiecewiseExpansionError(
            f"{ctx} link {i}: over reaches {missing}, which the curve's dims {list(frame)} do not "
            f"carry. A walk consumes the frame's own dimension — name one of {list(frame)}, or declare it in dims:."
        )
    refined: list[str] = []
    for d in frame:
        if d in consumed:
            refined.extend(p for p in schema.dimensions if p in produced and p not in refined)
        elif d not in refined:
            refined.append(d)
    refined.extend(p for p in schema.dimensions if p in produced and p not in refined)
    return tuple(refined)


def _walk(schema: Spec, link: PiecewiseLink) -> tuple[frozenset[str], frozenset[str]]:
    """The dims one walked link consumes and produces, read off the relation it names."""
    assert link.by is not None and link.over is not None and link.into is not None
    roles = dict(schema.relations[link.by].pairs)
    consumed, produced = (
        frozenset(roles[c] for c in ([written] if isinstance(written, str) else written))
        for written in (link.over, link.into)
    )
    return consumed, produced


def _spans(link: PiecewiseLink, frame: tuple[str, ...], ctx: str) -> frozenset[str]:
    """The dims a link spans without walking a relation — dimensions the curve does not already carry."""
    assert link.into is not None
    named = [link.into] if isinstance(link.into, str) else list(link.into)
    for d in named:
        if d in frame:
            raise PiecewiseExpansionError(
                f"{ctx}: into names '{d}', which the curve's dims already carries. The curve builds one "
                f"per coordinate of it, so it cannot also index this link's ties — drop it from dims:, "
                f'or split along a dimension of its own.'
            )
    return frozenset(named)


def _links_fit(
    block: PiecewiseBlock, expressions: tuple[frozenset[str], ...], rows: tuple[tuple[str, ...], ...], ctx: str
) -> None:
    """Every link expression carries exactly its row's frame — the rule a constraint's own ``dims:`` holds to.

    Both directions are refused because both broadcast one side of the row.
    A stray dim multiplies the rows the link builds; a missing one repeats
    the same row across it, which pins the expression to one operating point
    along a dimension the curve varies over. Neither is sayable another way,
    so neither is guessed, and the rewrite differs by where the frame came from.
    """
    for i, (found, own) in enumerate(zip(expressions, rows, strict=True)):
        if block.along in found:
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} expression already carries the breakpoint dim '{block.along}'"
            )
        if stray := sorted(found - set(own)):
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} expression carries {stray}, which its row's frame {list(own)} does "
                f'not — every stray dim multiplies the rows the link builds. Add it to dims:, sum it out, '
                f'or read it through a relation with by, over and into.'
            )
        if missing := sorted(set(own) - found):
            repeated = (
                f"link {i} expression does not carry {missing}, which its row's frame {list(own)} does — the same "
                f'row would repeat across {missing}, pinning the expression to one operating point along '
                f'{"it" if len(missing) == 1 else "them"}. '
            )
            rewrite = (
                f"The frame is the union of the link expressions' dims, so another link carries {missing}. "
                f'Declare dims: to say which curve the block builds, or vary this expression along {missing}.'
                if block.dims is None
                else f'Drop {missing} from dims:, or vary the expression along {missing}.'
            )
            raise PiecewiseExpansionError(f'{ctx}: {repeated}{rewrite}')


def _values_fit(schema: Spec, block: PiecewiseBlock, rows: tuple[tuple[str, ...], ...], ctx: str) -> None:
    """A values parameter varies along its own link's row and the breakpoint dim, and nothing else.

    Its own link's, because a refined link's curve is read per fine
    coordinate: ``bp_power`` is per flow where the block's frame is per
    converter, and comparing it against the frame would refuse it.
    """
    for i, (link, own) in enumerate(zip(block.links, rows, strict=True)):
        if stray := [d for d in schema.parameters[link.values].dims if d != block.along and d not in own]:
            raise PiecewiseExpansionError(
                f"{ctx}: link {i} values parameter '{link.values}' carries {stray}, which its "
                f"row's frame {list(own)} does not — the link builds one curve per coordinate of {list(own)}, so a "
                f'curve varying along {stray} has nothing to vary against. Declare a link expression over '
                f"it, or drop it from '{link.values}'."
            )


def _where_fits(block: PiecewiseBlock, mask: CurveMask, frame: tuple[str, ...], ctx: str) -> None:
    """A block's ``where:`` tests the frame it builds curves over and the breakpoint dim, and nothing else.

    Read here rather than left to the emitted declarations, whose refusal
    would name ``<block>_lam`` — a variable the author never wrote. A
    refined link's values parameter carries the link's own frame, so a
    where naming it is refused here too: raggedness is the curve's.
    """
    if stray := sorted(mask.dims - set(frame) - {block.along}):
        raise PiecewiseExpansionError(
            f'{ctx}: where {block.where!r} tests {stray}, which no link expression carries — a mask says '
            f"which of the block's own coordinates have a curve, and cannot add coordinates. Declare a "
            f'link expression over {stray}, or drop it from the where.'
        )


def _gate_rows(schema: Spec, block: PiecewiseBlock) -> tuple[GateRow, ...]:
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
    activity = block.activity
    if activity is None:
        return (('', None, '1'),)
    gate = schema.variables[activity]
    if gate.where is None or gate.absence == 'zero':
        return (('', None, f'({activity})'),)
    return (('', activity, f'({activity})'), (_UNGATED, f'NOT {activity}', '1'))


# ---------------------------------------------------------------------------
# the rows a block writes
# ---------------------------------------------------------------------------


def _section(raw: dict[str, object], name: str) -> dict[str, object]:
    """The *name* section of the raw model, created empty where the file declares none."""
    section = raw.setdefault(name, {})
    assert isinstance(section, dict), f'{name}: is a mapping in a validated model'
    return section


def _constraint(raw: dict[str, object], name: str, dims: Iterable[str], expression: str, where: str | None) -> None:
    _section(raw, 'constraints')[name] = {
        'dims': list(dims),
        **({'where': where} if where else {}),
        'expression': expression,
    }


def _write(raw: dict[str, object], curve: Curve) -> None:
    """Write the block's declarations into the raw model: its rows, and what its method assumes of the numbers.

    A formulation states its conditions the way it states its rows, so a
    model that has been written out carries them as language rather than as
    something a consumer has to know to ask for.
    """
    if curve.block.method == 'lp':
        _segment_lines(raw, curve)
    else:
        _weights(raw, curve)
    section = _section(raw, 'assumptions')
    for name, assumed in assumptions_of(curve.name, curve.block, curve.mask).items():
        section[name] = assumed.model_dump()


def _weights(raw: dict[str, object], curve: Curve) -> None:
    """The convex-combination form: weights, their convexity, a row per link, and the method's restriction."""
    block, names, where = curve.block, curve.names, curve.mask
    d = block.along
    _section(raw, 'variables')[names.weights] = {
        'dims': [*curve.frame, d],
        **({'where': where.text} if where.text else {}),
        'bounds': {'lower': 0.0, 'upper': 1.0},
        'description': 'convex-combination weight on a breakpoint',
    }
    for suffix, gate, rhs in curve.gates:
        _constraint(
            raw,
            names.convexity + suffix,
            curve.frame,
            f'sum({names.weights}, over={d}) == {rhs}',
            _all_of(where.exists, gate),
        )
    for cname, link, row in zip(names.links, block.links, curve.rows, strict=True):
        _constraint(
            raw,
            cname,
            row,
            f'({link.expression}) {link.sign} sum({_weights_read(names, link)} * {link.values}, over={d})',
            where.exists,
        )
    if block.method in ('sos2', 'adjacency'):
        _section(raw, 'sos')[curve.name] = {'variable': names.weights, 'along': d, 'type': 2}


def _weights_read(names: Names, link: PiecewiseLink) -> str:
    """How one link reads the curve's weights: by name, or through the relation that refines its frame.

    The walk is an ``at``, so the weights stay on the curve's own frame and
    the model never names them — which is the whole reason the block emits
    the row rather than the file writing it.
    """
    if not link.walks:
        return names.weights
    return f'at({names.weights}, by={link.by}, over={_columns(link.over)}, into={_columns(link.into)})'


def _columns(written: str | list[str] | None) -> str:
    """One relation column as its bare name, several as the bracketed list the operators take."""
    assert written is not None
    return written if isinstance(written, str) else f'[{", ".join(written)}]'


def _segment_lines(raw: dict[str, object], curve: Curve) -> None:
    """The segment-line form: a row per segment, and the two domain rows.

    The chord sits at the later breakpoint, so the first has none and its
    ``where:`` and ``edge=0`` travel together — without the exclusion the
    vacated position is a spurious line through the origin; under a mask the
    first breakpoint is the curve's own. The row is multiplied through by the
    run rather than dividing, which keeps its sense only because the
    breakpoints are strictly monotone. The domain rows are ``linopy``'s
    ``_add_lp`` rows under its names, each sitting on the edge of the curve
    the mask marks, which is why the mask has to be one run. Every row here
    is written from the link expressions and the breakpoint values, none of
    which the block masks, so a ``where`` over the frame alone is conjoined
    onto each rather than inherited as the weight rows inherit it.
    """
    block, names, where = curve.block, curve.names, curve.mask
    x_link, y_link = block.curve
    d = block.along
    dims = (*curve.frame, d)
    run = f'({x_link.values} - {_neighbour(x_link.values, d, 1)})'
    rise = f'({y_link.values} - {_neighbour(y_link.values, d, 1)})'
    _constraint(
        raw,
        names.chord,
        dims,
        f'({y_link.expression}) * {run} {y_link.sign} '
        f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}',
        _all_of(where.frame, where.neighbours()),
    )
    for cname, sense, end in ((names.domain_lo, '>=', 'first'), (names.domain_hi, '<=', 'last')):
        _constraint(
            raw,
            cname,
            dims,
            f'({x_link.expression}) {sense} {x_link.values}',
            _all_of(where.frame, where.edge(end)),
        )


def expand_piecewise(schema: Spec) -> Spec:
    """*schema* with every ``piecewise:`` block written out — *schema* itself where it declares none.

    A ``method: adjacency`` block states its restriction as the set
    ``method: sos2`` states, and then that set is written out here too: the
    binaries are what the method *is*, so the model that comes back carries no
    set of its own (:func:`math_spec.sos.emit` is where they are spelled).

    Raises:
        PiecewiseExpansionError: A block :func:`check` refuses.
    """
    if not schema.piecewise:
        return schema

    raw = schema.model_dump()
    raw.setdefault('variables', {})
    raw.setdefault('constraints', {})
    for name, block in schema.piecewise.items():
        _write(raw, check(schema, name, block))
    raw['piecewise'].clear()
    for name, block in schema.piecewise.items():
        if block.method == 'adjacency':
            emit(raw, name)
    expanded = Spec.model_validate(raw)
    expanded._expanded_piecewise = dict(schema.piecewise)
    del expanded.resolved  # validation typed the rows before the records were here, and a block's own where is on one
    return expanded
