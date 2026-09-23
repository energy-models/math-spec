# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Name resolution — the pass that reads the syntax tree into the program vocabulary.

The grammars emit bare names and calls; this module builds the
:mod:`math_spec.program` node each stands for, so every pass after — the dim
rules, the degree rules, the typesetter, lowering — reads one vocabulary. The
rules live in the language reference.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Literal, NamedTuple, assert_never, cast

import math_spec.degree as degree
from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    KeywordNode,
    NameListNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    nodes,
    shown,
)
from math_spec._where_parser import (
    ColumnNode,
    UnresolvedComparisonNode,
    UnresolvedCountNode,
    UnresolvedPredicateCallNode,
    UnresolvedWhereNode,
    parse_where,
)
from math_spec.dimensions import dims_of, pulled_back_dims
from math_spec.errors import DimensionError, LanguageError, SchemaError, case_context, did_you_mean, prefixed
from math_spec.exclusivity import overlapping
from math_spec.expansion import expand, parse_and_expand
from math_spec.model import NUMERIC_DTYPES
from math_spec.operators import (
    AMOUNTS,
    BUILTINS,
    EDGE_WRAP,
    PARTITION_NAMES_ITS_GROUP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.program import (
    Add,
    And,
    BooleanLiteral,
    Cases,
    Constant,
    ConstraintDeclaration,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Direction,
    Divide,
    Dual,
    Expression,
    ExpressionComparison,
    GroupSum,
    Holds,
    Mask,
    Multiply,
    Named,
    Negate,
    Not,
    ObjectiveDeclaration,
    Or,
    Parameter,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Power,
    Predicate,
    PredicateOperator,
    Pullback,
    PulledBackPredicate,
    Region,
    RelationComparison,
    RelationDeclaration,
    RelationDefined,
    RelationPairComparison,
    Sum,
    Translate,
    TranslatedPredicate,
    TypedPredicate,
    Variable,
    VariableDefined,
    WindowSum,
    carries_variable,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from math_spec._expression_parser import ComparisonOperator
    from math_spec.model import DeclaredDtype, ExpressionBlock, Spec


#: What a name a file may write turns out to be. Answered by
#: :meth:`Namespace.kind`, so a pass reading a name switches over this rather
#: than over the stores it would otherwise have to try in order.
DeclarationKind = Literal['variable', 'parameter', 'dimension', 'relation']

#: An ``edge=`` as a translation carries it: whether it wraps, and the number
#: the vacated positions contribute where it does not.
_Edge = tuple[bool, float | None]


class Namespace:
    """The declared names of one schema, by kind — the whole of what a file may name, read once.

    A name has one kind: model.py refuses one declared under two sections.
    """

    __slots__ = (
        '_loading',
        '_named',
        'constraints',
        'dimensions',
        'dtypes',
        'leaf_dims',
        'parameters',
        'relations',
        'schema',
        'variables',
    )

    def __init__(self, schema: Spec) -> None:
        #: The schema the names come from — what an expression is expanded and
        #: dim-checked against, since macros, named expressions and the dim
        #: rules read declarations the flat listing below does not carry.
        self.schema = schema
        self.variables = frozenset(schema.variables)
        self.parameters = frozenset(schema.parameters)
        self.dimensions = frozenset(schema.dimensions)
        #: The declared constraint names, off the flat namespace: a bare name
        #: never reaches them, so a model may name a constraint after a variable.
        #: Consulted only in ``dual()``'s argument position.
        self.constraints = frozenset(schema.constraints)
        #: name -> declared dtype, for dimensions, parameters and relations alike;
        #: what a where comparison checks its literal against.
        self.dtypes: dict[str, DeclaredDtype] = {
            **{p: pd.dtype for p, pd in schema.parameters.items()},
            **{d: dd.dtype for d, dd in schema.dimensions.items()},
        }
        #: relation name -> its columns and key, as declared.
        self.relations: dict[str, RelationDeclaration] = {
            n: RelationDeclaration(lk.pairs, lk.key_roles) for n, lk in schema.relations.items()
        }
        #: parameter or variable name -> the dims it is read through —
        #: parameters by their ``dims``, variables by their frame. Stamped onto
        #: each leaf a where names, the way a relation leaf carries ``over``.
        self.leaf_dims: dict[str, tuple[str, ...]] = {
            **{p: tuple(pd.dims) for p, pd in schema.parameters.items()},
            **{v: tuple(vd.dims) for v, vd in schema.variables.items()},
        }
        #: named expression -> its resolved node, or ``None``, and its refusals;
        #: filled the first time anything reads the name.
        self._named: dict[str, tuple[Named | None, tuple[str, ...]]] = {}
        #: The named expressions being resolved, outermost first — a cycle's chain.
        self._loading: list[str] = []

    def named(self, name: str, context: str) -> Named:
        """The ``expressions:`` entry *name* as the node that stands where its name is written.

        Resolved under the entry's own context the first time it is asked
        for, and read from then on, so a fault in it is reported once.

        Raises:
            SchemaError: The entry reads itself, or does not load.
        """
        if name in self._loading:
            chain = ' -> '.join([*self._loading[self._loading.index(name) :], name])
            msg = f'{context}: circular expression reference: {chain}'
            raise SchemaError(msg)
        node, _ = self.named_entry(name)
        if node is None:
            msg = f"{context}: named expression '{name}' does not load. Its refusal is listed with it."
            raise SchemaError(msg)
        return node

    def named_entry(self, name: str) -> tuple[Named | None, tuple[str, ...]]:
        """The ``expressions:`` entry *name* resolved, or ``None``, with every refusal it earned."""
        if name not in self._named:
            errors: list[str] = []
            self._loading.append(name)
            try:
                node = _named(name, self.schema.expressions[name], self, errors)
            finally:
                self._loading.pop()
            self._named[name] = (node, tuple(errors))
        return self._named[name]

    def kind(self, name: str) -> DeclarationKind | None:
        """What *name* was declared as, or ``None`` where the file declares it nowhere."""
        if name in self.variables:
            return 'variable'
        if name in self.parameters:
            return 'parameter'
        if name in self.dimensions:
            return 'dimension'
        if name in self.relations:
            return 'relation'
        return None

    def unknown(self, name: str, context: str, *, allow_dims: bool, formals: Iterable[str] = ()) -> str:
        """The refusal for a *name* declared nowhere, listing what it could have been.

        Args:
            name: The name the file wrote.
            context: The declaration it was found in.
            allow_dims: Whether a dimension would have been accepted there. It marks a
                where string, which reads a relation as readily as a parameter, so the
                listing carries the relations too; an expression, where a relation is not a
                value, lists the variables instead.
            formals: A macro's formals, listed first when there are any.
        """
        shown: list[tuple[str, Iterable[str]]] = [('Formals', formals)] if formals else []
        shown += (
            [('Parameters', self.parameters), ('Dimensions', self.dimensions), ('Relations', self.relations)]
            if allow_dims
            else [('Variables', self.variables), ('Parameters', self.parameters)]
        )
        listing = '\n'.join(f'  {kind}: {sorted(names)}' for kind, names in shown)
        return f"{context}: '{name}' not found.\n{listing}\nCheck for typos, or ensure '{name}' is declared."

    def unknown_constraint(self, name: str, context: str, *, formals: Iterable[str] = ()) -> str:
        """The refusal for a ``dual(name)`` naming no constraint — nor, inside a template, a formal."""
        also = ' or a formal of this macro' if formals else ''
        return (
            f"{context}: dual({name}): '{name}' is not a declared constraint{also}.\n"
            f'  Constraints: {sorted(self.constraints)}\n'
            f"Check for typos, or declare '{name}' under 'constraints:'."
        )


@dataclass(frozen=True)
class Resolved:
    """Every expression and where string of one schema, typed once at load, in the program's own vocabulary.

    :func:`~math_spec.validation.validate_expressions` builds it, and every
    reader after — the dim rules, lowering, the typesetter — walks these trees
    rather than parsing, expanding and resolving the text again. Each mapping
    is keyed as the schema's own section is. A ``where`` the file did not
    write, or one every row passes, is ``None``. What a program does not carry
    is here alone: every use of an ``expressions:`` entry stands as the
    :class:`~math_spec.program.Named` node resolution built for it, which
    lowering inlines.

    Attributes:
        expressions: Each ``expressions:`` entry as the node every use of it
            holds — a plain entry's body, or a cased one's
            :class:`~math_spec.program.Cases` with every region's mask typed
            and the ``otherwise`` carrying the negation of the rest.
        variables: Each variable's ``where``.
        constraints: Each constraint, as a program declares it.
        objective: The objective, ``None`` where the file declares none.
        relations: Each relation's columns and key, as declared — the one
            copy, which every :class:`~math_spec.program.Direction` and
            :class:`~math_spec.program.Partition` in the trees holds.
        assumptions: Each ``assumptions:`` entry's predicate and the mask it
            is checked under.
        piecewise: Each ``piecewise:`` block's link expressions, in link order.
    """

    expressions: dict[str, Named]
    variables: dict[str, Mask | None]
    constraints: dict[str, ConstraintDeclaration]
    objective: ObjectiveDeclaration | None
    relations: dict[str, RelationDeclaration]
    assumptions: dict[str, Holds]
    piecewise: dict[str, tuple[Expression, ...]]

    @cached_property
    def read_by_the_math(self) -> frozenset[str]:
        """The named expressions the math reads: every entry the objective, a constraint or a curve reaches, transitively.

        Read off those three positions alone: a bound and a ``where`` name no
        entry. The rest of the ``expressions:`` section is read back after a
        solve and never fed to one
        (:attr:`~math_spec.program.ExpressionDeclaration.in_math`). A curve
        counts because it states rows, so the answer does not move when the
        curve is written out (:meth:`~math_spec.model.Spec.expand`).
        """
        roots = [side for constraint in self.constraints.values() for side in (constraint.lhs, constraint.rhs)]
        if self.objective is not None:
            roots.append(self.objective.expression)
        roots.extend(link for links in self.piecewise.values() for link in links)
        return frozenset(node.name for node in walk(*roots) if isinstance(node, Named))


# ---------------------------------------------------------------------------
# the seam the rest of the package uses
# ---------------------------------------------------------------------------


def names_in(value: ArithmeticNode) -> tuple[str, ...]:
    """The names a relation kwarg carries: one bare, several bracketed, none otherwise."""
    if isinstance(value, NameNode):
        return (value.name,)
    return value.names if isinstance(value, NameListNode) else ()


def mask_of(node: Predicate | None) -> Mask | None:
    """The mask a declaration carries for a resolved where: ``None`` where there is none, or where every row passes."""
    if node is None or (isinstance(node, BooleanLiteral) and node.value):
        return None
    return Mask(node)


def remainder(masks: Iterable[Mask]) -> Mask:
    """The region left over: where not one of *masks* holds.

    The ``otherwise`` arm's own mask, built rather than written. ``cases:``
    carries at least one case, so there is no vacuous truth to spell.
    """
    first, *rest = masks
    left = ~first
    for mask in rest:
        left = left & ~mask
    return left


# ---------------------------------------------------------------------------
# expressions
# ---------------------------------------------------------------------------


def resolve_expression(
    node: ArithmeticNode,
    ns: Namespace,
    context: str,
    errors: list[str],
    *,
    formals: frozenset[str] = frozenset(),
) -> Expression | None:
    """Build the program tree *node* stands for, checking every name and operator call shape on the way.

    Returns:
        The tree, or ``None`` once anything failed — appending to *errors*
        rather than raising, so a caller collecting problems across a whole
        schema reports them together. Also ``None``, with nothing appended,
        where a name in *formals* stands under *node*: a macro template is
        checked by the rules a call site is before anything calls it, and
        only the call site that binds its formals has a tree to build.
    """
    before = len(errors)
    resolved = _Resolver(ns, context, errors, formals=formals).arith(node)
    return None if len(errors) > before else resolved


def resolve_where(
    node: Predicate | UnresolvedWhereNode,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> Predicate | None:
    """Rewrite a parsed where AST into typed predicates, folded as :class:`~math_spec.program.Mask` folds.

    Returns:
        The typed tree — a mask admitting every row or none comes back as the
        one ``BooleanLiteral`` — or ``None`` once anything failed, with the
        problems appended to *errors*.
    """
    before = len(errors)
    resolved = _Resolver(ns, context, errors, self_variable).where(node)
    return None if len(errors) > before else Mask(cast('Predicate', resolved)).root


def resolve_where_text(
    text: str | None,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> Predicate | None:
    """Parse and resolve one where string as :func:`resolve_where` does, a parse failure appended to *errors*.

    Returns:
        ``None`` where there is no mask to read, and where reading it failed.
    """
    if text is None:
        return None
    try:
        node = parse_where(text)
    except ValueError as e:
        errors.append(f'{context}: {e}')
        return None
    return resolve_where(node, ns, context, errors, self_variable)


def resolve_expression_text(
    text: str, ns: Namespace, context: str, errors: list[str], *, ceiling: int | None
) -> Expression | None:
    """Parse, expand, resolve and degree-check one expression string that stands for a value.

    *ceiling* is the degree the position honours, and ``None`` for an
    ``expressions:`` entry's body: what the math admits
    (:func:`~math_spec.degree.check_expression`) is a rule about the position
    that *reads* it, so it fires on the expanded tree of every objective and
    piecewise link, and not where an entry is declared. A constraint is
    :func:`resolve_constraint_text`'s.

    Returns:
        The typed tree, or ``None`` once anything failed, the problem appended
        to *errors*.
    """
    ast = _parsed(text, ns, context, errors)
    if ast is None:
        return None
    if isinstance(ast, ComparisonNode):
        errors.append(f'{context}: expression must not contain a comparison operator.\nGot: {text!r}')
        return None
    resolved = resolve_expression(ast, ns, context, errors)
    if resolved is None or ceiling is None:
        return resolved
    return None if _over_the_ceiling(resolved, context, errors, ceiling=ceiling) else resolved


def resolve_constraint_text(
    text: str, ns: Namespace, context: str, errors: list[str]
) -> tuple[Expression, ComparisonOperator, Expression] | None:
    """Parse, expand, resolve and degree-check one constraint string: exactly one comparison, a variable on a side (#1171).

    Returns:
        The two sides and the sense between them, or ``None`` once anything
        failed, the problem appended to *errors*.
    """
    ast = _parsed(text, ns, context, errors)
    if ast is None:
        return None
    if not isinstance(ast, ComparisonNode):
        errors.append(
            f'{context}: expression must contain exactly one comparison operator (<=, >=, ==).\nGot: {text!r}'
        )
        return None
    found = len(errors)
    resolver = _Resolver(ns, context, errors)
    left, right = resolver.arith(ast.left), resolver.arith(ast.right)
    if len(errors) > found or left is None or right is None:
        return None
    if any(_over_the_ceiling(side, context, errors, ceiling=2) for side in (left, right)):
        return None
    if not (carries_variable(left) or carries_variable(right)):
        errors.append(
            f'{context}: neither side of the comparison carries a variable, so the row decides nothing.\n'
            f'Got: {text!r}\n'
            f'A constraint is a claim about a decision, and a comparison of numbers and parameters '
            f'is settled before the solve — no consumer builds a row for it. Name the variable it should '
            f'bound, or state the fact under `assumptions:`, where the consumer binding the data checks it.'
        )
        return None
    return left, ast.op, right


def _parsed(text: str, ns: Namespace, context: str, errors: list[str]) -> ComparisonNode | ArithmeticNode | None:
    """*text* parsed and its macros expanded, or ``None`` with the refusal appended."""
    try:
        return parse_and_expand(text, ns, context)
    except ValueError as e:
        errors.append(prefixed(context, e))
        return None


def _over_the_ceiling(node: Expression, context: str, errors: list[str], *, ceiling: int) -> bool:
    """Whether *node* breaks the degree rules at *ceiling*, the refusal appended."""
    try:
        degree.check_expression(node, context, ceiling=ceiling)
    except LanguageError as e:
        errors.append(str(e))
        return True
    return False


def _named(name: str, block: ExpressionBlock, ns: Namespace, errors: list[str]) -> Named | None:
    """One ``expressions:`` entry as the node every use of it holds, or ``None`` once anything in it failed.

    A cased entry's arms are checked one by one, so every fault is collected
    rather than the first, and proved apart only once all of them resolve.
    The ``otherwise`` arm becomes the region left over, so a consumer adds
    regions rather than working out which one is left; the language proved
    the rest apart, so the regions are disjoint and total.
    """
    context = f"Named expression '{name}'"
    if not block.cases:
        assert block.expression is not None
        body = resolve_expression_text(block.expression, ns, context, errors, ceiling=None)
        return None if body is None else Named(name, body)

    found = len(errors)
    regions: list[Region] = []
    masks: dict[str, Predicate] = {}
    for case_name, case in block.cases.items():
        arm_context = case_context(name, case_name)
        when = resolve_where_text(case.when, ns, arm_context, errors)
        if isinstance(when, BooleanLiteral):
            errors.append(_constant_arm(arm_context, value=when.value))
        elif when is not None:
            masks[case_name] = when
        value = resolve_expression_text(case.expression, ns, arm_context, errors, ceiling=None)
        if when is not None and value is not None:
            regions.append(Region(Mask(when), value))
    assert block.otherwise is not None
    fallback = resolve_expression_text(block.otherwise, ns, case_context(name, None), errors, ceiling=None)
    if len(errors) > found or fallback is None:
        return None
    errors.extend(f'{context}: {problem}' for problem in overlapping(masks, ns.dtypes))
    if len(errors) > found:
        return None
    left_over = Region(remainder(region.when for region in regions), fallback)
    return Named(name, Cases((*regions, left_over)))


def _constant_arm(context: str, *, value: bool) -> str:
    """The refusal for a case arm whose mask the connectives already decided.

    Cases are proved apart rather than ranked, so an always-true arm is not
    one that shadows the arms under it — it is one no other arm can be proved
    apart from, and the ``otherwise`` it leaves is empty. An always-false arm
    is the plainer half: nothing to apply to.
    """
    if value:
        return (
            f'{context}: the mask admits every row, so no other arm can hold anywhere '
            f'and `otherwise:` covers nothing. Write the expression without `cases:`, '
            f'or narrow the `when`.'
        )
    return f'{context}: the mask admits no row, so this arm never applies. Delete the arm, or widen the `when`.'


@dataclass(frozen=True)
class _Resolver:
    """One resolution walk, and the three things every step of it reads.

    A node that cannot be built comes back as ``None`` with its refusal
    appended to ``errors``; every sibling is still read, so a declaration
    with two faults reports both. ``self_variable`` is the variable whose own
    ``where`` is being read, which may not ask whether it exists. ``formals``
    are a macro template's formals: a formal has no kind until a call site
    binds it, so a node one stands under is ``None`` with nothing appended.
    """

    ns: Namespace
    context: str
    errors: list[str]
    self_variable: str | None = None
    formals: frozenset[str] = frozenset()

    def _formal(self, value: ArithmeticNode) -> bool:
        """Whether *value* is a formal, left for the call site to bind."""
        return isinstance(value, NameNode) and value.name in self.formals

    # -- expressions -------------------------------------------------------

    def arith(self, node: ArithmeticNode) -> Expression | None:
        """The program node *node* stands for, or ``None``.

        A quoted keyword or a name list in arithmetic arrives through a macro
        formal bound to one.
        """
        if isinstance(node, NumberNode):
            return Constant(node.value)
        if isinstance(node, NameNode):
            return self._name(node)
        if isinstance(node, UnaryOperatorNode):
            operand = self.arith(node.operand)
            if operand is None:
                return None
            return Negate(operand) if node.op == '-' else operand
        if isinstance(node, BinaryOperatorNode):
            return self._binary(node)
        if isinstance(node, FunctionCallNode):
            return self._call(node)
        if isinstance(node, KeywordNode):
            self.errors.append(
                f'{self.context}: {node.value!r} is a quoted keyword, which is only legal as a '
                f"operator kwarg value such as shift(..., edge='wrap'). In an expression, quote "
                f'nothing — names resolve and numbers are written bare.'
            )
            return None
        if isinstance(node, NameListNode):
            self.errors.append(
                f'{self.context}: {node} is a list of names, which is only legal as an operator '
                f'kwarg value such as sum(x, by=[gen_bus, gen_tech]). In an expression, write the '
                f'terms out and add them.'
            )
            return None
        assert_never(node)

    def _binary(self, node: BinaryOperatorNode) -> Expression | None:
        """A subtraction is an addition of the negation, so a program has one additive node."""
        left, right = self.arith(node.left), self.arith(node.right)
        if left is None or right is None:
            return None
        match node.op:
            case '+':
                return Add(left, right)
            case '-':
                return Add(left, Negate(right))
            case '*':
                return Multiply(left, right)
            case '/':
                return Divide(left, right)
            case '**':
                return Power(left, right)
            case _:
                assert_never(node.op)

    def _name(self, node: NameNode) -> Expression | None:
        """A bare name as the variable, parameter or named expression it declares; a dimension or relation is not a value.

        A named expression arrives as the one node :meth:`Namespace.named`
        built for it; the cast is the one place a
        :class:`~math_spec.program.Named` enters a tree typed as a program's,
        which lowering makes true.
        """
        if node.name in self.formals:
            return None
        if node.name in self.ns.schema.expressions:
            try:
                return cast('Expression', self.ns.named(node.name, self.context))
            except SchemaError as e:
                self.errors.append(str(e))
                return None
        match self.ns.kind(node.name):
            case 'variable':
                return Variable(node.name)
            case 'parameter':
                dtype = self.ns.dtypes.get(node.name)
                if dtype is not None and dtype not in NUMERIC_DTYPES:
                    self.errors.append(_not_a_number(node.name, dtype, self.context))
                    return None
                return Parameter(node.name)
            case 'dimension':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a dimension, and a dimension is "
                    f'not a value in an expression. Dimensions appear in '
                    f"'dims:', in operator arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
                )
                return None
            case 'relation':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a relation, and a relation is structure "
                    f'rather than data, so it is not a value in an expression. A relation '
                    f'appears in a helper (sum(x, by={node.name})) and in a where — to '
                    f'carry numbers along this dimension, declare a parameter over it.'
                )
                return None
            case _:
                self.errors.append(self.ns.unknown(node.name, self.context, allow_dims=False, formals=self.formals))
                return None

    def _call(self, node: FunctionCallNode) -> Expression | None:
        """An operator call as the node it is: its shape checked, and each kwarg read by the kind the operator declares for it.

        Every argument is read even after one failed, so a call with two
        faults reports both. A formal anywhere under the call builds nothing
        and refuses nothing.
        """
        if node.name not in BUILTINS:
            self.errors.append(f'{self.context}: {unknown_operator_message(node.name)}')
            return None
        builtin = BUILTINS[node.name]
        shape_error = call_shape_error(node.name, len(node.args), node.kwargs)
        if shape_error is not None:
            self.errors.append(f'{self.context}: {shape_error}')
        if node.name == 'dual':
            return None if shape_error is not None else self._dual(node)
        args = [self.arith(a) for a in node.args]
        with_relation = any(k in node.kwargs for k in builtin.relation_kwargs)
        roles = {k: v for k, v in node.kwargs.items() if builtin.kind_of(k, with_relation=with_relation) == 'role'}
        if roles and 'by' not in node.kwargs:
            self.errors.append(
                f'{self.context}: {node.name}({", ".join(f"{k}=" for k in roles)}) names a column of a relation, '
                f'and no by= names the relation. Write {builtin.usage}'
            )
        dims: dict[str, str | None] = {}
        amounts: dict[str, int | str | None] = {}
        edge: _Edge | None = None
        for key, value in node.kwargs.items():
            match builtin.kind_of(key, with_relation=with_relation):
                case 'edge':
                    edge = self._edge(value, node.name)
                case 'dimension':
                    dims[key] = self._dim_ref(value, node.name, key)
                case 'value':
                    amounts[key] = self._amount(value, node.name, key)
                case 'relation' | 'role' | None:
                    pass
        read = None
        if 'by' in node.kwargs and builtin.kind_of('by') == 'relation':
            read = self._relation_ref(node.kwargs['by'], node.name, 'by', roles, dims.get('along'))
        unread = (
            shape_error is not None
            or not args
            or args[0] is None
            or None in dims.values()
            or None in amounts.values()
            or ('edge' in node.kwargs and edge is None)
            or ('by' in node.kwargs and read is None)
        )
        if unread:
            return None
        return self._built(node.name, cast('Expression', args[0]), dims, amounts, edge, read)

    def _built(
        self,
        operator: str,
        operand: Expression,
        dims: Mapping[str, str | None],
        amounts: Mapping[str, int | str | None],
        edge: _Edge | None,
        read: Direction | Partition | None,
    ) -> Expression | None:
        """The node *operator* builds from its read arguments, or ``None`` with the refusal appended."""
        if operator == 'sum':
            if read is not None:
                assert isinstance(read, Direction), 'a sum reads its relation in a direction'
                return GroupSum(operand, read)
            if (over := dims.get('over')) is not None:
                return Sum(operand, (over,))
            return self._bare_sum(operand)
        if operator == 'at':
            assert isinstance(read, Direction), 'at reads its relation in a direction'
            return Pullback(operand, read)
        assert read is None or isinstance(read, Partition), 'a translation reads its relation as a partition'
        along = dims['along']
        assert along is not None
        wrap, fill = edge if edge is not None else (False, None)
        if operator == 'shift':
            offset = amounts['offset']
            assert offset is not None
            if not self._edge_fits(operand, offset, wrap=wrap, fill=fill):
                return None
            return Translate(operand, along, offset, wrap=wrap, fill=fill, partition=read)
        if fill is not None:
            self.errors.append(
                f"{self.context}: sum_back(edge=...) takes 'wrap' or nothing. A window sums the terms "
                f'it reaches, so a position before the first contributes nothing rather than a '
                f'fill value; add the constant to the expression if you want one.'
            )
            return None
        width = amounts['window']
        assert width is not None
        return WindowSum(operand, along, width, wrap=wrap, partition=read)

    def _bare_sum(self, operand: Expression) -> Expression | None:
        """``sum(x)`` with no ``over=`` or ``by=`` reduces every dim the operand carries, which it has to carry some of."""
        try:
            inner = dims_of(operand, self.ns.schema, self.context)
        except DimensionError as e:
            self.errors.append(str(e))
            return None
        if not inner:
            self.errors.append(
                f'{self.context}: sum() with no over= or by= sums every dim the operand '
                f'carries, and this one carries none — the expression is already a '
                f'scalar. Drop the sum.'
            )
            return None
        return Sum(operand, tuple(sorted(inner)))

    def _edge_fits(self, operand: Expression, offset: int | str, *, wrap: bool, fill: float | None) -> bool:
        """What a ``shift``'s ``edge=`` may say, and where saying nothing is an answer.

        Every rule here is decidable from the file — whether the operand
        carries a variable, whether the offset is named, what the edge is
        written as — so a file breaking one is refused at load rather than by
        whoever lowers it.
        """
        if wrap:
            return True
        has_var = carries_variable(operand)
        if has_var and fill is not None and fill != 0:
            self.errors.append(
                f'{self.context}: shift(edge={fill:g}) over an expression containing a variable — only '
                f'fill=0 is representable there, since a vacated slot contributes no term. A nonzero '
                f'fill would be a constant standing where a term was; add that constant to the '
                f'expression instead.'
            )
            return False
        if fill is None and _vacates(offset) and not has_var:
            self.errors.append(_shift_over_data_message(self.context))
            return False
        if fill is None and isinstance(offset, str):
            self.errors.append(f'{self.context}: {_named_offset_edge_message(offset)}')
            return False
        return True

    def _amount(self, value: ArithmeticNode, operator: str, key: str) -> int | str | None:
        """``offset=`` or ``window=``: a whole number in the operator's range, or the name of a parameter.

        Closed so that :func:`math_spec.dimensions._check_named_amount` sees
        every parameter an amount carries, and so that a program's
        ``offset`` and ``width`` are the ``int | str`` they say.
        """
        if self._formal(value):
            return None
        words = AMOUNTS[operator]
        if (literal := _literal(value)) is not None:
            if not (literal.value.is_integer() and literal.value >= words.minimum):
                self.errors.append(f'{self.context}: {operator}({key}=...) {words.form}')
                return None
            return int(literal.value)
        bare = _without_sign(value)
        if not isinstance(bare, NameNode):
            self.errors.append(
                f'{self.context}: {operator}({key}=) takes a number or the name of an integer parameter. '
                f'Precompute it as a parameter.'
            )
            return None
        if self._formal(bare):
            return None
        if self.ns.kind(bare.name) != 'parameter':
            if self._name(bare) is not None:
                self.errors.append(f'{self.context}: {operator}({key}=...) {words.form}')
            return None
        if isinstance(value, UnaryOperatorNode) and value.op == '-':
            self.errors.append(
                f'{self.context}: {operator}({key}=-{bare.name}) negates a named {words.noun}. {words.negated}'
            )
            return None
        return bare.name

    def _edge(self, value: ArithmeticNode, operator: str) -> _Edge | None:
        """``edge=``: the closed keyword ``wrap``, or a number to contribute; a name here is a typo."""
        if self._formal(value):
            return None
        if isinstance(value, KeywordNode):
            if value.value == EDGE_WRAP:
                return True, None
            self.errors.append(f'{self.context}: {edge_error(operator, repr(value.value))}')
            return None
        if isinstance(value, NameNode):
            if value.name == EDGE_WRAP:
                self.errors.append(
                    f'{self.context}: {operator}(edge={EDGE_WRAP}) is a bare name where a keyword belongs. '
                    f"Write edge='{EDGE_WRAP}', quoted."
                )
                return None
            self.errors.append(f'{self.context}: {edge_error(operator, value.name)}')
            return None
        if (literal := _literal(value)) is None:
            self.errors.append(
                f"{self.context}: {operator}(edge=) is an expression, and an edge is the keyword '{EDGE_WRAP}' "
                f'or a number. Write the number itself.'
            )
            return None
        return False, literal.value

    def _dim_ref(self, value: ArithmeticNode, operator: str, key: str) -> str | None:
        """An operator kwarg whose *value* must name a declared dimension."""
        if self._formal(value):
            return None
        if not isinstance(value, NameNode):
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a dimension.')
            return None
        if value.name not in self.ns.dimensions:
            self.errors.append(_undeclared_dim(self.context, operator, f'{key}={value.name}', value.name, self.ns))
            return None
        return value.name

    def _dual(self, node: FunctionCallNode) -> Dual | None:
        """``dual(c)`` as the leaf it is, its one argument the name of a declared constraint.

        Constraints sit outside the flat namespace, so this store is consulted
        only here — a bare name in arithmetic never reaches it. A dual standing
        where the math is built is refused separately
        (:mod:`math_spec.degree`); this pass only types the name.
        """
        (value,) = node.args
        if self._formal(value):
            return None
        if not isinstance(value, NameNode):
            self.errors.append(
                f'{self.context}: dual() takes the name of a declared constraint, written bare — '
                f'dual(<constraint>). Name the constraint whose row dual you want.'
            )
            return None
        if value.name not in self.ns.constraints:
            self.errors.append(self.ns.unknown_constraint(value.name, self.context, formals=self.formals))
            return None
        return Dual(value.name)

    def _relation_ref(
        self,
        value: ArithmeticNode,
        operator: str,
        key: str,
        roles: Mapping[str, ArithmeticNode],
        along: str | None,
    ) -> Direction | Partition | None:
        """An operator's ``by=`` as the direction or the partition the call reads its relation in.

        A relation carries its own dimensions, so the call names columns rather
        than dims: ``over=`` the column consumed, ``into=`` the column
        produced, every other key column joined on. A value column not named
        is not read, and a bare relation's columns are all key. One call
        addresses one table, so several columns of one table are a list and
        several tables are not. *along* is the dimension a translation steps
        along, already read, or ``None`` where it was refused.
        """
        names = names_in(value)
        if not names:
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a relation.')
            return None
        if len(names) > 1:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) names {len(names)} relations, and one call '
                f'reads one table. Declare one relation with the columns of all of them, or read them in turn, '
                f'one call each.'
            )
            return None
        name = names[0]
        if name in self.formals or any(n in self.formals for v in roles.values() for n in names_in(v)):
            return None

        if (problem := self._not_a_relation(name, operator, key)) is not None:
            self.errors.append(problem)
            return None
        read = {k: self._role_name(v, operator, k) for k, v in roles.items()}
        if any(r is None for r in read.values()):
            return None
        named = {k: r for k, r in read.items() if r is not None}
        if operator in ('shift', 'sum_back'):
            if 'within' not in named:
                return None  # the call shape refused it already, with the wording that names the rewrite
            return self._partition(name, operator, along, named['within'])
        if not ({'over', 'into'} <= set(named)):
            return None  # the call shape refused it already, with the wording that names the rewrite
        return self._direction(name, operator, named['over'], named['into'])

    def _role_name(self, value: ArithmeticNode, operator: str, key: str) -> tuple[str, ...] | None:
        """``over=`` or ``into=`` as the column names it must be — one bare name, or a bracketed list of them."""
        if names := names_in(value):
            return names
        self.errors.append(
            f'{self.context}: {operator}({key}=...) names columns of the relation — a bare name, or a list of them.'
        )
        return None

    def _direction(
        self,
        name: str,
        operator: str,
        from_roles: tuple[str, ...],
        into_roles: tuple[str, ...],
    ) -> Direction | None:
        """Which direction ``sum`` or ``at`` reads relation *name* in, between the columns the call named.

        Both ends arrive written: the call shape refuses a call that leaves
        one unsaid, so that a relation may gain a value column without
        changing what this call means. ``at`` needs the read single-valued
        and ``sum`` needs it not: a sum that lands on the key has one term
        per coordinate and adds up nothing, which is a read, so it is
        refused toward ``at``. A read lands on key columns and nothing else,
        because a column outside the key is one no coordinate of the read
        fixes.
        """
        ns, context = self.ns, self.context
        shape = ns.relations[name]
        call = f'{operator}(by={name})'
        if not (
            self._known_roles(name, call, from_roles, 'over') and self._known_roles(name, call, into_roles, 'into')
        ):
            return None

        forward = operator == 'sum'
        if both := sorted(set(from_roles) & set(into_roles)):
            self.errors.append(
                f'{context}: {call}: over= and into= both name {both}, and a call reads between two sets of columns.'
            )
            return None
        for kwarg, roles in (('over', from_roles), ('into', into_roles)):
            dims = [shape.dim(r) for r in roles]
            if shared := sorted({d for d in dims if dims.count(d) > 1}):
                self.errors.append(
                    f'{context}: {call}: {kwarg}={list(roles)} names two columns over {shared}, and the operand '
                    f'carries each dimension once, so nothing says which column its coordinate is read at. Read '
                    f'between columns over distinct dimensions.'
                )
                return None
        if not forward and (outside := [r for r in into_roles if r not in shape.key]):
            self.errors.append(
                f"{context}: {call}: into={list(into_roles)} names {outside}, which the key of '{name}' does not "
                f'hold. A read lands on the key it reads at, {list(shape.key)}, and a column outside that key '
                f'arrives as a dimension the read never fixes. Land on the key, or sum toward {outside}.'
            )
            return None
        joined = tuple(r for r in shape.key if r not in from_roles and r not in into_roles)
        single_valued = set(shape.key) <= {*into_roles, *joined}
        direction = Direction(name, shape, from_roles, into_roles, joined)
        if not forward and not single_valued:
            self.errors.append(
                f"{context}: {call}: at reads one value per coordinate, and '{name}' is not single-valued in "
                f'{list(from_roles)} at the columns the call lands on ({[*into_roles, *joined]}) — its key is '
                f'{list(shape.key)}. Key the table by the columns the call lands on, or read the other way.'
            )
            return None
        if forward and single_valued:
            self.errors.append(
                f'{context}: {call}: this sum lands on the key {list(shape.key)}, so each coordinate has one '
                f"term and nothing is added up — that is a read, which is at()'s. Write "
                f'at(..., by={name}, over={list(from_roles)}, into={list(into_roles)}), or sum toward '
                f'a value column.'
            )
            return None
        return direction

    def _known_roles(self, name: str, call: str, roles: tuple[str, ...], kwarg: str) -> bool:
        """Whether every role *kwarg* names is a column of relation *name*, each once; the refusal otherwise."""
        shape = self.ns.relations[name]
        for role in roles:
            if role not in shape.roles:
                self.errors.append(
                    f"{self.context}: {call}: {kwarg}={role} names no column of '{name}', whose columns are "
                    f'{list(shape.roles)}.'
                )
                return False
        if len(set(roles)) < len(roles):
            self.errors.append(f'{self.context}: {call}: {kwarg}={list(roles)} names a column twice.')
            return False
        return True

    def _partition(
        self, name: str, operator: str, along_dim: str | None, within_roles: tuple[str, ...]
    ) -> Partition | None:
        """How a partition (``shift``, ``sum_back``, ``position``) steps along relation *name* over *along_dim*.

        It steps along the one key column over that dimension (a key has one
        column per dimension), joins on the other key columns and groups by the
        value columns *within_roles* names. ``None`` where the dimension is not one
        (already refused), the relation has no key column over it, or
        ``within=`` names a column that is not a value column.
        """
        context = self.context
        shape = self.ns.relations[name]
        call = f'{operator}(by={name})'
        if along_dim is None or not self._known_roles(name, call, within_roles, 'within'):
            return None
        if not shape.values:
            self.errors.append(
                f"{context}: {call}: '{name}' is a bare relation — every column is in its key — so it makes no "
                f'groups and no coordinate is in exactly one. Move the columns the group is made of under '
                f'values:, leaving key: the column {operator} steps along.'
            )
            return None
        over_keys = [r for r in shape.key if shape.dim(r) == along_dim]
        if not over_keys:
            self.errors.append(
                f"{context}: {call}: '{name}' has no key column over '{along_dim}' — its key is "
                f'{list(shape.key)} — and a partition steps along a key column over the dimension it groups.'
            )
            return None
        if keyed := [r for r in within_roles if r in shape.key]:
            self.errors.append(
                f"{context}: {call}: within={keyed} names a key column of '{name}', and a partition groups by "
                f'value columns — its value columns are {list(shape.values)}.'
            )
            return None
        (along,) = over_keys
        joined = tuple(r for r in shape.key if r != along)
        return Partition(name, shape, along, within_roles, joined)

    def _not_a_relation(self, name: str, operator: str, key: str) -> str | None:
        """Why *name* is not a relation; ``None`` where it is one."""
        ns, context = self.ns, self.context
        if name in ns.relations:
            return None
        if name in ns.dimensions:
            over_here = sorted(n for n, shape in ns.relations.items() if name in dict(shape.columns).values())
            hint = (
                f"  Relations with a column over '{name}': {over_here}"
                if over_here
                else f"  No relation has a column over '{name}'."
            )
            return (
                f"{context}: {operator}({key}={name}): '{name}' is a dimension, and "
                f'{key}= takes a relation — the named map out of a dimension.\n{hint}'
            )
        return (
            f'{context}: {operator}({key}={name}) does not name a relation. '
            f'{did_you_mean(name, ns.relations, label="Relations")}\n'
            f"Declare it under 'relations:' — {name}: {{key: <the columns a row is identified by>, "
            f'values: <the columns they determine>}}.'
        )

    # -- where strings -----------------------------------------------------

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
        offset = _literal(node.kwargs['offset'])
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
        by = self._relation_ref(node.kwargs['by'], 'at', 'by', roles, None)
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
        value = _literal(node.value)
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
        elif (literal := _literal(right)) is not None:
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
            if (resolved := self.arith(expanded)) is not None:
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
        index = None if isinstance(node.right, ColumnNode | KeywordNode) else _literal(node.right)
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
        if (problem := self._not_a_relation(by, 'position', 'by')) is not None:
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
        partition = self._partition(by, 'position', dimension, into)
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


