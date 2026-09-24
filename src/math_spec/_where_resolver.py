# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The where walk of name resolution: a parsed where string into the program's typed predicates.

A bare name, a comparison, a count and a predicate read through a relation
or along a dimension are each typed here against the namespace, and a
comparison of expressions hands its sides to the expression walk.
:mod:`math_spec.resolution` holds the namespace and the doors that call this.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, assert_never, cast

import math_spec.degree as degree
from math_spec._expression_parser import (
    ArithmeticNode,
    FunctionCallNode,
    KeywordNode,
    NameListNode,
    NameNode,
    literal_number,
    names_in,
    nodes,
)
from math_spec._expression_resolver import ExpressionResolver
from math_spec._where_parser import (
    ColumnNode,
    UnresolvedComparisonNode,
    UnresolvedCountNode,
    UnresolvedPredicateCallNode,
    UnresolvedWhereNode,
)
from math_spec.dimensions import dims_of, pulled_back_dims
from math_spec.errors import DimensionError, LanguageError, did_you_mean, prefixed
from math_spec.expansion import expand
from math_spec.operators import (
    PARTITION_NAMES_ITS_GROUP,
)
from math_spec.program import (
    Add,
    And,
    BooleanLiteral,
    Constant,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Direction,
    Divide,
    Expression,
    ExpressionComparison,
    Mask,
    Multiply,
    Negate,
    Not,
    Or,
    ParameterComparison,
    ParameterDefined,
    Power,
    Predicate,
    PredicateOperator,
    PulledBackPredicate,
    RelationComparison,
    RelationDefined,
    RelationPairComparison,
    TranslatedPredicate,
    TypedPredicate,
    VariableDefined,
    carries_variable,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.program import DeclaredDtype
    from math_spec.resolution import Namespace


@dataclass(frozen=True)
class WhereResolver:
    """One resolution walk over a where string, and the things every step of it reads.

    A node that cannot be typed comes back unresolved with its refusal
    appended to ``errors``; every sibling is still read, so a mask with two
    faults reports both. ``self_variable`` is the variable whose own
    ``where`` is being read, which may not ask whether it exists. A side
    that is an expression is built by an :class:`ExpressionResolver` over
    the same namespace.
    """

    ns: Namespace
    context: str
    errors: list[str]
    self_variable: str | None = None

    @property
    def _expressions(self) -> ExpressionResolver:
        return ExpressionResolver(self.ns, self.context, self.errors)

    def where(self, node: Predicate | UnresolvedWhereNode) -> Predicate | UnresolvedWhereNode:
        """One predicate node typed, or returned unresolved with its refusal appended."""
        if isinstance(node, BooleanLiteral | TypedPredicate):
            return node
        if isinstance(node, NameNode):
            return self._where_name(node)
        if isinstance(node, UnresolvedComparisonNode):
            return self._comparison(node)
        if isinstance(node, UnresolvedPredicateCallNode):
            return self._predicate_call(node)
        if isinstance(node, UnresolvedCountNode):
            return self._count(node)
        if isinstance(node, Not):
            return Not(self._child(node.operand))
        if isinstance(node, And):
            return And(self._child(node.left), self._child(node.right))
        if isinstance(node, Or):
            return Or(self._child(node.left), self._child(node.right))
        assert_never(node)

    def _child(self, node: Predicate | UnresolvedWhereNode) -> Predicate:
        """A connective's child, typed as resolved: an unresolved one survives only with its refusal appended."""
        return cast('Predicate', self.where(node))

    def _where_name(self, node: NameNode) -> Predicate | UnresolvedWhereNode:
        """A bare name: a parameter's or relation's definedness, or a variable's existence."""
        ns, context = self.ns, self.context
        kind = ns.kind(node.name)
        if kind is None:
            self.errors.append(ns.unknown(node.name, context, allow_dims=True))
            return node
        match kind:
            case 'parameter':
                return ParameterDefined(node.name, ns.leaf_dims[node.name])
            case 'dimension':
                self.errors.append(
                    f"{context}: '{node.name}' is a dimension, and a bare dimension "
                    f'name is true at every coordinate — the mask has no effect. '
                    f'Remove it, or compare it: where: "{node.name} > 0".'
                )
            case 'relation':
                shape = ns.relations[node.name]
                dims = tuple(shape.dim(k) for k in shape.key)
                if len(set(dims)) < len(dims):
                    self.errors.append(
                        f"{context}: '{node.name}' has two columns over one dimension ({list(shape.roles)}), so a "
                        f'bare name cannot say which the frame supplies. Compare a column: '
                        f'{node.name}.{shape.values[0] if shape.values else shape.roles[-1]} == ....'
                    )
                    return node
                return RelationDefined(node.name, dims)
            case 'variable':
                if node.name == self.self_variable:
                    self.errors.append(
                        f"{context}: variable '{node.name}' asks whether it exists in its own "
                        f'where, which nothing can answer — the mask is what decides where it '
                        f'exists. Test a parameter, or another variable declared before it.'
                    )
                else:
                    return VariableDefined(node.name, ns.leaf_dims[node.name])
        return node

    def _predicate_call(self, node: UnresolvedPredicateCallNode) -> Predicate | UnresolvedWhereNode:
        """``shift(<predicate>, along=, offset=)`` or ``at(<predicate>, by=, over=, into=)`` — the two operators that read a predicate and answer one.

        ``count`` answers a number, so it stands on a comparison's side and
        :meth:`_count` reads it there. Anything else naming a predicate is
        refused here rather than resolved into arithmetic it cannot be.

        An operand that failed to resolve is handed straight back: resolution
        collects problems rather than raising, and asking an unresolved
        predicate for its dims asserts instead of refusing.
        """
        context, found = self.context, len(self.errors)
        if node.name == 'count':
            self.errors.append(
                f'{context}: count() answers a number, and a where is a predicate. Compare it: '
                f'count(<predicate>, over=<dimension>) <op> <integer>.'
            )
            return node
        if node.name not in ('shift', 'at'):
            self.errors.append(
                f"{context}: '{node.name}()' does not read a predicate. `shift` and `at` read one and answer "
                f'one, `count` reads one and answers a number, and every other operator reads arithmetic. '
                f'Compare the predicate, or name a parameter carrying it.'
            )
            return node
        operand = self._child(node.operand)
        if len(self.errors) > found:
            return node
        if node.name == 'at':
            return self._pulled_back(node, Mask(operand))
        if (refusal := _kwargs_error(context, 'shift', node.kwargs, required=('along', 'offset'))) is not None:
            self.errors.append(refusal)
            return node
        along = node.kwargs['along']
        offset = literal_number(node.kwargs['offset'])
        if not isinstance(along, NameNode) or self.ns.kind(along.name) != 'dimension':
            self.errors.append(
                f'{context}: shift(<predicate>, along=) names the dimension the predicate is read back along. '
                f'Name a declared dimension.'
            )
            return node
        if offset is None or not offset.value.is_integer():
            self.errors.append(
                f'{context}: shift(<predicate>, offset=) counts whole coordinates back along '
                f"'{along.name}'. Write an integer."
            )
            return node
        mask = Mask(operand)
        if along.name not in mask.dims:
            self.errors.append(
                f"{context}: shift(<predicate>, along='{along.name}') reads the predicate back along a dimension "
                f'it does not carry — it reads {_listed(sorted(mask.dims))}. Translate it along one of those.'
            )
            return node
        return TranslatedPredicate(mask, along.name, int(offset.value), tuple(sorted(mask.dims)))

    def _pulled_back(self, node: UnresolvedPredicateCallNode, mask: Mask) -> Predicate | UnresolvedWhereNode:
        """``at(<predicate>, by=, over=, into=)`` — the predicate read through a relation, as ``at`` reads an array.

        The relation and its two ends are read by the rules an expression's
        ``at`` is, so the one refusal a file meets for a bad read is the same
        in a ``where:`` and in an expression.
        """
        context = self.context
        if (refusal := _kwargs_error(context, 'at', node.kwargs, required=('by', 'over', 'into'))) is not None:
            self.errors.append(refusal)
            return node
        found = len(self.errors)
        roles = {key: node.kwargs[key] for key in ('over', 'into')}
        by = self._expressions.relation_ref(node.kwargs['by'], 'at', 'by', roles, None)
        if len(self.errors) > found or not isinstance(by, Direction):
            return node
        try:
            dims = pulled_back_dims(by, mask.dims, context, 'the predicate')
        except DimensionError as refusal:
            self.errors.append(str(refusal))
            return node
        return PulledBackPredicate(mask, by, tuple(sorted(dims)))

    def _count(self, node: UnresolvedCountNode) -> Predicate | UnresolvedWhereNode:
        """``count(<predicate>, over=<dim>) <op> <integer>`` — how many coordinates the predicate admits.

        The reduction leaves every dim but ``over``, so the count is one
        number per remaining coordinate and a claim about each group needs no
        word for the group.
        """
        context, found = self.context, len(self.errors)
        operand = self._child(node.call.operand)
        if len(self.errors) > found:
            return node
        if (refusal := _kwargs_error(context, 'count', node.call.kwargs, required=('over',))) is not None:
            self.errors.append(refusal)
            return node
        over = node.call.kwargs['over']
        if not isinstance(over, NameNode) or self.ns.kind(over.name) != 'dimension':
            self.errors.append(
                f'{context}: count(<predicate>, over=) names the dimension the coordinates are counted along. '
                f'Name a declared dimension.'
            )
            return node
        value = literal_number(node.value)
        if value is None or not value.value.is_integer():
            self.errors.append(
                f'{context}: a count is a whole number of coordinates, so it is compared against one. '
                f'Write count(…, over={over.name}) {node.op} <integer>.'
            )
            return node
        if (decided := _decided_count(node.op, value.value)) is not None:
            self.errors.append(
                f'{context}: count(…, over={over.name}) {node.op} {value} holds at {decided} coordinate, because '
                f'a count is never negative. Delete the comparison, or write the bound it means.'
            )
            return node
        mask = Mask(operand)
        if over.name not in mask.dims:
            self.errors.append(
                f"{context}: count(<predicate>, over='{over.name}') counts along a dimension the predicate does "
                f'not carry — it reads {_listed(sorted(mask.dims))}. Count along one of those.'
            )
            return node
        dims = tuple(sorted(mask.dims - {over.name}))
        return CountComparison(mask, over.name, node.op, value.value, dims)

    def _comparison(self, node: UnresolvedComparisonNode) -> Predicate | UnresolvedWhereNode:
        """``side <op> side``, read for what each side is.

        A ``position()`` call on the left is the position form. A name against
        a literal or a second column is the plain form the dtype rules are
        written for, unless a side names a parameter or an ``expressions:``
        entry against the other, which is arithmetic however plain it looks.
        Everything else is a comparison of expressions.
        """
        if isinstance(node.left, FunctionCallNode) and node.left.name == 'position':
            return self._position(node.left, node)
        plain = self._plain(node)
        if plain is None:
            return self._expression_comparison(node)
        return self._plain_comparison(node, plain)

    def _plain(self, node: UnresolvedComparisonNode) -> _Plain | None:
        """The comparison as ``name <op> literal`` or ``name <op> name``, or ``None`` where the language reads it as arithmetic.

        A side that is arithmetic makes it so, and so does a name that is a
        value — a parameter or an ``expressions:`` entry — against another,
        however plain the two look.
        """
        ns = self.ns
        name, right = _side_name(node.left), node.right
        value: float | str | None
        quoted = isinstance(right, KeywordNode)
        if isinstance(right, KeywordNode):
            value = right.value
        elif isinstance(right, ColumnNode):
            value = right.shown
        elif (literal := literal_number(right)) is not None:
            value = literal.value
        else:
            value = _side_name(right)
            if value is not None and (value in ns.schema.expressions or ns.kind(value) == 'parameter'):
                return None
        if name is None or value is None or name in ns.schema.expressions:
            return None
        return _Plain(name, node.op, value, quoted)

    def _expression_comparison(self, node: UnresolvedComparisonNode) -> ExpressionComparison | UnresolvedComparisonNode:
        """``expression <op> expression``: each side expanded, typed and held to what a mask may read.

        A side is read as an expression is — macros and named expressions
        expand, every operator and dim rule applies — except that it names no
        variable and no dual, since a mask is built before either exists.
        """
        ns, context = self.ns, self.context
        found = len(self.errors)
        sides: list[Expression] = []
        for side in (node.left, node.right):
            if isinstance(side, ColumnNode | KeywordNode):
                self.errors.append(_not_arithmetic(context, side))
                continue
            if any(isinstance(n, FunctionCallNode) and n.name == 'count' for n in nodes(side)):
                self.errors.append(
                    f'{context}: count() stands on the left of its comparison, and reads a predicate rather than '
                    f'arithmetic. Write count(<predicate>, over=<dimension>) <op> <integer>.'
                )
                continue
            try:
                expanded = expand(side, ns, context)
            except ValueError as e:
                self.errors.append(prefixed(context, e))
                continue
            if (resolved := self._expressions.build(expanded)) is not None:
                sides.append(resolved)
        if len(self.errors) > found:
            return node
        assert len(sides) == 2, 'a side of a where builds or refuses, since a where holds no formal'
        dims: set[str] = set()
        for side in sides:
            if carries_variable(side):
                self.errors.append(
                    f'{context}: a where compares expressions, and one side names a variable. A where mask '
                    f'is built before variables exist — it may test parameters and dimension coordinates only.'
                )
            elif degree.calls_dual(side):
                self.errors.append(
                    f'{context}: a where compares expressions, and one side reads a dual, which only a solve '
                    f'produces. A mask is built before it — test the data instead.'
                )
            else:
                try:
                    degree.check_expression(side, context)
                    dims |= dims_of(side, ns.schema, context)
                except LanguageError as e:
                    self.errors.append(str(e))
        if len(self.errors) > found:
            return node
        left, right = sides
        if all(_is_number(side) for side in sides):
            self.errors.append(
                f"{context}: '{node.left} {node.op} {node.right}' compares two numbers, so it is decided before any "
                f'data arrives and admits every row or none. Name the parameter one side stands for, or drop '
                f'the comparison.'
            )
            return node
        return ExpressionComparison(left, node.op, right, tuple(d for d in ns.schema.dimensions if d in dims))

    def _position(
        self, call: FunctionCallNode, node: UnresolvedComparisonNode
    ) -> DimensionPosition | UnresolvedComparisonNode:
        """``position(dim[, by=relation, within=columns]) <op> i``: the name a dimension, ``by=`` a relation keyed over it."""
        ns, context = self.ns, self.context
        shape = _position_shape(call)
        if shape is None:
            self.errors.append(
                f'{context}: position() is written position(<dim>[, by=<relation>, within=<column>]), and this '
                f'call is not of that shape. It takes the dimension it counts along and nothing else beside by= and within=.'
            )
            return node
        dimension, by, into = shape
        index = None if isinstance(node.right, ColumnNode | KeywordNode) else literal_number(node.right)
        if index is None or not index.value.is_integer():
            self.errors.append(
                f'{context}: position({dimension}) is compared against an integer index, where 0 is first and a '
                f'negative number counts from the end. Write position({dimension}) {node.op} <integer>.'
            )
            return node
        position = int(index.value)
        if dimension not in ns.dimensions:
            self.errors.append(
                f"{context}: position() counts along a dimension's coordinates, and "
                f"'{dimension}' is {_declared_as(ns, dimension)}. "
                f'{did_you_mean(dimension, ns.dimensions, label="Dimensions")}'
            )
            return node
        if by is None:
            return DimensionPosition(dimension, node.op, position)
        if (problem := self._expressions.not_a_relation(by, 'position', 'by')) is not None:
            self.errors.append(problem)
            return node
        spelled = f'position({dimension}, by={by})'
        if into is None:
            self.errors.append(
                f'{context}: {spelled} leaves within= unsaid. {PARTITION_NAMES_ITS_GROUP} Write '
                f"position({dimension}, by={by}, within=<column>) — the value columns of '{by}' "
                f'are {list(ns.relations[by].values)}.'
            )
            return node
        partition = self._expressions.partition(by, 'position', dimension, into)
        if partition is None:
            return node
        return DimensionPosition(dimension, node.op, position, partition)

    def _plain_comparison(self, node: UnresolvedComparisonNode, plain: _Plain) -> Predicate | UnresolvedWhereNode:
        """``name <op> literal``, or the one structural form ``relation <op> relation``."""
        ns, context = self.ns, self.context
        value = plain.value
        left_name, _, left_column = plain.name.partition('.')
        if not plain.quoted and isinstance(value, str):
            right_name, _, right_column = value.partition('.')
            if (rhs_kind := ns.kind(right_name)) is not None:
                if rhs_kind == 'relation' and ns.kind(left_name) == 'relation':
                    left = self._relation_column(left_name, left_column or None, plain.name, plain.op)
                    right = self._relation_column(right_name, right_column or None, value, plain.op)
                    if left is None or right is None:
                        return node
                    if (refusal := _relation_pair_error(context, plain, value, ns, left, right)) is not None:
                        self.errors.append(refusal)
                        return node
                    dims = tuple(ns.relations[left_name].dim(k) for k in ns.relations[left_name].key)
                    return RelationPairComparison(left_name, left, right_name, right, plain.op, dims)
                self.errors.append(_declared_rhs_error(context, plain, value, rhs_kind))
                return node

        kind = ns.kind(left_name)
        if kind is None:
            self.errors.append(ns.unknown(left_name, context, allow_dims=True))
            return node
        if left_column and kind != 'relation':
            self.errors.append(
                f"{context}: '{plain.name}' reads a column of '{left_name}', which is {_declared_as(ns, left_name)}. "
                f'Only a relation has columns.'
            )
            return node
        column = None
        dtype: DeclaredDtype | None = None
        if kind == 'relation':
            column = self._relation_column(left_name, left_column or None, plain.name, plain.op)
            if column is None:
                return node
            dtype = ns.dtypes[ns.relations[left_name].dim(column)]
        elif kind in ('parameter', 'dimension'):
            dtype = ns.dtypes[left_name]
        if dtype is not None:
            typed = self._typed_literal(plain, dtype)
            if typed is None:
                return node
            value = typed

        match kind:
            case 'parameter':
                assert not isinstance(value, datetime.date)
                return ParameterComparison(left_name, plain.op, value, ns.leaf_dims[left_name])
            case 'dimension':
                return DimensionComparison(left_name, plain.op, value)
            case 'relation':
                assert column is not None
                shape = ns.relations[left_name]
                return RelationComparison(left_name, column, plain.op, value, tuple(shape.dim(k) for k in shape.key))
            case 'variable':
                self.errors.append(
                    f"{context}: where references variable '{left_name}'. A where "
                    f'mask is built before variables exist — it may test parameters '
                    f'and dimension coordinates only.'
                )
        return node

    def _relation_column(self, name: str, column: str | None, spelling: str, op: PredicateOperator) -> str | None:
        """The value column a where-comparison on relation *name* reads, or the refusal.

        A comparison reads one value per coordinate, so the relation is keyed
        and the column is one the key determines; unsaid, it is the one value
        column where there is exactly one.
        """
        ns, context = self.ns, self.context
        shape = ns.relations[name]
        if not shape.values:
            self.errors.append(
                f"{context}: '{spelling}' compares a column of '{name}', a bare relation — every column is in its "
                f'key — so it has no one value per coordinate to compare. Declare that column under values:, or '
                f"test the bare name — '{name}' — for whether a row exists."
            )
            return None
        if column is None:
            if len(shape.values) != 1:
                self.errors.append(
                    f"{context}: '{spelling}': '{name}' has {len(shape.values)} value columns ({list(shape.values)}), "
                    f'so say which the comparison reads: {name}.{shape.values[0] if shape.values else "..."}.'
                )
                return None
            return shape.values[0]
        if column not in shape.roles:
            self.errors.append(
                f"{context}: '{spelling}': '{column}' is not a column of '{name}', whose columns are {list(shape.roles)}."
            )
            return None
        if column in shape.key:
            self.errors.append(
                f"{context}: '{spelling}': '{column}' is a key column of '{name}', which the frame supplies rather "
                f"than reads. Compare the frame's own coordinate — {shape.dim(column)} {op} ... — or a value column."
            )
            return None
        return column

    def _typed_literal(self, node: _Plain, dtype: DeclaredDtype) -> float | str | datetime.date | None:
        """The comparison's literal, checked against the declared dtype.

        Getting it wrong is silent: polars reads a datetime column against an
        integer as an epoch offset, so ``snapshot > 0`` drops every coordinate
        before 1970 without a word (#460). Returns ``None`` once it has recorded
        an error, so the caller leaves the node unresolved.
        """
        context = self.context
        value = node.value
        text = isinstance(value, str)

        if dtype == 'datetime':
            if not text:
                self.errors.append(
                    f"{context}: '{node.name}' is a datetime dimension, so comparing it to "
                    f'{value!r} compares against the epoch — {node.name} > 0 means "after '
                    f'1970-01-01", not what it looks like. Quote an ISO date instead: '
                    f"{node.name} {node.op} '2030-01-01'."
                )
                return None
            try:
                return (
                    datetime.datetime.fromisoformat(value)
                    if _HAS_TIME.search(value)
                    else datetime.date.fromisoformat(value)
                )
            except ValueError:
                self.errors.append(
                    f"{context}: '{node.name}' is a datetime dimension and {value!r} is not an "
                    f"ISO date. Write '2030-01-01' or '2030-01-01T06:00'."
                )
                return None

        if dtype == 'str' and not text:
            self.errors.append(
                f"{context}: '{node.name}' has dtype 'str', so comparing it to the number "
                f'{value!r} matches no label. Quote it if it is one: {node.name} {node.op} '
                f"'{value:g}'."
            )
            return None
        if dtype in ('int', 'float', 'bool') and text:
            self.errors.append(
                f"{context}: '{node.name}' has dtype '{dtype}', so comparing it to the string "
                f'{value!r} matches nothing. Drop the quotes if it is a number.'
            )
            return None
        return value


#: An ISO literal carrying a time-of-day, which decides date vs datetime.
_HAS_TIME = re.compile(r'[T ]\d')


def _declared_as(ns: Namespace, name: str) -> str:
    kind = ns.kind(name)
    return f'a {kind}' if kind else 'not declared'


class _Plain(NamedTuple):
    """A where-comparison read as ``name <op> literal`` or ``name <op> name`` — the shape the dtype rules are written for.

    ``quoted`` says the right-hand side arrived in quotes, and so is a label
    rather than a name to look up.
    """

    name: str
    op: PredicateOperator
    value: float | str
    quoted: bool


def _side_name(side: ArithmeticNode | ColumnNode) -> str | None:
    """The name a side of a where-comparison spells — bare or ``relation.column`` — or ``None`` where it is arithmetic."""
    if isinstance(side, NameNode):
        return side.name
    if isinstance(side, ColumnNode):
        return side.shown
    return None


def _position_shape(call: FunctionCallNode) -> tuple[str, str | None, tuple[str, ...] | None] | None:
    """``(dim, by, within)`` off a ``position(...)`` call, or ``None`` where the call is not of that shape."""
    if len(call.args) != 1 or not isinstance(call.args[0], NameNode) or set(call.kwargs) - {'by', 'within'}:
        return None
    by, within = call.kwargs.get('by'), call.kwargs.get('within')
    if by is not None and not isinstance(by, NameNode):
        return None
    if within is not None and not isinstance(within, NameNode | NameListNode):
        return None
    into = names_in(within) if within is not None else None
    return call.args[0].name, by.name if by is not None else None, into


def _kwargs_error(
    context: str, name: str, kwargs: Mapping[str, ArithmeticNode], required: tuple[str, ...]
) -> str | None:
    """Why *kwargs* is not what *name* takes over a predicate, or ``None`` where it is.

    A predicate-reading call takes exactly the keywords named here. The
    arithmetic forms of these operators take more — an ``edge=``, a ``by=`` —
    and each is refused rather than ignored, since a predicate answers the
    vacated coordinate itself and a grouped form has nobody asking for it yet.
    """
    missing = [key for key in required if key not in kwargs]
    if missing:
        return f'{context}: {name}(<predicate>) needs {_listed([f"{key}=" for key in missing])}.'
    if extra := sorted(set(kwargs) - set(required)):
        edge = ' A predicate is false where a translation vacates, so there is no edge to state.'
        return (
            f'{context}: {name}(<predicate>) does not take {_listed([f"{key}=" for key in extra])}. '
            f'It takes {_listed([f"{key}=" for key in required])}, and nothing else.'
            f'{edge if "edge" in extra and name == "shift" else ""}'
        )
    return None


def _decided_count(op: str, value: float) -> str | None:
    """Whether comparing a count with *op* against *value* is settled by the count never being negative.

    Returns ``'every'`` where the comparison always holds, ``'no'`` where it
    never does, and ``None`` where the data decides.
    """
    if value < 0:
        return 'every' if op in ('>', '>=', '!=') else 'no'
    if value == 0 and op in ('>=', '<'):
        return 'every' if op == '>=' else 'no'
    return None


def _listed(items: list[str]) -> str:
    """``'a'``, ``'a' and 'b'``, ``'a', 'b' and 'c'`` — one rule, so every message reads the same."""
    quoted = [f"'{item}'" for item in items]
    if len(quoted) <= 1:
        return quoted[0] if quoted else 'nothing'
    return f'{", ".join(quoted[:-1])} and {quoted[-1]}'


def _is_number(side: Expression) -> bool:
    """Whether *side* is arithmetic over literals alone — a value the language can fold, and a where may not test."""
    return all(isinstance(n, Constant | Negate | Add | Multiply | Divide | Power) for n in walk(side))


def _not_arithmetic(context: str, side: ColumnNode | KeywordNode) -> str:
    """Why a relation column or a quoted label may not stand on a side of a comparison of expressions."""
    if isinstance(side, ColumnNode):
        return (
            f"{context}: '{side.shown}' is a column of a relation, which is compared against a literal or a "
            f'second column and is not read in arithmetic. Compare it on its own, or carry the value in a '
            f'parameter and test that.'
        )
    return (
        f"{context}: '{side.value}' is a quoted label, which is compared against one name. Put the name alone on "
        f'the other side, or drop the quotes if it is a number.'
    )


def _declared_rhs_error(context: str, node: _Plain, value: str, kind: str) -> str:
    """Why the right-hand side of a where-comparison may not name a variable, a relation or a dimension."""
    comparison = f"'{node.name} {node.op} {value}'"
    if kind == 'variable':
        return (
            f'{context}: {comparison} compares against variable {value!r}. '
            f'A where mask is built before variables exist.'
        )
    if kind == 'relation':
        return (
            f'{context}: {comparison} compares {node.name!r} against relation {value!r}, and a '
            f'relation is structure rather than data — a where tests values: a name against a literal, '
            f'or arithmetic over parameters. A relation stands on the right-hand side only against a '
            f'relation on the left sharing its dimension and its target.'
        )
    return (
        f'{context}: {comparison} compares against dimension {value!r}, which the RHS reads '
        f'as the literal coordinate {value!r} and so masks everything out. Comparing two '
        f'dimensions is not in the language; if {value!r} is a coordinate rather than the '
        f'dimension, rename one of the two.'
    )


def _relation_pair_error(context: str, node: _Plain, other: str, ns: Namespace, left: str, right: str) -> str | None:
    """Why two relation columns may not be compared, or ``None`` where they may.

    Both relations are read at their keys, so the keys must be over the same
    dimensions or no row carries both; and the two columns must be over one
    dimension, or no value of one is ever a value of the other. Both wrong
    answers are silent, and a build's data library decides which one.
    """
    comparison = f"'{node.name} {node.op} {other}'"
    left_name, right_name = node.name.partition('.')[0], other.partition('.')[0]
    ls, rs = ns.relations[left_name], ns.relations[right_name]
    left_keys, right_keys = {ls.dim(k) for k in ls.key}, {rs.dim(k) for k in rs.key}
    if left_keys != right_keys:
        return (
            f'{context}: {comparison} compares relations keyed over different dimensions '
            f"('{left_name}' by {sorted(left_keys)}, '{right_name}' by {sorted(right_keys)}) — there is no row "
            f'carrying both, so the comparison has nothing to test. Two relations may be compared only '
            f'where their keys are over the same dimensions.'
        )
    if ls.dim(left) != rs.dim(right):
        return (
            f"{context}: {comparison} compares '{node.name}' (a column over '{ls.dim(left)}') with "
            f"'{other}' (a column over '{rs.dim(right)}'). No value of one is ever a value of the other, so "
            f'the predicate can only mask everything out. Two columns may be compared only '
            f'where they are over the same dimension.'
        )
    return None
