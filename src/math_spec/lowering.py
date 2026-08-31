# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Lower a parsed YAML schema (typed AST) to a :class:`~math_spec.program.Program`.

One lowering, whatever builds the result: it reads the typed AST and emits
declarations with names resolved and shapes fixed. It lives on the language
side, so no consumer needs YAML knowledge and this module reaches no consumer
— which is what makes two consumers agreeing about a file structural rather
than careful.

Constructs with no lowering raise :class:`~math_spec.errors.LanguageError` naming
the construct and its rewrite, never a pointer at some other implementation:
a rejection here is a language gap (docs/about/roadmap.md) rather than a
routing decision.

The rules a lowered program then carries:

- a reduction over a dim the operand does not carry is an error, not a silent
  identity — ``math_spec.dimensions`` owns that rule and this module asks it;
- a constraint is **one rule** carrying its own name, so a row is read back by
  the name the file writes, with no positional suffix to guess;
- a file declares one objective, likewise one expression;
- an objective is scalar, so every reduction in it is one the file wrote and
  nothing sums on its own behalf.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

import math_spec.program as program
from math_spec.degree import is_postsolve_grade
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CasesNode,
    ComparisonNode,
    ConstraintNode,
    DimensionNode,
    EdgeNode,
    FunctionCallNode,
    KwargNode,
    LookupNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
)
from math_spec.piecewise import declaration_of, derivations_of, expand_piecewise
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from math_spec.model import Spec, _ExpandedSpec

_SENSES = {'==', '<=', '>='}


def _none_of(masks: list[program.Mask]) -> program.Mask:
    """The region left over: where not one of *masks* holds.

    The ``otherwise`` arm's own mask, built rather than written. An empty list
    cannot reach here — ``cases:`` carries at least one case — so there is no
    vacuous truth to spell.
    """
    remainder = ~masks[0]
    for mask in masks[1:]:
        remainder = remainder & ~mask
    return remainder


def to_program(spec: str | Path | dict[str, Any] | Spec | program.Program) -> program.Program:
    """*spec* as a :class:`~math_spec.program.Program` — the public door.

    Takes whatever you have: a YAML path, the YAML itself, a mapping, a loaded
    model, or a program already. Idempotent, so a caller that does not know
    which it holds can call this and be sure.

    Not memoised. :func:`~math_spec.piecewise.expand_piecewise` is, because
    validators reach for the expansion as well as consumers and the same model
    is expanded more than once on one pass; nothing has that shape here. Add it
    the day something lowers one model twice.

    Args:
        spec: What to read the declarations from.

    Returns:
        Every declaration the file makes, with names resolved and shapes
        fixed.

    Raises:
        SchemaError: The file is not a valid model.
        LanguageError: A construct outside the language, named with its
            rewrite.
    """
    if isinstance(spec, program.Program):
        return spec
    return lower_program(expand_piecewise(to_spec(spec)))


