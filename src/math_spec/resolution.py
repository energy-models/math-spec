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
from typing import TYPE_CHECKING, Literal, assert_never, cast

from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CaseArm,
    CasesNode,
    ComparisonNode,
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
    shown,
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
    WhereNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from math_spec.model import DeclaredDtype, Spec


#: What a name a file may write turns out to be. Answered by
#: :meth:`Namespace.kind`, so a pass reading a name switches over this rather
#: than over the stores it would otherwise have to try in order.
DeclarationKind = Literal['variable', 'parameter', 'dimension', 'lookup']


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
        lookups: Mapping[str, tuple[str, str | None]],
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
        #: lookup name -> ``(over, into)``; ``into`` is ``None`` for a label
        #: space, which owns its values.
        self.lookups: dict[str, tuple[str, str | None]] = dict(lookups)
        #: parameter or variable name -> the dims it is read through —
        #: parameters by their ``dims``, variables by their frame. Stamped onto
        #: each leaf a where names, the way a lookup leaf carries ``over``.
        self.leaf_dims: dict[str, tuple[str, ...]] = dict(leaf_dims)

    def groupable(self) -> dict[str, str]:
        """The lookups a ``by=`` may name: name -> the dimension it maps into.

        A label space is absent, which is what makes naming one in a ``by=``
        answerable with the promotion rewrite rather than "no such lookup".
        """
        return {n: into for n, (_, into) in self.lookups.items() if into is not None}

    @classmethod
    def of(cls, schema: Spec) -> Namespace:
        """Build the namespace of *schema*, the whole of what a file may name.

        A targeted lookup's values are labels of its target, so its dtype is
        the target's.
        """
        return cls(
            schema.variables,
            schema.parameters,
            schema.dimensions,
            {n: (lk.over, lk.into) for n, lk in schema.lookups.items()},
            {
                **{p: pd.dtype for p, pd in schema.parameters.items()},
                **{d: dd.dtype for d, dd in schema.dimensions.items()},
                **{n: schema.dimensions[lk.into].dtype for n, lk in schema.lookups.items() if lk.into is not None},
                **{n: lk.dtype for n, lk in schema.lookups.items() if lk.dtype is not None},
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

    def over_of(self, lookup: str) -> str:
        """The dimension *lookup* maps out of, whichever kind it is."""
        return self.lookups[lookup][0]

    def into_of(self, lookup: str) -> str | None:
        """The dimension *lookup*'s values are labels of, ``None`` for a label space."""
        return self.lookups[lookup][1]

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


# ---------------------------------------------------------------------------
# the seam the rest of the package uses
# ---------------------------------------------------------------------------


def expression_of(text: str, schema: Spec, ns: Namespace, context: str) -> ParsedNode:
    """Parse, expand and resolve *text* — the one path to a resolved spec-side tree.

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
    if resolved is None or (isinstance(resolved, BooleanLiteralNode) and resolved.value):
        return None
    return Mask(resolved)


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
        if isinstance(node, UnaryOperatorNode):
            return UnaryOperatorNode(node.op, self._arith(node.operand))
        if isinstance(node, BinaryOperatorNode):
            return BinaryOperatorNode(node.op, self._arith(node.left), self._arith(node.right))
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
        for key, value in node.kwargs.items():
            match builtin.kind_of(key):
                case 'edge':
                    kwargs[key] = self._edge(value, node.name)
                case 'dimension':
                    kwargs[key] = self._dim_ref(value, node.name, key)
                case 'lookup':
                    kwargs[key] = self._lookup_ref(value, node.name, key)
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
            self.errors.append(
                f"{self.context}: dual({value.name}): '{value.name}' is not a declared constraint.\n"
                f'  Constraints: {sorted(self.ns.constraints)}\n'
                f"Check for typos, or declare '{value.name}' under 'constraints:'."
            )
            return node
        return DualNode(value.name)

    def _lookup_ref(self, value: ArithmeticNode, operator: str, key: str) -> ArithmeticNode:
        """An operator kwarg whose *value* must name groupable lookups.

        A lookup carries its own dimensions, so nothing else in the call is
        consulted: the names alone decide both the dim the operator consumes and
        the ones it produces. A bracketed list is one grouping through several
        maps at once rather than a composition of groupings, so its members must
        share the dim they are over and must not target the same dim twice.
        """
        if isinstance(value, NameListNode):
            names = value.names
        elif isinstance(value, NameNode):
            names = (value.name,)
        else:
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a lookup.')
            return value

        ns = self.ns
        groupable = ns.groupable()
        named = [self._ungroupable(name, groupable, operator, key) for name in names]
        if any(problem is not None for problem in named):
            self.errors.extend(problem for problem in named if problem is not None)
            return value

        over = {ns.over_of(name) for name in names}
        if len(over) > 1:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) groups through lookups over '
                f'different dimensions ({", ".join(f"{n} over {ns.over_of(n)}" for n in names)}). '
                f'One grouping consumes one dimension, so every lookup in the list must be '
                f'over the same one — group through them in turn instead, one call each.'
            )
            return value

        targets = tuple(groupable[name] for name in names)
        repeated = sorted({t for t in targets if targets.count(t) > 1})
        if repeated:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) targets {repeated} more than once. '
                f'Each lookup in the list produces its own dimension, so two that land on the '
                f'same one would need it twice — drop one, or group into a dimension of its own.'
            )
            return value

        return LookupNode(names, dimension=next(iter(over)), into=targets)

    def _ungroupable(self, name: str, groupable: Mapping[str, str], operator: str, key: str) -> str | None:
        """Why *name* is not a groupable lookup; ``None`` where it is one."""
        ns, context = self.ns, self.context
        if name in ns.lookups and name not in groupable:
            over = ns.over_of(name)
            return (
                f'{context}: {operator}({key}={name}): '
                f"'{name}' is a label space over '{over}', not a groupable lookup — "
                f'it targets no dimension for the terms to land on. To group into it, '
                f'declare the axis and target it under a name of its own:\n'
                f'  dimensions:\n'
                f'    {name}: {{...}}\n'
                f'  lookups:\n'
                f'    {name}_of: {{over: {over}, into: {name}}}'
            )
        if name in groupable:
            return None
        if name in ns.dimensions:
            into_here = sorted(n for n, into in groupable.items() if into == name)
            hint = f"  Lookups into '{name}': {into_here}" if into_here else f"  No lookup maps into '{name}'."
            return (
                f"{context}: {operator}({key}={name}): '{name}' is a dimension, and "
                f'{key}= takes a lookup — the named map out of a dimension.\n{hint}'
            )
        return (
            f'{context}: {operator}({key}={name}) does not name a lookup. '
            f'{did_you_mean(name, groupable, label="Lookups")}\n'
            f"Declare it under 'lookups:' — {name}: {{over: <the dimension it maps "
            f'out of>, into: <the dimension its values are labels of>}}.'
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
                return LookupDefinedNode(node.name, ns.over_of(node.name))
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
        """``position(dim[, by=lookup]) <op> i``: the name a dimension, ``by=`` a lookup over it."""
        ns, context = self.ns, self.context
        if node.dimension not in ns.dimensions:
            self.errors.append(
                f"{context}: position() counts along a dimension's coordinates, and "
                f"'{node.dimension}' is {_declared_as(ns, node.dimension)}. "
                f'{did_you_mean(node.dimension, ns.dimensions, label="Dimensions")}'
            )
            return node
        if node.by is None:
            return DimensionPositionNode(node.dimension, node.op, node.position, node.by)
        call = f'position({node.dimension}, by={node.by})'
        if ns.kind(node.by) != 'lookup':
            self.errors.append(
                f"{context}: '{call}' groups by '{node.by}', which is {_declared_as(ns, node.by)}. "
                f'``by=`` takes a lookup over that dimension — either kind, since counting '
                f'inside a group lands no terms, unlike sum(by=) and at(by=). '
                f'{did_you_mean(node.by, ns.lookups, label="Lookups")}'
            )
            return node
        over = ns.over_of(node.by)
        if over != node.dimension:
            self.errors.append(
                f"{context}: '{call}' counts positions along '{node.dimension}' but groups by a "
                f"lookup over '{over}'. No row of '{node.dimension}' carries it, so there is no "
                f"position within a group to name — group by a lookup over '{node.dimension}'."
            )
            return node
        return DimensionPositionNode(node.dimension, node.op, node.position, node.by)

    def _comparison(self, node: UnresolvedComparisonNode) -> WhereNode | UnresolvedWhereNode:
        """``name <op> literal``, or the one structural form ``lookup <op> lookup``."""
        ns, context = self.ns, self.context
        value = node.value
        if not node.quoted and isinstance(value, str) and (rhs_kind := ns.kind(value)) is not None:
            if rhs_kind == 'lookup' and ns.kind(node.name) == 'lookup':
                if (refusal := _lookup_pair_error(context, node, value, ns)) is not None:
                    self.errors.append(refusal)
                    return node
                return LookupPairComparisonNode(node.name, value, ns.over_of(node.name), node.op)
            self.errors.append(_declared_rhs_error(context, node, value, rhs_kind))
            return node

        kind = ns.kind(node.name)
        if kind is None:
            self.errors.append(ns.unknown(node.name, context, allow_dims=True))
            return node
        if kind in ('parameter', 'dimension', 'lookup'):
            typed = self._typed_literal(node, ns.dtypes[node.name])
            if typed is None:
                return node
            value = typed

        match kind:
            case 'parameter':
                assert not isinstance(value, datetime.date)
                return ParameterComparisonNode(node.name, node.op, value, ns.leaf_dims[node.name])
            case 'dimension':
                return DimensionComparisonNode(node.name, node.op, value)
            case 'lookup':
                return LookupComparisonNode(node.name, ns.over_of(node.name), node.op, value)
            case 'variable':
                self.errors.append(
                    f"{context}: where references variable '{node.name}'. A where "
                    f'mask is built before variables exist — it may test parameters '
                    f'and dimension coordinates only.'
                )
        return node

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


def _label_set_of(ns: Namespace, lookup: str) -> str:
    """Where a lookup's values come from, as a refusal reads it."""
    into = ns.into_of(lookup)
    return f"'{lookup}' (mapping into '{into}')" if into is not None else f"'{lookup}' (a label space of its own)"


def _lookup_pair_error(context: str, node: UnresolvedComparisonNode, other: str, ns: Namespace) -> str | None:
    """Why two lookups may not be compared, or ``None`` where they may.

    They must map out of the same dimension, or no row carries both; and into
    the same one, or no value of one is ever a value of the other. Both wrong
    answers are silent, and a build's data library decides which one.
    """
    comparison = f"'{node.name} {node.op} {other}'"
    left_over, right_over = ns.over_of(node.name), ns.over_of(other)
    if left_over != right_over:
        return (
            f'{context}: {comparison} compares lookups over different dimensions '
            f"('{left_over}' and '{right_over}') — there is no row carrying both, so the "
            f'comparison has nothing to test. Two lookups may be compared only where they '
            f'map out of the same dimension.'
        )
    left, right = ns.into_of(node.name), ns.into_of(other)
    if left is None or right is None or left != right:
        return (
            f'{context}: {comparison} compares {_label_set_of(ns, node.name)} with '
            f'{_label_set_of(ns, other)}. No value of one is ever a value of the other, so '
            f'the predicate can only mask everything out. Two lookups may be compared only '
            f'where they map into the same dimension.'
        )
    return None
