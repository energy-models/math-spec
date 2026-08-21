# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

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
from typing import TYPE_CHECKING, Any, assert_never

from pydantic import ValidationError

from math_spec._yaml import read_yaml
from math_spec.degree import carries_variable
from math_spec.dimensions import check_schema
from math_spec.errors import SchemaError, schema_error
from math_spec.expansion import expand, parse_and_expand, parse_template
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
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
from math_spec.model import Model
from math_spec.operators import BUILTINS, unknown_operator_message
from math_spec.resolution import Namespace, resolve_expression, resolve_where
from math_spec.where_parser import parse_where

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def load_model(model: str | Path | dict[str, Any] | Model) -> Model:
    """Load and validate a model definition — the language's front door.

    Everything decidable without data is decided here: schema shape, every
    expression and where string, every macro template, and every declaration a
    formulation emits.

    Args:
        model: A YAML path, a mapping, or a loaded :class:`Model`.

    Returns:
        The schema *as the file declares it*, ``piecewise:`` intact.

    Raises:
        LanguageError: Anything the language does not accept.
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
        return Model.model_validate(raw)
    except ValidationError as exc:
        raise schema_error(exc) from None


def validate_expressions(schema: Model) -> None:
    """Validate and resolve every expression and where string in *schema*.

    What is checked:

    - the expression parses, and constraints hold exactly one comparison where
      objectives hold none;
    - every referenced name resolves, and every operator is a built-in whose
      dimension arguments name declared dimensions;
    - where strings parse *and* resolve — an unknown name there is an error,
      not a silently-empty mask;
    - macro formals may shadow model names but not a declared dimension, since
      ``over=snapshot`` under a formal ``snapshot`` cannot say which it means;
    - every dim rule (``dimensions.check_schema``), once names resolve.

    Dim rules run here rather than at either entry point because they are
    language rules: every lane arrives through this function, and one that
    could skip them would be a lane with a different language (hard rule 3).

    Raises:
        SchemaError: Listing every problem found, one per line.
    """
    ns = Namespace.of(schema)
    errors: list[str] = []

    _check_declared_values(schema, errors)

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

    for ename, block in schema.expressions.items():
        _check_expression(block.expression, schema, ns, f"Named expression '{ename}'", errors, comparison=False)

    for vname, vdef in schema.variables.items():
        _check_where(vdef.where, ns, f"Variable '{vname}'", errors)

    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        _check_where(cdef.where, ns, context, errors)
        _check_expression(cdef.expression, schema, ns, context, errors, comparison=True)

    if schema.objective is not None:
        _check_expression(schema.objective.expression, schema, ns, 'The objective', errors, comparison=False)

    _check_sos(schema, errors)

    if errors:
        raise SchemaError('\n'.join(errors))

    check_schema(schema)


def _check_sos(schema: Model, errors: list[str]) -> None:
    """Every ``sos:`` block names a variable, and a dim that variable carries.

    A set runs along one dimension of one variable, so ``over`` outside that
    variable's ``foreach`` has no members to hold — the one mistake here that
    would otherwise surface as an empty set the solver accepts. A second block
    over one variable is refused for a different reason: what an SOS *is* is a
    property of the variable, which is the shape both sinks and the eager lane
    take it in, so two would be two answers to one question.
    """
    foreach = {name: tuple(v.foreach) for name, v in schema.variables.items()}
    claimed: dict[str, str] = {}
    for name, block in schema.sos.items():
        context = f"Sos '{name}'"
        if block.over not in schema.dimensions:
            errors.append(f"{context}: over references undeclared dimension '{block.over}'.")
        elif block.variable not in foreach:
            errors.append(
                f"{context}: '{block.variable}' is not a declared variable.\n"
                f'  Variables: {sorted(foreach)}\n'
                f'A set is over one variable, so a parameter or an expression cannot carry one.'
            )
        elif block.over not in foreach[block.variable]:
            errors.append(
                f"{context}: over '{block.over}' is not a dim of variable "
                f"'{block.variable}' (foreach {list(foreach[block.variable])}). The set runs "
                f"along one of the variable's own dims — one set per coordinate of the rest."
            )
        elif block.variable in claimed:
            errors.append(
                f"{context}: variable '{block.variable}' already carries the set declared by "
                f"'{claimed[block.variable]}'. A variable holds one set — declare a second "
                f'variable, or state the other restriction as a constraint.'
            )
        else:
            claimed[block.variable] = name


#: What each declared dimension ``dtype`` accepts as a coordinate value. ``bool``
#: is excluded from ``int``/``float`` on purpose, being a Python int by accident.
_DTYPE_TYPES: dict[str, tuple[type, ...]] = {
    'str': (str,),
    'int': (int,),
    'float': (int, float),
    'datetime': (datetime.date,),
}


def _mistyped_labels(lead: str, dtype: str, labels: Iterable[Any]) -> Iterator[str]:
    """Every label in *labels* that is not *dtype*, as its own refusal.

    YAML resolves unquoted scalars by shape, and a coerced label does not join
    against the user's data — the rows vanish, and row absence is the structural
    zero, so the model solves a smaller problem without a word. *lead* names the
    position, so one wording serves every place a label can be written.
    """
    accepted = _DTYPE_TYPES[dtype]
    return (
        f"{lead} {label!r} has type {type(label).__name__}, but dtype is '{dtype}'.\n"
        f'YAML resolves unquoted scalars by shape (2024-01-01 → date, '
        f'12:30 → int) — quote the label, or declare the dtype it really is.'
        for label in labels
        if isinstance(label, bool) or not isinstance(label, accepted)
    )


def _check_declared_values(schema: Model, errors: list[str]) -> None:
    """Reject a declared label that is not the dtype the file declares.

    Two positions write labels. A dimension's own ``values:`` is one. A
    lookup's inline map is the other, on both sides: its keys are labels of the
    dimension it is over, and its values are labels of the set it maps into —
    the target dimension's, or its own where it is a label space. Declaring the
    map puts both sides in the file, so law 2 puts the check here rather than at
    bind time, where only the target side would ever have reached it.
    """
    for dname, ddef in schema.dimensions.items():
        errors.extend(_mistyped_labels(f"Dimension '{dname}': value", ddef.dtype, ddef.values or ()))

    for lname, lookup in schema.lookups.items():
        if lookup.values is None:
            continue
        over = schema.dimensions.get(lookup.over)
        if over is not None:
            errors.extend(_mistyped_labels(f"Lookup '{lname}': key", over.dtype, lookup.values))
        target = schema.dimensions.get(lookup.into) if lookup.into is not None else None
        dtype = target.dtype if target is not None else lookup.dtype
        if dtype is not None:
            mapped = [label for label in lookup.values.values() if label is not None]
            errors.extend(_mistyped_labels(f"Lookup '{lname}': value", dtype, mapped))


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

    A comparison is held to one more rule, and only after it resolves, because
    which names are variables is what resolution decides: it has to carry one.
    Only a constraint reaches that branch — the shape verdict above returned for
    everything else that could hold a comparison.
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
    resolved = resolve_expression(ast, ns, context, errors)
    if isinstance(resolved, ComparisonNode) and not carries_variable(resolved):
        errors.append(f'{context}: {_no_decision_message(expression)}')


def _no_decision_message(expression: str) -> str:
    """Why a comparison carrying no variable is refused rather than dropped.

    Both lanes reach the shape and neither builds a row for it — the relational
    one quietly, linopy with an error of its own — so the file is told at load,
    where the whole question is decidable and the sentence can name the file's
    own text (#1171). Not the same as a row the *data* left with no terms: that
    one the file wrote correctly, and it is answered where the data is.
    """
    return (
        f'neither side of the comparison carries a variable, so the row decides nothing.\n'
        f'Got: {expression!r}\n'
        f'A constraint is a claim about a decision, and a comparison of numbers and parameters '
        f'is settled before the solve — no lane builds a row for it. Name the variable it should '
        f'bound, or drop the declaration and check the fact where the data is prepared.'
    )


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
    if isinstance(node, (NumberNode, VariableNode, ParameterNode, DimensionNode, LookupNode, EdgeNode)):
        return

    if isinstance(node, (KeywordNode, NameListNode)):
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
            errors.append(f'{context}: {unknown_operator_message(node.name)}')
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