def lower_program(schema: _ExpandedSpec) -> program.Program:
    """Compile a :class:`_ExpandedSpec` into a :class:`Program`.

    Takes the expanded model rather than expanding one: a program is built from
    declarations, and `_ExpandedSpec` is the type that guarantees they are all
    there. Every caller already held one — the expansion is memoised on the
    model — so this moves no work, it only stops the guarantee being a
    convention four consumers happened to observe.

    A ``domain: binary`` variable lowers with fixed 0/1 bounds, so the domain
    needs no separate carrier.

    Raises:
        LanguageError: A construct outside the streaming language, named with
            its rewrite.
    """
    expanded = schema
    ns = Namespace.of(expanded)
    derivations = {
        name: how
        for block, ex in expanded.expanded_piecewise.items()
        for name, how in derivations_of(block, ex).items()
    }
    parameters = {
        name: program.ParameterDeclaration(tuple(pdef.dims), pdef.dtype, derivations.get(name))
        for name, pdef in expanded.parameters.items()
    }

    variables = {}
    for vname, vdef in expanded.variables.items():
        variable_type = vdef.domain
        if variable_type == 'binary':
            lower, upper = program.Constant(0.0), program.Constant(1.0)
        else:
            lower, upper = _bound_expression(vdef.bounds.lower), _bound_expression(vdef.bounds.upper)
        variables[vname] = program.VariableDeclaration(
            tuple(vdef.foreach),
            where=where_of(vdef.where, ns, f"variable '{vname}'", self_variable=vname),
            lower=lower,
            upper=upper,
            variable_type=variable_type,
            absence=vdef.absence,
        )

    constraints = {}
    for cname, cdef in expanded.constraints.items():
        where = where_of(cdef.where, ns, f"constraint '{cname}'")
        ast = expression_of(cdef.expression, expanded, ns, f"constraint '{cname}'")
        if not isinstance(ast, ComparisonNode):
            raise LanguageError(
                f"constraint '{cname}': expression must contain exactly one "
                f'comparison operator (<=, >=, ==). Got: {cdef.expression!r}'
            )
        if ast.op not in _SENSES:
            raise LanguageError(f"constraint '{cname}': unsupported sense '{ast.op}'")
        lowering = _Lowering(expanded, f"constraint '{cname}'")
        constraints[cname] = program.ConstraintDeclaration(
            tuple(cdef.foreach),
            lhs=lowering.expr(ast.left),
            sense=ast.op,
            rhs=lowering.expr(ast.right),
            where=where,
        )

    objective = None
    if (odef := expanded.objective) is not None:
        ast = expression_of(odef.expression, expanded, ns, 'the objective')
        if isinstance(ast, ComparisonNode):
            raise LanguageError('the objective: expression must not contain a comparison operator')
        objective = program.ObjectiveDeclaration(
            odef.sense,
            _Lowering(expanded, 'the objective').expr(ast),
        )

    dimensions = {
        dname: program.DimensionDeclaration(
            tuple(
                program.LookupDeclaration(lname, lk.into, lk.dtype)
                for lname, lk in expanded.lookups.items()
                if lk.over == dname
            ),
            ddef.dtype,
        )
        for dname, ddef in expanded.dimensions.items()
    }
    sos = {
        sname: program.SosDeclaration(
            sdef.variable,
            sdef.over,
            sos_type=sdef.type,
            big_m=sdef.big_m,
        )
        for sname, sdef in expanded.sos.items()
    }
    expressions: dict[str, program.ExpressionNode] = {}
    postsolve_names: list[str] = []
    for name in expanded.expressions:
        context = f"named expression '{name}'"
        ast = expression_of(name, expanded, ns, context)
        assert not isinstance(ast, ComparisonNode), 'load-time validation refuses a comparison in a named expression'
        if is_postsolve_grade(ast):
            postsolve_names.append(name)
        expressions[name] = _Lowering(expanded, context).expr(ast)
    return program.Program(
        parameters=parameters,
        variables=variables,
        constraints=constraints,
        objective=objective,
        dimensions=dimensions,
        sos=sos,
        piecewise={name: declaration_of(ex) for name, ex in expanded.expanded_piecewise.items()},
        named_expressions=expressions,
        postsolve_names=frozenset(postsolve_names),
    )


