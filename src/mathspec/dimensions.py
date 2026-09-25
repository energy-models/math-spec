# SPDX-FileCopyrightText: mathspec Contributors
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

from mathspec.errors import DimensionError, case_context
from mathspec.operators import AMOUNTS
from mathspec.program import (
    Add,
    Cases,
    Constant,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Direction,
    Divide,
    Dual,
    Expression,
    ExpressionComparison,
    GroupSum,
    Mask,
    Multiply,
    Named,
    Negate,
    Parameter,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Power,
    Pullback,
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
    from mathspec.program import Program
    from mathspec.spec import Spec


def dims_of(node: Expression, schema: Spec, context: str) -> frozenset[str]:
    """The dim set of a resolved expression, checking every rule on the way.

    Raises:
        DimensionError: On the first rule broken.
    """
    if isinstance(node, Constant):
        return frozenset()

    if isinstance(node, Parameter):
        return frozenset({**schema.parameters, **schema.given.parameters}[node.name].dims)

    if isinstance(node, Variable):
        return frozenset({**schema.variables, **schema.given.variables, **schema.given.expressions}[node.name].dims)

    if isinstance(node, Dual):
        return frozenset({**schema.constraints, **schema.given.constraints}[node.constraint].dims)

    if isinstance(node, Named):
        return _named_dims(node, schema, context)

    if isinstance(node, Cases):
        return frozenset().union(*(dims_of(region.value, schema, context) for region in node.regions))

    if isinstance(node, Negate | Add | Multiply | Power | Divide):
        return frozenset().union(*(dims_of(child, schema, context) for child in children(node)))

    inner = dims_of(node.operand, schema, context)
    if isinstance(node, Sum):
        return _sum_dims(node, inner, context)
    if isinstance(node, GroupSum):
        return _group_sum_dims(node, inner, context)
    if isinstance(node, Pullback):
        return _at_dims(node, inner, context)
    if isinstance(node, Translate | WindowSum):
        return _translation_dims(node, inner, schema, context)

    assert_never(node)


def _named_dims(node: Named, schema: Spec, context: str) -> frozenset[str]:
    """An entry's declared frame where it has one — a narrower arm or body broadcasts along the rest — else its body's."""
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
    for consumed in node.over:
        if consumed not in inner:
            raise DimensionError(_not_carried(context, f'sum(over={consumed})', inner, 'drop the sum, or fix the dim'))
    return inner - frozenset(node.over)


def _group_sum_dims(node: GroupSum, inner: frozenset[str], context: str) -> frozenset[str]:
    """``sum`` through a relation: the consumed dim goes, the produced dims arrive, the joined stay."""
    direction = node.direction
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


def _at_dims(node: Pullback, inner: frozenset[str], context: str) -> frozenset[str]:
    """``at`` is the adjoint of ``sum(by=)``: it consumes the dims a sum produces and produces the ones it consumes."""
    return pulled_back_dims(node.direction, inner, context, 'the expression')


def pulled_back_dims(direction: Direction, inner: frozenset[str], context: str, operand: str) -> frozenset[str]:
    """The dims *inner* has once ``at`` reads it through *direction*, an expression's or a predicate's alike.

    Raises:
        DimensionError: *operand* does not carry a dim the read consumes or
            joins on, or already carries one it lands on.
    """
    if absent := sorted(set(direction.consumed_dims) - inner):
        raise DimensionError(
            f'{context}: at(by={direction.name}) reads through '
            f'{absent}, which {operand} does not carry (dims '
            f'{sorted(inner)}). A pullback needs the coarse dims to read *from* — '
            f'sum is the direction that produces them.'
        )
    return _read_dims(f'at(by={direction.name})', direction, inner, context)


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


def _check_named_amount(
    node: Translate | WindowSum, verb: str, inner: frozenset[str], schema: Spec, context: str
) -> None:
    """The two rules of an ``offset=`` or ``window=`` naming a parameter that need the operand's dims; resolution holds it to its dtype."""
    kwarg, amount = ('offset', node.offset) if isinstance(node, Translate) else ('window', node.width)
    if not isinstance(amount, str):
        return
    words = AMOUNTS[verb]
    declared = {**schema.parameters, **schema.given.parameters}[amount]
    if node.along in declared.dims:
        raise DimensionError(
            f'{context}: {verb}({kwarg}={amount}) steps along '
            f"'{node.along}', but '{amount}' is declared over {sorted(declared.dims)}, which "
            f'carries it. A named {words.noun} that varies over the axis it steps along is {words.varies} '
            f"— declare '{amount}' over dims '{node.along}' is not one of."
        )
    groups = (
        frozenset(node.partition.dim(v) for v in node.partition.group) if node.partition is not None else frozenset()
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
                bdims = frozenset({**schema.parameters, **schema.given.parameters}[bound].dims)
                if not bdims <= frame:
                    raise DimensionError(
                        f"{context}: bounds.{side} parameter '{bound}' has dims "
                        f"{sorted(bdims - frame)} outside the variable's dims "
                        f'{sorted(frame)}.'
                    )

    for ename, entry in program.expressions.items():
        block = schema.expressions[ename]
        if block.dims is None:
            continue
        frame = frozenset(block.dims)
        if not isinstance(entry.expression, Cases):
            _check_body_dims(entry.expression, schema, frame, f"Named expression '{ename}'")
            continue
        for region, label in zip(entry.expression.regions, [*block.cases, None], strict=True):
            context = case_context(ename, label)
            if label is not None:
                _check_where_dims(region.when, frame, context)
            _check_value_dims(region.value, schema, frame, context)

    for gname, given in program.given.expressions.items():
        if given.term is None:
            continue
        context = f"Given expression '{gname}'"
        if extra := sorted(dims_of(given.term, schema, context) - set(given.dims)):
            raise DimensionError(
                f'{context}: its term carries {extra}, which its dims {list(given.dims)} do not. A term is read '
                f"over the frame the entry states: add {extra} to the entry's dims, or leave them out of the term."
            )

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


def _check_body_dims(node: Expression, schema: Spec, frame: frozenset[str], context: str) -> None:
    """A plain entry's body may only carry dims its declared frame does; fewer is constant along the rest."""
    got = dims_of(node, schema, context)
    if not got <= frame:
        raise DimensionError(
            f'{context}: the body carries dims {sorted(got - frame)} outside the dims: {sorted(frame)}. '
            f'The dims: are the frame the quantity is read over, and the body cannot widen it: add '
            f'{sorted(got - frame)} to dims:, or take them out of the body.'
        )


def _check_where_dims(
    mask: Mask | None,
    frame: frozenset[str],
    context: str,
) -> None:
    """A predicate may only test dims the frame carries; reducing an outside dim to fit would fail open.

    The refusal names the leaf that left the frame, reading its dims as
    [`dims`][mathspec.program.Mask.dims] does.
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
                leaf = f"a where-predicate read through '{atom.direction.name}'"
            case _:
                assert_never(atom)
        raise DimensionError(
            f'{context}: {leaf} reads dims {outside} outside the frame {sorted(frame)}. '
            f'Reducing a mask over an unlisted dim would silently widen it — add the dim to dims:, '
            f'or test a name the frame carries.'
        )
