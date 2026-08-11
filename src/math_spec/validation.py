"""Load-time validation of expression and where strings.

Every expression and where string is parsed, expanded and **resolved** before
any backend runs, so typos and malformed math fail at load time with the
offending component named — not mid-build, and not differently in each lane.

Resolution is the substance (``resolution.py``): this module walks the schema
and hands each string to the same pass the backends use, collecting every
problem rather than raising on the first. Name *checking* is not a separate
implementation of name *resolution*; that duplication is what let the two lanes
disagree about scoping.

Macro templates are the one thing checked without being resolved, their free
names including formals. They are name-checked against the schema plus their
own formals, so an unused macro still fails at load time.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, assert_never

from pydantic import ValidationError

from lpspec.errors import SchemaError, schema_error
from lpspec.language._yaml import read_yaml
from lpspec.language.dimensions import check_schema
from lpspec.language.expansion import expand, parse_and_expand, parse_template
from lpspec.language.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    CoordinateNode,
    DimensionNode,
    EdgeNode,
    FunctionCallNode,
    KeywordNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from lpspec.language.helpers import BUILTINS, unknown_helper_message
from lpspec.language.model import Model
from lpspec.language.resolution import Namespace, resolve_expression, resolve_where
from lpspec.language.where_parser import parse_where

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def load_model(
    model: str | Path | dict[str, Any] | Model,
    *,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> Model:
    """Load and validate a model definition — the language's front door.

    Accepts a YAML path, a dict, or a ``Model``. ``known_variables`` widens the
    variable set for the one file that is not valid alone: an extension for
    ``linopy.extend()``.

    Validation is complete on return — schema shape, every expression and where
    string, every macro template, and every declaration a formulation emits,
    which is why expansion runs *before* validation: validating the file as
    written checks a strict subset of the model that gets built.

    Returns the schema *as the file declares it*, ``piecewise:`` intact —
    expansion is idempotent and each lane redoes it, while the curvature guard
    needs the blocks themselves.

    Lives in ``language/`` rather than the runner because it is the whole of
    what a consumer binding no data needs; ``lpspec.api`` re-exports it.
    """
    if isinstance(model, (list, tuple)):
        msg = (
            'a model is one file, one dict or one Model, never a list of them. '
            'To compose several, merge the declarations into one dict and pass '
            'that — a native schema merge was declined (#30) because a library '
            'varying its declarations by data is already how you say this.'
        )
        raise TypeError(msg)
    if isinstance(model, Model):
        return model
    raw = model if isinstance(model, dict) else read_yaml(Path(model))
    try:
        return Model.model_validate(raw, context={'known_variables': known_variables})
    except ValidationError as exc:
        raise schema_error(exc) from None


def validate_expressions(
    schema: Model,
    *,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> None:
    """Validate and resolve every expression and where string in *schema*.

    Raises :class:`SchemaError` listing every problem found, one per line:

    - the expression parses, and constraints hold exactly one comparison where
      objectives hold none;
    - every referenced name resolves, and every helper is a built-in whose
      dimension arguments name declared dimensions;
    - where strings parse *and* resolve — an unknown name there is an error,
      not a silently-empty mask;
    - macro formals may shadow model names but not a declared dimension, since
      ``over=snapshot`` under a formal ``snapshot`` cannot say which it means;
    - every dim rule (``dimensions.check_schema``), once names resolve.

    Dim rules run here rather than at either entry point because they are
    language rules: every lane arrives through this function, and one that
    could skip them would be a lane with a different language (hard rule 3).

    *known_variables* maps variables valid in addition to *schema*'s to their
    dims, for ``linopy.extend()``. Parameters get no such widening — a YAML
    file declares every parameter it uses (hard rule 5).
    """
    ns = Namespace.of(schema, known_variables)
    errors: list[str] = []

    _check_dimension_values(schema, errors)

    for mname, macro in schema.macros.items():
        context = f"Macro '{mname}'"
        try:
            body_ast = expand(parse_template(mname, macro, context), schema, context)
            assert not isinstance(body_ast, ComparisonNode)
        except ValueError as e:
            errors.append(str(e) if str(e).startswith(context) else f'{context}: {e}')
            continue
        formals = {*macro.args, *macro.kwargs}
        errors.extend(
            f"{context}: formal '{f}' collides with declared dimension '{f}'. "
            f'Rename the formal — a dimension name inside a template is '
            f'ambiguous with the dimension itself.'
            for f in sorted(formals & ns.dimensions)
        )
        _check_template_names(body_ast, macro.template, context, ns, formals, errors)

    for ename, body in schema.expressions.items():
        _check_expression(body, schema, ns, f"Named expression '{ename}'", errors, comparison=False)

    for vname, vdef in schema.variables.items():
        _check_where(vdef.where, ns, f"Variable '{vname}'", errors)

    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        _check_where(cdef.where, ns, context, errors)
        _check_expression(cdef.expression, schema, ns, context, errors, comparison=True)

    if len(schema.objectives) > 1:
        names = ', '.join(repr(n) for n in schema.objectives)
        errors.append(
            f'{len(schema.objectives)} objectives declared ({names}) — a model optimises one.\n'
            f'Combine them into a single objective (a weighted sum is an ordinary expression), '
            f'or keep one per file.'
        )

    for oname, odef in schema.objectives.items():
        _check_expression(odef.expression, schema, ns, f"Objective '{oname}'", errors, comparison=False)

    if errors:
        raise SchemaError('\n'.join(errors))

    check_schema(schema, known_variables)


#: What each declared dimension ``dtype`` accepts as a coordinate value. ``bool``
#: is excluded from ``int``/``float`` on purpose, being a Python int by accident.
_DTYPE_TYPES: dict[str, tuple[type, ...]] = {
    'str': (str,),
    'int': (int,),
    'float': (int, float),
    'datetime': (datetime.date,),
}


def _check_dimension_values(schema: Model, errors: list[str]) -> None:
    """Reject a declared coordinate that is not the dtype the file declares.

    YAML resolves unquoted scalars by shape, and a coerced label does not join
    against the user's data — the rows vanish, and row absence is the structural
    zero, so the model solves a smaller problem without a word.
    """
    for dname, ddef in schema.dimensions.items():
        accepted = _DTYPE_TYPES[ddef.dtype]
        errors.extend(
            f"Dimension '{dname}': value {value!r} has type "
            f"{type(value).__name__}, but dtype is '{ddef.dtype}'.\n"
            f'YAML resolves unquoted scalars by shape (2024-01-01 → date, '
            f'12:30 → int) — quote the label, or declare the dtype it really is.'
            for value in ddef.values or ()
            if isinstance(value, bool) or not isinstance(value, accepted)
        )


def _parse_expand(
    expression: str,
    schema: Model,
    context: str,
    errors: list[str],
) -> ArithmeticNode | ComparisonNode | None:
    try:
        return parse_and_expand(expression, schema, context)
    except ValueError as e:
        errors.append(f'{context}: {e}')
        return None


def _check_expression(
    expression: str,
    schema: Model,
    ns: Namespace,
    context: str,
    errors: list[str],
    *,
    comparison: bool,
) -> None:
    """Parse, expand and resolve one expression, given whether it must compare.

    The three kinds a file declares differ only in that answer, so the parse,
    the shape verdict and the resolve are one path. Nothing resolves once the
    shape is wrong: an expression of the wrong kind would report its names
    against the wrong question.
    """
    ast = _parse_expand(expression, schema, context, errors)
    if ast is None:
        return
    if comparison and not isinstance(ast, ComparisonNode):
        errors.append(
            f'{context}: expression must contain exactly one comparison operator (<=, >=, ==).\nGot: {expression!r}'
        )
        return
    if not comparison and isinstance(ast, ComparisonNode):
        errors.append(f'{context}: expression must not contain a comparison operator.\nGot: {expression!r}')
        return
    resolve_expression(ast, ns, context, errors)


def _check_where(
    text: str | None,
    ns: Namespace,
    context: str,
    errors: list[str],
) -> None:
    if text is None:
        return
    try:
        node = parse_where(text)
    except ValueError as e:
        errors.append(f'{context}: {e}')
        return
    resolve_where(node, ns, context, errors)


def _check_template_names(
    node: ArithmeticNode,
    template: str,
    context: str,
    ns: Namespace,
    formals: set[str],
    errors: list[str],
) -> None:
    """Name-check a macro body, treating formals as bound.

    Not resolution: a formal has no kind until a call site substitutes for it,
    so the body cannot be typed. This catches the free names that are *not*
    formals, which is what makes an uncalled macro fail at load time. A closed
    keyword names nothing; a dimension kwarg accepts a formal as well as a
    declared dimension, the call site being able to bind one.
    """
    if isinstance(node, (NumberNode, VariableNode, ParameterNode, DimensionNode, CoordinateNode, EdgeNode)):
        return

    if isinstance(node, KeywordNode):
        return

    if isinstance(node, NameNode):
        if node.name not in formals and ns.kind(node.name) is None:
            errors.append(
                f"{context}: '{node.name}' not found in template {template!r}.\n"
                f'  Formals:    {sorted(formals)}\n'
                f'  Variables:  {sorted(ns.variables)}\n'
                f'  Parameters: {sorted(ns.parameters)}\n'
                f"Check for typos, or ensure '{node.name}' is declared."
            )
        return

    if isinstance(node, UnaryOperatorNode):
        _check_template_names(node.operand, template, context, ns, formals, errors)
        return

    if isinstance(node, BinaryOperatorNode):
        _check_template_names(node.left, template, context, ns, formals, errors)
        _check_template_names(node.right, template, context, ns, formals, errors)
        return

    if isinstance(node, FunctionCallNode):
        builtin = BUILTINS.get(node.name)
        if builtin is None:
            errors.append(f'{context}: {unknown_helper_message(node.name)}')
        for arg in node.args:
            _check_template_names(arg, template, context, ns, formals, errors)
        known_dims = ns.dimensions | formals
        for kwarg in builtin.dimension_kwargs if builtin else ():
            value = node.kwargs.get(kwarg)
            if isinstance(value, NameNode) and value.name not in known_dims:
                errors.append(
                    f'{context}: {node.name}({kwarg}={value.name}) does not name a '
                    f'declared dimension or a formal of this macro.'
                )
        for value in node.kwargs.values():
            if not isinstance(value, NameNode):
                _check_template_names(value, template, context, ns, formals, errors)
        return

    assert_never(node)
