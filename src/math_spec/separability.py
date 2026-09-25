# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The walk behind :attr:`~math_spec.program.Program.separability` — every axis's verdict, in one pass over a program."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

from math_spec.program import (
    Cases,
    DimensionPosition,
    Join,
    Mask,
    Reach,
    Separability,
    Sum,
    Translate,
    WindowSum,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from math_spec.program import Expression, Program


class _Block(NamedTuple):
    """One group of expressions the walk judges together, as the lowering's own messages label it.

    ``row`` is the constraint whose rows the block builds, and ``None`` where
    it builds none — a bound narrows a column, and the objective is one row no
    window cuts. A coupling reported against a block without a row is still a
    coupling, and never a linking row.
    """

    label: str
    row: str | None
    nodes: tuple[Expression, ...]
    mask: Mask | None
    reductions_couple: bool


def _built_blocks(program: Program) -> Iterator[_Block]:
    """Every block that builds rows.

    A named expression is not one: its body stands under each use, so walking
    the constraint sides reaches it, and walking it again would report one
    coupling twice.
    """
    for name, block in program.constraints.items():
        yield _Block(f"constraint '{name}'", name, (block.lhs, block.rhs), block.where, True)
    for name, variable in program.variables.items():
        bounds = tuple(side for side in (variable.lower, variable.upper) if side is not None)
        yield _Block(f"variable '{name}'", None, bounds, variable.where, True)
    if program.objective is not None:
        yield _Block('the objective', None, (program.objective.expression,), None, False)


def separabilities(program: Program) -> dict[str, Separability]:
    """Every axis's verdict, in one walk.

    One traversal rather than one per axis, because every construct that ties an
    axis together names the axis it ties: asking each node *which* dimension it
    is about answers for all of them at what answering for one cost.

    ``reductions_couple`` is the position a block stands in rather than anything
    about the block — a sum over the axis couples a constraint row to the whole
    horizon and leaves an objective additively separable. A translation reads
    ahead for a negative offset; what one reads behind is the window's edge,
    which is not asked. Each coupling carries the one modelling change that
    would lift it, after the dash.

    The border a decomposition cuts along falls out of the same walk, which is
    why it is taken here rather than in a pass of its own: a constraint the axis
    does not index, and one a coupling names, are the rows no window holds.
    """
    ahead = dict.fromkeys(program.dimensions, 0)
    reasons: dict[str, dict[str, dict[str, list[str]]]] = {
        kind: {dimension: {} for dimension in program.dimensions} for kind in ('coupled', 'restarts')
    }
    undecided: dict[str, dict[Reach, None]] = {dimension: {} for dimension in program.dimensions}
    rows: dict[str, str] = {}

    def report(kind: str, dimension: str, label: str, reason: str) -> None:
        reasons[kind][dimension].setdefault(label, []).append(reason)

    def waits_on(dimension: str, label: str, name: str, kind: Literal['offset', 'partition', 'coordinate']) -> None:
        undecided[dimension][Reach(label, name, kind)] = None

    for label, row, nodes, mask, reductions_couple in _built_blocks(program):
        if row is not None:
            rows[label] = row
        masks: list[Mask | None] = [mask]
        for node in walk(*nodes):
            if isinstance(node, Cases):
                masks.extend(region.when for region in node.regions)
            elif isinstance(node, Sum):
                for axis in node.over:
                    if axis.column is not None:
                        assert isinstance(node.operand, Join), 'a join axis is opened by the join the sum stands over'
                        report(
                            'coupled',
                            axis.dimension,
                            label,
                            f'groups {axis.dimension} into {", ".join(node.operand.columns.added_dims)} — window that dimension instead, or cut only at the group edges',
                        )
                    elif reductions_couple:
                        report(
                            'coupled',
                            axis.dimension,
                            label,
                            f'sums over {axis.dimension} — a rolling sum_back(window=n) windows, a total over the horizon does not',
                        )
            elif isinstance(node, Join) and not node.columns.axes:
                for dimension in node.columns.dropped_dims:
                    waits_on(dimension, label, node.columns.name, 'coordinate')
            elif isinstance(node, (Translate, WindowSum)):
                dimension = node.along
                if node.wrap:
                    report(
                        'coupled',
                        dimension,
                        label,
                        f'wraps around {dimension}, so its first row reads its last — an opening-state seed at '
                        f'position({dimension}) == 0 is what a rolling horizon replaces the wrap with',
                    )
                    continue
                if node.partition is not None:
                    waits_on(dimension, label, node.partition.name, 'partition')
                if isinstance(node, WindowSum):
                    continue
                if isinstance(node.offset, str):
                    waits_on(dimension, label, node.offset, 'offset')
                else:
                    ahead[dimension] = max(ahead[dimension], -node.offset)
        for candidate in masks:
            for atom in candidate.atoms if candidate is not None else ():
                if isinstance(atom, DimensionPosition):
                    report('restarts', atom.name, label, f'counts a position along {atom.name}')

    for name, block in program.sos.items():
        report(
            'coupled',
            block.along,
            f"set '{name}'",
            f'is a set along {block.along}, which a window would cut — only a window holding every whole set keeps it',
        )

    def joined(kind: str, dimension: str) -> dict[str, str]:
        return {label: ', '.join(dict.fromkeys(found)) for label, found in reasons[kind][dimension].items()}

    def linking_rows(dimension: str) -> tuple[str, ...]:
        """Each constraint no one window of *dimension* holds whole, in declaration order.

        Two shapes reach the border by different routes, and a constraint that
        takes both is still one name: a row the axis does not index stands in
        every window, and a row a coupling names reads the whole axis. Only a
        declaration that builds a row can put one here, which is what ``rows``
        holds the coupled labels to.
        """
        coupled = {rows[label] for label in reasons['coupled'][dimension] if label in rows}
        return tuple(
            name
            for name, constraint in program.constraints.items()
            if dimension not in constraint.dims or name in coupled
        )

    return {
        dimension: Separability(
            dimension=dimension,
            ahead=ahead[dimension],
            coupled=joined('coupled', dimension),
            undecided=tuple(undecided[dimension]),
            restarts=joined('restarts', dimension),
            linking_rows=linking_rows(dimension),
            linking_columns=tuple(
                name for name, variable in program.variables.items() if dimension not in variable.dims
            ),
        )
        for dimension in program.dimensions
    }
