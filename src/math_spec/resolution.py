# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Name resolution — the pass that makes the core AST fully typed.

Parsers emit unresolved names; this module rewrites each into the typed node
its kind asks for, so the AST reaching a consumer holds none. Done once here,
every consumer scopes identically by construction. The rules live in the
language reference; the namespace is flat, and macro formals are the one scope.
"""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, assert_never

from math_spec.errors import LanguageError
from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    KwargNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
    shown,
)
from math_spec.model import NUMERIC_DTYPES
from math_spec.operators import (
    BUILTINS,
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    TypedPredicateNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    VariableDefinedNode,
    WhereNode,
    parse_where,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from math_spec.model import Spec


class Namespace:
    """The declared names of one schema, by kind.

    Flat by construction: :meth:`kind` is a single lookup, not an ordered
    walk through several stores.
    """

    __slots__ = ('dimensions', 'dtypes', 'lookups', 'parameters', 'variables')

    def __init__(
        self,
        variables: Iterable[str],
        parameters: Iterable[str],
        dimensions: Iterable[str],
        lookups: Mapping[str, tuple[str, str | None]],
        dtypes: Mapping[str, str],
    ) -> None:
        self.variables = frozenset(variables)
        self.parameters = frozenset(parameters)
        self.dimensions = frozenset(dimensions)
        #: name -> declared dtype, for dimensions, parameters and lookups alike;
        #: what a where comparison checks its literal against.
        self.dtypes: dict[str, str] = dict(dtypes)
        #: lookup name -> ``(over, into)``; ``into`` is ``None`` for a label
        #: space, which owns its values.
        self.lookups: dict[str, tuple[str, str | None]] = dict(lookups)

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
        )

    def kind(self, name: str) -> str | None:
        """``'variable'`` | ``'parameter'`` | ``'dimension'`` | ``'lookup'`` | ``None``."""
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

    def _unknown(self, name: str, context: str, *, allow_dims: bool) -> str:
        shown = (
            [('Parameters', self.parameters), ('Dimensions', self.dimensions)]
            if allow_dims
            else [('Variables', self.variables), ('Parameters', self.parameters)]
        )
        listing = '\n'.join(f'  {kind}: {sorted(names)}' for kind, names in shown)
        return f"{context}: '{name}' not found.\n{listing}\nCheck for typos, or ensure '{name}' is declared."


# ---------------------------------------------------------------------------
# the seam a consumer uses
# ---------------------------------------------------------------------------


def expression_of(text: str, schema: Spec, ns: Namespace, context: str) -> ExpressionNode:
    """Parse, expand and resolve *text* — the only way a consumer gets an AST.

    ``validation.py`` runs the same path at load time, so a consumer calling
    this gets a *typed* tree off a result already known to be clean, without
    duplicating the pass.

    Raises:
        LanguageError: Listing every problem the text has.
    """
    errors: list[str] = []
    resolved = resolve_expression(parse_and_expand(text, schema, context), ns, context, errors)
    if errors:
        raise LanguageError('\n'.join(errors))
    assert resolved is not None
    return resolved


def where_of(text: str | None, ns: Namespace, context: str, self_variable: str | None = None) -> WhereNode | None:
    """Parse, resolve and fold a where string — ``None`` for no mask, however the file spelled it.

    Every constant the connectives decide is folded away, so a mask that
    admits every row arrives as ``None`` and one that admits none as
    ``BooleanLiteralNode(False)``; that node stands at the root of a mask or
    nowhere in it, and every reader — a program, a typeset page — gets the
    same predicate.

    Raises:
        LanguageError: Listing every problem the predicate has.
    """
    if text is None:
        return None
    errors: list[str] = []
    resolved = resolve_where(parse_where(text), ns, context, errors, self_variable)
    if errors:
        raise LanguageError('\n'.join(errors))
    assert resolved is not None
    folded = _fold(resolved)
    if isinstance(folded, BooleanLiteralNode) and folded.value:
        return None
    return folded


def _fold(node: WhereNode) -> WhereNode:
    """*node* with every literal a connective decides evaluated away.

    ``X AND True`` is ``X``, ``X OR True`` is every row, ``X AND False`` is
    none, and ``NOT True`` is ``False``. What survives is a predicate over
    data, or the one literal the whole mask reduces to.
    """
    if isinstance(node, NotNode):
        operand = _fold(node.operand)
        if isinstance(operand, BooleanLiteralNode):
            return BooleanLiteralNode(not operand.value)
        return NotNode(operand)
    if isinstance(node, AndNode):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteralNode):
            return right if left.value else left
        if isinstance(right, BooleanLiteralNode):
            return left if right.value else right
        return AndNode(left, right)
    if isinstance(node, OrNode):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteralNode):
            return left if left.value else right
        if isinstance(right, BooleanLiteralNode):
            return right if right.value else left
        return OrNode(left, right)
    return node


# ---------------------------------------------------------------------------
# expressions
# ---------------------------------------------------------------------------


def resolve_expression(
    node: ExpressionNode,
    ns: Namespace,
    context: str,
    errors: list[str],
) -> ExpressionNode | None:
    """Rewrite every ``NameNode`` under *node* to a typed node.

    Operator *call shapes* are checked here too (``operators.call_shape_error``).
    Arity is a language rule, and this is the pass every consumer goes through,
    so no consumer has to state a signature a second time.

    Returns:
        The typed tree, or ``None`` once anything failed — appending to
        *errors* rather than raising, so a caller collecting problems across a
        whole schema reports them together.
    """
    before = len(errors)
    if isinstance(node, ComparisonNode):
        resolved: ExpressionNode = ComparisonNode(
            node.op,
            _resolve_arith(node.left, ns, context, errors),
            _resolve_arith(node.right, ns, context, errors),
        )
    else:
        resolved = _resolve_arith(node, ns, context, errors)
    return None if len(errors) > before else resolved


def _resolve_arith(
    node: ArithmeticNode,
    ns: Namespace,
    context: str,
    errors: list[str],
    *,
    amount: bool = False,
) -> ArithmeticNode:
    """The recursive worker under :func:`resolve_expression`.

    *amount* marks an ``offset=``/``within=`` value, whose dtype rule is
    ``dimensions._check_named_amount``'s and stricter than "a number", so the
    numeric check here stands aside for it. A quoted keyword or a name list in
    arithmetic arrives through a macro formal bound to one.
    """
    if isinstance(node, NumberNode):
        return node

    if isinstance(node, VariableNode | ParameterNode | KwargNode):
        return node

    if isinstance(node, NameNode):
        match ns.kind(node.name):
            case 'variable':
                return VariableNode(node.name)
            case 'parameter':
                dtype = ns.dtypes.get(node.name)
                if not amount and dtype is not None and dtype not in NUMERIC_DTYPES:
                    errors.append(_not_a_number(node.name, dtype, context))
                    return node
                return ParameterNode(node.name)
            case 'dimension':
                errors.append(
                    f"{context}: '{node.name}' is a dimension, and a dimension is "
                    f'not a value in an expression. Dimensions appear in '
                    f"'foreach:', in operator arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
                )
                return node
            case 'lookup':
                errors.append(
                    f"{context}: '{node.name}' is a lookup, and a lookup is structure "
                    f'rather than data, so it is not a value in an expression. A lookup '
                    f'appears in a helper (sum(x, by={node.name})) and in a where — to '
                    f'carry numbers along this dimension, declare a parameter over it.'
                )
                return node
            case _:
                errors.append(ns._unknown(node.name, context, allow_dims=False))
                return node

    if isinstance(node, UnaryOperatorNode):
        return UnaryOperatorNode(node.op, _resolve_arith(node.operand, ns, context, errors))

    if isinstance(node, BinaryOperatorNode):
        return BinaryOperatorNode(
            node.op,
            _resolve_arith(node.left, ns, context, errors),
            _resolve_arith(node.right, ns, context, errors),
        )

    if isinstance(node, FunctionCallNode):
        if node.name not in BUILTINS:
            errors.append(f'{context}: {unknown_operator_message(node.name)}')
            return node
        builtin = BUILTINS[node.name]
        shape_error = call_shape_error(node.name, len(node.args), node.kwargs)
        if shape_error is not None:
            errors.append(f'{context}: {shape_error}')
        args = [_resolve_arith(a, ns, context, errors) for a in node.args]
        kwargs: dict[str, ArithmeticNode] = {}
        for key, value in node.kwargs.items():
            if key in builtin.edge_kwargs:
                kwargs[key] = _resolve_edge(value, context, node.name, errors)
            elif key in builtin.dimension_kwargs:
                kwargs[key] = _resolve_dim_ref(value, ns, context, node.name, key, errors)
            elif key in builtin.lookup_kwargs:
                kwargs[key] = _resolve_lookup_ref(value, ns, context, node.name, key, errors)
            else:
                kwargs[key] = _resolve_amount(value, ns, context, node.name, key, errors)
        return FunctionCallNode(node.name, args, kwargs)

    if isinstance(node, KeywordNode):
        errors.append(
            f'{context}: {node.value!r} is a quoted keyword, which is only legal as a '
            f"operator kwarg value such as shift(..., edge='wrap'). In an expression, quote "
            f'nothing — names resolve and numbers are written bare.'
        )
        return node

    if isinstance(node, NameListNode):
        errors.append(
            f'{context}: {node.shown} is a list of names, which is only legal as an operator '
            f'kwarg value such as sum(x, by=[gen_bus, gen_tech]). In an expression, write the '
            f'terms out and add them.'
        )
        return node

    assert_never(node)


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


def _undeclared_dim(context: str, operator: str, shown: str, name: str, ns: Namespace) -> str:
    return (
        f'{context}: {operator}({shown}) does not name a declared dimension.\n'
        f'  Dimensions: {sorted(ns.dimensions)}\n'
        f"Declare '{name}' under 'dimensions:', or fix the typo — an unknown "
        f'dimension makes {operator}() a silent no-op rather than an error.'
    )


def _unsigned(value: ArithmeticNode) -> ArithmeticNode:
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


def _resolve_amount(
    value: ArithmeticNode, ns: Namespace, context: str, operator: str, key: str, errors: list[str]
) -> ArithmeticNode:
    """Resolve ``offset=`` or ``within=``: a number or a parameter name, never an expression.

    Closed so that :func:`math_spec.dimensions._check_named_amount` sees every
    parameter an amount carries.
    """
    if (literal := _literal(value)) is not None:
        return literal
    if not isinstance(_unsigned(value), NameNode):
        errors.append(
            f'{context}: {operator}({key}=) takes a number or the name of an integer parameter. '
            f'Precompute it as a parameter.'
        )
        return value
    return _resolve_arith(value, ns, context, errors, amount=True)


def _resolve_edge(
    value: ArithmeticNode,
    context: str,
    operator: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve ``edge=``: the closed keyword ``wrap``, or a number to contribute.

    Takes no namespace: the keyword set is closed, so a name here is a typo
    rather than a lookup.
    """
    if isinstance(value, EdgeNode):
        return value
    if isinstance(value, KeywordNode):
        if value.value == EDGE_WRAP:
            return EdgeNode(EDGE_WRAP)
        errors.append(f'{context}: {edge_error(operator, repr(value.value))}')
        return value
    if isinstance(value, NameNode):
        if value.name == EDGE_WRAP:
            errors.append(
                f'{context}: {operator}(edge={EDGE_WRAP}) is a bare name where a keyword belongs. '
                f"Write edge='{EDGE_WRAP}', quoted."
            )
            return value
        errors.append(f'{context}: {edge_error(operator, value.name)}')
        return value
    if (literal := _literal(value)) is None:
        errors.append(
            f"{context}: {operator}(edge=) is an expression, and an edge is the keyword '{EDGE_WRAP}' "
            f'or a number. Write the number itself.'
        )
        return value
    return literal


