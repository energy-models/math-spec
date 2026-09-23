# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Lower a validated model to a :class:`~math_spec.program.Program`.

One lowering, on the language side: it packages the declarations a model
resolved to, with every named expression inlined where the math reads it, and
reaches no consumer. A construct with no lowering raises
:class:`~math_spec.errors.LanguageError` naming its rewrite.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, assert_never

import math_spec.program as program
from math_spec.errors import LanguageError
from math_spec.piecewise import declaration_of
from math_spec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from math_spec.model import Spec


def to_program(spec: str | Path | Mapping[str, object] | Spec | program.Program) -> program.Program:
    """*spec* as a :class:`~math_spec.program.Program` — the public door.

    Takes whatever you have: a YAML path, the YAML itself, a mapping, a loaded
    model, or a program already. Idempotent, so a caller that does not know
    which it holds can call this and be sure. The model is lowered as it
    arrived: nothing is written out here, so a ``piecewise:`` block still in
    it is refused, naming :meth:`~math_spec.model.Spec.expand`.

    Args:
        spec: What to read the declarations from.

    Returns:
        Every declaration the file makes, with names resolved and shapes
        fixed.

    Raises:
        SchemaError: The file is not a valid model.
        LanguageError: A construct outside the language, named with its
            rewrite, or a ``piecewise:`` block left as written.
    """
    if isinstance(spec, program.Program):
        return spec
    return lower_program(to_spec(spec))


def curve_left_as_written_message(blocks: list[str]) -> str:
    """The refusal for a model lowered with its ``piecewise:`` blocks still to be written out."""
    named = ', '.join(f"'{block}'" for block in blocks)
    return (
        f'piecewise: {named} states rows rather than being one, and a program holds the rows. Pass '
        f"spec.expand('piecewise'), which writes each block out as the variables and constraints it states "
        f'and keeps every sos: block for a consumer that takes a set — or spec.expand(), which writes the '
        f'sets out as binaries and linking rows too.'
    )


def lower_program(expanded: Spec) -> program.Program:
    """Compile a model whose curves are written out into a :class:`~math_spec.program.Program`.

    A ``domain: binary`` variable lowers with fixed 0/1 bounds. A ``sos:``
    block lowers as itself — a program carries a set, and
    :meth:`~math_spec.model.Spec.expand` is what states one as binaries
    instead. A ``piecewise:`` block does not lower at all: it states rows, and
    :meth:`~math_spec.model.Spec.expand` is what writes them, so a model still
    carrying one is refused rather than written out on the caller's behalf.

    Args:
        expanded: A model with no ``piecewise:`` block left, which
            :meth:`~math_spec.model.Spec.expand` returns.

    Raises:
        LanguageError: A construct outside the language, named with its
            rewrite, or a ``piecewise:`` block left as written.
    """
    if expanded.piecewise:
        raise LanguageError(curve_left_as_written_message(sorted(expanded.piecewise)))
    resolved = expanded.resolved
    parameters = {
        name: program.ParameterDeclaration(tuple(pdef.dims), pdef.dtype) for name, pdef in expanded.parameters.items()
    }

    variables = {}
    for vname, vdef in expanded.variables.items():
        domain = vdef.domain
        if domain == 'binary':
            lower, upper = program.Constant(0.0), program.Constant(1.0)
        else:
            lower, upper = _bound_expression(vdef.bounds.lower), _bound_expression(vdef.bounds.upper)
        variables[vname] = program.VariableDeclaration(
            tuple(vdef.dims),
            where=_inlined_mask(resolved.variables[vname]),
            lower=lower,
            upper=upper,
            domain=domain,
            absence=vdef.absence,
        )

    constraints = {
        cname: replace(c, lhs=inline(c.lhs), rhs=inline(c.rhs), where=_inlined_mask(c.where))
        for cname, c in resolved.constraints.items()
    }
    objective = None
    if resolved.objective is not None:
        objective = replace(resolved.objective, expression=inline(resolved.objective.expression))

    dimensions = {dname: program.DimensionDeclaration(ddef.dtype) for dname, ddef in expanded.dimensions.items()}
    sos = {
        sname: program.SosDeclaration(sdef.variable, sdef.over, sos_type=sdef.type)
        for sname, sdef in expanded.sos.items()
    }
    expressions = {
        name: program.ExpressionDeclaration(inline(entry), in_math=name in resolved.read_by_the_math)
        for name, entry in resolved.expressions.items()
    }
    assumptions = {
        name: replace(holds, predicate=inline_mask(holds.predicate), where=_inlined_mask(holds.where))
        for name, holds in resolved.assumptions.items()
    }
    return program.Program(
        parameters=parameters,
        variables=variables,
        constraints=constraints,
        objective=objective,
        dimensions=dimensions,
        relations=resolved.relations,
        sos=sos,
        piecewise={name: declaration_of(pw) for name, pw in expanded._expanded_piecewise.items()},
        assumptions=assumptions,
        expressions=expressions,
    )


def inline(node: program.Expression | program.Named) -> program.Expression:
    """*node* with every :class:`~math_spec.program.Named` replaced by its body — the tree a program carries.

    A region's ``when`` is inlined with its value, since a mask may compare
    expressions that name an entry.
    """
    if isinstance(node, program.Named):
        return inline(node.body)
    if isinstance(node, program.Constant | program.Parameter | program.Variable | program.Dual):
        return node
    if isinstance(node, program.Negate):
        return program.Negate(inline(node.operand))
    if isinstance(node, program.Add):
        return program.Add(inline(node.left), inline(node.right))
    if isinstance(node, program.Multiply):
        return program.Multiply(inline(node.left), inline(node.right))
    if isinstance(node, program.Power):
        return program.Power(inline(node.base), inline(node.exponent))
    if isinstance(node, program.Divide):
        return program.Divide(inline(node.numerator), inline(node.divisor))
    if isinstance(node, program.Sum | program.Join | program.Translate | program.WindowSum):
        return replace(node, operand=inline(node.operand))
    if isinstance(node, program.Cases):
        return program.Cases(tuple(program.Region(inline_mask(r.when), inline(r.value)) for r in node.regions))
    assert_never(node)


def inline_mask(mask: program.Mask) -> program.Mask:
    """*mask* with every named expression its comparisons read inlined, as :func:`inline` does for a tree."""
    return program.Mask(_inline_predicate(mask.root))


def _inlined_mask(mask: program.Mask | None) -> program.Mask | None:
    return None if mask is None else inline_mask(mask)


def _inline_predicate(node: program.Predicate) -> program.Predicate:
    if isinstance(node, program.ExpressionComparison):
        return replace(node, left=inline(node.left), right=inline(node.right))
    if isinstance(node, program.CountComparison):
        return replace(node, predicate=inline_mask(node.predicate))
    if isinstance(node, program.TranslatedPredicate | program.PulledBackPredicate):
        return replace(node, operand=inline_mask(node.operand))
    if isinstance(node, program.Not):
        return program.Not(_inline_predicate(node.operand))
    if isinstance(node, program.And):
        return program.And(_inline_predicate(node.left), _inline_predicate(node.right))
    if isinstance(node, program.Or):
        return program.Or(_inline_predicate(node.left), _inline_predicate(node.right))
    return node


def _bound_expression(value: float | str) -> program.Expression:
    if isinstance(value, str):
        return program.Parameter(value)
    return program.Constant(value)
