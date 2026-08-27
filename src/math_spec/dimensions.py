# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Static dim-set checking — a type system whose type is a set of dim names.

Parameter ``dims`` are declared, variable ``foreach`` is declared, and operator
dimension arguments are name-checked, so **every node's dim set is computable
before any data is bound**. That is the whole basis of this pass: it runs at
load time, on the resolved core AST, so every consumer gets the same answer by
construction. The per-node rules are the "Dim algebra" table in
``docs/reference/language/expressions.md``; at the declaration level::

    constraint  -> the dims of both sides together must *equal* foreach
    where       -> the predicate's dims must not exceed the frame
    bounds      -> the bound parameter's dims must not exceed foreach

The direction that matters most is the *stray* dim: one the frame does not
declare broadcasts silently at build time, so the same YAML quietly builds a
bigger model than it reads as. The missing direction is checked too, a foreach
dim the equation never uses just repeating one row across it — nearly always a
typo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from math_spec.errors import DimensionError
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    ExpressionNode,
    FunctionCallNode,
    KwargNode,
    LookupNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
)
from math_spec.operators import BUILTINS
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedWhereNode,
    VariableDefinedNode,
    WhereNode,
)

if TYPE_CHECKING:
    from math_spec.model import Model


def dims_of(
    node: ExpressionNode,
    schema: Model,
    context: str,
) -> frozenset[str]:
    """The dim set of a resolved expression, checking every rule on the way.

    Raises:
        DimensionError: On the first rule broken.
    """
    if isinstance(node, ComparisonNode):
        return _dims(node.left, schema, context) | _dims(node.right, schema, context)
    return _dims(node, schema, context)


def _dims(
    node: ArithmeticNode,
    schema: Model,
    context: str,
) -> frozenset[str]:
    """The recursive worker under :func:`dims_of`; a binary operator takes the union of its sides, unchecked, since :func:`check_schema` compares the result with the declared frame."""
    if isinstance(node, NumberNode):
        return frozenset()

    if isinstance(node, ParameterNode):
        return frozenset(schema.parameters[node.name].dims)

    if isinstance(node, VariableNode):
        return frozenset(schema.variables[node.name].foreach)

    if isinstance(node, UnresolvedNode | KwargNode):
        msg = f'{type(node).__name__} reached the dim checker; resolve the expression first.'
        raise AssertionError(msg)

    if isinstance(node, UnaryOperatorNode):
        return _dims(node.operand, schema, context)

    if isinstance(node, BinaryOperatorNode):
        return _dims(node.left, schema, context) | _dims(node.right, schema, context)

    if isinstance(node, FunctionCallNode):
        return _dims_call(node, schema, context)

    assert_never(node)


