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
from typing import TYPE_CHECKING, Literal, assert_never, cast

import math_spec.program as program
from math_spec.dimensions import dims_of
from math_spec.errors import LanguageError
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
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
from math_spec.piecewise import expand_piecewise
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.validation import to_spec
from math_spec.where_parser import AndNode, BooleanLiteralNode, NotNode, OrNode, WhereNode

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from math_spec.model import Spec, _ExpandedSpec

_SENSES = {'==', '<=', '>='}


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
    parameters = {
        name: program.ParameterDeclaration(tuple(pdef.dims), pdef.dtype) for name, pdef in expanded.parameters.items()
    }

    variables = {}
    for vname, vdef in expanded.variables.items():
        variable_type = cast('program.VariableType', vdef.domain)
        if variable_type == 'binary':
            lower, upper = program.Constant(0.0), program.Constant(1.0)
        else:
            lower, upper = _bound_expression(vdef.bounds.lower), _bound_expression(vdef.bounds.upper)
        variables[vname] = program.VariableDeclaration(
            tuple(vdef.foreach),
            where=_lower_where(vdef.where, ns, f"variable '{vname}'", self_variable=vname),
            lower=lower,
            upper=upper,
            variable_type=variable_type,
            absence=cast('program.VariableAbsence', vdef.absence),
        )

    constraints = {}
    for cname, cdef in expanded.constraints.items():
        where = _lower_where(cdef.where, ns, f"constraint '{cname}'")
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
            tuple(program.LookupDeclaration(cname, target) for cname, target in expanded.targeted_of(dname).items()),
            tuple(expanded.labels_of(dname)),
            ddef.dtype,
        )
        for dname, ddef in expanded.dimensions.items()
    }
    sos = {
        sname: program.SosDeclaration(
            sdef.variable,
            sdef.over,
            sos_type=cast('Literal[1, 2]', sdef.type),
            big_m=sdef.big_m,
        )
        for sname, sdef in expanded.sos.items()
    }
    expressions = {name: _lower_expression(expanded, ns, name) for name in expanded.expressions}
    return program.Program(
        parameters=parameters,
        variables=variables,
        constraints=constraints,
        objective=objective,
        dimensions=dimensions,
        sos=sos,
        named_expressions=expressions,
    )


def _lower_expression(schema: _ExpandedSpec, ns: Namespace, name: str) -> program.ExpressionNode:
    """Compile the named expression *name* into a program expression.

    Raises:
        KeyError: No named expression called *name*.
        LanguageError: A construct outside the streaming language.
    """
    expanded = schema
    context = f"named expression '{name}'"
    ast = expression_of(expanded.expressions[name].expression, expanded, ns, context)
    assert not isinstance(ast, ComparisonNode), 'load-time validation refuses a comparison in a named expression'
    return _Lowering(expanded, context).expr(ast)


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

        assert_never(node)

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

    def shift(self, node: FunctionCallNode) -> program.ExpressionNode:
        """``shift(x, over=d, offset=n)`` — the value at *t - offset* along one dim.

        The longest of the four because *offset* and *edge* are read together:
        what the vacated positions contribute decides whether a named offset is
        sayable at all, so it is settled before the offset is read.
        """
        over_node = node.kwargs['over']
        if not isinstance(over_node, DimensionNode):
            raise LanguageError(f'{self.context}: shift(over=...) must name a dimension')
        partition = _partition_of(node)
        by_node = node.kwargs['offset']
        sign = 1
        if isinstance(by_node, UnaryOperatorNode) and by_node.op == '-':
            sign, by_node = -1, by_node.operand
        operand = self.expr(node.args[0])
        edge = node.kwargs.get('edge')
        wrap = isinstance(edge, EdgeNode)
        fill = None if wrap else _edge_fill(edge)
        by: int | str
        if isinstance(by_node, ParameterNode):
            by = by_node.name
        else:
            assert isinstance(by_node, NumberNode), 'an offset= that is neither is refused at load'
            by = sign * int(by_node.value)
        return program.Translate(operand, over_node.name, offset=by, wrap=wrap, fill=fill, partition=partition)


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
}


def _edge_fill(edge: ArithmeticNode | None) -> float | None:
    """The number an ``edge=`` names, or ``None`` where it names nothing.

    What it *may* name is the language's to say (``dimensions._check_edge``);
    this only reads it.
    """
    if edge is None:
        return None
    sign = 1.0
    if isinstance(edge, UnaryOperatorNode) and edge.op in ('-', '+'):
        sign, edge = (-1.0 if edge.op == '-' else 1.0), edge.operand
    assert isinstance(edge, NumberNode), 'an edge= that is neither a keyword nor a number is refused at load'
    return sign * float(edge.value)


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


# ---------------------------------------------------------------------------
# where lowering
# ---------------------------------------------------------------------------


def _lower_where(text: str | None, ns: Namespace, context: str, self_variable: str | None = None) -> WhereNode | None:
    """Lower a where string to a program predicate, ``None`` when there is no mask.

    Every constant the connectives decide is folded away first, so a mask that
    admits every row arrives as ``None`` however the file spelled it and one
    that admits none arrives as ``BooleanLiteralNode(False)``.
    """
    node = where_of(text, ns, context, self_variable)
    if node is None:
        return None
    folded = _fold(node)
    if isinstance(folded, BooleanLiteralNode) and folded.value:
        return None
    return folded


def _fold(node: WhereNode) -> WhereNode:
    """*node* with every literal a connective decides evaluated away.

    A mask is decidable without data wherever a literal meets a connective, so
    it is decided here rather than by each consumer: ``X AND True`` is ``X``,
    ``X OR True`` is every row, ``X AND False`` is none, and ``NOT True`` is
    ``False``. What survives is a predicate over data, or the one literal the
    whole mask reduces to — which is what makes a ``BooleanLiteralNode`` a node
    a consumer meets at the root or nowhere.
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
