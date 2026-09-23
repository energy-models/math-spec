# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``piecewise:`` blocks into plain variables and constraints.

A block becomes ordinary affine declarations before anything reads the model,
under names prefixed with the block's own; what each method emits is tabled in
``docs/reference/language/piecewise.md``. Every rule a block is held to is
decided as the model loads, before its rows are written: the names it
references in :func:`~math_spec.validation.reference_errors`, its links and
its ``where:`` as lowering types them, and the fit of each link's row to its
expression, its values and the mask in :func:`declaration_of`. A refusal names
the link or key the file wrote rather than an emitted declaration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import math_spec.sos as sos
from math_spec._expression_parser import NAME
from math_spec.dimensions import dims_of
from math_spec.errors import DimensionError
from math_spec.model import AssumptionBlock, Curvature, PiecewiseBlock, PiecewiseLink, Spec
from math_spec.program import Link, PiecewiseDeclaration, PiecewiseMethod, carries_variable
from math_spec.resolution import resolve_expression_text

if TYPE_CHECKING:
    from collections.abc import Iterable

    from math_spec.program import Expression, Mask
    from math_spec.resolution import Namespace


# ---------------------------------------------------------------------------
# the mask, as each shape of row reads it
# ---------------------------------------------------------------------------


def _masks(where: str | None, along: str, *, ragged: bool) -> tuple[str | None, str | None, str | None]:
    """The block's ``where:`` as three shapes of row read it: ``(mask, frame, exists)``.

    A **ragged** where reads the breakpoint dim, so it says how far each curve
    runs: a row over the frame and that dim takes it as written (*mask*), and
    a row over the frame alone, which cannot read that dim, takes the count of
    breakpoints it admits (*exists*). A where over the frame alone says which
    curves exist: every row conjoins it as written (*frame*, and *exists*),
    and no row is ragged (*mask* is ``None``).
    """
    if ragged:
        return where, None, f'count({where}, over={along}) > 0'
    return None, where, where


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


def _operand(mask: str) -> str:
    """The mask as one operand of a connective: a bare name as it is, anything else parenthesised."""
    return mask if re.fullmatch(NAME, mask) else f'({mask})'


def _shifted(over: str, mask: str, offset: int) -> str:
    """*mask* read *offset* breakpoints back, false where that vacates."""
    return f'shift({mask}, along={over}, offset={offset})'


def _neighbours(over: str, mask: str | None) -> str:
    """Where a breakpoint and the one before it are both there: the rows a claim about a segment is true of."""
    if mask is None:
        return f'position({over}) > 0'
    return f'{_operand(mask)} AND {_shifted(over, mask, 1)}'


def _edge(over: str, mask: str | None, end: Literal['first', 'last']) -> str:
    """The first or last breakpoint of each curve: where the mask holds and does not one step outward.

    The vacated edge of a ``shift`` in a ``where`` is false, which is what
    makes the head and the tail of the axis their own edge.
    """
    if mask is None:
        return f'position({over}) == {0 if end == "first" else -1}'
    return f'{_operand(mask)} AND NOT {_shifted(over, mask, 1 if end == "first" else -1)}'


def _interior(over: str, mask: str | None) -> str:
    """Where a breakpoint has one on either side: the rows a claim about a bend is true of."""
    if mask is None:
        return f'position({over}) > 0 AND position({over}) != -1'
    return f'{_operand(mask)} AND {_shifted(over, mask, 1)} AND {_shifted(over, mask, -1)}'


# ---------------------------------------------------------------------------
# what a block assumes of its numbers
# ---------------------------------------------------------------------------