def _dims_call(
    node: FunctionCallNode,
    schema: Model,
    context: str,
) -> frozenset[str]:
    """The dim rule of one operator call.

    ``sum`` with neither ``over=`` nor ``by=`` takes every dim the operand
    carries, so its result is scalar. ``by=`` reduces the lookup's own dim
    *into* its target rather than away.
    ``at`` is the adjoint of ``sum``, one mapping table walked either way:
    ``sum`` consumes the dim the lookup is *over*, ``at`` the dim it maps
    *into*, and each produces the other.
    """
    if node.name == 'sum':
        inner = _dims(node.args[0], schema, context)
        by = node.kwargs.get('by')
        if by is None and 'over' not in node.kwargs:
            if not inner:
                raise DimensionError(
                    f'{context}: sum() with no over= or by= sums every dim the operand '
                    f'carries, and this one carries none — the expression is already a '
                    f'scalar. Drop the sum.'
                )
            return frozenset()
        if by is None:
            over = node.kwargs['over']
            assert isinstance(over, DimensionNode)
            if over.name not in inner:
                raise DimensionError(
                    f'{context}: sum(over={over.name}) but the expression has dims '
                    f'{sorted(inner)}. Summing over a dim the operand does not carry '
                    f'is a no-op that builds and solves wrong — drop the sum, or fix '
                    f'the dim.'
                )
            return inner - {over.name}

        assert isinstance(by, LookupNode)
        if by.dimension not in inner:
            raise DimensionError(
                f"{context}: sum(by={by.shown}) consumes '{by.dimension}', the dim it maps "
                f'out of, but the expression has dims {sorted(inner)}. Summing '
                f'over a dim the operand does not carry is a no-op that builds and '
                f'solves wrong — drop the sum, or fix the dim.'
            )
        collides = sorted(set(by.into) & (inner - {by.dimension}))
        if collides:
            raise DimensionError(
                f'{context}: sum(by={by.shown}) targets {collides}, '
                f'which the expression already carries ({sorted(inner)}). The result would '
                f"need {collides} twice — once as the operand's own dim and once as the "
                f'group it is placed into. Sum over one of the two first, '
                f'or group into a dimension the operand does not have.'
            )
        return (inner - {by.dimension}) | set(by.into)

    if node.name == 'at':
        inner = _dims(node.args[0], schema, context)
        by = node.kwargs['by']
        assert isinstance(by, LookupNode)
        absent = sorted(set(by.into) - inner)
        if absent:
            raise DimensionError(
                f'{context}: at(by={by.shown}) reads through '
                f'{absent}, which the expression does not carry (dims '
                f'{sorted(inner)}). A pullback needs the coarse dims to read *from* — '
                f'sum is the direction that produces them.'
            )
        if by.dimension in inner - set(by.into):
            raise DimensionError(
                f'{context}: at(by={by.shown}) places terms onto '
                f"'{by.dimension}', which the expression already carries ({sorted(inner)}). "
                f"The result would need '{by.dimension}' twice — once as the operand's own "
                f'dim and once as the dim it is spread onto. Sum over one of the two first.'
            )
        return (inner - set(by.into)) | {by.dimension}

    if node.name in ('shift', 'sum_back', 'sum_forward'):
        inner = _dims(node.args[0], schema, context)
        over = node.kwargs['over']
        assert isinstance(over, DimensionNode)
        if over.name not in inner:
            raise DimensionError(
                f'{context}: {node.name}(over={over.name}) but the expression has dims {sorted(inner)}.'
            )
        _check_named_amount(node, over.name, inner, schema, context)
        partition = node.kwargs.get('by')
        if partition is not None:
            assert isinstance(partition, LookupNode)
            if len(partition.names) > 1:
                raise DimensionError(
                    f'{context}: {node.name}(over={over.name}, by={partition.shown}) partitions by '
                    f'several lookups at once. A partition says which rows are neighbours rather than '
                    f'which group a term lands in, so it names one lookup — partition by a lookup whose '
                    f'values already distinguish them.'
                )
            if partition.dimension != over.name:
                raise DimensionError(
                    f'{context}: {node.name}(over={over.name}, by={partition.shown}) walks '
                    f"'{over.name}' but groups by a lookup over '{partition.dimension}'. No row of "
                    f"'{over.name}' carries it, so no coordinate has a neighbour inside a group — "
                    f"partition by a lookup over '{over.name}'."
                )
        return inner

    msg = f"operator '{node.name}' reached the dim checker without a rule; resolution admits only BUILTINS."
    raise AssertionError(msg)


#: Per axis-walking operator: the word its errors call the amount it takes,
#: why negating a named one at the call site is not what the caller means, and
#: what a named one that varies along the axis it walks becomes.
_AMOUNT_WORDING = {
    'shift': (
        'offset',
        'A named offset carries its sign in its values, so that one row pointing backwards says '
        'so where the data is read — negate the column instead.',
        'a permutation rather than a lag',
    ),
    'sum_back': (
        'width',
        'A width counts positions and so has no direction; which way a window reaches is the '
        "operator's own name rather than the sign of its width.",
        'a different window at every position, which is no longer "the last n"',
    ),
    'sum_forward': (
        'width',
        'A width counts positions and so has no direction; which way a window reaches is the '
        "operator's own name rather than the sign of its width.",
        'a different window at every position, which is no longer "the next n"',
    ),
}
#: The two windows differ only in which way they reach, which is what that
#: wording already says, so they answer it identically.


def _check_named_amount(node: FunctionCallNode, over: str, inner: frozenset[str], schema: Model, context: str) -> None:
    """The rules that hold of an ``offset=`` or ``within=`` naming a parameter.

    They are about the *amount* rather than about a dim set, but they live here
    because here is where the schema is in hand — a parameter's ``dtype`` and
    its ``dims`` are read off the same declaration, and splitting a documented
    set across two passes would give one rule of it several voices.

    A literal breaks none of them: it parses as a number, and a number has
    neither a dtype to declare nor dims to vary over.
    """
    (kwarg,) = BUILTINS[node.name].required_value_kwargs
    noun, negated, varies = _AMOUNT_WORDING[node.name]
    amount = node.kwargs[kwarg]
    if isinstance(amount, UnaryOperatorNode) and isinstance(amount.operand, ParameterNode):
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.op}{amount.operand.name}) negates a named {noun}. {negated}'
        )
    if not isinstance(amount, ParameterNode):
        return
    declared = schema.parameters[amount.name]
    if declared.dtype != 'int':
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) counts positions along '
            f"'{over}', but '{amount.name}' is declared dtype: {declared.dtype}. A count of "
            f'positions is integral — declare it dtype: int, which binds only an integer '
            f'column, so a fractional {noun} has nowhere to arrive from.'
        )
    if over in declared.dims:
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) walks '
            f"'{over}', but '{amount.name}' is declared over {sorted(declared.dims)}, which "
            f'carries it. A named {noun} that varies along the axis it walks is {varies} '
            f"— declare '{amount.name}' over dims '{over}' is not one of."
        )
    partition = node.kwargs.get('by')
    groups = frozenset(partition.into) if isinstance(partition, LookupNode) else frozenset()
    if stray := sorted(frozenset(declared.dims) - inner - groups):
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) reads its {noun} at the coordinate it '
            f"walks, but '{amount.name}' varies over {stray}, which that coordinate does not carry "
            f'(dims {sorted(inner)}). A dim the coordinate does not have is no coordinate at all — '
            f"declare '{amount.name}' over dims the expression carries, or group by a lookup into "
            f'one of {stray}, so that each group is reached by its own {noun}.'
        )


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


