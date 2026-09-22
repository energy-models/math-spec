# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Name resolution — the pass that makes the core AST fully typed.

Parsers emit unresolved names; this module rewrites each into the typed node
its kind asks for, so the AST reaching a consumer holds none. The rules live in
the language reference.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING, Literal, NamedTuple, assert_never, cast

from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CaseArm,
    CasesNode,
    ComparisonNode,
    DefinitionNode,
    DimensionNode,
    DualNode,
    EdgeNode,
    FunctionCallNode,
    JoinNode,
    KeywordNode,
    KwargNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    ParsedNode,
    PartitionNode,
    UnaryOperatorNode,
    VariableNode,
    case_context,
    nodes,
    shown,
    with_children,
)
from math_spec._where_parser import (
    ColumnNode,
    QuotedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedWhereNode,
    parse_where,
)
from math_spec.errors import LanguageError, did_you_mean
from math_spec.expansion import parse_and_expand
from math_spec.model import NUMERIC_DTYPES
from math_spec.operators import (
    BUILTINS,
    EDGE_WRAP,
    PARTITION_NAMES_ITS_GROUP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.program import (
    And,
    BooleanLiteral,
    DimensionComparison,
    DimensionPosition,
    Join,
    Mask,
    Not,
    Or,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Predicate,
    PredicateOperator,
    RelationComparison,
    RelationDeclaration,
    RelationDefined,
    RelationPairComparison,
    TypedPredicate,
    VariableDefined,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from math_spec.model import DeclaredDtype, Spec


#: What a name a file may write turns out to be. Answered by
#: :meth:`Namespace.kind`, so a pass reading a name switches over this rather
#: than over the stores it would otherwise have to try in order.
DeclarationKind = Literal['variable', 'parameter', 'dimension', 'relation']


class Namespace:
    """The declared names of one schema, by kind.

    A name has one kind: model.py refuses one declared under two sections.
    """

    __slots__ = ('constraints', 'dimensions', 'dtypes', 'leaf_dims', 'parameters', 'relations', 'variables')

    def __init__(
        self,
        variables: Iterable[str],
        parameters: Iterable[str],
        dimensions: Iterable[str],
        relations: Mapping[str, RelationDeclaration],
        dtypes: Mapping[str, DeclaredDtype],
        leaf_dims: Mapping[str, tuple[str, ...]],
        constraints: Iterable[str],
    ) -> None:
        self.variables = frozenset(variables)
        self.parameters = frozenset(parameters)
        self.dimensions = frozenset(dimensions)
        #: The declared constraint names, off the flat namespace: a bare name
        #: never reaches them, so a model may name a constraint after a variable.
        #: Consulted only in ``dual()``'s argument position.
        self.constraints = frozenset(constraints)
        #: name -> declared dtype, for dimensions, parameters and relations alike;
        #: what a where comparison checks its literal against.
        self.dtypes: dict[str, DeclaredDtype] = dict(dtypes)
        #: relation name -> its columns and key, as declared.
        self.relations: dict[str, RelationDeclaration] = dict(relations)
        #: parameter or variable name -> the dims it is read through —
        #: parameters by their ``dims``, variables by their frame. Stamped onto
        #: each leaf a where names, the way a relation leaf carries ``over``.
        self.leaf_dims: dict[str, tuple[str, ...]] = dict(leaf_dims)

    @classmethod
    def of(cls, schema: Spec) -> Namespace:
        """Build the namespace of *schema*, the whole of what a file may name."""
        return cls(
            schema.variables,
            schema.parameters,
            schema.dimensions,
            {n: RelationDeclaration(lk.pairs, lk.key_roles) for n, lk in schema.relations.items()},
            {
                **{p: pd.dtype for p, pd in schema.parameters.items()},
                **{d: dd.dtype for d, dd in schema.dimensions.items()},
            },
            {
                **{p: tuple(pd.dims) for p, pd in schema.parameters.items()},
                **{v: tuple(vd.dims) for v, vd in schema.variables.items()},
            },
            schema.constraints,
        )

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


class ResolvedConstraint(NamedTuple):
    """One constraint's typed halves: the comparison it states, and the mask it holds under."""

    expression: ComparisonNode
    where: Mask | None


@dataclass(frozen=True)
class Resolved:
    """Every expression and where string of one schema, typed once at load.

    :func:`~math_spec.validation.validate_expressions` builds it, and every
    reader after — the dim rules, lowering, the typesetter — walks these trees
    rather than parsing, expanding and resolving the text again. Each mapping
    is keyed as the schema's own section is. A ``where`` the file did not
    write, or one every row passes, is ``None``.

    Attributes:
        expressions: Each ``expressions:`` entry as the node its name expands
            to — a plain entry a :class:`~math_spec._expression_parser.DefinitionNode`
            carrying its name over its body, a cased one a
            :class:`~math_spec._expression_parser.CasesNode` with every arm's
            ``when`` typed. Every entry either names is inlined where it
            stood, so a walk over one sees the whole chain.
        variables: Each variable's ``where``.
        constraints: Each constraint's comparison and ``where``.
        objective: The objective's expression, ``None`` where the file
            declares none.
        relations: Each relation's columns and key, as declared — the one
            copy, which every :class:`~math_spec.program.Join` and
            :class:`~math_spec.program.Partition` in the trees holds.
    """

    expressions: dict[str, CasesNode | DefinitionNode]
    variables: dict[str, Mask | None]
    constraints: dict[str, ResolvedConstraint]
    objective: ArithmeticNode | None
    relations: dict[str, RelationDeclaration]

    @cached_property
    def read_by_the_math(self) -> frozenset[str]:
        """The named expressions the math reads: every entry the objective or a constraint reaches, transitively.

        Read off those two positions alone: a bound and a ``where`` name no
        entry, and a piecewise link's expression reaches here through the
        constraints its expansion emitted. The rest of the ``expressions:``
        section is read back after a solve and never fed to one
        (:attr:`~math_spec.program.ExpressionDeclaration.in_math`).
        """
        roots: list[ParsedNode] = [constraint.expression for constraint in self.constraints.values()]
        if self.objective is not None:
            roots.append(self.objective)
        return frozenset(node.name for node in nodes(*roots) if isinstance(node, CasesNode | DefinitionNode))


# ---------------------------------------------------------------------------
# the seam the rest of the package uses
# ---------------------------------------------------------------------------


def expression_of(text: str, schema: Spec, ns: Namespace, context: str) -> ParsedNode:
    """Parse, expand and resolve *text* in one call, raising rather than collecting.

    A declaration's tree is on :class:`Resolved`; this is for a text that is
    not one.

    Raises:
        LanguageError: Listing every problem the text has.
    """
    errors: list[str] = []
    resolved = resolve_expression(parse_and_expand(text, schema, context), ns, context, errors)
    if errors:
        raise LanguageError('\n'.join(errors))
    assert resolved is not None
    return resolved


def where_of(text: str | None, ns: Namespace, context: str, self_variable: str | None = None) -> Mask | None:
    """Parse and resolve a where string into the :class:`~math_spec.program.Mask` a declaration carries.

    ``None`` for no mask, however the file spelled it: a mask that admits every
    row is dropped, and one that admits none arrives as a mask over
    ``BooleanLiteral(False)``.

    Raises:
        LanguageError: Listing every problem the predicate has.
    """
    errors: list[str] = []
    resolved = resolve_where_text(text, ns, context, errors, self_variable)
    if errors:
        raise LanguageError('\n'.join(errors))
    return mask_of(resolved)


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


# ---------------------------------------------------------------------------
# expressions
# ---------------------------------------------------------------------------


def resolve_expression(
    node: ParsedNode,
    ns: Namespace,
    context: str,
    errors: list[str],
) -> ParsedNode | None:
    """Rewrite every ``NameNode`` under *node* to a typed node, checking operator call shapes on the way.

    Returns:
        The typed tree, or ``None`` once anything failed — appending to
        *errors* rather than raising, so a caller collecting problems across a
        whole schema reports them together.
    """
    before = len(errors)
    resolved = _Resolver(ns, context, errors).expression(node)
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


@dataclass(frozen=True)
class _Resolver:
    """One resolution walk, and the three things every step of it reads.

    A node that cannot be typed comes back unresolved with its refusal
    appended to ``errors``; the public doors discard the tree once ``errors``
    grew, which is what lets a connective's children be typed as resolved.
    ``self_variable`` is the variable whose own ``where`` is being read, which
    may not ask whether it exists.
    """

    ns: Namespace
    context: str
    errors: list[str]
    self_variable: str | None = None

    # -- expressions -------------------------------------------------------

    def expression(self, node: ParsedNode) -> ParsedNode:
        """Every ``NameNode`` under *node* typed; a comparison keeps its shape."""
        if isinstance(node, ComparisonNode):
            return ComparisonNode(node.op, self._arith(node.left), self._arith(node.right))
        return self._arith(node)

    def _arith(self, node: ArithmeticNode, *, amount: bool = False) -> ArithmeticNode:
        """One arithmetic node typed.

        *amount* marks an ``offset=``/``window=`` value, whose dtype rule is
        ``dimensions._check_named_amount``'s and stricter than "a number", so the
        numeric check here stands aside for it. A quoted keyword or a name list in
        arithmetic arrives through a macro formal bound to one.
        """
        if isinstance(node, NumberNode | VariableNode | ParameterNode | DualNode | KwargNode):
            return node
        if isinstance(node, NameNode):
            return self._name(node, amount=amount)
        if isinstance(node, UnaryOperatorNode | BinaryOperatorNode | DefinitionNode):
            return with_children(node, self._arith)
        if isinstance(node, FunctionCallNode):
            return self._call(node)
        if isinstance(node, KeywordNode):
            self.errors.append(
                f'{self.context}: {node.value!r} is a quoted keyword, which is only legal as a '
                f"operator kwarg value such as shift(..., edge='wrap'). In an expression, quote "
                f'nothing — names resolve and numbers are written bare.'
            )
            return node
        if isinstance(node, NameListNode):
            self.errors.append(
                f'{self.context}: {node} is a list of names, which is only legal as an operator '
                f'kwarg value such as sum(x, by=[gen_bus, gen_tech]). In an expression, write the '
                f'terms out and add them.'
            )
            return node
        if isinstance(node, CasesNode):
            return self._cases(node)
        assert_never(node)

    def _name(self, node: NameNode, *, amount: bool) -> ArithmeticNode:
        """A bare name as the variable or parameter it declares; a dimension or relation is not a value."""
        match self.ns.kind(node.name):
            case 'variable':
                return VariableNode(node.name)
            case 'parameter':
                dtype = self.ns.dtypes.get(node.name)
                if not amount and dtype is not None and dtype not in NUMERIC_DTYPES:
                    self.errors.append(_not_a_number(node.name, dtype, self.context))
                    return node
                return ParameterNode(node.name)
            case 'dimension':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a dimension, and a dimension is "
                    f'not a value in an expression. Dimensions appear in '
                    f"'dims:', in operator arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
                )
                return node
            case 'relation':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a relation, and a relation is structure "
                    f'rather than data, so it is not a value in an expression. A relation '
                    f'appears in a helper (sum(x, by={node.name})) and in a where — to '
                    f'carry numbers along this dimension, declare a parameter over it.'
                )
                return node
            case _:
                self.errors.append(self.ns.unknown(node.name, self.context, allow_dims=False))
                return node

    def _call(self, node: FunctionCallNode) -> ArithmeticNode:
        """An operator call: its shape checked, and each kwarg typed by the kind the operator declares for it."""
        if node.name not in BUILTINS:
            self.errors.append(f'{self.context}: {unknown_operator_message(node.name)}')
            return node
        builtin = BUILTINS[node.name]
        shape_error = call_shape_error(node.name, len(node.args), node.kwargs)
        if shape_error is not None:
            self.errors.append(f'{self.context}: {shape_error}')
        if node.name == 'dual':
            return node if shape_error is not None else self._dual(node)
        args = tuple(self._arith(a) for a in node.args)
        kwargs: dict[str, ArithmeticNode] = {}
        with_relation = any(k in node.kwargs for k in builtin.relation_kwargs)
        roles = {k: v for k, v in node.kwargs.items() if builtin.kind_of(k, with_relation=with_relation) == 'role'}
        if roles and 'by' not in node.kwargs:
            self.errors.append(
                f'{self.context}: {node.name}({", ".join(f"{k}=" for k in roles)}) names a column of a relation, '
                f'and no by= names the relation. Write {builtin.usage}'
            )
        for key, value in node.kwargs.items():
            match builtin.kind_of(key, with_relation=with_relation):
                case 'edge':
                    kwargs[key] = self._edge(value, node.name)
                case 'dimension':
                    kwargs[key] = self._dim_ref(value, node.name, key)
                case 'relation':
                    kwargs[key] = self._relation_ref(value, node.name, key, roles, node.kwargs.get('along'))
                case 'role':
                    pass
                case 'value':
                    kwargs[key] = self._amount(value, node.name, key)
                case None:
                    pass  # a keyword the operator does not declare; the shape error already named it
        return FunctionCallNode(node.name, args, kwargs)

    def _cases(self, node: CasesNode) -> CasesNode:
        """Each arm's value and ``when`` typed under the arm's own context."""
        arms = []
        for arm in node.arms:
            arm_context = case_context(node.name, None if arm.when is None else arm.label)
            when = None if arm.when is None else resolve_where(arm.when, self.ns, arm_context, self.errors)
            arms.append(CaseArm(arm.label, when, replace(self, context=arm_context)._arith(arm.value)))
        return CasesNode(node.name, tuple(arms))

    def _amount(self, value: ArithmeticNode, operator: str, key: str) -> ArithmeticNode:
        """``offset=`` or ``window=``: a number or a parameter name, never an expression.

        Closed so that :func:`math_spec.dimensions._check_named_amount` sees every
        parameter an amount carries.
        """
        if (literal := _literal(value)) is not None:
            return literal
        if not isinstance(_without_sign(value), NameNode):
            self.errors.append(
                f'{self.context}: {operator}({key}=) takes a number or the name of an integer parameter. '
                f'Precompute it as a parameter.'
            )
            return value
        return self._arith(value, amount=True)

    def _edge(self, value: ArithmeticNode, operator: str) -> ArithmeticNode:
        """``edge=``: the closed keyword ``wrap``, or a number to contribute; a name here is a typo."""
        if isinstance(value, KeywordNode):
            if value.value == EDGE_WRAP:
                return EdgeNode()
            self.errors.append(f'{self.context}: {edge_error(operator, repr(value.value))}')
            return value
        if isinstance(value, NameNode):
            if value.name == EDGE_WRAP:
                self.errors.append(
                    f'{self.context}: {operator}(edge={EDGE_WRAP}) is a bare name where a keyword belongs. '
                    f"Write edge='{EDGE_WRAP}', quoted."
                )
                return value
            self.errors.append(f'{self.context}: {edge_error(operator, value.name)}')
            return value
        if (literal := _literal(value)) is None:
            self.errors.append(
                f"{self.context}: {operator}(edge=) is an expression, and an edge is the keyword '{EDGE_WRAP}' "
                f'or a number. Write the number itself.'
            )
            return value
        return literal

    def _dim_ref(self, value: ArithmeticNode, operator: str, key: str) -> ArithmeticNode:
        """An operator kwarg whose *value* must name a declared dimension."""
        if not isinstance(value, NameNode):
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a dimension.')
            return value
        if value.name not in self.ns.dimensions:
            self.errors.append(_undeclared_dim(self.context, operator, f'{key}={value.name}', value.name, self.ns))
            return value
        return DimensionNode(value.name)

    def _dual(self, node: FunctionCallNode) -> ArithmeticNode:
        """``dual(c)`` typed to the leaf it is, its one argument the name of a declared constraint.

        Constraints sit outside the flat namespace, so this store is consulted
        only here — a bare name in arithmetic never reaches it. A dual standing
        where the math is built is refused separately
        (:mod:`math_spec.validation`); this pass only types the name.
        """
        (value,) = node.args
        if not isinstance(value, NameNode):
            self.errors.append(
                f'{self.context}: dual() takes the name of a declared constraint, written bare — '
                f'dual(<constraint>). Name the constraint whose row dual you want.'
            )
            return node
        if value.name not in self.ns.constraints:
            self.errors.append(self.ns.unknown_constraint(value.name, self.context))
            return node
        return DualNode(value.name)

    def _relation_ref(
        self,
        value: ArithmeticNode,
        operator: str,
        key: str,
        roles: Mapping[str, ArithmeticNode],
        over: ArithmeticNode | None,
    ) -> ArithmeticNode:
        """An operator's ``by=``, with the ``over=`` and ``into=`` that say how the relation is joined and grouped.

        A relation carries its own dimensions, so the call names columns rather
        than dims: ``over=`` the columns joined on and summed away, ``into=``
        the columns grouped by, every other key column joined on and kept. A
        value column not named is not read, and a bare relation's columns are
        all key. One call
        addresses one table, so several columns of one table are a list and
        several tables are not.
        """
        names = names_in(value)
        if not names:
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a relation.')
            return value
        if len(names) > 1:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) names {len(names)} relations, and one call '
                f'reads one table. Declare one relation with the columns of all of them, or read them in turn, '
                f'one call each.'
            )
            return value
        name = names[0]

        if (problem := self._not_a_relation(name, operator, key)) is not None:
            self.errors.append(problem)
            return value
        read = {k: self._role_name(v, operator, k) for k, v in roles.items()}
        if any(r is None for r in read.values()):
            return value
        named = {k: r for k, r in read.items() if r is not None}
        if operator in ('shift', 'sum_back'):
            if 'within' not in named:
                return value  # the call shape refused it already, with the wording that names the rewrite
            over_dim = over.name if isinstance(over, NameNode | DimensionNode) else None
            partition = self._partition(name, operator, over_dim, named['within'])
            return value if partition is None else PartitionNode(partition)
        if not ({'over', 'into'} <= set(named)):
            return value  # the call shape refused it already, with the wording that names the rewrite
        join = self._join(name, operator, named['over'], named['into'])
        return value if join is None else JoinNode(join)

    def _role_name(self, value: ArithmeticNode, operator: str, key: str) -> tuple[str, ...] | None:
        """``over=`` or ``into=`` as the column names it must be — one bare name, or a bracketed list of them."""
        if isinstance(value, NameNode):
            return (value.name,)
        if isinstance(value, NameListNode):
            return value.names
        self.errors.append(
            f'{self.context}: {operator}({key}=...) names columns of the relation — a bare name, or a list of them.'
        )
        return None

    def _join(
        self,
        name: str,
        operator: str,
        from_roles: tuple[str, ...],
        into_roles: tuple[str, ...],
    ) -> Join | None:
        """How ``sum`` or ``at`` joins relation *name*, between the columns the call named.

        Both ends arrive written: the call shape refuses a call that leaves
        one unsaid, so that a relation may gain a value column without
        changing what this call means. A lookup needs every group to be one
        row and a sum needs it not: a sum whose grouped columns hold the whole
        key has one row per group and adds up nothing, which is a lookup, so
        it is refused toward ``at``. A lookup groups by key columns and nothing
        else, because a column outside the key is one no row of the join
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
                f'hold. A lookup reads one row per key, {list(shape.key)}, and a column outside that key '
                f'arrives as a dimension no row of the join fixes. Group by the key, or sum toward {outside}.'
            )
            return None
        kept = tuple(r for r in shape.key if r not in from_roles and r not in into_roles)
        join = Join(name, shape, (*from_roles, *kept), (*into_roles, *kept))
        one_row_per_group = set(shape.key) <= set(join.grouped)
        if not forward and not one_row_per_group:
            self.errors.append(
                f"{context}: {call}: at reads one row per group, and grouping '{name}' by {list(join.grouped)} "
                f'leaves several rows in a group — its key is {list(shape.key)}. Key the table by the columns '
                f'the call groups by, or sum instead.'
            )
            return None
        if forward and one_row_per_group:
            self.errors.append(
                f'{context}: {call}: the columns this sum groups by, {list(join.grouped)}, hold the whole key '
                f'{list(shape.key)}, so every group is one row and nothing is added up — that is a join with no '
                f"group-by, which is at()'s. Write at(..., by={name}, over={list(from_roles)}, "
                f'into={list(into_roles)}), or sum toward a value column.'
            )
            return None
        return join

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
        if isinstance(node, UnresolvedNameNode):
            return self._where_name(node)
        if isinstance(node, UnresolvedComparisonNode):
            return self._comparison(node)
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

    def _where_name(self, node: UnresolvedNameNode) -> Predicate | UnresolvedWhereNode:
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

    def _comparison(self, node: UnresolvedComparisonNode) -> Predicate | UnresolvedWhereNode:
        """``side <op> side``, read for what each side is: a ``position()`` call, or a name against a literal or a column.

        The grammar admits any arithmetic on a side, and this is where the
        language decides what it accepts there.
        """
        if isinstance(node.left, FunctionCallNode) and node.left.name == 'position':
            return self._position(node.left, node)
        plain = self._plain(node)
        return node if plain is None else self._plain_comparison(node, plain)

    def _plain(self, node: UnresolvedComparisonNode) -> _Plain | None:
        """The comparison as ``name <op> literal`` or ``name <op> name``, or ``None`` with the refusal appended."""
        name, right = _side_name(node.left), node.right
        value: float | str | None
        quoted = isinstance(right, QuotedNode)
        if isinstance(right, QuotedNode):
            value = right.value
        elif isinstance(right, ColumnNode):
            value = right.shown
        elif (literal := _literal(right)) is not None:
            value = literal.value
        else:
            value = _side_name(right)
        if name is None or value is None:
            self.errors.append(
                f'{self.context}: a where-comparison tests one name, relation column or position() against a '
                f'literal or a second column, and a side here is arithmetic, which is not in the language. '
                f'Precompute the test as a boolean parameter in data prep and test that.'
            )
            return None
        return _Plain(name, node.op, value, quoted)

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
        index = None if isinstance(node.right, ColumnNode | QuotedNode) else _literal(node.right)
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
    into = within.names if isinstance(within, NameListNode) else (within.name,) if within is not None else None
    return call.args[0].name, by.name if by is not None else None, into


def _literal(value: ArithmeticNode) -> NumberNode | None:
    """The number a literal names, its sign folded in — ``None`` where *value* is not one.

    Folded here so that every later reader of an ``offset=`` or ``edge=`` —
    the dim rules, lowering, the typesetter — meets one signed number rather
    than each peeling a unary minus of its own.
    """
    if isinstance(value, NumberNode):
        return value
    if isinstance(value, UnaryOperatorNode) and isinstance(value.operand, NumberNode):
        return NumberNode(-value.operand.value if value.op == '-' else value.operand.value)
    return None


def _declared_rhs_error(context: str, node: _Plain, value: str, kind: str) -> str:
    """Why the right-hand side of a where-comparison may not name a declaration."""
    comparison = f"'{node.name} {node.op} {value}'"
    if kind == 'parameter':
        return (
            f'{context}: {comparison} compares two parameters, which is not in the '
            f'language — a where-comparison tests one parameter or dimension against '
            f'a literal. Precompute the comparison as a boolean parameter in data '
            f'prep and test that.'
        )
    if kind == 'variable':
        return (
            f'{context}: {comparison} compares against variable {value!r}. '
            f'A where mask is built before variables exist.'
        )
    if kind == 'relation':
        return (
            f'{context}: {comparison} compares {node.name!r} against relation {value!r}, and a '
            f'relation is structure rather than data — every other comparison tests a name '
            f'against a literal. A relation on the right-hand side is the one exception, and '
            f'only where the left-hand side is a relation sharing its dimension and its target.'
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
