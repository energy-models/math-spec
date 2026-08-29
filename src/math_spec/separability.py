# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Whether a program's rows may be built a window at a time along one dimension.

A driver that solves a horizon in windows — a rolling horizon, a myopic
pathway — is asking one question of the model before it starts: **would
windowing change the answer?** A model whose storage carries over a snapshot
survives being cut into windows that overlap by a row. A model with an annual
budget does not survive it at all, and today nothing says so: the windows solve,
each is feasible, and the pathway is wrong.

The question is decidable before any data binds, because it is the locality the
ceiling already argues in — *pointwise*, *bounded halo*, *global* — asked about
a **dimension** rather than about an operator. This module asks it.

**A reduction means opposite things by position**, and that is the whole of the
care here. In a constraint, a sum over the axis ties every window to every
other and windowing is unsound. In the objective it is additively separable —
an objective *is* a sum, so summing the windows' objectives is summing the
model's. A verdict that treated the two alike would refuse every windowable
model there is.

What is **not** decided here is whether the modeller wanted the window. A
`position(t) == 0` seed fires once over a horizon and once per window, and both
are models somebody means; this reports that windowing changes which rows it
selects and stops there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from math_spec.errors import did_you_mean
from math_spec.program import At, Cases, GroupSum, Sum, Translate, Window, walk
from math_spec.where_parser import AndNode, DimensionPositionNode, NotNode, OrNode

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from math_spec.program import ExpressionNode, Program
    from math_spec.where_parser import WhereNode


@dataclass(frozen=True)
class Separability:
    """What windowing one dimension would cost, and what it would break.

    A verdict rather than facts, unlike :class:`~math_spec.program.Footprint`:
    whether windowing changes the answer has one right answer, where what a
    sink can ingest has one per sink.

    Attributes:
        dimension: The axis asked about.
        halo: Coordinates two neighbouring windows must share for the rows to
            come out the same. ``0`` is pointwise; a ``shift`` of one is ``1``;
            a ``sum_back`` of ``n`` is ``n - 1``. Meaningful only where nothing
            is coupled — a model that does not separate has no overlap that
            would fix it.
        coupled: Each declaration that ties the axis together, to the
            construct that ties it. Empty is the answer a driver wants.
    """

    dimension: str
    halo: int
    coupled: Mapping[str, str]

    @property
    def windowable(self) -> bool:
        """Whether the rows may be built a window at a time, given :attr:`halo` of overlap."""
        return not self.coupled


def separable(program: Program, dimension: str) -> Separability:
    """What windowing *dimension* would cost this program, and what it would break.

    Args:
        program: The model, lowered. Locality lives in the resolved operators,
            so this reads a program rather than the file it came from.
        dimension: The axis to cut along.

    Returns:
        The verdict — see :class:`Separability`.

    Raises:
        KeyError: *dimension* is not one the program declares, named with the
            near miss.
    """
    if dimension not in program.dimensions:
        raise KeyError(f"unknown dimension '{dimension}'. " + did_you_mean(dimension, list(program.dimensions)))

    halo = 0
    coupled: dict[str, str] = {}
    for label, nodes, mask, reductions_couple in _blocks(program):
        reach, reasons = _couplings(nodes, mask, dimension, reductions_couple=reductions_couple)
        halo = max(halo, reach)
        if reasons:
            coupled[label] = ', '.join(dict.fromkeys(reasons))
    for name, block in program.sos.items():
        if block.over == dimension:
            coupled[f"set '{name}'"] = f'is a set over {dimension}, which a window would cut'
    return Separability(dimension=dimension, halo=halo, coupled=coupled)


def _blocks(program: Program) -> Iterator[tuple[str, tuple[ExpressionNode, ...], WhereNode | None, bool]]:
    """Every block that builds rows, labelled as the lowering's own messages label it.

    A named expression is not one: it is inlined where it is referenced, so
    walking the constraint sides reaches it, and walking it again would report
    one coupling twice.
    """
    for name, block in program.constraints.items():
        yield f"constraint '{name}'", (block.lhs, block.rhs), block.where, True
    for name, variable in program.variables.items():
        yield f"variable '{name}'", (variable.lower, variable.upper), variable.where, True
    if program.objective is not None:
        yield 'the objective', (program.objective.expression,), None, False


def _couplings(
    nodes: tuple[ExpressionNode, ...],
    mask: WhereNode | None,
    dimension: str,
    *,
    reductions_couple: bool,
) -> tuple[int, list[str]]:
    """One block's halo along *dimension*, and why it does not separate at all.

    ``reductions_couple`` is the position the block stands in rather than
    anything about the block: a sum over the axis couples a constraint row to
    the whole horizon and leaves an objective additively separable.
    """
    halo = 0
    reasons: list[str] = []
    masks: list[WhereNode | None] = [mask]
    for node in walk(*nodes):
        if isinstance(node, Cases):
            masks.extend(region.when for region in node.regions)
        elif isinstance(node, Sum) and dimension in node.over:
            if reductions_couple:
                reasons.append(f'sums over {dimension}')
        elif isinstance(node, GroupSum) and node.over == dimension:
            reasons.append(f'groups {dimension} away')
        elif isinstance(node, At) and dimension in node.into:
            reasons.append(f'reads {dimension} at a coordinate the data chooses')
        elif isinstance(node, (Translate, Window)) and node.dimension == dimension:
            reach = node.offset if isinstance(node, Translate) else node.width
            if node.wrap:
                reasons.append(f'wraps around {dimension}, so its first row reads its last')
            elif node.partition is not None:
                reasons.append(f"walks inside the groups '{node.partition}' makes, which a window may cut")
            elif isinstance(reach, str):
                reasons.append(f"reaches back by '{reach}', so how far is data's to say")
            else:
                halo = max(halo, abs(reach) if isinstance(node, Translate) else reach - 1)
    reasons.extend(
        f'counts a position along {dimension}, which a window restarts'
        for candidate in masks
        for predicate in _masks(candidate)
        if isinstance(predicate, DimensionPositionNode) and predicate.name == dimension
    )
    return halo, reasons


def _masks(where: WhereNode | None) -> Iterator[WhereNode]:
    """Every predicate under *where*, the composites included.

    A where tree is not an expression tree, so ``program.walk`` does not reach
    it, and ``children`` descends into a region's *value* and not its ``when``
    — which is why the masks a block is judged on are collected during the walk
    rather than read off the declaration alone. One recursion here rather than a
    public walker, there being one caller; it belongs beside ``children`` in
    ``where_parser`` the day there are two.
    """
    if where is None:
        return
    yield where
    if isinstance(where, NotNode):
        yield from _masks(where.operand)
    elif isinstance(where, (AndNode, OrNode)):
        yield from _masks(where.left)
        yield from _masks(where.right)