def check_schema(schema: Model) -> None:
    """Check every declaration's dim rules.

    Raises:
        DimensionError: On the first declaration that breaks one.
    """
    ns = Namespace.of(schema)

    for vname, vdef in schema.variables.items():
        frame = frozenset(vdef.foreach)
        context = f"Variable '{vname}'"
        _check_where_dims(where_of(vdef.where, ns, context), schema, frame, context)
        for side in ('lower', 'upper'):
            bound = getattr(vdef.bounds, side)
            if isinstance(bound, str):
                bdims = frozenset(schema.parameters[bound].dims)
                if not bdims <= frame:
                    raise DimensionError(
                        f"{context}: bounds.{side} parameter '{bound}' has dims "
                        f"{sorted(bdims - frame)} outside the variable's foreach "
                        f'{sorted(frame)}.'
                    )

    for cname, cdef in schema.constraints.items():
        frame = frozenset(cdef.foreach)
        context = f"Constraint '{cname}'"
        _check_where_dims(where_of(cdef.where, ns, context), schema, frame, context)
        got = dims_of(expression_of(cdef.expression, schema, ns, context), schema, context)
        if got != frame:
            stray, missing = sorted(got - frame), sorted(frame - got)
            detail = (
                f'carries dims {stray} that are not in foreach {sorted(frame)} — every '
                f'stray dim multiplies the rows this constraint builds; add it to '
                f'foreach if that is intended, or sum it out'
                if stray
                else f'does not carry {missing}, which foreach declares — the same row '
                f'would be repeated across {missing}; drop it from foreach, or use it '
                f'in the expression'
            )
            raise DimensionError(f'{context}: the expression {detail}.')

    if schema.objective is not None:
        context = 'The objective'
        got = dims_of(expression_of(schema.objective.expression, schema, ns, context), schema, context)
        if got:
            raise DimensionError(
                f'{context}: the expression carries dims {sorted(got)}, and an objective is one '
                f'number. Wrap each additive term in its own sum(): '
                f'`sum(p * cost) + sum(p_nom * capex)`.'
            )


def _check_where_dims(
    node: WhereNode | None,
    schema: Model,
    frame: frozenset[str],
    context: str,
) -> None:
    """A predicate may only test dims the frame carries.

    Reducing an outside dim to fit — with ``any()``, say — is a mask that fails
    *open*, silently including everything. It is rejected here, at load
    time.
    """
    if node is None:
        return

    if isinstance(node, (ParameterDefinedNode, ParameterComparisonNode)):
        pdims = frozenset(schema.parameters[node.name].dims)
        if not pdims <= frame:
            raise DimensionError(
                f"{context}: where-parameter '{node.name}' has dims "
                f'{sorted(pdims - frame)} outside the frame {sorted(frame)}. Reducing '
                f'a mask over an unlisted dim would silently widen it.'
            )
    elif isinstance(node, VariableDefinedNode):
        vdims = frozenset(schema.variables[node.name].foreach)
        if not vdims <= frame:
            raise DimensionError(
                f"{context}: where-variable '{node.name}' has dims "
                f'{sorted(vdims - frame)} outside the frame {sorted(frame)}. A mask '
                f'reducing over an unlisted dim would silently widen it — say which '
                f'reduction you mean.'
            )
    elif isinstance(node, (DimensionComparisonNode, DimensionPositionNode)):
        if node.name not in frame:
            raise DimensionError(
                f"{context}: where-comparison on dimension '{node.name}', which is not in the frame {sorted(frame)}."
            )
    elif isinstance(node, (LookupComparisonNode, LookupPairComparisonNode, LookupDefinedNode)):
        if node.over not in frame:
            raise DimensionError(
                f"{context}: where-comparison on lookup '{node.name}', which is over "
                f"dimension '{node.over}' — not in the frame {sorted(frame)}. A lookup is "
                f'read on the dim it maps out of, so that dim has to be one the '
                f'declaration ranges over.'
            )
    elif isinstance(node, NotNode):
        _check_where_dims(node.operand, schema, frame, context)
    elif isinstance(node, (AndNode, OrNode)):
        _check_where_dims(node.left, schema, frame, context)
        _check_where_dims(node.right, schema, frame, context)
    elif isinstance(node, UnresolvedWhereNode):
        msg = f'{type(node).__name__} reached the dim checker unresolved.'
        raise AssertionError(msg)
    elif not isinstance(node, BooleanLiteralNode):
        assert_never(node)
