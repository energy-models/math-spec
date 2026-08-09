"""Name resolution — the pass that makes the core AST fully typed.

Parsers emit ``NameNode``: a token, not yet a meaning. This module rewrites
each one into a typed node (``VariableNode`` / ``ParameterNode`` / ``DimensionNode`` /
``CoordinateNode``, and
``ParameterComparisonNode`` / ``DimensionComparisonNode`` / ``ParameterDefinedNode`` on the where
side), so the AST reaching either backend holds no unresolved names.

Doing this once, here, is what makes scoping identical across the lanes by
construction rather than by test. When each backend resolved for itself they
disagreed three ways, every one of which built a model on one lane and raised
on the other — see SPEC §5.3 for the list and the rules that replace it.

The namespace is flat and collisions are load errors (``schema.py``); macro
formals are the one scope, and may not collide with a declared dimension.
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
    CoordinateNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from lpspec.language.helpers import BUILTINS, EDGE_WRAP, call_shape_error, edge_error, unknown_helper_message
from lpspec.language.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    VariableDefinedNode,
    WhereNode,
    parse_where,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lpspec.language.schema import MathSchema


class Namespace:
    """The declared names of one schema, by kind.

    Flat by construction: :meth:`kind` is a single lookup, not an ordered
    walk through several stores.
    """

    __slots__ = ('coordinates', 'dimensions', 'dtypes', 'parameters', 'variables')

    def __init__(
        self,
        variables: Iterable[str],
        parameters: Iterable[str],
        dimensions: Iterable[str],
        coordinates: Mapping[str, Mapping[str, str]] | None = None,
        dtypes: Mapping[str, str] | None = None,
    ) -> None:
        self.variables = frozenset(variables)
        self.parameters = frozenset(parameters)
        self.dimensions = frozenset(dimensions)
        #: name -> declared dtype, for dimensions and parameters alike. A where
        #: comparison is the one place a *literal* meets a declared type, and
        #: comparing the wrong one is silent: polars reads a datetime against
        #: an integer as an epoch offset and drops rows, and row absence is the
        #: structural zero. Empty when a caller builds a namespace by hand,
        #: which only widens what is accepted.
        self.dtypes: dict[str, str] = dict(dtypes or {})
        #: dim -> {coordinate name: target dim}. Scoped, so it is not part of
        #: :meth:`kind` — a coordinate name is only meaningful under its dim.
        self.coordinates: dict[str, dict[str, str]] = {d: dict(c) for d, c in (coordinates or {}).items()}

    @classmethod
    def of(cls, schema: MathSchema, known_variables: Iterable[str] = ()) -> Namespace:
        """Build the namespace of *schema*.

        ``known_variables`` widens the variable set only — used by
        ``linopy.extend()``, where expressions may reference variables already
        on the model. Parameters get no such widening: a YAML file declares
        every parameter it uses (hard rule 5).
        """
        return cls(
            set(schema.variables) | set(known_variables),
            schema.parameters,
            schema.dimensions,
            {d: dd.coords for d, dd in schema.dimensions.items()},
            {
                **{p: pd.dtype for p, pd in schema.parameters.items()},
                **{d: dd.dtype for d, dd in schema.dimensions.items()},
            },
        )

    def kind(self, name: str) -> str | None:
        """``'variable'`` | ``'parameter'`` | ``'dimension'`` | ``None``."""
        if name in self.variables:
            return 'variable'
        if name in self.parameters:
            return 'parameter'
        if name in self.dimensions:
            return 'dimension'
        return None

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


def expression_of(text: str, schema: MathSchema, ns: Namespace, context: str) -> ExpressionNode:
    """Parse, expand and resolve *text* — the only way a backend gets an AST.

    Raises :class:`LanguageError` listing every problem. ``validation.py`` calls the
    same path at load time, so by the time a backend calls this the result is
    known to be clean; calling it again is how the backend gets a *typed* tree
    without duplicating the pass.
    """
    errors: list[str] = []
    resolved = resolve_expression(parse_and_expand(text, schema, context), ns, context, errors)
    if errors:
        raise LanguageError('\n'.join(errors))
    assert resolved is not None
    return resolved


def where_of(text: str | None, ns: Namespace, context: str, self_variable: str | None = None) -> WhereNode | None:
    """Parse and resolve a where string; ``None`` stays ``None``."""
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

    Appends to *errors* and returns ``None`` if anything failed to resolve, so
    a caller collecting problems across a whole schema reports them together.

    Helper *call shapes* are checked here too (``helpers.call_shape_error``).
    Arity is a language rule, and this is the pass every consumer goes through,
    so neither backend has to state a signature a second time.
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
    if isinstance(node, NumberNode):
        return node

    if isinstance(node, (VariableNode, ParameterNode, DimensionNode, CoordinateNode, EdgeNode)):
        return node  # idempotent: piecewise re-resolves expanded links

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
                    f"'foreach:', in helper arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
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
            errors.append(f'{context}: {unknown_helper_message(node.name)}')
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
            elif key in builtin.coordinate_kwargs or key in builtin.optional_coordinate_kwargs:
                # scoped to the sibling over= dim, so that kwarg has to be read
                # here rather than resolved on its own
                # scoped to the sibling dimension kwarg, whichever the helper
                # names it — `over=` where the dim is consumed, `onto=` where
                # it is produced
                sibling = builtin.dimension_kwargs[0] if builtin.dimension_kwargs else 'over'
                kwargs[key] = _resolve_coordinate_ref(
                    value, node.kwargs.get(sibling), ns, context, node.name, key, errors
                )
            else:
                kwargs[key] = _resolve_arith(value, ns, context, errors)
        return FunctionCallNode(node.name, args, kwargs)

    assert_never(node)


def _undeclared_dim(context: str, helper: str, shown: str, name: str, ns: Namespace) -> str:
    return (
        f'{context}: {helper}({shown}) does not name a declared dimension.\n'
        f'  Dimensions: {sorted(ns.dimensions)}\n'
        f"Declare '{name}' under 'dimensions:', or fix the typo — an unknown "
        f'dimension makes {helper}() a silent no-op rather than an error.'
    )


def _resolve_edge(
    value: ArithmeticNode,
    context: str,
    helper: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve ``edge=``: the closed keyword ``wrap``, or a number to contribute.

    A bare name here is never a model name — the one keyword is closed, so an
    unrecognised name is a typo rather than a lookup. That is why this does not
    take a namespace: nothing in it could make ``edge=usual`` mean anything.
    """
    if isinstance(value, EdgeNode):
        return value
    if isinstance(value, NameNode):
        if value.name == EDGE_WRAP:
            return EdgeNode(EDGE_WRAP)
        errors.append(f'{context}: {edge_error(helper, value.name)}')
        return value
    return value


