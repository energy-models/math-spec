# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The walk behind :attr:`~math_spec.program.Program.separability` — every axis's verdict, in one pass over a program."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from math_spec.program import (
    At,
    Cases,
    DimensionPositionNode,
    GroupSum,
    Mask,
    Reach,
    Separability,
    Sum,
    Translate,
    Window,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from math_spec.program import ExpressionNode, Program


def _built_blocks(program: Program) -> Iterator[tuple[str, tuple[ExpressionNode, ...], Mask | None, bool]]:
    """Every block that builds rows, labelled as the lowering's own messages label it.

    A named expression is not one: it is inlined where it is referenced, so
    walking the constraint sides reaches it, and walking it again would
    report one coupling twice.
    """
    for name, block in program.constraints.items():
        yield f"constraint '{name}'", (block.lhs, block.rhs), block.where, True
    for name, variable in program.variables.items():
        yield f"variable '{name}'", (variable.lower, variable.upper), variable.where, True
    if program.objective is not None:
        yield 'the objective', (program.objective.expression,), None, False


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
    """
    ahead = dict.fromkeys(program.dimensions, 0)
    reasons: dict[str, dict[str, dict[str, list[str]]]] = {
        kind: {dimension: {} for dimension in program.dimensions} for kind in ('coupled', 'restarts')
    }
    undecided: dict[str, dict[Reach, None]] = {dimension: {} for dimension in program.dimensions}

    def report(kind: str, dimension: str, label: str, reason: str) -> None:
        reasons[kind][dimension].setdefault(label, []).append(reason)

    def waits_on(dimension: str, label: str, name: str, kind: Literal['offset', 'partition', 'coordinate']) -> None:
        undecided[dimension][Reach(label, name, kind)] = None

    for label, nodes, mask, reductions_couple in _built_blocks(program):
        masks: list[Mask | None] = [mask]
        for node in walk(*nodes):
            if isinstance(node, Cases):
                masks.extend(region.when for region in node.regions)
            elif isinstance(node, Sum):
                if reductions_couple:
                    for dimension in node.over:
                        report(
                            'coupled',
                            dimension,
                            label,
                            f'sums over {dimension} — a rolling sum_back(within=n) windows, a total over the horizon does not',
                        )
            elif isinstance(node, GroupSum):
                for dimension in node.over:
                    report(
                        'coupled',
                        dimension,
                        label,
                        f'groups {dimension} into {", ".join(node.into)} — window that dimension instead, or cut only at the group edges',
                    )
            elif isinstance(node, At):
                for dimension in node.into:
                    for lookup in node.coordinate:
                        waits_on(dimension, label, lookup, 'coordinate')
            elif isinstance(node, (Translate, Window)):
                dimension = node.dimension
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
                if isinstance(node, Window):
                    continue
                if isinstance(node.offset, str):
                    waits_on(dimension, label, node.offset, 'offset')
                else:
                    ahead[dimension] = max(ahead[dimension], -node.offset)
        for candidate in masks:
            for atom in candidate.atoms if candidate is not None else ():
                if isinstance(atom, DimensionPositionNode):
                    report('restarts', atom.name, label, f'counts a position along {atom.name}')

    for name, block in program.sos.items():
        report(
            'coupled',
            block.over,
            f"set '{name}'",
            f'is a set over {block.over}, which a window would cut — only a window holding every whole set keeps it',
        )

    def joined(kind: str, dimension: str) -> dict[str, str]:
        return {label: ', '.join(dict.fromkeys(found)) for label, found in reasons[kind][dimension].items()}

    return {
        dimension: Separability(
            dimension=dimension,
            ahead=ahead[dimension],
            coupled=joined('coupled', dimension),
            undecided=tuple(undecided[dimension]),
            restarts=joined('restarts', dimension),
        )
        for dimension in program.dimensions
    }
