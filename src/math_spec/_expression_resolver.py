# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The expression walk of name resolution: an arithmetic syntax tree into the program's expression nodes.

Every operator call is read here — its shape against :data:`~math_spec.operators.BUILTINS`,
its dimension and relation arguments against the namespace — and the node it
stands for is built. :mod:`math_spec.resolution` holds the namespace and the
doors that call this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never, cast

from math_spec._expression_parser import (
    MAX_DEPTH,
    ArithmeticNode,
    BinaryOperatorNode,
    FunctionCallNode,
    KeywordNode,
    NameListNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    depth,
    literal_number,
    names_in,
    shown,
)
from math_spec.dimensions import dims_of
from math_spec.errors import DimensionError, SchemaError, did_you_mean
from math_spec.model import NUMERIC_DTYPES
from math_spec.operators import (
    AMOUNTS,
    BUILTINS,
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.program import (
    Add,
    Constant,
    Direction,
    Divide,
    Dual,
    Expression,
    GroupSum,
    Multiply,
    Negate,
    Parameter,
    Partition,
    Power,
    Pullback,
    Sum,
    Translate,
    Variable,
    WindowSum,
    carries_variable,
    children,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.resolution import Namespace


#: An ``edge=`` as a translation carries it: whether it wraps, and the number
#: the vacated positions contribute where it does not.
_Edge = tuple[bool, float | None]

#: How deep a resolved tree may be with every named expression it reads
#: written in — the tree every pass after resolution recurses over. Three
#: times what one text may nest, since a text reads other texts: a chain of
#: 200 entries survived every pass on a default stack and 250 did not (#643).
MAX_RESOLVED_DEPTH = 3 * MAX_DEPTH


@dataclass(frozen=True)
class ExpressionResolver:
    """One resolution walk over an expression, and the three things every step of it reads.

    A node that cannot be built comes back as ``None`` with its refusal
    appended to ``errors``; every sibling is still read, so a declaration
    with two faults reports both. ``formals`` are a macro template's formals:
    a formal has no kind until a call site binds it, so a node one stands
    under is ``None`` with nothing appended.
    """

    ns: Namespace
    context: str
    errors: list[str]
    formals: frozenset[str] = frozenset()

    def _formal(self, value: ArithmeticNode) -> bool:
        """Whether *value* is a formal, left for the call site to bind."""
        return isinstance(value, NameNode) and value.name in self.formals

    def build(self, node: ArithmeticNode) -> Expression | None:
        """The program tree *node* stands for, held to :data:`MAX_RESOLVED_DEPTH` before anything walks it.

        The depth is measured with every named expression written in, since
        that is the tree every later pass recurses over, and measured with an
        explicit stack, since a recursion would be the crash it prevents.
        """
        resolved = self.arith(node)
        if resolved is None or (found := depth(resolved, children)) <= MAX_RESOLVED_DEPTH:
            return resolved
        self.errors.append(
            f'{self.context}: the expression nests {found} deep with every named expression it reads written in, '
            f'past the {MAX_RESOLVED_DEPTH} levels the language admits. Reduce over a dimension with sum() rather '
            f'than writing the terms out, or precompute the deepest part as a parameter — a named expression '
            f'stands inline where it is read, so naming a part does not make the tree shallower.'
        )
        return None

    def arith(self, node: ArithmeticNode) -> Expression | None:
        """The program node *node* stands for, or ``None``.

        A quoted keyword or a name list in arithmetic arrives through a macro
        formal bound to one.
        """
        if isinstance(node, NumberNode):
            return Constant(node.value)
        if isinstance(node, NameNode):
            return self._name(node)
        if isinstance(node, UnaryOperatorNode):
            operand = self.arith(node.operand)
            if operand is None:
                return None
            return Negate(operand) if node.op == '-' else operand
        if isinstance(node, BinaryOperatorNode):
            return self._binary(node)
        if isinstance(node, FunctionCallNode):
            return self._call(node)
        if isinstance(node, KeywordNode):
            self.errors.append(
                f'{self.context}: {node.value!r} is a quoted keyword, which is only legal as a '
                f"operator kwarg value such as shift(..., edge='wrap'). In an expression, quote "
                f'nothing — names resolve and numbers are written bare.'
            )
            return None
        if isinstance(node, NameListNode):
            self.errors.append(
                f'{self.context}: {node} is a list of names, which is only legal as an operator '
                f'kwarg value such as sum(x, by=[gen_bus, gen_tech]). In an expression, write the '
                f'terms out and add them.'
            )
            return None
        assert_never(node)

    def _binary(self, node: BinaryOperatorNode) -> Expression | None:
        """A subtraction is an addition of the negation, so a program has one additive node."""
        left, right = self.arith(node.left), self.arith(node.right)
        if left is None or right is None:
            return None
        match node.op:
            case '+':
                return Add(left, right)
            case '-':
                return Add(left, Negate(right))
            case '*':
                return Multiply(left, right)
            case '/':
                return Divide(left, right)
            case '**':
                return Power(left, right)
            case _:
                assert_never(node.op)

    def _name(self, node: NameNode) -> Expression | None:
        """A bare name as the variable, parameter or named expression it declares; a dimension or relation is not a value.

        A named expression arrives as the one node :meth:`Namespace.named`
        built for it; the cast is the one place a
        :class:`~math_spec.program.Named` enters a tree typed as a program's,
        which lowering makes true.
        """
        if node.name in self.formals:
            return None
        if node.name in self.ns.schema.expressions:
            try:
                return cast('Expression', self.ns.named(node.name, self.context))
            except SchemaError as e:
                self.errors.append(str(e))
                return None
        match self.ns.kind(node.name):
            case 'variable':
                return Variable(node.name)
            case 'parameter':
                dtype = self.ns.dtypes.get(node.name)
                if dtype is not None and dtype not in NUMERIC_DTYPES:
                    self.errors.append(not_a_number(node.name, dtype, self.context))
                    return None
                return Parameter(node.name)
            case 'dimension':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a dimension, and a dimension is "
                    f'not a value in an expression. Dimensions appear in '
                    f"'dims:', in operator arguments (sum(x, over={node.name})), "
                    f'and in where-comparisons — to use its coordinates as data, '
                    f'declare a parameter over it.'
                )
                return None
            case 'relation':
                self.errors.append(
                    f"{self.context}: '{node.name}' is a relation, and a relation is structure "
                    f'rather than data, so it is not a value in an expression. A relation '
                    f'appears in a helper (sum(x, by={node.name})) and in a where — to '
                    f'carry numbers along this dimension, declare a parameter over it.'
                )
                return None
            case _:
                self.errors.append(self.ns.unknown(node.name, self.context, allow_dims=False, formals=self.formals))
                return None

    def _call(self, node: FunctionCallNode) -> Expression | None:
        """An operator call as the node it is: its shape checked, and each kwarg read by the kind the operator declares for it.

        Every argument is read even after one failed, so a call with two
        faults reports both. A formal anywhere under the call builds nothing
        and refuses nothing.
        """
        if node.name not in BUILTINS:
            self.errors.append(f'{self.context}: {unknown_operator_message(node.name)}')
            return None
        builtin = BUILTINS[node.name]
        shape_error = call_shape_error(node.name, len(node.args), node.kwargs)
        if shape_error is not None:
            self.errors.append(f'{self.context}: {shape_error}')
        if node.name == 'dual':
            return None if shape_error is not None else self._dual(node)
        args = [self.arith(a) for a in node.args]
        with_relation = any(k in node.kwargs for k in builtin.relation_kwargs)
        roles = {k: v for k, v in node.kwargs.items() if builtin.kind_of(k, with_relation=with_relation) == 'role'}
        unrelated = bool(roles) and 'by' not in node.kwargs
        if unrelated:
            self.errors.append(
                f'{self.context}: {node.name}({", ".join(f"{k}=" for k in roles)}) names a column of a relation, '
                f'and no by= names the relation. Write {builtin.usage}'
            )
        dims: dict[str, str | None] = {}
        amounts: dict[str, int | str | None] = {}
        edge: _Edge | None = None
        for key, value in node.kwargs.items():
            match builtin.kind_of(key, with_relation=with_relation):
                case 'edge':
                    edge = self._edge(value, node.name)
                case 'dimension':
                    dims[key] = self._dim_ref(value, node.name, key)
                case 'value':
                    amounts[key] = self._amount(value, node.name, key)
                case 'relation' | 'role' | None:
                    pass
        read = None
        if 'by' in node.kwargs and builtin.kind_of('by') == 'relation':
            read = self.relation_ref(node.kwargs['by'], node.name, 'by', roles, dims.get('along'))
        unread = (
            shape_error is not None
            or unrelated
            or not args
            or args[0] is None
            or None in dims.values()
            or None in amounts.values()
            or ('edge' in node.kwargs and edge is None)
            or ('by' in node.kwargs and read is None)
        )
        if unread:
            return None
        return self._built(node.name, cast('Expression', args[0]), dims, amounts, edge, read)

    def _built(
        self,
        operator: str,
        operand: Expression,
        dims: Mapping[str, str | None],
        amounts: Mapping[str, int | str | None],
        edge: _Edge | None,
        read: Direction | Partition | None,
    ) -> Expression | None:
        """The node *operator* builds from its read arguments, or ``None`` with the refusal appended."""
        if operator == 'sum':
            if read is not None:
                assert isinstance(read, Direction), 'a sum reads its relation in a direction'
                return GroupSum(operand, read)
            if (over := dims.get('over')) is not None:
                return Sum(operand, (over,))
            return self._bare_sum(operand)
        if operator == 'at':
            assert isinstance(read, Direction), 'at reads its relation in a direction'
            return Pullback(operand, read)
        assert read is None or isinstance(read, Partition), 'a translation reads its relation as a partition'
        along = dims['along']
        assert along is not None
        wrap, fill = edge if edge is not None else (False, None)
        if operator == 'shift':
            offset = amounts['offset']
            assert offset is not None
            if not self._edge_fits(operand, offset, wrap=wrap, fill=fill):
                return None
            return Translate(operand, along, offset, wrap=wrap, fill=fill, partition=read)
        if fill is not None:
            self.errors.append(
                f"{self.context}: sum_back(edge=...) takes 'wrap' or nothing. A window sums the terms "
                f'it reaches, so a position before the first contributes nothing rather than a '
                f'fill value; add the constant to the expression if you want one.'
            )
            return None
        width = amounts['window']
        assert width is not None
        return WindowSum(operand, along, width, wrap=wrap, partition=read)

    def _bare_sum(self, operand: Expression) -> Expression | None:
        """``sum(x)`` with no ``over=`` or ``by=`` reduces every dim the operand carries, which it has to carry some of."""
        try:
            inner = dims_of(operand, self.ns.schema, self.context)
        except DimensionError as e:
            self.errors.append(str(e))
            return None
        if not inner:
            self.errors.append(
                f'{self.context}: sum() with no over= or by= sums every dim the operand '
                f'carries, and this one carries none — the expression is already a '
                f'scalar. Drop the sum.'
            )
            return None
        return Sum(operand, tuple(sorted(inner)))

    def _edge_fits(self, operand: Expression, offset: int | str, *, wrap: bool, fill: float | None) -> bool:
        """What a ``shift``'s ``edge=`` may say, and where saying nothing is an answer.

        Every rule here is decidable from the file — whether the operand
        carries a variable, whether the offset is named, what the edge is
        written as — so a file breaking one is refused at load rather than by
        whoever lowers it.
        """
        if wrap:
            return True
        has_var = carries_variable(operand)
        if has_var and fill is not None and fill != 0:
            self.errors.append(
                f'{self.context}: shift(edge={fill:g}) over an expression containing a variable — only '
                f'fill=0 is representable there, since a vacated slot contributes no term. A nonzero '
                f'fill would be a constant standing where a term was; add that constant to the '
                f'expression instead.'
            )
            return False
        if fill is None and _vacates(offset) and not has_var:
            self.errors.append(_shift_over_data_message(self.context))
            return False
        if fill is None and isinstance(offset, str):
            self.errors.append(f'{self.context}: {_named_offset_edge_message(offset)}')
            return False
        return True

    def _amount(self, value: ArithmeticNode, operator: str, key: str) -> int | str | None:
        """``offset=`` or ``window=``: a whole number in the operator's range, or the name of a parameter.

        Closed so that :func:`math_spec.dimensions._check_named_amount` sees
        every parameter an amount carries, and so that a program's
        ``offset`` and ``width`` are the ``int | str`` they say.
        """
        words = AMOUNTS[operator]
        if (literal := literal_number(value)) is not None:
            if not (literal.value.is_integer() and literal.value >= words.minimum):
                self.errors.append(f'{self.context}: {operator}({key}=...) {words.form}')
                return None
            return int(literal.value)
        bare = _without_sign(value)
        if not isinstance(bare, NameNode):
            self.errors.append(
                f'{self.context}: {operator}({key}=) takes a number or the name of an integer parameter. '
                f'Precompute it as a parameter.'
            )
            return None
        if self.ns.kind(bare.name) != 'parameter':
            if self._name(bare) is not None:
                self.errors.append(f'{self.context}: {operator}({key}=...) {words.form}')
            return None
        if (dtype := self.ns.dtypes[bare.name]) != 'int':
            self.errors.append(
                f"{self.context}: {operator}({key}={bare.name}) counts positions, but '{bare.name}' is declared "
                f'dtype: {dtype}. A count of positions is integral — declare it dtype: int, which accepts only an '
                f'integer column, so a fractional {words.noun} has nowhere to arrive from.'
            )
            return None
        if isinstance(value, UnaryOperatorNode) and value.op == '-':
            self.errors.append(
                f'{self.context}: {operator}({key}=-{bare.name}) negates a named {words.noun}. {words.negated}'
            )
            return None
        return bare.name

    def _edge(self, value: ArithmeticNode, operator: str) -> _Edge | None:
        """``edge=``: the closed keyword ``wrap``, or a number to contribute; a name here is a typo."""
        if self._formal(value):
            return None
        if isinstance(value, KeywordNode):
            if value.value == EDGE_WRAP:
                return True, None
            self.errors.append(f'{self.context}: {edge_error(operator, repr(value.value))}')
            return None
        if isinstance(value, NameNode):
            if value.name == EDGE_WRAP:
                self.errors.append(
                    f'{self.context}: {operator}(edge={EDGE_WRAP}) is a bare name where a keyword belongs. '
                    f"Write edge='{EDGE_WRAP}', quoted."
                )
                return None
            self.errors.append(f'{self.context}: {edge_error(operator, value.name)}')
            return None
        if (literal := literal_number(value)) is None:
            self.errors.append(
                f"{self.context}: {operator}(edge=) is an expression, and an edge is the keyword '{EDGE_WRAP}' "
                f'or a number. Write the number itself.'
            )
            return None
        return False, literal.value

    def _dim_ref(self, value: ArithmeticNode, operator: str, key: str) -> str | None:
        """An operator kwarg whose *value* must name a declared dimension."""
        if self._formal(value):
            return None
        if not isinstance(value, NameNode):
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a dimension.')
            return None
        if value.name not in self.ns.dimensions:
            self.errors.append(
                _undeclared_dim(self.context, operator, f'{key}={value.name}', value.name, self.ns, self.formals)
            )
            return None
        return value.name

    def _dual(self, node: FunctionCallNode) -> Dual | None:
        """``dual(c)`` as the leaf it is, its one argument the name of a declared constraint.

        Constraints sit outside the flat namespace, so this store is consulted
        only here — a bare name in arithmetic never reaches it. A dual standing
        where the math is built is refused separately
        (:mod:`math_spec.degree`); this pass only types the name.
        """
        (value,) = node.args
        if self._formal(value):
            return None
        if not isinstance(value, NameNode):
            self.errors.append(
                f'{self.context}: dual() takes the name of a declared constraint, written bare — '
                f'dual(<constraint>). Name the constraint whose row dual you want.'
            )
            return None
        if value.name not in self.ns.constraints:
            self.errors.append(self.ns.unknown_constraint(value.name, self.context, formals=self.formals))
            return None
        return Dual(value.name)

    def relation_ref(
        self,
        value: ArithmeticNode,
        operator: str,
        key: str,
        roles: Mapping[str, ArithmeticNode],
        along: str | None,
    ) -> Direction | Partition | None:
        """An operator's ``by=`` as the direction or the partition the call reads its relation in.

        A relation carries its own dimensions, so the call names columns rather
        than dims: ``over=`` the column consumed, ``into=`` the column
        produced, every other key column joined on. A value column not named
        is not read, and a bare relation's columns are all key. One call
        addresses one table, so several columns of one table are a list and
        several tables are not. *along* is the dimension a translation steps
        along, already read, or ``None`` where it was refused.
        """
        names = names_in(value)
        if not names:
            self.errors.append(f'{self.context}: {operator}({key}=...) must name a relation.')
            return None
        if len(names) > 1:
            self.errors.append(
                f'{self.context}: {operator}({key}={shown(names)}) names {len(names)} relations, and one call '
                f'reads one table. Declare one relation with the columns of all of them, or read them in turn, '
                f'one call each.'
            )
            return None
        name = names[0]
        if name in self.formals:
            return None
        if (problem := self.not_a_relation(name, operator, key)) is not None:
            self.errors.append(problem)
            return None
        if any(n in self.formals for v in roles.values() for n in names_in(v)):
            return None
        read = {k: self._role_name(v, operator, k) for k, v in roles.items()}
        named = {k: r for k, r in read.items() if r is not None}
        if operator in ('shift', 'sum_back'):
            if 'within' not in named:
                return None  # refused already, by the call shape or by the role that named no column
            return self.partition(name, operator, along, named['within'])
        if not ({'over', 'into'} <= set(named)):
            return None  # refused already, by the call shape or by the role that named no column
        return self.direction(name, operator, named['over'], named['into'])

    def _role_name(self, value: ArithmeticNode, operator: str, key: str) -> tuple[str, ...] | None:
        """``over=`` or ``into=`` as the column names it must be — one bare name, or a bracketed list of them."""
        if names := names_in(value):
            return names
        self.errors.append(
            f'{self.context}: {operator}({key}=...) names columns of the relation — a bare name, or a list of them.'
        )
        return None

    def direction(
        self,
        name: str,
        operator: str,
        from_roles: tuple[str, ...],
        into_roles: tuple[str, ...],
    ) -> Direction | None:
        """Which direction ``sum`` or ``at`` reads relation *name* in, between the columns the call named.

        Both ends arrive written: the call shape refuses a call that leaves
        one unsaid, so that a relation may gain a value column without
        changing what this call means. ``at`` needs the read single-valued
        and ``sum`` needs it not: a sum that lands on the key has one term
        per coordinate and adds up nothing, which is a read, so it is
        refused toward ``at``. A read lands on key columns and nothing else,
        because a column outside the key is one no coordinate of the read
        fixes.
        """
        ns, context = self.ns, self.context
        shape = ns.relations[name]
        call = f'{operator}(by={name})'
        if not (
            self._known_roles(name, call, from_roles, 'over') and self._known_roles(name, call, into_roles, 'into')
        ):
            return None

        forward = operator == 'sum'
        if both := sorted(set(from_roles) & set(into_roles)):
            self.errors.append(
                f'{context}: {call}: over= and into= both name {both}, and a call reads between two sets of columns.'
            )
            return None
        for kwarg, roles in (('over', from_roles), ('into', into_roles)):
            dims = [shape.dim(r) for r in roles]
            if shared := sorted({d for d in dims if dims.count(d) > 1}):
                self.errors.append(
                    f'{context}: {call}: {kwarg}={list(roles)} names two columns over {shared}, and the operand '
                    f'carries each dimension once, so nothing says which column its coordinate is read at. Read '
                    f'between columns over distinct dimensions.'
                )
                return None
        if not forward and (outside := [r for r in into_roles if r not in shape.key]):
            self.errors.append(
                f"{context}: {call}: into={list(into_roles)} names {outside}, which the key of '{name}' does not "
                f'hold. A read lands on the key it reads at, {list(shape.key)}, and a column outside that key '
                f'arrives as a dimension the read never fixes. Land on the key, or sum toward {outside}.'
            )
            return None
        joined = tuple(r for r in shape.key if r not in from_roles and r not in into_roles)
        single_valued = set(shape.key) <= {*into_roles, *joined}
        direction = Direction(name, shape, from_roles, into_roles, joined)
        if not forward and not single_valued:
            self.errors.append(
                f"{context}: {call}: at reads one value per coordinate, and '{name}' is not single-valued in "
                f'{list(from_roles)} at the columns the call lands on ({[*into_roles, *joined]}) — its key is '
                f'{list(shape.key)}. Key the table by the columns the call lands on, or read the other way.'
            )
            return None
        if forward and single_valued:
            self.errors.append(
                f'{context}: {call}: this sum lands on the key {list(shape.key)}, so each coordinate has one '
                f"term and nothing is added up — that is a read, which is at()'s. Write "
                f'at(..., by={name}, over={list(from_roles)}, into={list(into_roles)}), or sum toward '
                f'a value column.'
            )
            return None
        return direction

    def _known_roles(self, name: str, call: str, roles: tuple[str, ...], kwarg: str) -> bool:
        """Whether every role *kwarg* names is a column of relation *name*, each once; the refusal otherwise."""
        shape = self.ns.relations[name]
        for role in roles:
            if role not in shape.roles:
                self.errors.append(
                    f"{self.context}: {call}: {kwarg}={role} names no column of '{name}', whose columns are "
                    f'{list(shape.roles)}.'
                )
                return False
        if len(set(roles)) < len(roles):
            self.errors.append(f'{self.context}: {call}: {kwarg}={list(roles)} names a column twice.')
            return False
        return True

    def partition(
        self, name: str, operator: str, along_dim: str | None, within_roles: tuple[str, ...]
    ) -> Partition | None:
        """How a partition (``shift``, ``sum_back``, ``position``) steps along relation *name* over *along_dim*.

        It steps along the one key column over that dimension (a key has one
        column per dimension), joins on the other key columns and groups by the
        value columns *within_roles* names. ``None`` where the dimension is not one
        (already refused), the relation has no key column over it, or
        ``within=`` names a column that is not a value column.
        """
        context = self.context
        shape = self.ns.relations[name]
        call = f'{operator}(by={name})'
        if along_dim is None or not self._known_roles(name, call, within_roles, 'within'):
            return None
        if not shape.values:
            self.errors.append(
                f"{context}: {call}: '{name}' is a bare relation — every column is in its key — so it makes no "
                f'groups and no coordinate is in exactly one. Move the columns the group is made of under '
                f'values:, leaving key: the column {operator} steps along.'
            )
            return None
        over_keys = [r for r in shape.key if shape.dim(r) == along_dim]
        if not over_keys:
            self.errors.append(
                f"{context}: {call}: '{name}' has no key column over '{along_dim}' — its key is "
                f'{list(shape.key)} — and a partition steps along a key column over the dimension it groups.'
            )
            return None
        if keyed := [r for r in within_roles if r in shape.key]:
            self.errors.append(
                f"{context}: {call}: within={keyed} names a key column of '{name}', and a partition groups by "
                f'value columns — its value columns are {list(shape.values)}.'
            )
            return None
        (along,) = over_keys
        joined = tuple(r for r in shape.key if r != along)
        return Partition(name, shape, along, within_roles, joined)

    def not_a_relation(self, name: str, operator: str, key: str) -> str | None:
        """Why *name* is not a relation; ``None`` where it is one."""
        ns, context = self.ns, self.context
        if name in ns.relations:
            return None
        if name in ns.dimensions:
            over_here = sorted(n for n, shape in ns.relations.items() if name in dict(shape.columns).values())
            hint = (
                f"  Relations with a column over '{name}': {over_here}"
                if over_here
                else f"  No relation has a column over '{name}'."
            )
            return (
                f"{context}: {operator}({key}={name}): '{name}' is a dimension, and "
                f'{key}= takes a relation — the named map out of a dimension.\n{hint}'
            )
        return (
            f'{context}: {operator}({key}={name}) does not name a relation{_or_a_formal(self.formals)}. '
            f'{did_you_mean(name, ns.relations, label="Relations")}\n'
            f"Declare it under 'relations:' — {name}: {{key: <the columns a row is identified by>, "
            f'values: <the columns they determine>}}.'
        )


def not_a_number(name: str, dtype: str, context: str) -> str:
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
        f'only dtype: float and dtype: int accept a column it can be done to. {instead}'
    )