def _resolve_dim_ref(
    value: ArithmeticNode,
    ns: Namespace,
    context: str,
    helper: str,
    key: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve a helper kwarg whose *value* must name a declared dimension."""
    if isinstance(value, DimensionNode):
        return value
    if not isinstance(value, NameNode):
        errors.append(f'{context}: {helper}({key}=...) must name a dimension.')
        return value
    if value.name not in ns.dimensions:
        errors.append(_undeclared_dim(context, helper, f'{key}={value.name}', value.name, ns))
        return value
    return DimensionNode(value.name)


def _resolve_coordinate_ref(
    value: ArithmeticNode,
    over: ArithmeticNode | None,
    ns: Namespace,
    context: str,
    helper: str,
    key: str,
    errors: list[str],
) -> ArithmeticNode:
    """Resolve a helper kwarg naming a coordinate on the sibling ``over=`` dim."""
    if isinstance(value, CoordinateNode):
        return value
    if not isinstance(value, (NameNode, DimensionNode)):
        errors.append(f'{context}: {helper}({key}=...) must name a coordinate.')
        return value
    if not isinstance(over, (NameNode, DimensionNode)):
        errors.append(
            f'{context}: {helper}({key}={value.name}) needs a sibling over=<dim> '
            f'naming the dimension that carries the coordinate.'
        )
        return value
    declared = ns.coordinates.get(over.name, {})
    if value.name not in declared:
        listing = (
            f'  Coordinates on {over.name}: {sorted(declared)}'
            if declared
            else f"  '{over.name}' declares no coordinates."
        )
        errors.append(
            f'{context}: {helper}(over={over.name}, {key}={value.name}) does not name a '
            f"coordinate of '{over.name}'.\n{listing}\n"
            f"Declare it under 'dimensions.{over.name}.coords', naming the dimension "
            f'its values are labels of.'
        )
        return value
    return CoordinateNode(value.name, dimension=over.name, into=declared[value.name])


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
    is *not* legal is an unknown name: it used to mean "scalar False" in the
    eager lane, which silently produced an empty model.
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
    getting it wrong is **silent**: polars compares a datetime column against an
    integer as an offset from the epoch, so ``snapshot > 0`` quietly means
    *"after 1970-01-01"* and drops every earlier coordinate. Row absence is the
    structural zero, so the model then solves a smaller problem without a word
    (#460). This is the guard ``_check_dimension_values`` already applies to a
    dimension's declared ``values:``, one construct over.

    Returns ``None`` when it has recorded an error, so the caller leaves the
    node unresolved rather than lowering something it could not type.
    """
    if dtype is None:  # a namespace built by hand declares no types
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
    return (
        f'{context}: {shown} compares against dimension {value!r}, which the RHS reads '
        f'as the literal coordinate {value!r} — so the predicate tests one dimension '
        f"against another dimension's *name* and masks everything out. Comparing two "
        f'dimensions to each other is not in the language; if {value!r} is a coordinate '
        f'rather than the dimension, rename one of the two.'
    )


def _resolve_where(
    node: WhereNode, ns: Namespace, context: str, errors: list[str], self_variable: str | None = None
) -> WhereNode:
    if isinstance(node, BooleanLiteralNode):
        return node

    if isinstance(node, (ParameterComparisonNode, DimensionComparisonNode, ParameterDefinedNode, VariableDefinedNode)):
        return node  # already resolved

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

    if isinstance(node, UnresolvedComparisonNode):
        value = node.value
        # A *bare* name on the right is ambiguous — it may name a declaration —
        # and is refused for that reason. Quoting is what says "label, not
        # name", so a quoted one skips the check rather than colliding with it.
        if not node.quoted and isinstance(value, str) and (rhs_kind := ns.kind(value)) is not None:
            errors.append(_declared_rhs_error(context, node, value, rhs_kind))
            return node

        kind = ns.kind(node.name)
        if kind in ('parameter', 'dimension'):
            typed = _typed_literal(node, ns.dtypes.get(node.name), context, errors)
            if typed is None:
                return node
            value = typed

        match kind:
            case 'parameter':
                # `_DTYPE_TYPES` gives a parameter float/int/bool/str and never
                # datetime, so the date branch above cannot have fired here.
                assert not isinstance(value, datetime.date)
                return ParameterComparisonNode(node.name, node.op, value)
            case 'dimension':
                return DimensionComparisonNode(node.name, node.op, value)
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