# ---------------------------------------------------------------------------
# expression lowering
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Lowering:
    """One expression walk, and the two things every step of it reads.

    ``schema`` and ``context`` are fixed for a whole walk, so they are its
    state rather than two arguments every recursion repeats. Extend this
    rather than adding a parameter to :meth:`expr` and every operator seam.
    """

    schema: _ExpandedSpec
    context: str

    def expr(self, node: ArithmeticNode) -> program.ExpressionNode:
        """Rewrite one resolved core-AST expression as a program expression.

        Nothing is judged here: the expression passed every language rule at
        load, and this walk only decides which node a call becomes and the
        shapes a node cannot represent — a ``GroupSum`` groups by a declared
        lookup, a ``Translate`` distance is an integer literal. ``Sum`` and
        ``GroupSum`` stay two nodes under one surface verb, reducing a dim away
        and reducing it into another being different relational shapes.
        """
        if isinstance(node, NumberNode):
            return program.Constant(node.value)

        if isinstance(node, VariableNode):
            return program.Variable(node.name)

        if isinstance(node, ParameterNode):
            return program.Parameter(node.name)

        if isinstance(node, UnresolvedNode | KwargNode):
            msg = f'{node!r} reached lowering. Expressions go through resolution.expression_of() first.'
            raise AssertionError(msg)

        if isinstance(node, ConstraintNode):
            msg = f'{self.context}: a constraint reference reached lowering outside dual(); only dual() consumes one.'
            raise AssertionError(msg)

        if isinstance(node, UnaryOperatorNode):
            inner = self.expr(node.operand)
            return program.Negate(inner) if node.op == '-' else inner

        if isinstance(node, BinaryOperatorNode):
            left = self.expr(node.left)
            right = self.expr(node.right)
            match node.op:
                case '+':
                    return program.Add(left, right)
                case '-':
                    return program.Add(left, program.Negate(right))
                case '*':
                    return program.Multiply(left, right)
                case '/':
                    return program.Divide(left, right)
                case '**':
                    return program.Power(left, right)
                case _:  # pragma: no cover — the parser admits no other operator
                    raise AssertionError(f'{self.context}: operator {node.op!r} reached lowering')

        if isinstance(node, FunctionCallNode):
            try:
                lower_call = _CALLS[node.name]
            except KeyError:
                raise LanguageError(f"{self.context}: built-in '{node.name}' declares no lowering case") from None
            return lower_call(self, node)

        if isinstance(node, CasesNode):
            return self._cases(node)

        assert_never(node)

    def _cases(self, node: CasesNode) -> program.Cases:
        """A cased expression, with every region carrying the mask it applies under.

        The ``otherwise`` arm carries no ``when`` in the file; here it carries
        the negation of every other region's, so a consumer adds regions rather
        than working out which one is left. The language proved the rest apart
        before this ran, so the negation is exactly the remainder and the
        regions stay disjoint and total.

        Every ``when`` arrives folded from resolution, and an arm that folded
        to a literal was refused at load — so no literal reaches a region.
        """
        stated = [program.Mask(arm.when) for arm in node.arms if arm.when is not None]
        regions = []
        for arm in node.arms:
            when = program.Mask(arm.when) if arm.when is not None else _none_of(stated)
            regions.append(program.Region(when, self.expr(arm.value)))
        return program.Cases(tuple(regions))

    def sum(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``sum(x)``, ``sum(x, over=d)`` or ``sum(x, by=lookup)``.

        Two program nodes under one surface verb: reducing a dim away and reducing it
        *into* another are different relational shapes, so ``by=`` decides which
        before anything else is read.
        """
        by_node = node.kwargs.get('by')
        operand = self.expr(node.args[0])
        if by_node is None and 'over' not in node.kwargs:
            return program.Sum(operand, tuple(sorted(dims_of(node.args[0], self.schema, self.context))))
        if by_node is None:
            over_node = node.kwargs['over']
            if not isinstance(over_node, DimensionNode):
                raise LanguageError(f'{self.context}: sum(over=...) must name a dimension')
            return program.Sum(operand, (over_node.name,))
        if not isinstance(by_node, LookupNode):
            raise LanguageError(f'{self.context}: sum(by=...) must name a lookup')
        return program.GroupSum(operand, over=by_node.dimension, coordinate=by_node.names, into=by_node.into)

    def at(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``at(x, by=lookup)`` — the adjoint of :meth:`sum`'s ``by=`` form."""
        by_node = node.kwargs['by']
        if not isinstance(by_node, LookupNode):
            raise LanguageError(f'{self.context}: at(by=...) must name a lookup')
        return program.At(
            self.expr(node.args[0]),
            over=by_node.dimension,
            coordinate=by_node.names,
            into=by_node.into,
        )

    def sum_back(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``sum_back(x, over=d, within=w)`` — a trailing window along one dimension.

        *within* is an integer literal of at least one, or a parameter naming a
        per-entity width, which the language holds to the two rules that make it
        mean one thing before this is reached.

        ``by=`` names the lookup the window stops at the edges of, and rides on
        the node the way it rides on a translation — the dim rules have already
        held it to one lookup over the walked dimension.
        """
        over_node = node.kwargs['over']
        if not isinstance(over_node, DimensionNode):
            raise LanguageError(f'{self.context}: sum_back(over=...) must name a dimension')
        within_node = node.kwargs['within']
        operand = self.expr(node.args[0])
        wrap = isinstance(node.kwargs.get('edge'), EdgeNode)
        width: int | str
        if isinstance(within_node, ParameterNode):
            width = within_node.name
        else:
            assert isinstance(within_node, NumberNode), 'a within= that is neither is refused at load'
            width = int(within_node.value)
        return program.Window(operand, over_node.name, width=width, wrap=wrap, partition=_partition_of(node))

    def dual(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``dual(c)`` — the shadow price of constraint ``c``, read after the solve.

        Reachable only from a post-solve-grade entry; the loader refuses
        ``dual`` anywhere the math a solver ingests is built, so a
        :class:`program.Dual` never stands under the objective or a constraint.
        """
        (arg,) = node.args
        assert isinstance(arg, ConstraintNode), "resolution resolves dual()'s argument to a constraint reference"
        return program.Dual(arg.name)

    def shift(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``shift(x, over=d, offset=n)`` — the value at *t - offset* along one dim.

        What the vacated positions contribute is ``edge=``'s to say, and the
        language has already held it to the keyword or a number.
        """
        over_node = node.kwargs['over']
        if not isinstance(over_node, DimensionNode):
            raise LanguageError(f'{self.context}: shift(over=...) must name a dimension')
        by_node = node.kwargs['offset']
        operand = self.expr(node.args[0])
        edge = node.kwargs.get('edge')
        by: int | str
        if isinstance(by_node, ParameterNode):
            by = by_node.name
        else:
            assert isinstance(by_node, NumberNode), 'an offset= that is neither is refused at load'
            by = int(by_node.value)
        return program.Translate(
            operand,
            over_node.name,
            offset=by,
            wrap=isinstance(edge, EdgeNode),
            fill=edge.value if isinstance(edge, NumberNode) else None,
            partition=_partition_of(node),
        )


#: One lowering per name in the language's ``BUILTIN_NAMES``. A table rather
#: than a chain of ``if``s because the set is *closed* — nothing registers into
#: it, and a name the language declares with no entry here is refused by name
#: rather than by ``KeyError``. Each method is named for the operator it
#: lowers, so the table reads as the identity it nearly is.
_CALLS: dict[str, Callable[[_Lowering, FunctionCallNode], program.ExpressionNode]] = {
    'sum': _Lowering.sum,
    'at': _Lowering.at,
    'sum_back': _Lowering.sum_back,
    'shift': _Lowering.shift,
    'dual': _Lowering.dual,
}


def _partition_of(node: FunctionCallNode) -> str | None:
    """The lookup a translation walks inside, if the call names one.

    That it is a *single* lookup, and one *over the translated dimension*, is
    checked with the other dim rules (``math_spec.dimensions``), where a model
    is refused before any data is read.
    """
    by_node = node.kwargs.get('by')
    if by_node is None:
        return None
    assert isinstance(by_node, LookupNode)
    return by_node.names[0]


def _bound_expression(value: float | str) -> program.ExpressionNode:
    if isinstance(value, str):
        return program.Parameter(value)
    return program.Constant(value)
