"""Static dim-set checking — a type system whose type is a set of dim names.

Parameter ``dims`` are declared, variable ``foreach`` is declared, and operator
dimension arguments are name-checked, so **every node's dim set is computable
before any data is bound**. That is the whole basis of this pass: it runs at
load time, on the resolved core AST, so both lanes get the same answer by
construction rather than by differential test.

The rules::

    number                  -> no dims
    parameter p             -> its declared dims
    variable v              -> its foreach
    -x, +x                  -> same dims as x
    a + b, a * b, a / b     -> every dim either side carries (set union)
    sum(x, over=d)          -> x's dims without d;  error if x has no d
    sum(x, over=d, group_by=c)
                            -> x's dims without d, plus the dim c targets;
                               error if x has no d, or d declares no coord c
    shift(x, over=d, by=n)  -> same dims as x;      error if x has no d

and at the declaration level::

    constraint  -> the dims of both sides together must *equal* foreach
    where       -> the predicate's dims must not exceed the frame
    bounds      -> the bound parameter's dims must not exceed foreach

The direction that matters most is the *stray* dim: one the frame does not
declare broadcasts silently in the eager lane and adds coordinate columns in
the relational one, so the same YAML quietly builds a bigger model than it
reads as. The missing direction is checked too, a foreach dim the equation
never uses just repeating one row across it — nearly always a typo.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, assert_never

from lpspec.errors import DimensionError
from lpspec.language.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    CoordinateNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from lpspec.language.resolution import Namespace, expression_of, where_of
from lpspec.language.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    VariableDefinedNode,
    WhereNode,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from lpspec.language.model import Model


def dims_of(
    node: ExpressionNode,
    schema: Model,
    context: str,
    external: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> frozenset[str]:
    """The dim set of a resolved expression, checking every rule on the way.

    ``external`` gives the dims of variables that live on a model rather than
    in this schema — ``linopy.extend()``'s case, mirroring how
    ``known_variables`` widens the namespace.

    Raises:
        DimensionError: On the first rule broken.
    """
    if isinstance(node, ComparisonNode):
        return _dims(node.left, schema, context, external) | _dims(node.right, schema, context, external)
    return _dims(node, schema, context, external)


def _dims(
    node: ArithmeticNode,
    schema: Model,
    context: str,
    external: Mapping[str, Sequence[str]],
) -> frozenset[str]:
    """The recursive worker under :func:`dims_of`.

    A binary operator takes the *union* of its sides with no subset check: an
    outer product is legitimate when the frame declares the result — the
    convex-piecewise epigraph multiplies a per-segment slope by a per-snapshot
    variable and wants one row per (snapshot, generator, segment). What must
    not be silent is the *declaration* disagreeing, which ``dims == foreach``
    in :func:`check_schema` catches where model size is decided. A variable
    absent from the schema is one already on the model, its dims in *external*.
    """
    if isinstance(node, NumberNode):
        return frozenset()

    if isinstance(node, ParameterNode):
        return frozenset(schema.parameters[node.name].dims)

    if isinstance(node, VariableNode):
        if node.name in schema.variables:
            return frozenset(schema.variables[node.name].foreach)
        return frozenset(external[node.name])

    if isinstance(node, (NameNode, KeywordNode, DimensionNode, CoordinateNode, EdgeNode)):
        msg = f'{type(node).__name__} reached the dim checker; resolve the expression first.'
        raise AssertionError(msg)

    if isinstance(node, UnaryOperatorNode):
        return _dims(node.operand, schema, context, external)

    if isinstance(node, BinaryOperatorNode):
        return _dims(node.left, schema, context, external) | _dims(node.right, schema, context, external)

    if isinstance(node, FunctionCallNode):
        return _dims_call(node, schema, context, external)

    assert_never(node)


def _dims_call(
    node: FunctionCallNode,
    schema: Model,
    context: str,
    external: Mapping[str, Sequence[str]],
) -> frozenset[str]:
    """The dim rule of one operator call.

    ``group_by`` reduces the ``over`` dim *into* another rather than away.
    ``at`` is the adjoint of ``sum`` and takes the same two arguments, one
    mapping table walked either way: ``sum`` consumes the dim that *declares*
    the coordinate, ``at`` the dim it *targets*.
    """
    if node.name == 'sum':
        inner = _dims(node.args[0], schema, context, external)
        over = node.kwargs['over']
        assert isinstance(over, DimensionNode)
        by = node.kwargs.get('group_by')
        verb = f'sum(over={over.name}, group_by=...)' if by is not None else f'sum(over={over.name})'
        if over.name not in inner:
            raise DimensionError(
                f'{context}: {verb} but the expression has dims '
                f'{sorted(inner)}. Summing over a dim the operand does not carry '
                f'is a no-op that builds and solves wrong — drop the sum, or fix '
                f'the dim.'
            )
        if by is None:
            return inner - {over.name}

        assert isinstance(by, CoordinateNode)
        if by.into in inner - {over.name}:
            raise DimensionError(
                f"{context}: sum(over={over.name}, group_by={by.name}) targets '{by.into}', "
                f'which the expression already carries ({sorted(inner)}). The result would '
                f"need '{by.into}' twice — once as the operand's own dim and once as the "
                f'group it is placed into — and neither lane can represent that: the union '
                f'below would silently absorb one of them. Sum over one of the two first, '
                f'or group into a dimension the operand does not have.'
            )
        return (inner - {over.name}) | {by.into}

    if node.name == 'at':
        inner = _dims(node.args[0], schema, context, external)
        over = node.kwargs['onto']
        by = node.kwargs['by']
        assert isinstance(over, DimensionNode)
        assert isinstance(by, CoordinateNode)
        if by.into not in inner:
            raise DimensionError(
                f'{context}: at(onto={over.name}, by={by.name}) reads through '
                f"'{by.into}', which the expression does not carry (dims "
                f'{sorted(inner)}). A pullback needs the coarse dim to read *from* — '
                f'sum is the direction that produces it.'
            )
        if over.name in inner - {by.into}:
            raise DimensionError(
                f'{context}: at(onto={over.name}, by={by.name}) places terms onto '
                f"'{over.name}', which the expression already carries ({sorted(inner)}). "
                f"The result would need '{over.name}' twice — once as the operand's own "
                f'dim and once as the dim it is spread onto. Sum over one of the two first.'
            )
        return (inner - {by.into}) | {over.name}

    if node.name == 'shift':
        inner = _dims(node.args[0], schema, context, external)
        over = node.kwargs['over']
        assert isinstance(over, DimensionNode)
        if over.name not in inner:
            raise DimensionError(f'{context}: shift(over={over.name}) but the expression has dims {sorted(inner)}.')
        return inner

    msg = f"{context}: operator '{node.name}' has no dim rule"
    raise DimensionError(msg)


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


def check_schema(
    schema: Model,
    external: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> None:
    """Check every declaration's dim rules.

    ``external`` maps variables already on a model to their dims, so
    ``linopy.extend()`` can reference them (hard rule 5 keeps parameters
    schema-local, but variables legitimately come from the model argument).

    Raises:
        DimensionError: On the first declaration that breaks one.
    """
    ns = Namespace.of(schema, external)

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
        _check_where_dims(where_of(cdef.where, ns, f"Constraint '{cname}'"), schema, frame, f"Constraint '{cname}'")
        context = f"Constraint '{cname}'"
        got = dims_of(expression_of(cdef.expression, schema, ns, context), schema, context, external)
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
        dims_of(expression_of(schema.objective.expression, schema, ns, context), schema, context, external)


def _check_where_dims(
    node: WhereNode | None,
    schema: Model,
    frame: frozenset[str],
    context: str,
) -> None:
    """A predicate may only test dims the frame carries.

    Reducing an outside dim to fit — with ``any()``, say — is a mask that fails
    *open*, silently including everything. Both lanes reject it, and they
    reject it here, at load time.
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
    elif isinstance(node, DimensionComparisonNode):
        if node.name not in frame:
            raise DimensionError(
                f"{context}: where-comparison on dimension '{node.name}', which is not in the frame {sorted(frame)}."
            )
    elif isinstance(node, NotNode):
        _check_where_dims(node.operand, schema, frame, context)
    elif isinstance(node, (AndNode, OrNode)):
        _check_where_dims(node.left, schema, frame, context)
        _check_where_dims(node.right, schema, frame, context)
    elif isinstance(node, (UnresolvedNameNode, UnresolvedComparisonNode)):
        msg = f'{type(node).__name__} reached the dim checker unresolved.'
        raise AssertionError(msg)
    elif not isinstance(node, BooleanLiteralNode):
        assert_never(node)
