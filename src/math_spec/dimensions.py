# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Static dim-set checking — a type system whose type is a set of dim names.

Every node's dim set is computable before any data is attached, so this pass runs
at load on the resolved tree. The per-node rules are the "Dim algebra" table in
``docs/reference/language/expressions.md``; a constraint's two sides together
must equal its ``dims``, and a where or a bound may not exceed the frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from math_spec.errors import DimensionError, case_context
from math_spec.operators import AMOUNTS
from math_spec.program import (
    Add,
    Cases,
    Constant,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Divide,
    Dual,
    Expression,
    ExpressionComparison,
    Join,
    JoinColumns,
    Mask,
    Multiply,
    Named,
    Negate,
    Parameter,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Power,
    PulledBackPredicate,
    RelationComparison,
    RelationDefined,
    RelationPairComparison,
    Sum,
    Translate,
    TranslatedPredicate,
    Variable,
    VariableDefined,
    WindowSum,
    children,
)

if TYPE_CHECKING:
    from math_spec.model import Spec
    from math_spec.program import Program


def dims_of(node: Expression, schema: Spec, context: str) -> frozenset[str]:
    """The dim set of a resolved expression, checking every rule on the way.

    Raises:
        DimensionError: On the first rule broken.
    """
    if isinstance(node, Constant):
        return frozenset()

    if isinstance(node, Parameter):
        return frozenset(schema.parameters[node.name].dims)

    if isinstance(node, Variable):
        return frozenset(schema.variables[node.name].dims)

    if isinstance(node, Dual):
        return frozenset(schema.constraints[node.constraint].dims)

    if isinstance(node, Named):
        return _named_dims(node, schema, context)

    if isinstance(node, Cases):
        return frozenset().union(*(dims_of(region.value, schema, context) for region in node.regions))

    if isinstance(node, Negate | Add | Multiply | Power | Divide):
        return frozenset().union(*(dims_of(child, schema, context) for child in children(node)))

    inner = dims_of(node.operand, schema, context)
    if isinstance(node, Sum):
        return _sum_dims(node, inner, context)
    if isinstance(node, Join):
        return join_dims(node.columns, inner, context, 'the expression')
    if isinstance(node, Translate | WindowSum):
        return _translation_dims(node, inner, schema, context)

    assert_never(node)


def _named_dims(node: Named, schema: Spec, context: str) -> frozenset[str]:
    """A cased entry's declared frame rather than the union of its arms — a narrower arm broadcasts — and a plain entry's body."""
    declared = schema.expressions[node.name].dims
    if declared is not None:
        return frozenset(declared)
    return dims_of(node.body, schema, context)


def _not_carried(context: str, call: str, inner: frozenset[str], rewrite: str) -> str:
    """The refusal for an operator reaching a dim its operand does not carry; *rewrite* is the operator's own."""
    return (
        f'{context}: {call} but the expression has dims {sorted(inner)}. An operator over a dim the '
        f'operand does not carry is a no-op that builds and solves wrong — {rewrite}.'
    )


def _sum_dims(node: Sum, inner: frozenset[str], context: str) -> frozenset[str]:
    """``sum`` reduces each named dim away, so the operand carries every one."""
    for summed in node.over:
        if summed not in inner:
            raise DimensionError(_not_carried(context, f'sum(over={summed})', inner, 'drop the sum, or fix the dim'))
    return inner - frozenset(node.over)


def join_dims(columns: JoinColumns, inner: frozenset[str], context: str, operand: str) -> frozenset[str]:
    """The dims *inner* has once *columns* joins it, an expression's or a predicate's alike.

    The dims joined on go, the dims grouped by arrive, and each column joined
    on and not grouped by opens its own axis (:attr:`JoinColumns.axes`), which
    the :class:`~math_spec.program.Sum` over the join takes away. A column
    both joined on and grouped by keeps its dim. The call a refusal quotes is
    ``at`` where each group is one row, and ``sum`` otherwise.

    Raises:
        DimensionError: *operand* does not carry a dim the call joins on, or
            already carries one the call adds.
    """
    lookup = columns.one_row_per_group
    call = f'{"at" if lookup else "sum"}(by={columns.name})'
    if missing := sorted(set(columns.dropped_dims) - inner):
        if lookup:
            raise DimensionError(
                f'{context}: {call} joins on {missing}, which {operand} does not carry (dims '
                f'{sorted(inner)}). A lookup joins the operand on the columns it reads at — '
                f'sum is the call that groups by them.'
            )
        raise DimensionError(
            _not_carried(context, f'{call} joins on {missing} to sum it away,', inner, 'drop the sum, or fix the dim')
        )
    added, dropped = set(columns.added_dims), set(columns.dropped_dims)
    if clash := sorted((added & inner) - dropped):
        raise DimensionError(
            f'{context}: {call} groups by {clash}, which the expression already carries.\n'
            f'A join on a column the operand carries matches it rather than grouping by it, so a '
            f'call brings the dims it groups by. Move the factor carrying {clash} outside the operator, '
            f'or group by a column over another dimension.'
        )
    _check_joined(call, columns, inner, context)
    return (inner - set(columns.joined_dims)) | set(columns.grouped_dims) | set(columns.axes)


#: The verb a file writes each translation with, which its refusals quote.
_VERBS: dict[type[Translate | WindowSum], str] = {Translate: 'shift', WindowSum: 'sum_back'}


