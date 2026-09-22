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

from typing import TYPE_CHECKING, Literal, NamedTuple

from math_spec._expression_parser import ComparisonNode
from math_spec.degree import check_expression
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError, PiecewiseExpansionError
from math_spec.expansion import parse_and_expand
from math_spec.model import Curvature, PiecewiseBlock, PiecewiseLink, PiecewiseMethod, Spec, undeclared_dimension
from math_spec.program import Mask, PiecewiseDeclaration
from math_spec.resolution import Namespace, mask_of, resolve_expression, resolve_where_text
from math_spec.sos import Emitted, emit

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def _nominated(pw: PiecewiseBlock) -> str | None:
    """The block's own values parameter ``points:`` names, so the mask is derived from it — or ``None``."""
    return pw.points if pw.points in {link.values for link in pw.links} else None


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


def _columns(written: str | list[str] | None) -> str:
    """One relation column as its bare name, several as the bracketed list the operators take."""
    assert written is not None
    return written if isinstance(written, str) else f'[{", ".join(written)}]'


#: The suffix on the second gate row, where the gate variable does not exist.
_UNGATED = '_ungated'


def _curvature_required(pw: PiecewiseBlock) -> Curvature | None:
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


def declaration_of(pw: PiecewiseBlock, where: Mask | None = None) -> PiecewiseDeclaration:
    """The curve of one expanded block, as a program carries it.

    Args:
        pw: The block as written.
        where: The block's own ``where:``, lowered — which coordinates have a
            curve, and so which ones what the block assumes is asked at.
    """
    return PiecewiseDeclaration(
        along=pw.along,
        method=pw.method,
        breakpoints=tuple(link.values for link in pw.links),
        where=where,
    )


class Assumed(NamedTuple):
    """One condition a method puts on the numbers, as the language writes it.

    ``holds`` and ``where`` are where strings, resolved like any the file
    wrote. ``description`` is the sentence a refusal quotes, which names the
    method and the rewrite that takes a curve of any shape.
    """

    holds: str
    where: str | None
    description: str


