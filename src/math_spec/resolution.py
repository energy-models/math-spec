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
    KeywordNode,
    KwargNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    ParsedNode,
    UnaryOperatorNode,
    VariableNode,
    case_context,
    nodes,
    shown,
    with_children,
)
from math_spec._where_parser import (
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    UnresolvedWhereNode,
    parse_where,
)
from math_spec.errors import LanguageError, did_you_mean
from math_spec.expansion import parse_and_expand
from math_spec.model import NUMERIC_DTYPES
from math_spec.operators import (
    BUILTINS,
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.program import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    Mask,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    TypedPredicateNode,
    VariableDefinedNode,
    Walk,
    WhereNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from math_spec.model import DeclaredDtype, Spec


#: What a name a file may write turns out to be. Answered by
#: :meth:`Namespace.kind`, so a pass reading a name switches over this rather
#: than over the stores it would otherwise have to try in order.
DeclarationKind = Literal['variable', 'parameter', 'dimension', 'lookup']


class LookupShape(NamedTuple):
    """A lookup as the resolver reads it: ``(role, dimension)`` per column, and the key roles."""

    columns: tuple[tuple[str, str], ...]
    key: tuple[str, ...]

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(role for role, _ in self.columns)

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(role for role in self.roles if role not in self.key)

    def dim(self, role: str) -> str:
        return dict(self.columns)[role]

    def roles_over(self, dimension: str) -> tuple[str, ...]:
        """The roles bound to *dimension*."""
        return tuple(role for role, dim in self.columns if dim == dimension)


class Namespace:
    """The declared names of one schema, by kind.

    A name has one kind: model.py refuses one declared under two sections.
    """

    __slots__ = ('constraints', 'dimensions', 'dtypes', 'leaf_dims', 'lookups', 'parameters', 'variables')

    def __init__(
        self,
        variables: Iterable[str],
        parameters: Iterable[str],
        dimensions: Iterable[str],
        lookups: Mapping[str, LookupShape],
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
        #: name -> declared dtype, for dimensions, parameters and lookups alike;
        #: what a where comparison checks its literal against.
        self.dtypes: dict[str, DeclaredDtype] = dict(dtypes)
        #: lookup name -> its columns and key, as declared.
        self.lookups: dict[str, LookupShape] = dict(lookups)
        #: parameter or variable name -> the dims it is read through —
        #: parameters by their ``dims``, variables by their frame. Stamped onto
        #: each leaf a where names, the way a lookup leaf carries ``over``.
        self.leaf_dims: dict[str, tuple[str, ...]] = dict(leaf_dims)

    @classmethod
    def of(cls, schema: Spec) -> Namespace:
        """Build the namespace of *schema*, the whole of what a file may name."""
        return cls(
            schema.variables,
            schema.parameters,
            schema.dimensions,
            {n: LookupShape(lk.columns, lk.keys) for n, lk in schema.lookups.items()},
            {
                **{p: pd.dtype for p, pd in schema.parameters.items()},
                **{d: dd.dtype for d, dd in schema.dimensions.items()},
            },
            {
                **{p: tuple(pd.dims) for p, pd in schema.parameters.items()},
                **{v: tuple(vd.foreach) for v, vd in schema.variables.items()},
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
        if name in self.lookups:
            return 'lookup'
        return None

    def shape_of(self, lookup: str) -> LookupShape:
        """The columns and key of *lookup*, as declared."""
        return self.lookups[lookup]

    def unknown(self, name: str, context: str, *, allow_dims: bool, formals: Iterable[str] = ()) -> str:
        """The refusal for a *name* declared nowhere, listing what it could have been.

        Args:
            name: The name the file wrote.
            context: The declaration it was found in.
            allow_dims: Whether a dimension would have been accepted there.
            formals: A macro's formals, listed first when there are any.
        """
        shown: list[tuple[str, Iterable[str]]] = [('Formals', formals)] if formals else []
        shown += (
            [('Parameters', self.parameters), ('Dimensions', self.dimensions)]
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
    """

    expressions: dict[str, CasesNode | DefinitionNode]
    variables: dict[str, Mask | None]
    constraints: dict[str, ResolvedConstraint]
    objective: ArithmeticNode | None

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
    ``BooleanLiteralNode(False)``.

    Raises:
        LanguageError: Listing every problem the predicate has.
    """
    errors: list[str] = []
    resolved = resolve_where_text(text, ns, context, errors, self_variable)
    if errors:
        raise LanguageError('\n'.join(errors))
    return mask_of(resolved)


def names_in(value: ArithmeticNode) -> tuple[str, ...]:
    """The names a lookup kwarg carries: one bare, several bracketed, none otherwise."""
    if isinstance(value, NameNode):
        return (value.name,)
    return value.names if isinstance(value, NameListNode) else ()


def mask_of(node: WhereNode | None) -> Mask | None:
    """The mask a declaration carries for a resolved where: ``None`` where there is none, or where every row passes."""
    if node is None or (isinstance(node, BooleanLiteralNode) and node.value):
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
    node: WhereNode | UnresolvedWhereNode,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> WhereNode | None:
    """Rewrite a parsed where AST into typed predicates, folded as :class:`~math_spec.program.Mask` folds.

    Returns:
        The typed tree — a mask admitting every row or none comes back as the
        one ``BooleanLiteralNode`` — or ``None`` once anything failed, with the
        problems appended to *errors*.
    """
    before = len(errors)
    resolved = _Resolver(ns, context, errors, self_variable).where(node)
    return None if len(errors) > before else Mask(cast('WhereNode', resolved)).root


def resolve_where_text(
    text: str | None,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> WhereNode | None:
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

        *amount* marks an ``offset=``/``within=`` value, whose dtype rule is
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
                f'{self.context}: {node.shown} is a list of names, which is only legal as an operator '
                f'kwarg value such as sum(x, by=[gen_bus, gen_tech]). In an expression, write the '
                f'terms out and add them.'
            )
            return node
        if isinstance(node, CasesNode):
            return self._cases(node)
        assert_never(node)

    def _name(self, node: NameNode, *, amount: bool) -> ArithmeticNode:
        """A bare name as the variable or parameter it declares; a dimension or lookup is not a value."""
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
                    f"'foreach:', in operator arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
                )
                return node
            case 'lookup':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a lookup, and a lookup is structure "
                    f'rather than data, so it is not a value in an expression. A lookup '
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
        roles = {key: value for key, value in node.kwargs.items() if builtin.kind_of(key) == 'role'}
        if roles and 'by' not in node.kwargs:
            self.errors.append(
                f'{self.context}: {node.name}({", ".join(f"{k}=" for k in roles)}) names a column of a lookup, '
                f'and no by= names the lookup. Write {builtin.usage}'
            )
        for key, value in node.kwargs.items():
            match builtin.kind_of(key):
                case 'edge':
                    kwargs[key] = self._edge(value, node.name)
                case 'dimension':
                    kwargs[key] = self._dim_ref(value, node.name, key)
                case 'lookup':
                    kwargs[key] = self._lookup_ref(value, node.name, key, roles, node.kwargs.get('over'))
                case 'role':
                    pass
                case 'value':
                    kwargs[key] = self._amount(value, node.name, key)
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
        """``offset=`` or ``within=``: a number or a parameter name, never an expression.

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

    def _lookup_ref(
        self,
        value: ArithmeticNode,
        operator: str,
        key: str,
        roles: Mapping[str, ArithmeticNode],
        over: ArithmeticNode | None,
    ) -> ArithmeticNode:
        """An operator's ``by=``, with the ``from=`` and ``into=`` that say how each lookup is walked.

        A lookup carries its own dimensions, so the call names columns rather
        than dims: ``from=`` the column consumed, ``into=`` the column produced,
        every other key column joined on — a value column not walked is not
        read, and a bare relation's columns are all key. Where the declaration
        leaves one choice
        — a key of one column, a value of one column — the call may leave it
        unsaid. A bracketed list is one grouping through several tables at
        once rather than a composition of groupings, so its members walk the
        same dimension, take their defaults, and must not produce the same
        dim twice.
        """
        names = names_in(value)
        if not names:
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a lookup.')
            return value

        problems = [p for p in (self._not_a_lookup(n, operator, key) for n in names) if p is not None]
        if problems:
            self.errors.extend(problems)
            return value
        if len(names) > 1 and roles:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}, {", ".join(f"{k}=" for k in roles)}): a list '
                f'walks each lookup by its declared key and value, so from= and into= have nothing to name. '
                f'Name one lookup, or declare one table with the columns of both.'
            )
            return value
        named = {k: self._role_name(v, operator, k) for k, v in roles.items()}
        if any(r is None for r in named.values()):
            return value
        if operator in ('shift', 'sum_back'):
            over_dim = over.name if isinstance(over, NameNode | DimensionNode) else None
            walks = [self._partition_walk(n, operator, over_dim) for n in names]
        else:
            walks = [self._walk(n, operator, named.get('from'), named.get('into')) for n in names]
        if any(w is None for w in walks):
            return value
        resolved = [w for w in walks if w is not None]

        def fine_of(w: Walk) -> tuple[str, ...]:
            return w.produced_dims if operator == 'at' and w.produced else w.consumed_dims

        def coarse_of(w: Walk) -> tuple[str, ...]:
            return w.consumed_dims if operator == 'at' else w.produced_dims

        fine = {frozenset(fine_of(w)) for w in resolved}
        if len(fine) > 1:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) groups through lookups along different '
                f'dimensions ({", ".join(f"{w.name} along {sorted(fine_of(w))}" for w in resolved)}). One grouping '
                f'consumes one set of dimensions, so every lookup in the list must walk the same — group through '
                f'them in turn instead, one call each.'
            )
            return value
        coarse = tuple(dim for w in resolved for dim in coarse_of(w))
        repeated = sorted({t for t in coarse if coarse.count(t) > 1})
        if repeated:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) produces {repeated} more than once. '
                f'Each column walked to produces its own dimension, so two that land on the '
                f'same one would need it twice — drop one.'
            )
            return value
        return LookupNode(names, dimensions=fine_of(resolved[0]), into=coarse, walks=tuple(resolved))

    def _role_name(self, value: ArithmeticNode, operator: str, key: str) -> tuple[str, ...] | None:
        """``from=`` or ``into=`` as the column names it must be — one bare name, or a bracketed list of them."""
        if isinstance(value, NameNode):
            return (value.name,)
        if isinstance(value, NameListNode):
            return value.names
        self.errors.append(
            f'{self.context}: {operator}({key}=...) names columns of the lookup — a bare name, or a list of them.'
        )
        return None

    def _walk(
        self,
        name: str,
        operator: str,
        from_roles: tuple[str, ...] | None,
        into_roles: tuple[str, ...] | None,
    ) -> Walk | None:
        """How ``sum`` or ``at`` walks lookup *name*, from the columns the call named and the declaration's defaults.

        The call consumes one or more columns and produces one or more; a
        side it leaves unsaid is taken from the declaration where it has
        exactly one candidate, and refused with the candidates otherwise.
        """
        ns, context = self.ns, self.context
        shape = ns.shape_of(name)
        call = f'{operator}(by={name})'

        def known(roles: tuple[str, ...] | None, kwarg: str) -> bool:
            for role in roles or ():
                if role not in shape.roles:
                    self.errors.append(
                        f"{context}: {call}: {kwarg}={role} names no column of '{name}', whose columns are "
                        f'{list(shape.roles)}.'
                    )
                    return False
            if roles is not None and len(set(roles)) < len(roles):
                self.errors.append(f'{context}: {call}: {kwarg}={list(roles)} names a column twice.')
                return False
            return True

        if not (known(from_roles, 'from') and known(into_roles, 'into')):
            return None

        forward = operator == 'sum'
        if from_roles is None:
            side = shape.key if forward else shape.values
            default = self._default_role(name, call, 'from', side, 'key' if forward else 'value')
            if default is None:
                return None
            from_roles = (default,)
        if into_roles is None:
            side = shape.values if forward else shape.key
            default = self._default_role(name, call, 'into', side, 'value' if forward else 'key')
            if default is None:
                return None
            into_roles = (default,)
        if both := sorted(set(from_roles) & set(into_roles)):
            self.errors.append(
                f'{context}: {call}: from= and into= both name {both}, and a walk goes between two sets of columns.'
            )
            return None
        joined = tuple(r for r in (shape.key or shape.roles) if r not in from_roles and r not in into_roles)
        walk = Walk(name, from_roles, into_roles, joined, shape.columns, shape.key)
        if not forward and not walk.is_function_read:
            self.errors.append(
                f"{context}: {call}: at reads one value per coordinate, and '{name}' is not single-valued in "
                f'{list(from_roles)} at the columns the operand fixes ({[*into_roles, *joined]}) — its key is '
                f'{list(shape.key)}. Declare a key those columns contain, or read the other way.'
            )
            return None
        return walk

    def _partition_walk(self, name: str, operator: str, walked_dim: str | None) -> Walk | None:
        """How a partition (``shift``, ``sum_back``, ``position``) walks lookup *name* along *walked_dim*.

        It walks the one key column over that dimension, joins on the other
        key columns and groups by the value columns. ``None`` where the
        dimension is not one (already refused) or the lookup has no such
        column, or two.
        """
        context = self.context
        shape = self.ns.shape_of(name)
        call = f'{operator}(by={name})'
        if walked_dim is None:
            return None
        if not shape.key:
            self.errors.append(
                f"{context}: {call}: '{name}' declares no key, so no coordinate is in exactly one group. "
                f'Declare key: on the lookup, naming the column {operator} walks.'
            )
            return None
        over_keys = [r for r in shape.key if shape.dim(r) == walked_dim]
        if not over_keys:
            self.errors.append(
                f"{context}: {call}: '{name}' has no key column over '{walked_dim}' — its key is "
                f'{list(shape.key)} — and a partition walks a key column over the dimension it groups.'
            )
            return None
        if len(over_keys) > 1:
            self.errors.append(
                f"{context}: {call}: '{name}' has {len(over_keys)} key columns over '{walked_dim}' ({over_keys}), "
                f"and a partition walks exactly one. Declare a lookup keyed by one column over '{walked_dim}'."
            )
            return None
        (walked,) = over_keys
        joined = tuple(r for r in shape.key if r != walked)
        return Walk(name, (walked,), (), joined, shape.columns, shape.key)

    def _default_role(self, name: str, call: str, kwarg: str, side: tuple[str, ...], what: str) -> str | None:
        """The one column *side* offers, or the refusal naming what the call has to choose from."""
        if len(side) == 1:
            return side[0]
        shape = self.ns.shape_of(name)
        if not shape.key:
            self.errors.append(
                f"{self.context}: {call}: '{name}' declares no key, so nothing says which column {call.split('(', maxsplit=1)[0]} "
                f'walks. Name both: {kwarg}= among {list(shape.roles)} — or declare key: on the lookup.'
            )
            return None
        self.errors.append(
            f"{self.context}: {call}: '{name}' has {len(side)} {what} columns ({list(side)}), and the call has to say "
            f'which {kwarg}= names.'
        )
        return None

    def _not_a_lookup(self, name: str, operator: str, key: str) -> str | None:
        """Why *name* is not a lookup; ``None`` where it is one."""
        ns, context = self.ns, self.context
        if name in ns.lookups:
            return None
        if name in ns.dimensions:
            over_here = sorted(n for n, shape in ns.lookups.items() if name in dict(shape.columns).values())
            hint = (
                f"  Lookups with a column over '{name}': {over_here}"
                if over_here
                else f"  No lookup has a column over '{name}'."
            )
            return (
                f"{context}: {operator}({key}={name}): '{name}' is a dimension, and "
                f'{key}= takes a lookup — the named map out of a dimension.\n{hint}'
            )
        return (
            f'{context}: {operator}({key}={name}) does not name a lookup. '
            f'{did_you_mean(name, ns.lookups, label="Lookups")}\n'
            f"Declare it under 'lookups:' — {name}: {{over: [<its columns>], key: <the column a row is "
            f'identified by>}}.'
        )

    # -- where strings -----------------------------------------------------

    def where(self, node: WhereNode | UnresolvedWhereNode) -> WhereNode | UnresolvedWhereNode:
        """One predicate node typed, or returned unresolved with its refusal appended."""
        if isinstance(node, BooleanLiteralNode | TypedPredicateNode):
            return node
        if isinstance(node, UnresolvedNameNode):
            return self._where_name(node)
        if isinstance(node, UnresolvedPositionNode):
            return self._position(node)
        if isinstance(node, UnresolvedComparisonNode):
            return self._comparison(node)
        if isinstance(node, NotNode):
            return NotNode(self._child(node.operand))
        if isinstance(node, AndNode):
            return AndNode(self._child(node.left), self._child(node.right))
        if isinstance(node, OrNode):
            return OrNode(self._child(node.left), self._child(node.right))
        assert_never(node)

    def _child(self, node: WhereNode | UnresolvedWhereNode) -> WhereNode:
        """A connective's child, typed as resolved: an unresolved one survives only with its refusal appended."""
        return cast('WhereNode', self.where(node))

    def _where_name(self, node: UnresolvedNameNode) -> WhereNode | UnresolvedWhereNode:
        """A bare name: a parameter's or lookup's definedness, or a variable's existence."""
        ns, context = self.ns, self.context
        kind = ns.kind(node.name)
        if kind is None:
            self.errors.append(ns.unknown(node.name, context, allow_dims=True))
            return node
        match kind:
            case 'parameter':
                return ParameterDefinedNode(node.name, ns.leaf_dims[node.name])
            case 'dimension':
                self.errors.append(
                    f"{context}: '{node.name}' is a dimension, and a bare dimension "
                    f'name is true at every coordinate — the mask has no effect. '
                    f'Remove it, or compare it: where: "{node.name} > 0".'
                )
            case 'lookup':
                shape = ns.shape_of(node.name)
                dims = tuple(shape.dim(k) for k in shape.key) if shape.key else tuple(dim for _, dim in shape.columns)
                if len(set(dims)) < len(dims):
                    self.errors.append(
                        f"{context}: '{node.name}' has two columns over one dimension ({list(shape.roles)}), so a "
                        f'bare name cannot say which the frame supplies. Compare a column: '
                        f'{node.name}.{shape.values[0] if shape.values else shape.roles[-1]} == ....'
                    )
                    return node
                return LookupDefinedNode(node.name, dims)
            case 'variable':
                if node.name == self.self_variable:
                    self.errors.append(
                        f"{context}: variable '{node.name}' asks whether it exists in its own "
                        f'where, which nothing can answer — the mask is what decides where it '
                        f'exists. Test a parameter, or another variable declared before it.'
                    )
                else:
                    return VariableDefinedNode(node.name, ns.leaf_dims[node.name])
        return node

    def _position(self, node: UnresolvedPositionNode) -> DimensionPositionNode | UnresolvedPositionNode:
        """``position(dim[, by=lookup]) <op> i``: the name a dimension, ``by=`` a lookup keyed over it."""
        ns, context = self.ns, self.context
        if node.dimension not in ns.dimensions:
            self.errors.append(
                f"{context}: position() counts along a dimension's coordinates, and "
                f"'{node.dimension}' is {_declared_as(ns, node.dimension)}. "
                f'{did_you_mean(node.dimension, ns.dimensions, label="Dimensions")}'
            )
            return node
        if node.by is None:
            return DimensionPositionNode(node.dimension, node.op, node.position)
        call = f'position({node.dimension}, by={node.by})'
        if ns.kind(node.by) != 'lookup':
            self.errors.append(
                f"{context}: '{call}' groups by '{node.by}', which is {_declared_as(ns, node.by)}. "
                f'``by=`` takes a lookup with a key column over that dimension. '
                f'{did_you_mean(node.by, ns.lookups, label="Lookups")}'
            )
            return node
        walk = self._partition_walk(node.by, 'position', node.dimension)
        if walk is None:
            return node
        (walked,) = walk.consumed
        return DimensionPositionNode(node.dimension, node.op, node.position, node.by, walked, walk.joined_dims)

    def _comparison(self, node: UnresolvedComparisonNode) -> WhereNode | UnresolvedWhereNode:
        """``name <op> literal``, or the one structural form ``lookup <op> lookup``."""
        ns, context = self.ns, self.context
        value = node.value
        left_name, _, left_column = node.name.partition('.')
        if not node.quoted and isinstance(value, str):
            right_name, _, right_column = value.partition('.')
            if (rhs_kind := ns.kind(right_name)) is not None:
                if rhs_kind == 'lookup' and ns.kind(left_name) == 'lookup':
                    left = self._lookup_column(left_name, left_column or None, node.name)
                    right = self._lookup_column(right_name, right_column or None, value)
                    if left is None or right is None:
                        return node
                    if (refusal := _lookup_pair_error(context, node, value, ns, left, right)) is not None:
                        self.errors.append(refusal)
                        return node
                    dims = tuple(ns.shape_of(left_name).dim(k) for k in ns.shape_of(left_name).key)
                    return LookupPairComparisonNode(left_name, left, right_name, right, node.op, dims)
                self.errors.append(_declared_rhs_error(context, node, value, rhs_kind))
                return node

        kind = ns.kind(left_name)
        if kind is None:
            self.errors.append(ns.unknown(left_name, context, allow_dims=True))
            return node
        if left_column and kind != 'lookup':
            self.errors.append(
                f"{context}: '{node.name}' reads a column of '{left_name}', which is {_declared_as(ns, left_name)}. "
                f'Only a lookup has columns.'
            )
            return node
        column = None
        dtype: DeclaredDtype | None = None
        if kind == 'lookup':
            column = self._lookup_column(left_name, left_column or None, node.name)
            if column is None:
                return node
            dtype = ns.dtypes[ns.shape_of(left_name).dim(column)]
        elif kind in ('parameter', 'dimension'):
            dtype = ns.dtypes[left_name]
        if dtype is not None:
            typed = self._typed_literal(node, dtype)
            if typed is None:
                return node
            value = typed

        match kind:
            case 'parameter':
                assert not isinstance(value, datetime.date)
                return ParameterComparisonNode(left_name, node.op, value, ns.leaf_dims[left_name])
            case 'dimension':
                return DimensionComparisonNode(left_name, node.op, value)
            case 'lookup':
                assert column is not None
                shape = ns.shape_of(left_name)
                return LookupComparisonNode(left_name, column, node.op, value, tuple(shape.dim(k) for k in shape.key))
            case 'variable':
                self.errors.append(
                    f"{context}: where references variable '{left_name}'. A where "
                    f'mask is built before variables exist — it may test parameters '
                    f'and dimension coordinates only.'
                )
        return node

    def _lookup_column(self, name: str, column: str | None, spelling: str) -> str | None:
        """The value column a where-comparison on lookup *name* reads, or the refusal.

        A comparison reads one value per coordinate, so the lookup is keyed
        and the column is one the key determines; unsaid, it is the one value
        column where there is exactly one.
        """
        ns, context = self.ns, self.context
        shape = ns.shape_of(name)
        if not shape.key:
            self.errors.append(
                f"{context}: '{spelling}' compares a column of '{name}', which declares no key, so it has no one "
                f'value per coordinate to compare. Declare key: on the lookup, or test the bare name — '
                f"'{name}' — for whether a row exists."
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
                f"than reads. Compare the frame's own coordinate — {shape.dim(column)} {{op}} ... — or a value column."
            )
            return None
        return column

    def _typed_literal(
        self, node: UnresolvedComparisonNode, dtype: DeclaredDtype
    ) -> float | str | datetime.date | None:
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


def _declared_rhs_error(context: str, node: UnresolvedComparisonNode, value: str, kind: str) -> str:
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
    if kind == 'lookup':
        return (
            f'{context}: {comparison} compares {node.name!r} against lookup {value!r}, and a '
            f'lookup is structure rather than data — every other comparison tests a name '
            f'against a literal. A lookup on the right-hand side is the one exception, and '
            f'only where the left-hand side is a lookup sharing its dimension and its target.'
        )
    return (
        f'{context}: {comparison} compares against dimension {value!r}, which the RHS reads '
        f'as the literal coordinate {value!r} and so masks everything out. Comparing two '
        f'dimensions is not in the language; if {value!r} is a coordinate rather than the '
        f'dimension, rename one of the two.'
    )


def _lookup_pair_error(
    context: str, node: UnresolvedComparisonNode, other: str, ns: Namespace, left: str, right: str
) -> str | None:
    """Why two lookup columns may not be compared, or ``None`` where they may.

    Both lookups are read at their keys, so the keys must be over the same
    dimensions or no row carries both; and the two columns must be over one
    dimension, or no value of one is ever a value of the other. Both wrong
    answers are silent, and a build's data library decides which one.
    """
    comparison = f"'{node.name} {node.op} {other}'"
    left_name, right_name = node.name.partition('.')[0], other.partition('.')[0]
    ls, rs = ns.shape_of(left_name), ns.shape_of(right_name)
    left_keys, right_keys = {ls.dim(k) for k in ls.key}, {rs.dim(k) for k in rs.key}
    if left_keys != right_keys:
        return (
            f'{context}: {comparison} compares lookups keyed over different dimensions '
            f"('{left_name}' by {sorted(left_keys)}, '{right_name}' by {sorted(right_keys)}) — there is no row "
            f'carrying both, so the comparison has nothing to test. Two lookups may be compared only '
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