def _curvature_required(curve: PiecewiseDeclaration) -> Curvature | None:
    """The curvature *curve*'s method is only exact for, or ``None`` if any shape works.

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
    if curve.method not in ('convex', 'lp'):
        return None
    if (sign := curve.curve[1].sign) == '==':
        return 'either'
    return 'convex' if sign == '>=' else 'concave'


def assumptions_of(name: str, curve: PiecewiseDeclaration, where: str | None) -> dict[str, AssumptionBlock]:
    """What block *name* assumes of its numbers, by the name the document prints and a refusal quotes.

    Every curve assumes its breakpoints are there: a missing parameter row is
    not absence, it is a zero, so an undeclared breakpoint sits the curve on
    the origin rather than shortening it. A walked link's breakpoints are over
    its own rows, so each is asked of the rows that link reads the curve at,
    under a name of its own. A curve has an x-axis only where two links tie
    it, so the increasing condition — and the shape it is checked with —
    exist only there; ``lp`` alone needs a segment to state a line for; a
    ragged ``where:`` must mark one run.

    Each condition is a where string over the parameters the file declared,
    so *where* is the block's ``where:`` as the file wrote it — a typed mask
    has no text — and *curve* says how each row reads it. The expansion
    writes the conditions into ``assumptions:``, and a model that still
    declares the block derives the same text at load. Each is asked only
    where a curve runs, so the ``where:`` goes into every one of them: a
    model written out and read back holds the data to what the block did.
    """
    d = curve.along
    mask, frame, exists = _masks(where, d, ragged=curve.ragged)
    rewrite = (
        f'Bind the rows, or narrow where: {mask!r} to where the curve runs.'
        if mask is not None
        else 'Bind the rows, or declare where: to say how far the curve runs.'
    )
    assumed: dict[str, AssumptionBlock] = {}
    if values := [link.values for link in curve.links if not link.walks]:
        assumed[f'{name}_complete'] = AssumptionBlock(
            holds=' AND '.join(dict.fromkeys(values)),
            where=where,
            description=f"piecewise '{name}': every breakpoint the curve runs through needs a row in "
            f'{_quoted(values)} — a missing row is read as a zero rather than as a shorter curve, so it sits '
            f'the curve on the origin. {rewrite}',
        )
    for link in curve.links:
        if link.walks:
            assumed[f'{name}_{link.name}_complete'] = AssumptionBlock(
                holds=link.values,
                where=through(where, link) if link.reads else _all_of(link.by, where),
                description=f"piecewise '{name}' link '{link.name}': every breakpoint the curve runs through needs a "
                f"row in '{link.values}' at every row the link reads the curve at — a missing row is read as a zero "
                f'rather than as a shorter curve, so it sits that row on the origin. {rewrite}',
            )
    curvature = _curvature_required(curve)
    if curvature is not None:
        x, y = (link.values for link in curve.curve)
        assumed[f'{name}_increasing'] = AssumptionBlock(
            holds=f'{_back(x, d, 1)} < {x}',
            where=_all_of(frame, _neighbours(d, mask)),
            description=f"piecewise '{name}': method: {curve.method} requires strictly increasing breakpoints "
            f"in '{x}' along '{d}'",
        )
        assumed[f'{name}_curvature'] = _bends(name, curve, x, y, curvature, mask=mask, frame=frame, exists=exists)
    if curve.method == 'lp':
        assumed[f'{name}_breakpoints'] = AssumptionBlock(
            holds=f'count({mask or curve.curve[0].values}, over={d}) >= 2',
            where=exists,
            description=f"piecewise '{name}': method: lp needs at least two breakpoints per curve — the method "
            f'*is* its segment lines, so a curve with no segment states nothing and leaves the bounded link on '
            f'its own bound. Use method: adjacency, sos2 or convex, which pin it to the points it does have.',
        )
    if mask is not None:
        assumed[f'{name}_contiguous'] = AssumptionBlock(
            holds=f'count({_edge(d, mask, "first")}, over={d}) == 1',
            where=exists,
            description=f"piecewise '{name}': where: {mask!r} must mark a consecutive run of at least one "
            f'breakpoint per curve — {_GAP[curve.method]}.',
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


#: What a block may assume of its numbers, by suffix — the names
#: :func:`assumptions_of` writes, reserved whether or not the method states each.
_ASSUMED = ('complete', 'increasing', 'curvature', 'breakpoints', 'contiguous')


def through(text: str | None, link: Link) -> str | None:
    """*text* as *link*'s row reads it: through the link's relation where the row reads the where so, else as written."""
    if text is None or not link.reads:
        return text
    return f'at({text}, by={link.by}, over={_columns(link.over)}, into={_columns(link.into)})'


def _quoted(names: Iterable[str]) -> str:
    """Parameter names as a refusal lists them, in link order and without repeats."""
    return ', '.join(f"'{name}'" for name in dict.fromkeys(names))


def _back(parameter: str, over: str, offset: int) -> str:
    """*parameter* read *offset* breakpoints back, the vacated row filled with zero and excluded by the ``where``.

    ``edge=0`` is what the language admits over data, and the mask beside it
    is what keeps the invented zero from ever being read.
    """
    return f'shift({parameter}, along={over}, offset={offset}, edge=0)'


def _bends(
    name: str,
    curve: PiecewiseDeclaration,
    x: str,
    y: str,
    curvature: Curvature,
    *,
    mask: str | None,
    frame: str | None,
    exists: str | None,
) -> AssumptionBlock:
    """The curve bends the way *curvature* says, as a comparison of the two slopes at each breakpoint.

    The slopes are compared as a cross-product rather than as two quotients,
    so nothing divides by a run the increasing condition is what rules out.
    ``either`` is one bend in *some* direction, which is a claim about the
    whole axis rather than about a breakpoint: it counts the bends that go the
    wrong way and asks that one of the two directions has none.
    """
    d = curve.along
    rise, run = f'({y} - {_back(y, d, 1)})', f'({x} - {_back(x, d, 1)})'
    next_rise, next_run = f'({_back(y, d, -1)} - {y})', f'({_back(x, d, -1)} - {x})'
    bend = f'{rise} * {next_run} {{}} {next_rise} * {run}'
    interior = _interior(d, mask)
    shape = 'a single bend' if curvature == 'either' else f'a {curvature} curve'
    description = (
        f"piecewise '{name}': method: {curve.method} is exact only for {shape}, and '{y}' over '{x}' along "
        f"'{d}' is not one, so the answer is wrong rather than loose. Use method: adjacency "
        f'or sos2, which take a curve of any shape.'
    )
    if curvature == 'either':
        up, down = bend.format('>'), bend.format('<')
        return AssumptionBlock(
            holds=f'count({up} AND {interior}, over={d}) == 0 OR count({down} AND {interior}, over={d}) == 0',
            where=exists,
            description=description,
        )
    return AssumptionBlock(
        holds=bend.format('<=' if curvature == 'convex' else '>='),
        where=_all_of(frame, interior),
        description=description,
    )


# ---------------------------------------------------------------------------
# the names a block writes
# ---------------------------------------------------------------------------

#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


@dataclass(frozen=True)
class Emitted:
    """Every name one block's expansion may write, spelled once for the emitter and the collision check.

    Every name is reserved whichever method the block declares: which method
    writes which is the method's business, and a collision is the file's
    either way. ``set`` holds the names a method that states a set writes
    through :func:`math_spec.sos.emit`.
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
    def of(cls, name: str, curve: PiecewiseDeclaration) -> Emitted:
        """The names block *name* writes, a link's row named after the link."""
        return cls(
            name,
            f'{name}_lam',
            f'{name}_convexity',
            sos.Emitted.of(name, 2),
            f'{name}_chord',
            f'{name}_domain_lo',
            f'{name}_domain_hi',
            tuple(f'{name}_{link.name}' for link in curve.links),
            (
                *(f'{name}_{what}' for what in _ASSUMED),
                *(f'{name}_{link.name}_complete' for link in curve.links if link.walks),
            ),
        )

    @property
    def ungated(self) -> str:
        """The second gate row, where the gate variable does not exist."""
        return self.convexity + _UNGATED

    @property
    def rows(self) -> tuple[str, ...]:
        """Every constraint the block writes for itself, its link rows aside."""
        return (
            self.convexity,
            self.ungated,
            self.set.pick,
            self.set.link,
            self.set.below,
            self.chord,
            self.domain_lo,
            self.domain_hi,
        )

    @property
    def reused(self) -> tuple[str, ...]:
        """Each link row whose name the block's own rows or variables already take."""
        own = {self.lam, self.set.seg, *self.rows}
        return tuple(row for row in self.links if row in own)

    @property
    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each name by the kind of declaration it would collide with."""
        return (
            ('variable', (self.lam, self.set.seg)),
            ('constraint', (*self.rows, *self.links)),
            ('sos', (self.name,)),
            ('assumption', self.assumptions),
        )


# ---------------------------------------------------------------------------
# the block as lowering types it
# ---------------------------------------------------------------------------


def resolve_links(name: str, pw: PiecewiseBlock, ns: Namespace, errors: list[str]) -> tuple[Expression, ...] | None:
    """Block *name*'s link expressions typed, in link order, or ``None`` once one failed, its refusal appended.

    A link is read affinely, so it is held to degree 1 where it is read.
    """
    links = [
        resolve_expression_text(link.expression, ns, f"piecewise '{name}' link '{key}'", errors, ceiling=1)
        for key, link in pw.links.items()
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
    i, key = next((i, key) for i, (key, link) in enumerate(pw.links.items()) if link is x)
    if carries_variable(links[i]):
        return None
    return (
        f"piecewise '{name}' link '{key}': method: lp bounds the curve's domain by rows comparing this link's "
        f'expression against its first and last breakpoint, and {x.expression!r} carries no variable, so those rows '
        f'decide nothing. Name a variable in the link, or use method: convex, sos2 or adjacency, whose weights pin '
        f'the domain themselves.'
    )


def declaration_of(
    schema: Spec, name: str, pw: PiecewiseBlock, links: tuple[Expression, ...], where: Mask | None
) -> PiecewiseDeclaration:
    """Block *name* as the program carries it, with *links* and *where* typed, every fit rule decided.

    Each link's row is ``dims:``, or its refinement through the link's
    relation; its expression carries exactly that row, its values parameter
    varies along it and the breakpoint dim and nothing else, and the
    ``where:`` tests ``dims:`` and the breakpoint dim alone. A walked row
    reads the where through its relation when the mask carries every dim the
    walk reads the curve at. Decided here, on the link the file wrote, rather
    than on the emitted declarations, whose refusal would name ``<block>_lam``
    — a variable the author never wrote.

    Raises:
        DimensionError: A link that does not fit its row, a where outside
            ``dims:``, or a mask carrying part of what a walk reads through.
    """
    ctx = f"piecewise '{name}'"
    rows = {key: _row(schema, pw, link) for key, link in pw.links.items()}
    for node, (key, row) in zip(links, rows.items(), strict=True):
        _link_fits(ctx, key, pw, dims_of(node, schema, f"{ctx} link '{key}'"), row)
    for (key, link), row in zip(pw.links.items(), rows.values(), strict=True):
        _values_fit(schema, ctx, key, pw, link, row)
    _where_fits(ctx, pw, where)
    carried = (where.dims if where is not None else frozenset()) - {pw.along}
    typed = tuple(
        Link(
            key,
            node,
            link.values,
            rows[key],
            link.sign,
            link.by,
            _named(link.over),
            _named(link.into),
            _reads(schema, ctx, key, pw, link, carried),
        )
        for node, (key, link) in zip(links, pw.links.items(), strict=True)
    )
    return PiecewiseDeclaration(
        pw.along, typed, pw.method, tuple(pw.dims), where, activity=pw.activity, description=pw.description
    )


def _row(schema: Spec, block: PiecewiseBlock, link: PiecewiseLink) -> tuple[str, ...]:
    """The dims one link's row is built over: ``dims:``, or its refinement through the link's relation.

    The produced dims stand where the consumed ones did, so a walked row
    reads in the shape of the curve it ties rather than in relation order.
    """
    if not link.walks:
        return tuple(block.dims)
    consumed, produced = _walk(schema, link)
    refined: list[str] = []
    for d in block.dims:
        if d in consumed:
            refined.extend(p for p in schema.dimensions if p in produced and p not in refined)
        elif d not in refined:
            refined.append(d)
    return tuple(refined)


def _reads(
    schema: Spec, ctx: str, key: str, block: PiecewiseBlock, link: PiecewiseLink, carried: frozenset[str]
) -> bool:
    """Whether a walked link's row reads the block's ``where:`` through its relation; ``False`` for one that does not walk.

    A walked row is over the dims the walk produces, where a mask over the
    ones it consumes cannot be read as written. Read through the relation it
    can, as ``at`` reads it, when the mask carries every dim the walk consumes
    or joins on (*carried* is what the mask carries, the breakpoint dim
    aside). A mask carrying none of them is over dims the row keeps, and
    reads as written.

    Raises:
        DimensionError: The mask carries some of the dims the walk reads
            through and not the rest.
    """
    if not link.walks:
        return False
    assert link.by is not None
    consumed, _ = _walk(schema, link)
    relation = schema.relations[link.by]
    roles = dict(relation.pairs)
    written = {*_named(link.over), *_named(link.into)}
    needed = consumed | {roles[c] for c in relation.key_roles if c not in written}
    if (partial := sorted(needed - carried)) and needed & carried:
        raise DimensionError(
            f"{ctx} link '{key}': where {block.where!r} carries {sorted(needed & carried)} and not {partial}, and "
            f"the link reads the curve through '{link.by}' at all of {sorted(needed)}. Carry all of them in the "
            f'where, so the row reads it through the relation, or none, so the row reads it as written.'
        )
    return bool(needed & carried)


def _walk(schema: Spec, link: PiecewiseLink) -> tuple[frozenset[str], frozenset[str]]:
    """The dims one walked link consumes and produces, read off the relation it names."""
    assert link.by is not None
    roles = dict(schema.relations[link.by].pairs)
    consumed, produced = (frozenset(roles[c] for c in _named(written)) for written in (link.over, link.into))
    return consumed, produced


def _named(written: str | list[str] | None) -> tuple[str, ...]:
    """The relation columns a walk names on one side, as written: none, one bare, or a list."""
    if written is None:
        return ()
    return (written,) if isinstance(written, str) else tuple(written)


def _columns(columns: tuple[str, ...]) -> str:
    """One relation column as its bare name, several as the bracketed list the operators take."""
    return columns[0] if len(columns) == 1 else f'[{", ".join(columns)}]'


def _link_fits(ctx: str, key: str, block: PiecewiseBlock, found: frozenset[str], own: tuple[str, ...]) -> None:
    """A link expression carries exactly its row's frame — the rule a constraint's own ``dims:`` holds to.

    Both directions are refused because both broadcast one side of the row.
    A stray dim multiplies the rows the link builds; a missing one repeats
    the same row across it, which pins the expression to one operating point
    along a dimension the curve varies over. Neither is sayable another way,
    so neither is guessed.
    """
    if block.along in found:
        raise DimensionError(f"{ctx}: link '{key}' expression already carries the breakpoint dim '{block.along}'")
    if stray := sorted(found - set(own)):
        raise DimensionError(
            f"{ctx}: link '{key}' expression carries {stray}, which its row {list(own)} does not — "
            f'every stray dim multiplies the rows the link builds. Add it to dims:, sum it out, or read '
            f'it through a relation with by, over and into.'
        )
    if missing := sorted(set(own) - found):
        raise DimensionError(
            f"{ctx}: link '{key}' expression does not carry {missing}, which its row {list(own)} does — "
            f'the same row would repeat across {missing}, pinning the expression to one operating point '
            f'along {"it" if len(missing) == 1 else "them"}. Drop {missing} from dims:, or vary the '
            f'expression along {missing}.'
        )


def _values_fit(
    schema: Spec, ctx: str, key: str, block: PiecewiseBlock, link: PiecewiseLink, own: tuple[str, ...]
) -> None:
    """A values parameter varies along its own link's row and the breakpoint dim, and nothing else.

    Its own link's, because a walked link's curve is read per fine
    coordinate: ``bp_power`` is per flow where the block's frame is per
    converter, and comparing it against the frame would refuse it.
    """
    if stray := [d for d in schema.parameters[link.values].dims if d != block.along and d not in own]:
        raise DimensionError(
            f"{ctx}: link '{key}' values parameter '{link.values}' carries {stray}, which its row "
            f'{list(own)} does not — the link reads one curve per coordinate of {list(own)}, so a curve '
            f"varying along {stray} has nothing to vary against. Drop it from '{link.values}', or add it to "
            f'dims:.'
        )


def _where_fits(ctx: str, block: PiecewiseBlock, where: Mask | None) -> None:
    """A block's ``where:`` tests ``dims:`` and the breakpoint dim, and nothing else.

    A walked link's values parameter carries the link's own row, so a where
    naming it is refused here too: raggedness is the curve's.
    """
    dims = where.dims if where is not None else frozenset()
    if stray := sorted(dims - set(block.dims) - {block.along}):
        raise DimensionError(
            f'{ctx}: where {block.where!r} tests {stray}, which dims {block.dims} does not carry — a mask says '
            f'which of the curves the block builds exist, and cannot add coordinates. Add {stray} to dims:, '
            f'or drop it from the where.'
        )


# ---------------------------------------------------------------------------
# the rows a block writes
# ---------------------------------------------------------------------------


class _Block:
    """One ``piecewise:`` block, written out into the raw model.

    Every rule the block is held to was decided as the model loaded, so what
    is left is writing: the link text the file wrote, on the row the program
    says each link builds, under the where each row reads.
    """

    def __init__(
        self, schema: Spec, raw: dict[str, object], name: str, pw: PiecewiseBlock, curve: PiecewiseDeclaration
    ) -> None:
        self.schema = schema
        self.raw = raw
        self.name = name
        #: The block as the file wrote it, for the link text the rows repeat and the where they carry.
        self.pw = pw
        #: The block as the program carries it, for each link's row, how it reads the where, and the names it writes.
        self.curve = curve
        self.emitted = Emitted.of(name, curve)
        self.frame = list(curve.frame)
        #: The where as a ragged row, a frame row, and a row over the frame alone read it.
        self.mask, self.frame_mask, self.exists = _masks(pw.where, pw.along, ragged=curve.ragged)

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
        for name, assumed in assumptions_of(self.name, self.curve, self.pw.where).items():
            assumptions[name] = assumed.model_dump()

    # -- emitters ----------------------------------------------------------

    def _constraint(self, name: str, dims: Iterable[str], expression: str, where: str | None = None) -> None:
        sos.section(self.raw, 'constraints')[name] = {
            'dims': list(dims),
            **({'where': where} if where else {}),
            'expression': expression,
        }

    def _weights(self) -> None:
        """The convex-combination form: weights, their convexity, a row per link, and the method's restriction."""
        pw, emitted, d = self.pw, self.emitted, self.pw.along
        sos.section(self.raw, 'variables')[emitted.lam] = {
            'dims': [*self.frame, d],
            **({'where': pw.where} if pw.where else {}),
            'bounds': {'lower': 0.0, 'upper': 1.0},
            'description': 'convex-combination weight on a breakpoint',
        }
        for suffix, gate, rhs in self._gate_rows():
            self._constraint(
                emitted.convexity + suffix,
                self.frame,
                f'sum({emitted.lam}, over={d}) == {rhs}',
                _all_of(self.exists, gate),
            )
        for cname, written, link in zip(emitted.links, pw.links.values(), self.curve.links, strict=True):
            self._constraint(
                cname,
                link.dims,
                f'({written.expression}) {link.sign} sum({self._weights_read(link)} * {link.values}, over={d})',
                through(self.exists, link),
            )
        if pw.method in ('sos2', 'adjacency'):
            sos.section(self.raw, 'sos')[self.name] = {'variable': emitted.lam, 'along': d, 'type': 2}

    def _weights_read(self, link: Link) -> str:
        """How one link reads the curve's weights: by name, or through the relation that refines its frame.

        The walk is an ``at``, so the weights stay on the curve's own frame and
        the model never names them — which is the whole reason the block emits
        the row rather than the file writing it.
        """
        if not link.walks:
            return self.emitted.lam
        return f'at({self.emitted.lam}, by={link.by}, over={_columns(link.over)}, into={_columns(link.into)})'

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
        first breakpoint is the curve's own. The row is multiplied through by the
        run rather than dividing, which keeps its sense only because the
        breakpoints are strictly monotone. The domain rows are ``linopy``'s
        ``_add_lp`` rows under its names, each sitting on the edge of the curve
        the mask marks, which is why the mask has to be one run. Every row here
        is written from the link expressions and the breakpoint values, none of
        which the block masks, so a ``where`` over the frame alone is conjoined
        onto each rather than inherited as the weight rows inherit it.
        """
        pw, emitted, d = self.pw, self.emitted, self.pw.along
        x_link, y_link = pw.curve
        mask, frame = self.mask, self.frame_mask
        dims = (*self.frame, d)
        run = f'({x_link.values} - {_back(x_link.values, d, 1)})'
        rise = f'({y_link.values} - {_back(y_link.values, d, 1)})'
        self._constraint(
            emitted.chord,
            dims,
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}',
            _all_of(frame, _neighbours(d, mask)),
        )
        for cname, sense, end in ((emitted.domain_lo, '>=', 'first'), (emitted.domain_hi, '<=', 'last')):
            self._constraint(
                cname, dims, f'({x_link.expression}) {sense} {x_link.values}', _all_of(frame, _edge(d, mask, end))
            )


def expand_piecewise(schema: Spec) -> Spec:
    """*schema* with every ``piecewise:`` block written out — *schema* itself where it declares none.

    A ``method: adjacency`` block states its restriction as the set
    ``method: sos2`` states, and then that set is written out here too: the
    binaries are what the method *is*, so the model that comes back carries no
    set of its own (:func:`math_spec.sos.emit` is where they are spelled).
    Each block's rows and names are read off the program *schema* lowered to.
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