def assumptions_of(block: str, pw: PiecewiseBlock) -> dict[str, Assumed]:
    """What *block* assumes of its numbers, by the name the document prints and a refusal quotes.

    Every curve assumes its breakpoints are there: a missing parameter row is
    not absence, it is a zero, so an undeclared breakpoint sits the curve on
    the origin rather than shortening it. A curve has an x-axis only where two
    links tie it, so the increasing condition — and the shape it is checked
    with — exist only there; ``lp`` alone needs a segment to state a line for;
    a mask must be one run.

    Read off the block rather than off an expansion, so a model states what it
    assumes whether or not its curves have been written out. Each condition is
    a where string over the parameters the file declared: the expansion writes
    them into ``assumptions:``, and a model that still declares the block
    derives the same text at load.
    """
    d, mask = pw.along, pw.points
    assumed: dict[str, Assumed] = {}
    assumed[f'{block}_complete'] = Assumed(
        ' AND '.join(dict.fromkeys(link.values for link in pw.links)),
        mask,
        f"piecewise '{block}': every breakpoint the curve runs through needs a row in "
        f'{_quoted(link.values for link in pw.links)} — a missing row is read as a zero rather than as a '
        f'shorter curve, so it sits the curve on the origin. '
        + (
            f"Bind the rows, or narrow points: '{mask}' to where the curve runs."
            if mask is not None
            else 'Bind the rows, or declare points: to say how far the curve runs.'
        ),
    )
    curvature = _curvature_required(pw)
    if curvature is not None:
        x, y = (link.values for link in pw.curve)
        assumed[f'{block}_increasing'] = Assumed(
            f'{_back(x, d, 1)} < {x}',
            _neighbours(d, mask),
            f"piecewise '{block}': method: {pw.method} requires strictly increasing breakpoints in '{x}' along '{d}'",
        )
        assumed[f'{block}_curvature'] = _bends(block, pw, x, y, curvature)
    if pw.method == 'lp':
        assumed[f'{block}_breakpoints'] = Assumed(
            f'count({mask or pw.curve[0].values}, over={d}) >= 2',
            None,
            f"piecewise '{block}': method: lp needs at least two breakpoints per curve — the method *is* its "
            f'segment lines, so a curve with no segment states nothing and leaves the bounded link on its own '
            f'bound. Use method: adjacency, sos2 or convex, which pin it to the points it does have.',
        )
    if mask is not None:
        assumed[f'{block}_contiguous'] = Assumed(
            f'count({_edge(d, mask, "first")}, over={d}) == 1',
            None,
            f"piecewise '{block}': points: '{mask}' must mark a consecutive run of at least one breakpoint per "
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


def _bends(block: str, pw: PiecewiseBlock, x: str, y: str, curvature: Curvature) -> Assumed:
    """The curve bends the way *curvature* says, as a comparison of the two slopes at each breakpoint.

    The slopes are compared as a cross-product rather than as two quotients,
    so nothing divides by a run the increasing condition is what rules out.
    ``either`` is one bend in *some* direction, which is a claim about the
    whole axis rather than about a breakpoint: it counts the bends that go the
    wrong way and asks that one of the two directions has none.
    """
    d, mask = pw.along, pw.points
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
        return Assumed(
            f'count({up} AND {interior}, over={d}) == 0 OR count({down} AND {interior}, over={d}) == 0',
            None,
            description,
        )
    return Assumed(bend.format('<=' if curvature == 'convex' else '>='), interior, description)


class _Block:
    """One ``piecewise:`` block being expanded into the raw model it writes.

    Every name the expansion may write is spelled once here, so the emitters
    and the collision check read the same table — ``set`` is the one a method
    that states a set writes through :func:`math_spec.sos.emit`. ``mask`` is
    the parameter masking the weights, or ``None`` for a whole curve: the
    ``bool`` the file named, or one of the block's own values parameters,
    which as a bare name in a ``where`` is true wherever it has a row.
    The block's own ``where`` is a second mask, over the frame rather than
    the breakpoint dim, and every row the expansion writes holds under both.

    Raises:
        PiecewiseExpansionError: A block naming something that does not exist,
            or emitting a name the file already declares.
    """

    def __init__(self, schema: Spec, raw: dict[str, object], name: str, pw: PiecewiseBlock) -> None:
        self.schema = schema
        self.raw = raw
        self.name = name
        self.pw = pw
        self.lam = f'{name}_lam'
        self.convexity = f'{name}_convexity'
        self.set = Emitted.of(name, 2)
        self.chord = f'{name}_chord'
        self.domain_lo = f'{name}_domain_lo'
        self.domain_hi = f'{name}_domain_hi'
        self.links = tuple(f'{name}_link{i}' for i in range(len(pw.links)))
        self.mask = pw.points
        self.ns = Namespace(schema)
        self._expression_dims: dict[int, frozenset[str]] = {}
        self.context = f"piecewise '{name}'"
        self.frame = self._validated_frame()

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
        section = self._section('assumptions')
        for name, assumed in assumptions_of(self.name, self.pw).items():
            entry: dict[str, object] = {'holds': assumed.holds, 'description': assumed.description}
            if assumed.where is not None:
                entry['where'] = assumed.where
            section[name] = entry

    # -- emitters ----------------------------------------------------------

    def _section(self, name: str) -> dict[str, object]:
        """The *name* section of the raw model, created empty where the file declares none."""
        section = self.raw.setdefault(name, {})
        assert isinstance(section, dict), f'{name}: is a mapping in a validated model'
        return section

    def _weight(self, name: str, **fields: object) -> None:
        """A variable over the frame and the breakpoint dim, masked as the block is."""
        where = _all_of(self.pw.where, self.mask)
        self._section('variables')[name] = {
            'dims': [*self.frame, self.pw.along],
            **({'where': where} if where else {}),
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
        d = self.pw.along
        self._weight(
            self.lam,
            bounds={'lower': 0.0, 'upper': 1.0},
            description='convex-combination weight on a breakpoint',
        )
        gated = self._gate_rows()
        for suffix, where, rhs in gated:
            self._constraint(
                self.convexity + suffix,
                list(self.frame),
                f'sum({self.lam}, over={d}) == {rhs}',
                _all_of(self.pw.where, where),
            )
        for i, (cname, link) in enumerate(zip(self.links, self.pw.links, strict=True)):
            self._constraint(
                cname,
                self._link_frame(i, link, list(self.frame)),
                f'({link.expression}) {link.sign} sum({self._weights_read(link)} * {link.values}, over={d})',
                self.pw.where,
            )
        if self.pw.method in ('sos2', 'adjacency'):
            self._section('sos')[self.name] = {'variable': self.lam, 'along': d, 'type': 2}

    def _weights_read(self, link: PiecewiseLink) -> str:
        """How one link reads the curve's weights: by name, or through the relation that refines its frame.

        The walk is an ``at``, so the weights stay on the curve's own frame and
        the model never names them — which is the whole reason the block emits
        the row rather than the file writing it.
        """
        if not link.walks:
            return self.lam
        return f'at({self.lam}, by={link.by}, over={_columns(link.over)}, into={_columns(link.into)})'

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
        which the block masks, so the block's own ``where`` is conjoined onto
        each rather than inherited as the weight rows inherit it.
        """
        x_link, y_link = self.pw.curve
        d = self.pw.along
        run = f'({x_link.values} - shift({x_link.values}, along={d}, offset=1, edge=0))'
        rise = f'({y_link.values} - shift({y_link.values}, along={d}, offset=1, edge=0))'
        self._constraint(
            self.chord,
            [*self.frame, d],
            f'({y_link.expression}) * {run} {y_link.sign} '
            f'{rise} * (({x_link.expression}) - {x_link.values}) + {y_link.values} * {run}',
            _all_of(self.pw.where, _neighbours(d, self.mask)),
        )
        edges = ((self.domain_lo, '>=', 'first'), (self.domain_hi, '<=', 'last'))
        for cname, sense, end in edges:
            self._constraint(
                cname,
                [*self.frame, d],
                f'({x_link.expression}) {sense} {x_link.values}',
                _all_of(self.pw.where, _edge(d, self.mask, end)),
            )

    # -- checks ------------------------------------------------------------

    def _emitted_by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Every name this block may write, by the kind of declaration each would collide with.

        The set a block states writes names of its own, and they are reserved
        whichever method the block declares: which of the two write them is the
        method's business, and a collision is the file's either way.
        """
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
            ('assumption', tuple(assumptions_of(self.name, self.pw))),
        )

    def _validated_frame(self) -> tuple[str, ...]:
        """Check every name the block writes and settle its frame, declared by ``dims:`` or read off the links.

        A values parameter is checked against the frame in a second pass, since
        the last link's expression widens the frame as readily as the first; left
        to the emitted declarations the refusal would name ``<block>_link0``, a
        constraint the author never wrote.
        """
        if self.pw.along not in self.schema.dimensions:
            raise PiecewiseExpansionError(undeclared_dimension('piecewise', self.name, self.pw.along))
        for i, link in enumerate(self.pw.links):
            self._check_values(i, link)
        frame: list[str] = []
        if self.pw.dims is None:
            self._widen(frame, self._link_dims())
        else:
            frame.extend(self._declared_frame())
        self._widen(frame, self._activity_dims())
        self._links_fit(frame)
        self._values_fit(frame)
        self._points_fit(frame)
        self._where_fits(frame)
        self._nothing_collides()
        return tuple(frame)

    def _declared_frame(self) -> list[str]:
        """The frame ``dims:`` states, in the order the file wrote it.

        Declared order rather than declaration order: ``dims:`` is the same key
        a variable and a constraint carry, and there the file's order is the
        emitted one.
        """
        ctx, dims = self.context, self.pw.dims
        assert dims is not None
        for d in dims:
            if d not in self.schema.dimensions:
                raise PiecewiseExpansionError(undeclared_dimension('piecewise', self.name, d))
            if d == self.pw.along:
                raise PiecewiseExpansionError(
                    f"{ctx}: dims carries '{self.pw.along}', the breakpoint dim. The frame is what the block "
                    f'builds one curve per, and every curve runs along the breakpoints — drop it from dims:.'
                )
        if len(set(dims)) != len(dims):
            raise PiecewiseExpansionError(f'{ctx}: dims repeats a dimension: {dims}')
        return list(dims)

    def _walk(self, i: int, link: PiecewiseLink) -> tuple[frozenset[str], frozenset[str]]:
        """The dims one refined link's walk consumes and produces, its relation and columns checked to exist."""
        ctx = f'{self.context} link {i}'
        assert link.by is not None and link.over is not None and link.into is not None
        if link.by not in self.schema.relations:
            raise PiecewiseExpansionError(
                f"{ctx}: by references undeclared relation '{link.by}'. A refined link reads the curve's "
                f'weights through a declared relation — declare it, or drop by, over and into.'
            )
        roles = dict(self.schema.relations[link.by].pairs)
        sides: list[frozenset[str]] = []
        for side, written in (('over', link.over), ('into', link.into)):
            named = [written] if isinstance(written, str) else list(written)
            if stray := [c for c in named if c not in roles]:
                raise PiecewiseExpansionError(
                    f"{ctx}: {side} names {stray}, which relation '{link.by}' has no column for "
                    f'(it has {sorted(roles)})'
                )
            sides.append(frozenset(roles[c] for c in named))
        consumed, produced = sides
        if shared := sorted(consumed & produced):
            raise PiecewiseExpansionError(
                f'{ctx}: over and into both reach {shared}, so the walk consumes and produces one dimension. '
                f'Name different columns on each side.'
            )
        return consumed, produced

    def _link_frame(self, i: int, link: PiecewiseLink, frame: list[str]) -> list[str]:
        """The dims one link's row is built over: the curve's frame, or its refinement through the link's relation.

        The produced dims stand where the consumed ones did, so a refined row
        reads in the shape of the curve it ties rather than in relation order.
        """
        if not link.refined:
            return list(frame)
        consumed, produced = self._walk(i, link) if link.walks else (frozenset(), self._spans(i, link, frame))
        if missing := sorted(consumed - set(frame)):
            raise PiecewiseExpansionError(
                f"{self.context} link {i}: over reaches {missing}, which the curve's dims {frame} do not "
                f"carry. A walk consumes the frame's own dimension — name one of {frame}, or declare it in dims:."
            )
        refined: list[str] = []
        for d in frame:
            if d in consumed:
                refined.extend(p for p in self.schema.dimensions if p in produced and p not in refined)
            elif d not in refined:
                refined.append(d)
        refined.extend(p for p in self.schema.dimensions if p in produced and p not in refined)
        return refined

    def _spans(self, i: int, link: PiecewiseLink, frame: list[str]) -> frozenset[str]:
        """The dims a link spans without walking a relation — declared dimensions the curve does not already carry."""
        ctx = f'{self.context} link {i}'
        assert link.into is not None
        named = [link.into] if isinstance(link.into, str) else list(link.into)
        for d in named:
            if d not in self.schema.dimensions:
                raise PiecewiseExpansionError(undeclared_dimension('piecewise', self.name, d))
            if d == self.pw.along:
                raise PiecewiseExpansionError(
                    f"{ctx}: into names '{d}', the breakpoint dim. A link spans the dimension its ties are "
                    f'indexed by, and every tie runs along the breakpoints.'
                )
            if d in frame:
                raise PiecewiseExpansionError(
                    f"{ctx}: into names '{d}', which the curve's dims already carries. The curve builds one "
                    f"per coordinate of it, so it cannot also index this link's ties — drop it from dims:, "
                    f'or split along a dimension of its own.'
                )
        return frozenset(named)

    def _links_fit(self, frame: list[str]) -> None:
        """Every link expression carries exactly its row's frame — the rule a constraint's own ``dims:`` holds to.

        Both directions are refused because both broadcast one side of the row.
        A stray dim multiplies the rows the link builds; a missing one repeats
        the same row across it, which pins the expression to one operating point
        along a dimension the curve varies over. Neither is sayable another way,
        so neither is guessed.
        """
        for i, link in enumerate(self.pw.links):
            own = self._link_frame(i, link, frame)
            found = self._dims_of(i, link)
            if self.pw.along in found:
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} expression already carries the breakpoint dim '{self.pw.along}'"
                )
            if stray := sorted(found - set(own)):
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} expression carries {stray}, which its row's frame {own} does "
                    f'not — every stray dim multiplies the rows the link builds. Add it to dims:, sum it out, '
                    f'or read it through a relation with by, over and into.'
                )
            if missing := sorted(set(own) - found):
                raise PiecewiseExpansionError(f'{self.context}: {self._too_coarse(i, missing, own)}')

    def _too_coarse(self, i: int, missing: list[str], own: list[str]) -> str:
        """Why a link varying less than its row is refused, and the rewrite — which differs by where the frame came from."""
        repeated = (
            f"link {i} expression does not carry {missing}, which its row's frame {own} does — the same "
            f'row would repeat across {missing}, pinning the expression to one operating point along '
            f'{"it" if len(missing) == 1 else "them"}. '
        )
        if self.pw.dims is None:
            return repeated + (
                f"The frame is the union of the link expressions' dims, so another link carries {missing}. "
                f'Declare dims: to say which curve the block builds, or vary this expression along {missing}.'
            )
        return repeated + f'Drop {missing} from dims:, or vary the expression along {missing}.'

    def _widen(self, frame: list[str], dims: Iterable[tuple[str, frozenset[str]]]) -> None:
        """Add each labelled dim set to *frame* in declaration order, refusing the breakpoint dim.

        Declaration order, because iterating a set would vary the emitted
        ``dims`` — and every column index behind it — per process.
        """
        for what, found in dims:
            for d in (d for d in self.schema.dimensions if d in found):
                if d == self.pw.along:
                    raise PiecewiseExpansionError(
                        f"{self.context}: {what} already carries the breakpoint dim '{self.pw.along}'"
                    )
                if d not in frame:
                    frame.append(d)

    def _check_values(self, i: int, link: PiecewiseLink) -> None:
        """A link's values parameter exists and runs along the breakpoint dim."""
        values = link.values
        if values not in self.schema.parameters:
            raise PiecewiseExpansionError(f"{self.context}: link {i} values references undeclared parameter '{values}'")
        if self.pw.along not in self.schema.parameters[values].dims:
            raise PiecewiseExpansionError(
                f"{self.context}: link {i} values parameter '{values}' must carry dim "
                f"'{self.pw.along}' (has {self.schema.parameters[values].dims})"
            )

    def _link_dims(self) -> Iterator[tuple[str, frozenset[str]]]:
        """Each link expression's dims — the inferred frame is their union."""
        for i, link in enumerate(self.pw.links):
            yield f'link {i} expression', self._dims_of(i, link)

    def _dims_of(self, i: int, link: PiecewiseLink) -> frozenset[str]:
        """One link expression's dims, parsed once — the inferred frame reads them before the fit does."""
        if i not in self._expression_dims:
            self._expression_dims[i] = self._expr_dims(link.expression, f'{self.context} link {i}')
        return self._expression_dims[i]

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
        """A values parameter varies along its own link's frame and the breakpoint dim, and nothing else.

        Its own link's, because a refined link's curve is read per fine
        coordinate: ``bp_power`` is per flow where the block's frame is per
        converter, and comparing it against the frame would refuse it.
        """
        for i, link in enumerate(self.pw.links):
            own = self._link_frame(i, link, frame)
            if stray := [d for d in self.schema.parameters[link.values].dims if d != self.pw.along and d not in own]:
                raise PiecewiseExpansionError(
                    f"{self.context}: link {i} values parameter '{link.values}' carries {stray}, which its "
                    f"row's frame {own} does not — the link builds one curve per coordinate of {own}, so a "
                    f'curve varying along {stray} has nothing to vary against. Declare a link expression over '
                    f"it, or drop it from '{link.values}'."
                )

    def _points_fit(self, frame: list[str]) -> None:
        """A ``points:`` naming a parameter of its own is a bool mask along the breakpoint dim, inside the frame."""
        pw, ctx = self.pw, self.context
        if pw.points is None:
            return
        for i, link in enumerate(pw.links):
            if link.values == pw.points and link.refined:
                raise PiecewiseExpansionError(
                    f"{ctx}: points names '{pw.points}', which is link {i}'s values parameter and sits on that "
                    f"link's own frame rather than the curve's. Raggedness is a property of the curve — name "
                    f'the values parameter of a link that reads no relation, or declare a bool mask over '
                    f'{list(self.pw.dims or ())} and the breakpoint dim.'
                )
        if _nominated(pw) is not None:
            return
        if pw.points not in self.schema.parameters:
            raise PiecewiseExpansionError(f"{ctx}: points references undeclared parameter '{pw.points}'")
        if (dtype := self.schema.parameters[pw.points].dtype) != 'bool':
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' is {dtype}, and a mask is a bool parameter — one "
                f'saying, per breakpoint, whether the curve reaches it. Declare it dtype: bool.'
            )
        mask = self.schema.parameters[pw.points].dims
        if pw.along not in mask:
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' must carry dim '{pw.along}' — "
                f'it says how far each curve runs along it (has {mask})'
            )
        if stray := [d for d in mask if d != pw.along and d not in frame]:
            raise PiecewiseExpansionError(
                f"{ctx}: points parameter '{pw.points}' carries {stray}, which the links do not — "
                f"a mask says which of the block's own coordinates exist, and cannot add coordinates"
            )

    def _where_fits(self, frame: list[str]) -> None:
        """A block's ``where:`` tests the frame it builds curves over, and never the breakpoint dim.

        Read here rather than left to the emitted declarations, whose refusal
        would name ``<block>_lam`` — a variable the author never wrote.
        """
        pw, ctx = self.pw, self.context
        if pw.where is None:
            return
        errors: list[str] = []
        resolved = resolve_where_text(pw.where, self.ns, f'{ctx} where', errors)
        if errors:
            raise PiecewiseExpansionError('\n'.join(errors))
        if (mask := mask_of(resolved)) is None:
            return
        if pw.along in mask.dims:
            raise PiecewiseExpansionError(
                f"{ctx}: where {pw.where!r} tests '{pw.along}', the breakpoint dim. A where says which coordinates "
                f'have a curve at all, and points: says how far each curve runs along it — move the test there.'
            )
        if stray := sorted(mask.dims - set(frame)):
            raise PiecewiseExpansionError(
                f'{ctx}: where {pw.where!r} tests {stray}, which no link expression carries — a mask says '
                f"which of the block's own coordinates have a curve, and cannot add coordinates. Declare a "
                f'link expression over {stray}, or drop it from the where.'
            )

    def _nothing_collides(self) -> None:
        """No name the block writes is one the file already declares."""
        declared = {
            'variable': self.schema.variables,
            'constraint': self.schema.constraints,
            'sos': self.schema.sos,
            'assumption': self.schema.assumptions,
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
    for name, pw in schema.piecewise.items():
        _Block(schema, raw, name, pw).expand()
    raw['piecewise'].clear()
    for name, pw in schema.piecewise.items():
        if pw.method == 'adjacency':
            emit(raw, name)
    expanded = Spec.model_validate(raw)
    expanded._expanded_piecewise = dict(schema.piecewise)
    del expanded.resolved  # validation typed the rows before the records were here, and a block's own where is on one
    return expanded