def _undeclared_dim(context: str, operator: str, call: str, name: str, ns: Namespace, formals: frozenset[str]) -> str:
    return (
        f'{context}: {operator}({call}) does not name a declared dimension{_or_a_formal(formals)}. '
        f'{did_you_mean(name, ns.dimensions, label="Dimensions")}\n'
        f"Declare '{name}' under 'dimensions:', or fix the typo — an unknown "
        f'dimension makes {operator}() a silent no-op rather than an error.'
    )


def _or_a_formal(formals: frozenset[str]) -> str:
    """The words a refusal inside a template adds, since a formal would have stood there too."""
    return ' or a formal of this macro' if formals else ''


def _without_sign(value: ArithmeticNode) -> ArithmeticNode:
    """*value* under its sign, if it carries one."""
    return value.operand if isinstance(value, UnaryOperatorNode) else value


def _vacates(offset: int | str) -> bool:
    """Whether a translation leaves anything behind.

    A literal zero step reaches every coordinate from itself, so there is no
    vacated position for an ``edge=`` to answer for and the refusal has
    nothing to refuse. A *named* offset may be zero in the data and is not
    known here, so it vacates until proved otherwise.
    """
    return offset != 0


def _named_offset_edge_message(name: str) -> str:
    """Why a named offset must say what the vacated positions contribute.

    The absent edge propagates through a presence frame keyed by the translated
    dimension alone, and a per-entity offset vacates a different slot for each
    entity — which that frame cannot say. Refused rather than answered wrongly
    (#850); the two edges that write their own answer are allowed.
    """
    return (
        f'shift(offset={name}) leaves the vacated positions absent, which a '
        f'per-entity offset cannot say yet.\n'
        f"Add edge='wrap' for a cyclic translation, or edge=<number> for what the "
        f'vacated positions contribute.'
    )


def _shift_over_data_message(context: str) -> str:
    """The three ways out of a translation over data with no ``edge=``, the third being two things at once."""
    return (
        f'{context}: shift() over a variable-free expression leaves vacated positions with no '
        f'value, and inventing one is what silently pinned a bound to zero. Say which you mean:\n'
        f"  shift(x, along=d, offset=n, edge='wrap')   the dimension really is cyclic\n"
        f'  shift(x, along=d, offset=n, edge=0)        the vacated positions contribute zero\n'
        f'  ...and a where: excluding them        the vacated rows should not exist at all\n'
        f'A where: alone does not lift this — it is decided on the expression, before any mask '
        f'is read — and edge=0 alone leaves a row whose bound is that zero.'
    )
