# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Every node a `Program` can carry is one some file actually lowers to.

The sibling of `test_the_golden_model_carries_every_node_kind_the_walk_renders`,
one state along. That one holds the *renderer* to the AST; this holds the
*lowering* to the program, and the two cannot share a fixture: rendering
accepts more than lowering does, so the golden model carries a shift over a
variable-free expression that lowering refuses outright.

Without this, a node can join `ExpressionNode` with nothing producing it and
the suite stays green — `assert_never` fires only where some test happens to
lower a file that uses the construct. That is how `cases:` reached a release
candidate unlowerable.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import math_spec as ms
from math_spec.program import ExpressionNode, Program, walk

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'


def _expressions(program: Program) -> list[ExpressionNode]:
    """Every tree a program hangs on to, wherever it hangs it.

    Bounds and named expressions among them: a node reachable only from a
    post-solve-grade entry — `Dual` is the only such node — is still a node
    a consumer has to build.
    """
    trees = [side for c in program.constraints.values() for side in (c.lhs, c.rhs)]
    trees += [bound for v in program.variables.values() for bound in (v.lower, v.upper)]
    trees += list(program.named_expressions.values())
    if program.objective is not None:
        trees.append(program.objective.expression)
    return trees


def test_every_program_node_is_one_some_file_lowers_to():
    """A node nothing produces is a node no consumer has been asked to build."""
    program = ms.to_program(FIXTURE)
    reached = {type(node).__name__ for node in walk(*_expressions(program))}
    declared = {node.__name__ for node in get_args(ExpressionNode)}

    assert declared <= reached, (
        f'{FIXTURE.name} lowers to none of {sorted(declared - reached)}. A node no file reaches is '
        f'one whose lowering nobody has run — add a declaration using the construct it stands for.'
    )


def test_the_fixture_carries_nothing_the_program_has_no_node_for():
    """The other direction, so the fixture cannot drift into asserting nothing."""
    program = ms.to_program(FIXTURE)
    reached = {type(node).__name__ for node in walk(*_expressions(program))}
    declared = {node.__name__ for node in get_args(ExpressionNode)}

    assert reached <= declared, f'{FIXTURE.name} lowers to {sorted(reached - declared)}, which is not a program node'
