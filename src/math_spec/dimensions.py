# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Static dim-set checking — a type system whose type is a set of dim names.

Every node's dim set is computable before any data is bound, so this pass runs
at load on the resolved AST. The per-node rules are the "Dim algebra" table in
``docs/reference/language/expressions.md``; a constraint's two sides together
must equal its ``foreach``, and a where or a bound may not exceed the frame.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, NamedTuple, assert_never

import math_spec.degree as degree
from math_spec.errors import DimensionError
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CasesNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KwargNode,
    LookupNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
    case_context,
)
from math_spec.operators import BUILTINS
from math_spec.program import (
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    Mask,
    ParameterComparisonNode,
    ParameterDefinedNode,
    VariableDefinedNode,
)
from math_spec.resolution import Namespace, expression_of, where_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec.model import Spec


def dims_of(
    node: ExpressionNode,
    schema: Spec,
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
    schema: Spec,
    context: str,
) -> frozenset[str]:
    """The recursive worker under :func:`dims_of`."""
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

    if isinstance(node, CasesNode):
        return _cases_dims(node, schema)

    assert_never(node)


def _cases_dims(node: CasesNode, schema: Spec) -> frozenset[str]:
    """The declared frame rather than the union of the arms.

    A narrower arm broadcasts, as a parameter with fewer dims does.
    """
    return frozenset(schema.expressions[node.name].foreach or ())


def _not_carried(context: str, call: str, inner: frozenset[str], rewrite: str) -> str:
    """The refusal for an operator walking a dim its operand does not carry; *rewrite* is the operator's own."""
    return (
        f'{context}: {call} but the expression has dims {sorted(inner)}. An operator over a dim the '
        f'operand does not carry is a no-op that builds and solves wrong — {rewrite}.'
    )


def _dims_call(node: FunctionCallNode, schema: Spec, context: str) -> frozenset[str]:
    """The dim rule of the operator *node* calls, applied to the dims its operand carries."""
    inner = _dims(node.args[0], schema, context)
    return _CALL_RULES[node.name](node, inner, schema, context)


def _sum_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``sum`` reduces a dim away, or through a lookup into the dim it maps *into*."""
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
            raise DimensionError(_not_carried(context, f'sum(over={over.name})', inner, 'drop the sum, or fix the dim'))
        return inner - {over.name}

    assert isinstance(by, LookupNode)
    if by.dimension not in inner:
        raise DimensionError(
            _not_carried(
                context,
                f"sum(by={by.shown}) consumes '{by.dimension}', the dim it maps out of,",
                inner,
                'drop the sum, or fix the dim',
            )
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


def _at_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``at`` is the adjoint of ``sum(by=)``: it consumes the dim a lookup maps *into* and produces the one it is over."""
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


def _translation_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``shift`` and ``sum_back`` keep every dim, and their amount, edge and partition are checked here."""
    over = node.kwargs['over']
    assert isinstance(over, DimensionNode)
    if over.name not in inner:
        raise DimensionError(
            _not_carried(
                context,
                f'{node.name}(over={over.name})',
                inner,
                f'walk a dim the operand carries, or drop the {node.name}',
            )
        )
    _check_named_amount(node, over.name, inner, schema, context)
    _check_amount_form(node, context)
    _check_edge(node, context)
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


#: The dim rule of each built-in, by name.
_CALL_RULES: dict[str, Callable[[FunctionCallNode, frozenset[str], Spec, str], frozenset[str]]] = {
    'sum': _sum_dims,
    'at': _at_dims,
    'shift': _translation_dims,
    'sum_back': _translation_dims,
}


class _Amount(NamedTuple):
    """What an axis-walking operator's errors say about the amount it takes."""

    #: The word for the amount.
    noun: str
    #: Why negating a named one at the call site is not what the caller means.
    negated: str
    #: What a named one that varies along the axis it walks becomes.
    varies: str
    #: The least whole number a literal may be.
    minimum: float
    #: What a literal must be written as, after ``operator(kwarg=...)``.
    form: str


_AMOUNTS = {
    'shift': _Amount(
        'offset',
        'A named offset carries its sign in its values, so that one row pointing backwards says '
        'so where the data is read — negate the column instead.',
        'a permutation rather than a lag',
        -math.inf,
        'must be a whole number, or the name of an integer parameter when the offset differs per '
        'entity — a lead time, a transit time, a minimum up time.',
    ),
    'sum_back': _Amount(
        'width',
        'A width counts positions and so has no direction; which way a window reaches is the '
        "operator's own name rather than the sign of its width.",
        'a different window at every position, which is no longer "the last n"',
        1,
        'needs a whole number of positions of at least 1, or the name of an integer parameter when '
        'the window differs per entity. A width of 1 is the operand itself.',
    ),
}


