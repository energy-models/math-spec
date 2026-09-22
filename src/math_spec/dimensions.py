# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Static dim-set checking — a type system whose type is a set of dim names.

Every node's dim set is computable before any data is bound, so this pass runs
at load on the resolved AST. The per-node rules are the "Dim algebra" table in
``docs/reference/language/expressions.md``; a constraint's two sides together
must equal its ``dims``, and a where or a bound may not exceed the frame.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, NamedTuple, assert_never

import math_spec.degree as degree
from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CasesNode,
    ComparisonNode,
    DefinitionNode,
    DimensionNode,
    DirectionNode,
    DualNode,
    EdgeNode,
    FunctionCallNode,
    KwargNode,
    NumberNode,
    ParameterNode,
    ParsedNode,
    PartitionNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
    case_context,
    children,
)
from math_spec.errors import DimensionError
from math_spec.operators import BUILTINS
from math_spec.program import (
    ArithmeticComparison,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Direction,
    ExpressionComparison,
    Mask,
    ParameterComparison,
    ParameterDefined,
    Partition,
    RelationComparison,
    RelationDefined,
    RelationPairComparison,
    TranslatedPredicate,
    VariableDefined,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec.model import Spec
    from math_spec.resolution import Resolved


def dims_of(
    node: ParsedNode,
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
    """The recursive worker under :func:`dims_of`.

    An operator has a rule of its own and a cased entry declares its frame;
    every other branch carries the union of what is under it.
    """
    if isinstance(node, NumberNode):
        return frozenset()

    if isinstance(node, ParameterNode):
        return frozenset(schema.parameters[node.name].dims)

    if isinstance(node, VariableNode):
        return frozenset({**schema.variables, **schema.given.variables}[node.name].dims)

    if isinstance(node, UnresolvedNode | KwargNode):
        msg = f'{type(node).__name__} reached the dim checker; resolve the expression first.'
        raise AssertionError(msg)

    if isinstance(node, DualNode):
        return frozenset({**schema.constraints, **schema.given.constraints}[node.constraint].dims)

    if isinstance(node, FunctionCallNode):
        return _dims_call(node, schema, context)

    if isinstance(node, CasesNode):
        return _cases_dims(node, schema)

    if isinstance(node, UnaryOperatorNode | BinaryOperatorNode | DefinitionNode):
        return frozenset().union(*(_dims(child, schema, context) for child in children(node)))

    assert_never(node)


def _cases_dims(node: CasesNode, schema: Spec) -> frozenset[str]:
    """The declared frame rather than the union of the arms.

    A narrower arm broadcasts, as a parameter with fewer dims does.
    """
    return frozenset(schema.expressions[node.name].dims or ())


def _not_carried(context: str, call: str, inner: frozenset[str], rewrite: str) -> str:
    """The refusal for an operator reaching a dim its operand does not carry; *rewrite* is the operator's own."""
    return (
        f'{context}: {call} but the expression has dims {sorted(inner)}. An operator over a dim the '
        f'operand does not carry is a no-op that builds and solves wrong — {rewrite}.'
    )


def _dims_call(node: FunctionCallNode, schema: Spec, context: str) -> frozenset[str]:
    """The dim rule of the operator *node* calls, applied to the dims its operand carries."""
    inner = _dims(node.args[0], schema, context)
    return _CALL_RULES[node.name](node, inner, schema, context)


def _sum_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``sum`` reduces a dim away, or reads a relation: the consumed dim goes, the produced dims arrive, the joined stay."""
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
        consumed = node.kwargs['over']
        assert isinstance(consumed, DimensionNode)
        if consumed.name not in inner:
            raise DimensionError(
                _not_carried(context, f'sum(over={consumed.name})', inner, 'drop the sum, or fix the dim')
            )
        return inner - {consumed.name}

    assert isinstance(by, DirectionNode), 'resolution reads sum(by=) in a direction'
    direction = by.direction
    if missing := sorted(set(direction.consumed_dims) - inner):
        raise DimensionError(
            _not_carried(
                context,
                f'sum(by={direction.name}) consumes {missing}, the dims it reads from,',
                inner,
                'drop the sum, or fix the dim',
            )
        )
    return _read_dims(f'sum(by={direction.name})', direction, inner, context)


def _at_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``at`` is the adjoint of ``sum(by=)``: it consumes the dims a sum produces and produces the ones it consumes."""
    by = node.kwargs['by']
    assert isinstance(by, DirectionNode), 'resolution reads at(by=) in a direction'
    direction = by.direction
    if absent := sorted(set(direction.consumed_dims) - inner):
        raise DimensionError(
            f'{context}: at(by={direction.name}) reads through '
            f'{absent}, which the expression does not carry (dims '
            f'{sorted(inner)}). A pullback needs the coarse dims to read *from* — '
            f'sum is the direction that produces them.'
        )
    return _read_dims(f'at(by={direction.name})', direction, inner, context)


def _translation_dims(node: FunctionCallNode, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``shift`` and ``sum_back`` keep every dim, and their amount, edge and partition are checked here."""
    over = node.kwargs['along']
    assert isinstance(over, DimensionNode)
    if over.name not in inner:
        raise DimensionError(
            _not_carried(
                context,
                f'{node.name}(along={over.name})',
                inner,
                f'name a dim the operand carries, or drop the {node.name}',
            )
        )
    _check_named_amount(node, over.name, inner, schema, context)
    _check_amount_form(node, context)
    _check_edge(node, context)
    by = node.kwargs.get('by')
    if by is not None:
        assert isinstance(by, PartitionNode), "resolution reads a translation's by= as a partition"
        _check_joined(f'{node.name}(along={over.name}, by={by.partition.name})', by.partition, inner, context)
    return inner


def _read_dims(call: str, direction: Direction, inner: frozenset[str], context: str) -> frozenset[str]:
    """The dims after a relation is read in *direction*: the consumed go, the produced arrive, the joined stay.

    The dims a call lands on are its own to bring, so the operand does not
    already carry one. Where it does, the call would tie the operand's axis to
    the one it produces rather than adding it, and it reads the same either
    way. A relation into its own dimension is not that case: there the dim
    landed on is the dim just consumed, so every factor is read at the
    coordinate the sum runs over, and nothing is tied.
    """
    consumed, produced = set(direction.consumed_dims), set(direction.produced_dims)
    if clash := sorted((produced & inner) - consumed):
        raise DimensionError(
            f'{context}: {call} lands on {clash}, which the expression already carries.\n'
            f'A call brings the dims it lands on, so that reading it tells you what it '
            f'adds. Move the factor carrying {clash} outside the operator, or read to a column '
            f'over another dimension.'
        )
    _check_joined(call, direction, inner, context)
    return (inner - consumed) | produced


def _check_joined(call: str, use: Direction | Partition, inner: frozenset[str], context: str) -> None:
    """The columns a call joins on are read at their dimensions, so the operand carries every one, each once.

    A joined dimension the call also consumes is the same ambiguity as two
    joined columns over one dimension: the operand's one coordinate would
    have to be read as both. A partition consumes nothing.
    """
    dims = use.joined_dims
    if missing := sorted(set(dims) - inner):
        raise DimensionError(
            f'{context}: {call} joins on {missing} (columns {[r for r in use.joined if use.dim(r) in missing]} '
            f"of '{use.name}'), which the expression does not carry (dims {sorted(inner)}). A relation is "
            f'read between two of its columns and joined at the others — index the operand by them, or '
            f'read it between different columns.'
        )
    consumed = use.consumed_dims if isinstance(use, Direction) else ()
    if twice := sorted({d for d in dims if dims.count(d) > 1 or d in consumed}):
        raise DimensionError(
            f"{context}: {call} joins '{use.name}' on {twice} through more than one column, and the operand "
            f'carries each dimension once. Read between different columns, or use a relation whose joined '
            f'columns are over distinct dimensions.'
        )


#: The dim rule of each built-in, by name.
_CALL_RULES: dict[str, Callable[[FunctionCallNode, frozenset[str], Spec, str], frozenset[str]]] = {
    'sum': _sum_dims,
    'at': _at_dims,
    'shift': _translation_dims,
    'sum_back': _translation_dims,
}


class _Amount(NamedTuple):
    """What the errors of an operator that steps along an axis say about the amount it takes."""

    #: The word for the amount.
    noun: str
    #: Why negating a named one at the call site is not what the caller means.
    negated: str
    #: What a named one that varies over the axis it steps along becomes.
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
    """The kwarg an operator that steps along an axis takes its amount through, and the value written there."""
    (kwarg,) = BUILTINS[node.name].required_value_kwargs
    return kwarg, node.kwargs[kwarg]


def _whole(node: ArithmeticNode, minimum: float) -> bool:
    """Whether *node* is a literal whole number of at least *minimum*."""
    return isinstance(node, NumberNode) and int(node.value) == node.value and node.value >= minimum


def _check_amount_form(node: FunctionCallNode, context: str) -> None:
    """An ``offset=`` or ``window=`` is a whole number in the operator's range, or a parameter name."""
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
        f"  shift(x, along=d, offset=n, edge='wrap')   the dimension really is cyclic\n"
        f'  shift(x, along=d, offset=n, edge=0)        the vacated positions contribute zero\n'
        f'  ...and a where: excluding them        the vacated rows should not exist at all\n'
        f'A where: alone does not lift this — it is decided on the expression, before any mask '
        f'is read — and edge=0 alone leaves a row whose bound is that zero.'
    )


def _check_named_amount(node: FunctionCallNode, over: str, inner: frozenset[str], schema: Spec, context: str) -> None:
    """The rules that hold of an ``offset=`` or ``window=`` naming a parameter; a literal breaks none of them."""
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
            f'{context}: {node.name}({kwarg}={amount.name}) steps along '
            f"'{over}', but '{amount.name}' is declared over {sorted(declared.dims)}, which "
            f'carries it. A named {words.noun} that varies over the axis it steps along is {words.varies} '
            f"— declare '{amount.name}' over dims '{over}' is not one of."
        )
    by = node.kwargs.get('by')
    groups = (
        frozenset(by.partition.dim(v) for v in by.partition.group) if isinstance(by, PartitionNode) else frozenset()
    )
    if stray := sorted(frozenset(declared.dims) - inner - groups):
        raise DimensionError(
            f'{context}: {node.name}({kwarg}={amount.name}) reads its {words.noun} at the coordinate it '
            f"steps from, but '{amount.name}' varies over {stray}, which that coordinate does not carry "
            f'(dims {sorted(inner)}). A dim the coordinate does not have is no coordinate at all — '
            f"declare '{amount.name}' over dims the expression carries, or group by a relation into "
            f'one of {stray}, so that each group is reached by its own {words.noun}.'
        )


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


def check_schema(schema: Spec, resolved: Resolved) -> None:
    """Check every declaration's dim rules, on the trees *resolved* holds for *schema*.

    Raises:
        DimensionError: On the first declaration that breaks one.
    """
    for vname, vdef in schema.variables.items():
        frame = frozenset(vdef.dims)
        context = f"Variable '{vname}'"
        _check_where_dims(resolved.variables[vname], frame, context)
        for side in ('lower', 'upper'):
            bound = getattr(vdef.bounds, side)
            if isinstance(bound, str):
                bdims = frozenset(schema.parameters[bound].dims)
                if not bdims <= frame:
                    raise DimensionError(
                        f"{context}: bounds.{side} parameter '{bound}' has dims "
                        f"{sorted(bdims - frame)} outside the variable's dims "
                        f'{sorted(frame)}.'
                    )

    for ename, node in resolved.expressions.items():
        if not isinstance(node, CasesNode):
            continue
        frame = frozenset(schema.expressions[ename].dims or [])
        for arm in node.arms:
            context = case_context(ename, None if arm.when is None else arm.label)
            if arm.when is not None:
                _check_where_dims(Mask(arm.when), frame, context)
            _check_value_dims(arm.value, schema, frame, context)

    for cname, (expression, where) in resolved.constraints.items():
        frame = frozenset(schema.constraints[cname].dims)
        context = f"Constraint '{cname}'"
        _check_where_dims(where, frame, context)
        got = dims_of(expression, schema, context)
        if got != frame:
            stray, missing = sorted(got - frame), sorted(frame - got)
            detail = (
                f'carries dims {stray} that are not in its dims: {sorted(frame)} — every '
                f'stray dim multiplies the rows this constraint builds; add it to '
                f'dims: if that is intended, or sum it out'
                if stray
                else f'does not carry {missing}, which its dims: declares — the same row '
                f'would be repeated across {missing}; drop it from dims:, or use it '
                f'in the expression'
            )
            raise DimensionError(f'{context}: the expression {detail}.')

    if resolved.objective is not None:
        context = 'The objective'
        got = dims_of(resolved.objective, schema, context)
        if got:
            raise DimensionError(
                f'{context}: the expression carries dims {sorted(got)}, and an objective is one '
                f'number. Wrap each additive term in its own sum(): '
                f'`sum(p * cost) + sum(p_nom * capex)`.'
            )


def _check_value_dims(node: ArithmeticNode, schema: Spec, frame: frozenset[str], context: str) -> None:
    """A region's value may only carry dims the frame does — the ``otherwise:`` included.

    A wider one would give the quantity dims its declaration does not, which is
    the second answer a ``dims:`` exists to avoid.
    """
    got = dims_of(node, schema, context)
    if not got <= frame:
        raise DimensionError(
            f'{context}: the value carries dims {sorted(got - frame)} outside the dims: '
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
            case ParameterDefined() | ParameterComparison():
                leaf = f"where-parameter '{atom.name}'"
            case VariableDefined():
                leaf = f"where-variable '{atom.name}'"
            case DimensionComparison() | DimensionPosition():
                leaf = f"where-dimension '{atom.name}'"
            case RelationComparison() | RelationPairComparison() | RelationDefined():
                leaf = f"where-relation '{atom.name}'"
            case ArithmeticComparison() | ExpressionComparison():
                leaf = 'a where-comparison of expressions'
            case CountComparison():
                leaf = f"a where-count over '{atom.over}'"
            case TranslatedPredicate():
                leaf = f"a where-predicate translated along '{atom.along}'"
            case _:
                assert_never(atom)
        raise DimensionError(
            f'{context}: {leaf} reads dims {outside} outside the frame {sorted(frame)}. '
            f'Reducing a mask over an unlisted dim would silently widen it — add the dim to dims:, '
            f'or test a name the frame carries.'
        )