def _resolve_dim_ref(
    value: ArithmeticNode,
    ns: Namespace,
    context: str,
    operator: str,
    key: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve an operator kwarg whose *value* must name a declared dimension."""
    if isinstance(value, DimensionNode):
        return value
    if not isinstance(value, NameNode):
        errors.append(f'{context}: {operator}({key}=...) must name a dimension.')
        return value
    if value.name not in ns.dimensions:
        errors.append(_undeclared_dim(context, operator, f'{key}={value.name}', value.name, ns))
        return value
    return DimensionNode(value.name)


def _resolve_lookup_ref(
    value: ArithmeticNode,
    ns: Namespace,
    context: str,
    operator: str,
    key: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve an operator kwarg whose *value* must name groupable lookups.

    A lookup carries its own dimensions, so nothing else in the call is
    consulted: the names alone decide both the dim the operator consumes and
    the ones it produces. A bracketed list is one grouping through several
    maps at once rather than a composition of groupings, so its members must
    share the dim they are over and must not target the same dim twice —
    both checked here, where the declarations are still in hand.
    """
    if isinstance(value, LookupNode):
        return value
    if isinstance(value, NameListNode):
        names = value.names
    elif isinstance(value, NameNode):
        names = (value.name,)
    else:
        errors.append(f'{context}: {operator}({key}=...) must name a lookup.')
        return value

    groupable = ns.groupable()
    named = [_ungroupable(name, ns, groupable, context, operator, key) for name in names]
    if any(problem is not None for problem in named):
        errors.extend(problem for problem in named if problem is not None)
        return value

    over = {ns.over_of(name) for name in names}
    if len(over) > 1:
        errors.append(
            f'{context}: {operator}({key}={shown(names)}) groups through lookups over '
            f'different dimensions ({", ".join(f"{n} over {ns.over_of(n)}" for n in names)}). '
            f'One grouping consumes one dimension, so every lookup in the list must be '
            f'over the same one — group through them in turn instead, one call each.'
        )
        return value

    targets = tuple(groupable[name] for name in names)
    repeated = sorted({t for t in targets if targets.count(t) > 1})
    if repeated:
        errors.append(
            f'{context}: {operator}({key}={shown(names)}) targets {repeated} more than once. '
            f'Each lookup in the list produces its own dimension, so two that land on the '
            f'same one would need it twice — drop one, or group into a dimension of its own.'
        )
        return value

    return LookupNode(names, dimension=next(iter(over)), into=targets)


def _ungroupable(
    name: str,
    ns: Namespace,
    groupable: Mapping[str, str],
    context: str,
    operator: str,
    key: str,
) -> str | None:
    """Why *name* is not a groupable lookup; ``None`` where it is one."""
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
    listing = f'  Lookups: {sorted(groupable)}' if groupable else '  No lookups are declared.'
    return (
        f'{context}: {operator}({key}={name}) does not name a lookup.\n{listing}\n'
        f"Declare it under 'lookups:' — {name}: {{over: <the dimension it maps "
        f'out of>, into: <the dimension its values are labels of>}}.'
    )


# ---------------------------------------------------------------------------
# where strings
# ---------------------------------------------------------------------------


def resolve_where(
    node: WhereNode,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> WhereNode | None:
    """Rewrite a parsed where AST into typed predicates.

    Both parameters and dimensions are legal here — a where-string is a
    predicate over the frame, and the frame carries its own coordinates. What
    is *not* legal is an unknown name: read as "scalar False" it would mask
    every row out and produce an empty model in silence.
    """
    before = len(errors)
    resolved = _resolve_where(node, ns, context, errors, self_variable)
    return None if len(errors) > before else resolved


#: An ISO literal carrying a time-of-day, which decides date vs datetime.
_HAS_TIME = re.compile(r'[T ]\d')


def _typed_literal(
    node: UnresolvedComparisonNode,
    dtype: str,
    context: str,
    errors: list[str],
) -> float | str | datetime.date | None:
    """The comparison's literal, checked against the declared dtype.

    Getting it wrong is silent: polars reads a datetime column against an
    integer as an epoch offset, so ``snapshot > 0`` drops every coordinate
    before 1970 without a word (#460). Returns ``None`` once it has recorded
    an error, so the caller leaves the node unresolved.
    """
    value = node.value
    text = isinstance(value, str)

    if dtype == 'datetime':
        if not text:
            errors.append(
                f"{context}: '{node.name}' is a datetime dimension, so comparing it to "
                f'{value!r} compares against the epoch — {node.name} > 0 means "after '
                f'1970-01-01", not what it looks like. Quote an ISO date instead: '
                f"{node.name} {node.op} '2030-01-01'."
            )
            return None
        try:
            return (
                datetime.datetime.fromisoformat(str(value))
                if _HAS_TIME.search(str(value))
                else datetime.date.fromisoformat(str(value))
            )
        except ValueError:
            errors.append(
                f"{context}: '{node.name}' is a datetime dimension and {value!r} is not an "
                f"ISO date. Write '2030-01-01' or '2030-01-01T06:00'."
            )
            return None

    if dtype == 'str' and not text:
        errors.append(
            f"{context}: '{node.name}' has dtype 'str', so comparing it to the number "
            f'{value!r} matches no label. Quote it if it is one: {node.name} {node.op} '
            f"'{value:g}'."
        )
        return None
    if dtype in ('int', 'float', 'bool') and text:
        errors.append(
            f"{context}: '{node.name}' has dtype '{dtype}', so comparing it to the string "
            f'{value!r} matches nothing. Drop the quotes if it is a number.'
        )
        return None
    return value


def _declared_rhs_error(context: str, node: UnresolvedComparisonNode, value: str, kind: str) -> str:
    """Why the right-hand side of a where-comparison may not name a declaration."""
    shown = f"'{node.name} {node.op} {value}'"
    if kind == 'parameter':
        return (
            f'{context}: {shown} compares two parameters, which is not in the '
            f'language — a where-comparison tests one parameter or dimension against '
            f'a literal. Precompute the comparison as a boolean parameter in data '
            f'prep and test that.'
        )
    if kind == 'variable':
        return f'{context}: {shown} compares against variable {value!r}. A where mask is built before variables exist.'
    if kind == 'lookup':
        return (
            f'{context}: {shown} compares {node.name!r} against lookup {value!r}, and a '
            f'lookup is structure rather than data — every other comparison tests a name '
            f'against a literal. A lookup on the right-hand side is the one exception, and '
            f'only where the left-hand side is a lookup sharing its dimension and its target.'
        )
    return (
        f'{context}: {shown} compares against dimension {value!r}, which the RHS reads '
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
    shown = f"'{node.name} {node.op} {other}'"
    left_over, right_over = ns.over_of(node.name), ns.over_of(other)
    if left_over != right_over:
        return (
            f'{context}: {shown} compares lookups over different dimensions '
            f"('{left_over}' and '{right_over}') — there is no row carrying both, so the "
            f'comparison has nothing to test. Two lookups may be compared only where they '
            f'map out of the same dimension.'
        )
    left, right = ns.into_of(node.name), ns.into_of(other)
    if left is None or right is None or left != right:
        return (
            f'{context}: {shown} compares {_label_set_of(ns, node.name)} with '
            f'{_label_set_of(ns, other)}. No value of one is ever a value of the other, so '
            f'the predicate can only mask everything out. Two lookups may be compared only '
            f'where they map into the same dimension.'
        )
    return None


def _resolve_position(node: UnresolvedPositionNode, ns: Namespace, context: str, errors: list[str]) -> WhereNode:
    """Type ``position(dim[, by=lookup]) <op> i``.

    The name has to be a dimension, the one thing with an order to count
    along; ``by=`` has to be a lookup over that dimension, or no row of it
    carries a group for a position to be counted in.
    """
    if node.dimension not in ns.dimensions:
        kind = ns.kind(node.dimension)
        was = f'a {kind}' if kind else 'not declared'
        errors.append(
            f"{context}: position() counts along a dimension's coordinates, and "
            f"'{node.dimension}' is {was}.\n  Dimensions: {sorted(ns.dimensions)}"
        )
        return node
    if node.by is None:
        return DimensionPositionNode(node.dimension, node.op, node.position, node.by)
    call = f'position({node.dimension}, by={node.by})'
    if (kind := ns.kind(node.by)) != 'lookup':
        was = f'a {kind}' if kind else 'not declared'
        errors.append(
            f"{context}: '{call}' groups by '{node.by}', which is {was}. "
            f'``by=`` takes a lookup, the same as sum(by=) and at(by=).\n'
            f'  Lookups: {sorted(ns.lookups)}'
        )
        return node
    over = ns.over_of(node.by)
    if over != node.dimension:
        errors.append(
            f"{context}: '{call}' counts positions along '{node.dimension}' but groups by a "
            f"lookup over '{over}'. No row of '{node.dimension}' carries it, so there is no "
            f"position within a group to name — group by a lookup over '{node.dimension}'."
        )
        return node
    return DimensionPositionNode(node.dimension, node.op, node.position, node.by)


def _resolve_where(
    node: WhereNode, ns: Namespace, context: str, errors: list[str], self_variable: str | None = None
) -> WhereNode:
    if isinstance(node, BooleanLiteralNode):
        return node

    if isinstance(node, TypedPredicateNode):
        return node

    if isinstance(node, UnresolvedNameNode):
        match ns.kind(node.name):
            case 'parameter':
                return ParameterDefinedNode(node.name)
            case 'dimension':
                errors.append(
                    f"{context}: '{node.name}' is a dimension, and a bare dimension "
                    f'name is true at every coordinate — the mask has no effect. '
                    f'Remove it, or compare it: where: "{node.name} > 0".'
                )
                return node
            case 'lookup':
                return LookupDefinedNode(node.name, ns.over_of(node.name))
            case 'variable':
                if node.name == self_variable:
                    errors.append(
                        f"{context}: variable '{node.name}' asks whether it exists in its own "
                        f'where, which nothing can answer — the mask is what decides where it '
                        f'exists. Test a parameter, or another variable declared before it.'
                    )
                    return node
                return VariableDefinedNode(node.name)
            case _:
                errors.append(ns._unknown(node.name, context, allow_dims=True))
                return node

    if isinstance(node, UnresolvedPositionNode):
        return _resolve_position(node, ns, context, errors)

    if isinstance(node, UnresolvedComparisonNode):
        value = node.value
        if not node.quoted and isinstance(value, str) and (rhs_kind := ns.kind(value)) is not None:
            if rhs_kind == 'lookup' and ns.kind(node.name) == 'lookup':
                if (refusal := _lookup_pair_error(context, node, value, ns)) is not None:
                    errors.append(refusal)
                    return node
                return LookupPairComparisonNode(node.name, value, ns.over_of(node.name), node.op)
            errors.append(_declared_rhs_error(context, node, value, rhs_kind))
            return node

        kind = ns.kind(node.name)
        if kind in ('parameter', 'dimension', 'lookup'):
            typed = _typed_literal(node, ns.dtypes[node.name], context, errors)
            if typed is None:
                return node
            value = typed

        match kind:
            case 'parameter':
                assert not isinstance(value, datetime.date)
                return ParameterComparisonNode(node.name, node.op, value)
            case 'dimension':
                return DimensionComparisonNode(node.name, node.op, value)
            case 'lookup':
                return LookupComparisonNode(node.name, ns.over_of(node.name), node.op, value)
            case 'variable':
                errors.append(
                    f"{context}: where references variable '{node.name}'. A where "
                    f'mask is built before variables exist — it may test parameters '
                    f'and dimension coordinates only.'
                )
                return node
            case _:
                errors.append(ns._unknown(node.name, context, allow_dims=True))
                return node

    if isinstance(node, NotNode):
        return NotNode(_resolve_where(node.operand, ns, context, errors, self_variable))
    if isinstance(node, AndNode):
        return AndNode(
            _resolve_where(node.left, ns, context, errors, self_variable),
            _resolve_where(node.right, ns, context, errors, self_variable),
        )
    if isinstance(node, OrNode):
        return OrNode(
            _resolve_where(node.left, ns, context, errors, self_variable),
            _resolve_where(node.right, ns, context, errors, self_variable),
        )

    assert_never(node)