def _amount_of(node: FunctionCallNode) -> tuple[str, ArithmeticNode]:
    """The kwarg an axis-walking operator takes its amount through, and the value written there."""
    (kwarg,) = BUILTINS[node.name].required_value_kwargs
    return kwarg, node.kwargs[kwarg]


def _whole(node: ArithmeticNode, minimum: float) -> bool:
    """Whether *node* is a literal whole number of at least *minimum*."""
    return isinstance(node, NumberNode) and int(node.value) == node.value and node.value >= minimum


def _check_amount_form(node: FunctionCallNode, context: str) -> None:
    """An ``offset=`` or ``within=`` is a whole number in the operator's range, or a parameter name."""
    kwarg, amount = _amount_of(node)
    if isinstance(amount, ParameterNode) or _whole(amount, _AMOUNTS[node.name].minimum):
        return
    raise DimensionError(f'{context}: {node.name}({kwarg}=...) {_AMOUNTS[node.name].form}')


def _check_edge(node: FunctionCallNode, context: str) -> None:
    """What an ``edge=`` may say, and where saying nothing is an answer.

    Every rule here is decidable from the file — whether the operand carries a
    variable, whether the offset is named, what the edge is written as — so a
    file breaking one is refused at load rather than by whoever lowers it.
    """
    edge = node.kwargs.get('edge')
    if node.name == 'sum_back':
        if edge is not None and not isinstance(edge, EdgeNode):
            raise DimensionError(
                f"{context}: sum_back(edge=...) takes 'wrap' or nothing. A window sums the terms "
                f'it reaches, so a position before the first contributes nothing rather than a '
                f'fill value; add the constant to the expression if you want one.'
            )
        return

    if isinstance(edge, EdgeNode):
        return
    fill = _edge_fill(edge, context)
    has_var = degree.carries_variable(node.args[0])
    if has_var and fill is not None and fill != 0:
        raise DimensionError(
            f'{context}: shift(edge={fill:g}) over an expression containing a variable — only '
            f'fill=0 is representable there, since a vacated slot contributes no term. A nonzero '
            f'fill would be a constant standing where a term was; add that constant to the '
            f'expression instead.'
        )
    offset = node.kwargs['offset']
    if fill is None and _vacates(offset) and not has_var:
        raise DimensionError(_shift_over_data_message(context))
    if fill is None and isinstance(offset, ParameterNode):
        raise DimensionError(f'{context}: {_named_offset_edge_message(offset.name)}')


def _vacates(offset: ArithmeticNode) -> bool:
    """Whether a translation leaves anything behind.

    A literal zero step reaches every coordinate from itself, so there is no
    vacated position for an ``edge=`` to answer for and the refusal below has
    nothing to refuse. A *named* offset may be zero in the data and is not
    known here, so it vacates until proved otherwise.
    """
    return not (isinstance(offset, NumberNode) and offset.value == 0)


def _edge_fill(edge: ArithmeticNode | None, context: str) -> float | None:
    """The number an ``edge=`` names, or ``None`` where it names nothing."""
    if edge is None:
        return None
    assert isinstance(edge, NumberNode), (
        f'{context}: resolution refuses an edge that is neither wrap nor a number first'
    )
    return edge.value


def _named_offset_edge_message(name: str) -> str:
    """Why a named offset must say what the vacated positions contribute.

    The absent edge propagates through a presence frame keyed by the translated
    dimension alone, and a per-entity offset vacates a different slot for each
    entity — which that frame cannot say. Refused rather than answered wrongly
    (#850); the two edges that write their own answer are allowed.
    """
    return (
        f'shift(offset={name}) leaves the vacated positions absent, which a '
        f'per-entity offset cannot say yet.\n'
        f"Add edge='wrap' for a cyclic translation, or edge=<number> for what the "
        f'vacated positions contribute.'
    )


def _shift_over_data_message(context: str) -> str:
    """The three ways out of a translation over data with no ``edge=``, the third being two things at once."""
    return (
        f'{context}: shift() over a variable-free expression leaves vacated positions with no '
        f'value, and inventing one is what silently pinned a bound to zero. Say which you mean:\n'
        f"  shift(x, over=d, offset=n, edge='wrap')   the dimension really is cyclic\n"
        f'  shift(x, over=d, offset=n, edge=0)        the vacated positions contribute zero\n'
        f'  ...and a where: excluding them        the vacated rows should not exist at all\n'
        f'A where: alone does not lift this — it is decided on the expression, before any mask '
        f'is read — and edge=0 alone leaves a row whose bound is that zero.'
    )