def _not_a_number(name: str, dtype: str, context: str) -> str:
    """Why a ``str`` or ``bool`` parameter is refused where a value belongs; the rewrite is the dtype's own."""
    if dtype == 'str':
        instead = (
            f'A label selects rather than scales: compare it in a where '
            f'("{name} == \'some_label\'"), and carry the numbers it picks out in a '
            f'parameter of its own.'
        )
    else:
        instead = (
            f'A flag masks rather than scales: name it in a where ("{name}", "NOT {name}"), '
            f'which is what a mask is — or declare it dtype: int where the 0/1 is meant to '
            f'arrive as data and be multiplied by.'
        )
    return (
        f"{context}: '{name}' is declared dtype: {dtype}, and an expression is arithmetic — "
        f'only dtype: float and dtype: int bind a column it can be done to. {instead}'
    )


def _undeclared_dim(context: str, operator: str, call: str, name: str, ns: Namespace) -> str:
    return (
        f'{context}: {operator}({call}) does not name a declared dimension. '
        f'{did_you_mean(name, ns.dimensions, label="Dimensions")}\n'
        f"Declare '{name}' under 'dimensions:', or fix the typo — an unknown "
        f'dimension makes {operator}() a silent no-op rather than an error.'
    )


def _declared_as(ns: Namespace, name: str) -> str:
    kind = ns.kind(name)
    return f'a {kind}' if kind else 'not declared'


def _without_sign(value: ArithmeticNode) -> ArithmeticNode:
    """*value* under its sign, if it carries one."""
    return value.operand if isinstance(value, UnaryOperatorNode) else value


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


def _literal(value: ArithmeticNode) -> NumberNode | None:
    """The number a literal names, its sign folded in — ``None`` where *value* is not one."""
    if isinstance(value, NumberNode):
        return value
    if isinstance(value, UnaryOperatorNode) and isinstance(value.operand, NumberNode):
        return NumberNode(-value.operand.value if value.op == '-' else value.operand.value)
    return None


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


def _vacates(offset: int | str) -> bool:
    """Whether a translation leaves anything behind.

    A literal zero step reaches every coordinate from itself, so there is no
    vacated position for an ``edge=`` to answer for and the refusal has
    nothing to refuse. A *named* offset may be zero in the data and is not
    known here, so it vacates until proved otherwise.
    """
    return offset != 0


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
