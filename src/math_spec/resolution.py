"""Name resolution — the pass that makes the core AST fully typed.

Parsers emit ``NameNode``: a token, not yet a meaning. This module rewrites
each one into a typed node (``VariableNode`` / ``ParameterNode`` / ``DimensionNode`` /
``LookupNode``, and
``ParameterComparisonNode`` / ``DimensionComparisonNode`` / ``ParameterDefinedNode`` on the where
side), so the AST reaching either backend holds no unresolved names.

Doing this once here is what makes scoping identical across the lanes by
construction rather than by test: a backend that resolves for itself is one
that can build a model the other refuses. The name-resolution rules live in
the language reference.

The namespace is flat and collisions are load errors; macro formals are the one
scope, and may not collide with a declared dimension.
"""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, assert_never

from lpspec.errors import LanguageError
from lpspec.language.expansion import parse_and_expand
from lpspec.language.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from lpspec.language.operators import BUILTINS, EDGE_WRAP, call_shape_error, edge_error, unknown_operator_message
from lpspec.language.where_parser import (
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
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    VariableDefinedNode,
    WhereNode,
    parse_where,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lpspec.language.model import Model


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
        lookups: Mapping[str, tuple[str, str | None]] | None = None,
        dtypes: Mapping[str, str] | None = None,
    ) -> None:
        self.variables = frozenset(variables)
        self.parameters = frozenset(parameters)
        self.dimensions = frozenset(dimensions)
        #: name -> declared dtype, for dimensions, parameters and label-space
        #: lookups alike. A where comparison is the one place a *literal*
        #: meets a declared type, and comparing the wrong one is silent: polars
        #: reads a datetime against an integer as an epoch offset and drops
        #: rows, and row absence is the structural zero. Empty when a caller
        #: builds a namespace by hand, which only widens what is accepted.
        self.dtypes: dict[str, str] = dict(dtypes or {})
        #: lookup name -> ``(over, into)``, both kinds in one store: ``into`` is
        #: ``None`` for a label space, which owns its values and targets
        #: nothing. That is the schema's own discriminator
        #: (:class:`~lpspec.language.model.LookupBlock` declares exactly one of
        #: ``into:`` and ``dtype:``), carried rather than re-encoded as two
        #: dicts — one fact, one home.
        self.lookups: dict[str, tuple[str, str | None]] = dict(lookups or {})

    def groupable(self) -> dict[str, str]:
        """The lookups a ``by=`` may name: name -> the dimension it maps into.

        A label space is absent, which is what makes naming one in a ``by=``
        answerable with the promotion rewrite rather than "no such lookup".
        """
        return {n: into for n, (_, into) in self.lookups.items() if into is not None}

    @classmethod
    def of(cls, schema: Model) -> Namespace:
        """Build the namespace of *schema*.

        Every name a file may use is declared in that file (hard rule 5), so
        the schema is the whole namespace and there is nothing to widen it
        with.
        """
        return cls(
            set(schema.variables),
            schema.parameters,
            schema.dimensions,
            {n: (lk.over, lk.into) for n, lk in schema.lookups.items()},
            {
                **{p: pd.dtype for p, pd in schema.parameters.items()},
                **{d: dd.dtype for d, dd in schema.dimensions.items()},
                # A targeted lookup's values are labels of its target, so the
                # target's dtype is what a literal is checked against.
                **{
                    n: schema.dimensions[lk.into].dtype
                    for n, lk in schema.lookups.items()
                    if lk.into is not None and lk.into in schema.dimensions
                },
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
# the seam both backends use
# ---------------------------------------------------------------------------


def expression_of(text: str, schema: Model, ns: Namespace, context: str) -> ExpressionNode:
    """Parse, expand and resolve *text* — the only way a backend gets an AST.

    ``validation.py`` runs the same path at load time, so a backend calling
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
    """Parse and resolve a where string; ``None`` stays ``None``.

    Raises:
        LanguageError: Listing every problem the predicate has.
    """
    if text is None:
        return None
    errors: list[str] = []
    resolved = resolve_where(parse_where(text), ns, context, errors, self_variable)
    if errors:
        raise LanguageError('\n'.join(errors))
    return resolved


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
    so neither backend has to state a signature a second time.

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


def _resolve_arith(node: ArithmeticNode, ns: Namespace, context: str, errors: list[str]) -> ArithmeticNode:
    """The recursive worker under :func:`resolve_expression`.

    Idempotent — already-typed nodes pass through unchanged, because
    piecewise re-resolves expanded links. The ``KeywordNode`` branch is
    unreachable from a file: the grammar admits a quoted value only in a
    kwarg position, and the kwarg branches consume it there. It exists for a
    hand-built AST, and because the union must be exhausted.
    """
    if isinstance(node, NumberNode):
        return node

    if isinstance(node, (VariableNode, ParameterNode, DimensionNode, LookupNode, EdgeNode)):
        return node

    if isinstance(node, NameNode):
        match ns.kind(node.name):
            case 'variable':
                return VariableNode(node.name)
            case 'parameter':
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
                kwargs[key] = _resolve_arith(value, ns, context, errors)
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


def _undeclared_dim(context: str, operator: str, shown: str, name: str, ns: Namespace) -> str:
    return (
        f'{context}: {operator}({shown}) does not name a declared dimension.\n'
        f'  Dimensions: {sorted(ns.dimensions)}\n'
        f"Declare '{name}' under 'dimensions:', or fix the typo — an unknown "
        f'dimension makes {operator}() a silent no-op rather than an error.'
    )


def _resolve_edge(
    value: ArithmeticNode,
    context: str,
    operator: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve ``edge=``: the closed keyword ``wrap``, or a number to contribute.

    Takes no namespace: the keyword set is closed, so an unrecognised name here
    is a typo rather than a lookup and nothing could make ``edge=usual`` mean
    anything. The keyword must still be quoted — a bare ``edge=wrap`` would make
    ``over=wrap`` and ``edge='wrap'`` the same token meaning two things in one
    call, and quoting is how the language says "literal, not a name" (the
    where-string rules).
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
                f"Write edge='{EDGE_WRAP}' — quoted, because a bare word in a kwarg value is a "
                f'name to resolve and this one is a literal.'
            )
            return value
        errors.append(f'{context}: {edge_error(operator, value.name)}')
        return value
    return value


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
    elif isinstance(value, (NameNode, DimensionNode)):
        names = (value.name,)
    else:
        errors.append(f'{context}: {operator}({key}=...) must name a lookup.')
        return value

    shown = names[0] if len(names) == 1 else f'[{", ".join(names)}]'
    groupable = ns.groupable()
    named = [_ungroupable(name, ns, groupable, context, operator, key) for name in names]
    if any(problem is not None for problem in named):
        errors.extend(problem for problem in named if problem is not None)
        return value

    over = {ns.lookups[name][0] for name in names}
    if len(over) > 1:
        errors.append(
            f'{context}: {operator}({key}={shown}) groups through lookups over '
            f'different dimensions ({", ".join(f"{n} over {ns.lookups[n][0]}" for n in names)}). '
            f'One grouping consumes one dimension, so every lookup in the list must be '
            f'over the same one — group through them in turn instead, one call each.'
        )
        return value

    targets = tuple(groupable[name] for name in names)
    repeated = sorted({t for t in targets if targets.count(t) > 1})
    if repeated:
        errors.append(
            f'{context}: {operator}({key}={shown}) targets {repeated} more than once. '
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
        over, _ = ns.lookups[name]
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
    dtype: str | None,
    context: str,
    errors: list[str],
) -> float | str | datetime.date | None:
    """The comparison's literal, checked against the declared dtype.

    A where comparison is the one place a literal meets a declared type, and
    getting it wrong is **silent**: polars reads a datetime column against an
    integer as an epoch offset, so ``snapshot > 0`` means *"after 1970-01-01"*
    and drops every earlier coordinate — row absence being the structural zero,
    the model then solves a smaller problem without a word (#460).

    Returns ``None`` once it has recorded an error, so the caller leaves the
    node unresolved rather than lowering something it could not type.

    ``dtype`` is ``None`` for a hand-built namespace, which accepts any
    literal. A parameter's dtype is never ``datetime`` (``_DTYPE_TYPES``), so
    only a dimension comparison receives a ``datetime.date`` from here.
    """
    if dtype is None:
        return node.value
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
    """Why the right-hand side of a where-comparison may not name a declaration.

    One refusal — the RHS is a literal — but three distinct reasons, and the
    wording has to say which, since only the dimension case is a *silent* wrong
    answer rather than an obvious one.
    """
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
        f'as the literal coordinate {value!r} — so the predicate tests one dimension '
        f"against another dimension's *name* and masks everything out. Comparing two "
        f'dimensions to each other is not in the language; if {value!r} is a coordinate '
        f'rather than the dimension, rename one of the two.'
    )


def _label_set_of(ns: Namespace, lookup: str) -> str:
    """Where a lookup's values come from, as a refusal reads it."""
    into = ns.into_of(lookup)
    return f"'{lookup}' (mapping into '{into}')" if into is not None else f"'{lookup}' (a label space of its own)"


def _lookup_pair_error(context: str, node: UnresolvedComparisonNode, other: str, ns: Namespace) -> str | None:
    """Why two lookups may not be compared, or ``None`` where they may.

    Two conditions, and each catches a *silent* wrong answer rather than an
    obvious one. They must map out of the same dimension, or no row carries
    both. And their values must come from the same label set, or no value of
    one can equal a value of the other — a comparison the eager lane answers
    ``True`` everywhere for ``!=`` while polars refuses the Enum mismatch, so
    without this the two lanes disagree on a model both accepted. A label
    space owns its values, so it is never the other side of one.
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
    """Type ``lhs <op> index(dim, i)`` — both sides must name the same dimension.

    Comparing one dimension's coordinate against another's would be comparing
    labels across label spaces, which can only mask everything out; and
    ``index`` of anything but a dimension has no coordinate order to count
    along.

    ``by=`` groups that order, so it takes a lookup *over the dimension being
    counted*: the groups are its target's labels, and a lookup over anything
    else has no position within a group to name.
    """
    for named in (node.name, node.dimension):
        if named not in ns.dimensions:
            kind = ns.kind(named)
            was = f'a {kind}' if kind else 'not declared'
            errors.append(
                f"{context}: index() counts along a dimension's coordinates, and "
                f"'{named}' is {was}.\n  Dimensions: {sorted(ns.dimensions)}"
            )
            return node
    if node.name != node.dimension:
        errors.append(
            f"{context}: '{node.name} {node.op} index({node.dimension}, {node.position})' compares "
            f"a '{node.name}' coordinate against a '{node.dimension}' one. No label of one is a "
            f'label of the other, so the predicate can only mask everything out — index() names '
            f'a position in the dimension being tested.'
        )
        return node
    if node.by is not None and _refuse_grouping(node, node.by, ns, context, errors):
        return node
    return DimensionPositionNode(node.name, node.op, node.position, node.by)


def _refuse_grouping(node: UnresolvedPositionNode, by: str, ns: Namespace, context: str, errors: list[str]) -> bool:
    """Whether ``by=`` names something other than a lookup over the counted dim.

    The groups are the lookup's target labels and the positions are counted
    inside each, so a lookup over another dimension carries no row of the one
    being indexed — there is nothing for a position to be a position *in*.
    """
    shown = f'index({node.dimension}, {node.position}, by={by})'
    if (kind := ns.kind(by)) != 'lookup':
        was = f'a {kind}' if kind else 'not declared'
        errors.append(
            f"{context}: '{shown}' groups by '{by}', which is {was}. "
            f'``by=`` takes a lookup, the same as sum(by=) and at(by=).\n'
            f'  Lookups: {sorted(ns.lookups)}'
        )
        return True
    over = ns.over_of(by)
    if over != node.dimension:
        errors.append(
            f"{context}: '{shown}' counts positions along '{node.dimension}' but groups by a "
            f"lookup over '{over}'. No row of '{node.dimension}' carries it, so there is no "
            f"position within a group to name — group by a lookup over '{node.dimension}'."
        )
        return True
    return False


def _resolve_where(
    node: WhereNode, ns: Namespace, context: str, errors: list[str], self_variable: str | None = None
) -> WhereNode:
    if isinstance(node, BooleanLiteralNode):
        return node

    if isinstance(
        node,
        (
            ParameterComparisonNode,
            DimensionComparisonNode,
            DimensionPositionNode,
            LookupComparisonNode,
            LookupPairComparisonNode,
            LookupDefinedNode,
            ParameterDefinedNode,
            VariableDefinedNode,
        ),
    ):
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
                return LookupDefinedNode(node.name, ns.lookups[node.name][0])
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
            typed = _typed_literal(node, ns.dtypes.get(node.name), context, errors)
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
                return LookupComparisonNode(node.name, ns.lookups[node.name][0], node.op, value)
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