def _translation_dims(node: Translate | WindowSum, inner: frozenset[str], schema: Spec, context: str) -> frozenset[str]:
    """``shift`` and ``sum_back`` keep every dim, and a named amount and a partition are checked here."""
    verb = _VERBS[type(node)]
    if node.along not in inner:
        raise DimensionError(
            _not_carried(
                context,
                f'{verb}(along={node.along})',
                inner,
                f'name a dim the operand carries, or drop the {verb}',
            )
        )
    _check_named_amount(node, verb, inner, schema, context)
    if node.partition is not None:
        _check_joined(f'{verb}(along={node.along}, by={node.partition.name})', node.partition, inner, context)
    return inner


def _check_joined(call: str, use: JoinColumns | Partition, inner: frozenset[str], context: str) -> None:
    """The columns a call joins on are matched at their dimensions, so the operand carries every one, each once.

    Two joined columns over one dimension would match the operand's one
    coordinate twice: the ``over=`` column and an unnamed key column, or two
    unnamed key columns. A partition joins on the key columns it does not
    step along.
    """
    dims = use.joined_dims
    if missing := sorted(set(dims) - inner):
        raise DimensionError(
            f'{context}: {call} joins on {missing} (columns {[r for r in use.joined if use.dim(r) in missing]} '
            f"of '{use.name}'), which the expression does not carry (dims {sorted(inner)}). A join matches "
            f'the operand on every key column the call does not name — index the operand by them, or '
            f'name them in the call.'
        )
    if twice := sorted({d for d in dims if dims.count(d) > 1}):
        raise DimensionError(
            f"{context}: {call} joins '{use.name}' on {twice} through more than one column, and the operand "
            f'carries each dimension once. Join on distinct dimensions, or use a relation whose key '
            f'columns are over distinct dimensions.'
        )


def _check_named_amount(
    node: Translate | WindowSum, verb: str, inner: frozenset[str], schema: Spec, context: str
) -> None:
    """The two rules of an ``offset=`` or ``window=`` naming a parameter that need the operand's dims; resolution holds it to its dtype."""
    kwarg, amount = ('offset', node.offset) if isinstance(node, Translate) else ('window', node.width)
    if not isinstance(amount, str):
        return
    words = AMOUNTS[verb]
    declared = schema.parameters[amount]
    if node.along in declared.dims:
        raise DimensionError(
            f'{context}: {verb}({kwarg}={amount}) steps along '
            f"'{node.along}', but '{amount}' is declared over {sorted(declared.dims)}, which "
            f'carries it. A named {words.noun} that varies over the axis it steps along is {words.varies} '
            f"— declare '{amount}' over dims '{node.along}' is not one of."
        )
    groups = (
        frozenset(node.partition.dim(v) for v in node.partition.grouped) if node.partition is not None else frozenset()
    )
    if stray := sorted(frozenset(declared.dims) - inner - groups):
        raise DimensionError(
            f'{context}: {verb}({kwarg}={amount}) reads its {words.noun} at the coordinate it '
            f"steps from, but '{amount}' varies over {stray}, which that coordinate does not carry "
            f'(dims {sorted(inner)}). A dim the coordinate does not have is no coordinate at all — '
            f"declare '{amount}' over dims the expression carries, or group by a relation into "
            f'one of {stray}, so that each group is reached by its own {words.noun}.'
        )


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


def check_schema(schema: Spec, program: Program) -> None:
    """Check every declaration's dim rules, on the trees *program* holds for *schema*.

    Raises:
        DimensionError: On the first declaration that breaks one.
    """
    for vname, vdef in schema.variables.items():
        frame = frozenset(vdef.dims)
        context = f"Variable '{vname}'"
        _check_where_dims(program.variables[vname].where, frame, context)
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

    for ename, entry in program.expressions.items():
        if not isinstance(entry.expression, Cases):
            continue
        block = schema.expressions[ename]
        frame = frozenset(block.dims or [])
        for region, label in zip(entry.expression.regions, [*block.cases, None], strict=True):
            context = case_context(ename, label)
            if label is not None:
                _check_where_dims(region.when, frame, context)
            _check_value_dims(region.value, schema, frame, context)

    for cname, constraint in program.constraints.items():
        frame = frozenset(constraint.dims)
        context = f"Constraint '{cname}'"
        _check_where_dims(constraint.where, frame, context)
        got = dims_of(constraint.lhs, schema, context) | dims_of(constraint.rhs, schema, context)
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

    if program.objective is not None:
        context = 'The objective'
        got = dims_of(program.objective.expression, schema, context)
        if got:
            raise DimensionError(
                f'{context}: the expression carries dims {sorted(got)}, and an objective is one '
                f'number. Wrap each additive term in its own sum(): '
                f'`sum(p * cost) + sum(p_nom * capex)`.'
            )


def _check_value_dims(node: Expression, schema: Spec, frame: frozenset[str], context: str) -> None:
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
            case ExpressionComparison():
                leaf = 'a where-comparison of expressions'
            case CountComparison():
                leaf = f"a where-count over '{atom.over}'"
            case TranslatedPredicate():
                leaf = f"a where-predicate translated along '{atom.along}'"
            case PulledBackPredicate():
                leaf = f"a where-predicate read through '{atom.columns.name}'"
            case _:
                assert_never(atom)
        raise DimensionError(
            f'{context}: {leaf} reads dims {outside} outside the frame {sorted(frame)}. '
            f'Reducing a mask over an unlisted dim would silently widen it — add the dim to dims:, '
            f'or test a name the frame carries.'
        )