def _check_named_amount(node: FunctionCallNode, over: str, inner: frozenset[str], schema: Spec, context: str) -> None:
    """The rules that hold of an ``offset=`` or ``within=`` naming a parameter; a literal breaks none of them."""
    kwarg, amount = _amount_of(node)
    words = _AMOUNTS[node.name]
    if isinstance(amount, UnaryOperatorNode) and isinstance(amount.operand, ParameterNode):
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.op}{amount.operand.name}) negates a named {words.noun}. {words.negated}'
        )
    if not isinstance(amount, ParameterNode):
        return
    declared = schema.parameters[amount.name]
    if declared.dtype != 'int':
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) counts positions along '
            f"'{over}', but '{amount.name}' is declared dtype: {declared.dtype}. A count of "
            f'positions is integral — declare it dtype: int, which binds only an integer '
            f'column, so a fractional {words.noun} has nowhere to arrive from.'
        )
    if over in declared.dims:
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) walks '
            f"'{over}', but '{amount.name}' is declared over {sorted(declared.dims)}, which "
            f'carries it. A named {words.noun} that varies along the axis it walks is {words.varies} '
            f"— declare '{amount.name}' over dims '{over}' is not one of."
        )
    partition = node.kwargs.get('by')
    groups = frozenset(partition.into) if isinstance(partition, LookupNode) else frozenset()
    if stray := sorted(frozenset(declared.dims) - inner - groups):
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) reads its {words.noun} at the coordinate it '
            f"walks, but '{amount.name}' varies over {stray}, which that coordinate does not carry "
            f'(dims {sorted(inner)}). A dim the coordinate does not have is no coordinate at all — '
            f"declare '{amount.name}' over dims the expression carries, or group by a lookup into "
            f'one of {stray}, so that each group is reached by its own {words.noun}.'
        )


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


def check_schema(schema: Spec) -> None:
    """Check every declaration's dim rules.

    Raises:
        DimensionError: On the first declaration that breaks one.
    """
    ns = Namespace.of(schema)

    for vname, vdef in schema.variables.items():
        frame = frozenset(vdef.foreach)
        context = f"Variable '{vname}'"
        _check_where_dims(where_of(vdef.where, ns, context), frame, context)
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

    for ename, block in schema.expressions.items():
        if not block.cases:
            continue
        frame = frozenset(block.foreach or [])
        for case_name, case in block.cases.items():
            context = case_context(ename, case_name)
            _check_where_dims(where_of(case.when, ns, context), frame, context)
            _check_value_dims(case.expression, schema, ns, frame, context)
        assert block.otherwise is not None
        _check_value_dims(block.otherwise, schema, ns, frame, case_context(ename, None))

    for cname, cdef in schema.constraints.items():
        frame = frozenset(cdef.foreach)
        context = f"Constraint '{cname}'"
        _check_where_dims(where_of(cdef.where, ns, context), frame, context)
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


def _check_value_dims(
    text: str,
    schema: Spec,
    ns: Namespace,
    frame: frozenset[str],
    context: str,
) -> None:
    """A region's value may only carry dims the frame does — the ``otherwise:`` included.

    A wider one would give the quantity dims its declaration does not, which is
    the second answer a ``foreach:`` exists to avoid.
    """
    got = dims_of(expression_of(text, schema, ns, context), schema, context)
    if not got <= frame:
        raise DimensionError(
            f'{context}: the value carries dims {sorted(got - frame)} outside the foreach '
            f'{sorted(frame)}. A case is a value within the frame — it cannot widen it.'
        )


def _check_where_dims(
    mask: Mask | None,
    frame: frozenset[str],
    context: str,
) -> None:
    """A predicate may only test dims the frame carries; reducing an outside dim to fit would fail open.

    The refusal names the leaf that left the frame, reading its dims as
    :attr:`~math_spec.program.Mask.dims` does.
    """
    if mask is None:
        return

    for atom in mask.atoms:
        if not (outside := sorted(Mask(atom).dims - frame)):
            continue
        match atom:
            case ParameterDefinedNode() | ParameterComparisonNode():
                noun = 'parameter'
            case VariableDefinedNode():
                noun = 'variable'
            case DimensionComparisonNode() | DimensionPositionNode():
                noun = 'dimension'
            case LookupComparisonNode() | LookupPairComparisonNode() | LookupDefinedNode():
                noun = 'lookup'
            case _:
                assert_never(atom)
        raise DimensionError(
            f"{context}: where-{noun} '{atom.name}' reads dims {outside} outside the frame {sorted(frame)}. "
            f'Reducing a mask over an unlisted dim would silently widen it — add the dim to foreach, '
            f'or test a name the frame carries.'
        )
