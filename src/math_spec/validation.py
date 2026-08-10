"""Load-time validation of expression and where strings.

Every expression and where string in a schema is parsed, expanded and
**resolved** before any backend runs, so typos and malformed math fail at load
time with the offending component named — not mid-build, and not differently
in each lane.

Resolution is the substance here (``resolution.py``): this module walks the
schema and hands each string to the same pass the backends use, collecting
every problem rather than raising on the first. Name *checking* is not a
separate implementation of name *resolution* — that duplication is what let
the two lanes disagree about scoping in the first place.

Macro templates are the one thing checked without being resolved: their free
names include formals, which are not model names. They are name-checked
against the schema plus their own formals, so an unused macro still fails at
load time if its body references something that does not exist.
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
from lpspec.language.piecewise import expand_piecewise
from lpspec.language.resolution import Namespace, resolve_expression, resolve_where
from lpspec.language.where_parser import parse_where

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def load_model(model: str | Path | dict[str, Any] | Model) -> Model:
    """Load and validate a model definition — the language's front door.

    Accepts a YAML file path, an already-parsed dict, or a ``Model``.
    Validation is complete at this point: schema shape, every expression and
    where string, every named expression and macro template — and every
    declaration a formulation emits, since those are language too. That is why
    expansion runs *before* validation here, the order the linopy lane already
    uses: validating the file as written checks a strict subset of the model
    that gets built.

    Returns the schema *as the file declares it*, with ``piecewise:`` blocks
    intact — expansion is idempotent and each lane redoes it, while the
    curvature data guard needs the blocks themselves
    (:func:`lpspec.sources.validate_piecewise_data`).

    This is the whole of what a consumer that binds no data needs, which is
    why it lives in ``language/`` and not in the runner: ``typeset`` reaches
    it without reaching an engine. ``lpspec.api`` re-exports it.
    """
    if isinstance(model, (list, tuple)):
        msg = (
            'composing multiple YAML files into one program is not implemented '
            'yet — track https://github.com/fluxopt/lpspec/issues/30'
        )
        raise NotImplementedError(msg)
    if isinstance(model, Model):
        return model
    raw = model if isinstance(model, dict) else read_yaml(Path(model))
    try:
        schema = Model(**raw)
    except ValidationError as exc:
        raise schema_error(exc) from None
    validate_expressions(expand_piecewise(schema))
    return schema


def validate_expressions(
    schema: Model,
    *,
    known_variables: Mapping[str, Sequence[str]] = MappingProxyType({}),
) -> None:
    """Validate and resolve every expression and where string in *schema*.

    Checks, per constraint/objective equation:

    - the expression parses;
    - constraints contain exactly one comparison, objectives none;
    - every referenced name resolves to a declared variable or parameter;
    - every helper function is a built-in, and its dimension arguments name
      declared dimensions;
    - where strings parse *and* resolve — an unknown name in a where is an
      error, not a silently-empty mask;
    - every dim rule (``dimensions.check_schema``), once names resolve.

    Parameters
    ----------
    schema : Model
        The schema to validate.
    known_variables : Mapping[str, Sequence[str]]
        Variables valid in addition to those declared in *schema*, mapped to
        their dims — used by ``linopy.extend()``, where expressions may
        reference variables already present on the model. The dims are needed
        for the same reason the names are: dim checking is a language rule. Parameters get no such widening: a
        YAML file declares every parameter it uses (hard rule 5).

    Raises
    ------
    SchemaError
        Listing every problem found, one per line.
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
        # Formals may shadow model names but not a declared dimension:
        # `over=snapshot` under a formal `snapshot` cannot say which it means.
        formals = {*macro.args, *macro.kwargs}
        errors.extend(
            f"{context}: formal '{f}' collides with declared dimension '{f}'. "
            f'Rename the formal — a dimension name inside a template is '
            f'ambiguous with the dimension itself.'
            for f in sorted(formals & ns.dimensions)
        )
        _check_template_names(body_ast, macro.template, context, ns, formals, errors)

    for ename, body in schema.expressions.items():
        context = f"Named expression '{ename}'"
        ast = _parse_expand(body, schema, context, errors)
        if ast is None:
            continue
        if isinstance(ast, ComparisonNode):
            errors.append(f'{context}: must not contain a comparison operator.\nGot: {body!r}')
            continue
        resolve_expression(ast, ns, context, errors)

    for vname, vdef in schema.variables.items():
        _check_where(vdef.where, ns, f"Variable '{vname}'", errors)

    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        _check_where(cdef.where, ns, context, errors)
        ast = _parse_expand(cdef.expression, schema, context, errors)
        if ast is not None:
            if not isinstance(ast, ComparisonNode):
                errors.append(
                    f'{context}: expression must contain exactly one '
                    f'comparison operator (<=, >=, ==).\n'
                    f'Got: {cdef.expression!r}'
                )
            else:
                resolve_expression(ast, ns, context, errors)

    if len(schema.objectives) > 1:
        names = ', '.join(repr(n) for n in schema.objectives)
        errors.append(
            f'{len(schema.objectives)} objectives declared ({names}) — a model optimises one.\n'
            f'Combine them into a single objective (a weighted sum is an ordinary expression), '
            f'or keep one per file.'
        )

    for oname, odef in schema.objectives.items():
        context = f"Objective '{oname}'"
        ast = _parse_expand(odef.expression, schema, context, errors)
        if ast is not None:
            if isinstance(ast, ComparisonNode):
                errors.append(
                    f'{context}: expression must not contain a comparison operator.\nGot: {odef.expression!r}'
                )
            else:
                resolve_expression(ast, ns, context, errors)

    if errors:
        raise SchemaError('\n'.join(errors))

    # Dim rules are language rules, not backend rules, so they run here rather
    # than at either entry point — linopy.build/extend and api.load_model all
    # arrive through this function, and a lane that could skip them would be a
    # lane with a different language (hard rule 3).
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

    Not resolution: a formal has no kind until the call site substitutes an
    argument for it, so the body cannot be typed. This catches the free names
    that are *not* formals, which is what makes an uncalled macro still fail
    at load time.
    """
    if isinstance(node, (NumberNode, VariableNode, ParameterNode, DimensionNode, CoordinateNode, EdgeNode)):
        return

    if isinstance(node, KeywordNode):
        return  # a closed keyword names nothing, so there is nothing to check it against

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
        # a formal may be bound to a dimension at the call site
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
