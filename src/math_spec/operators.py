# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The closed set of built-in operators and their call shapes.

One home for each signature: a composition is a macro, and the set is closed
to a file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Builtin:
    """The call shape of one built-in operator.

    Keyword arguments come in four kinds, and the kind decides what resolution
    turns the value into: ``dimension_kwargs`` name a dimension
    (``sum(x, over=generator)``); ``relation_kwargs`` name a relation, which
    carries its own dimensions, so it needs no sibling kwarg;
    ``edge_kwargs`` take a closed keyword or a number;
    ``required_value_kwargs`` are ordinary values that must be present — a
    number, never a name to resolve (``shift(..., offset=1)``).

    Every operator takes one positional argument, the expression; every
    dimension or relation it names arrives in a kwarg *value*, which is what
    lets a macro pass one as a formal. ``usage`` is the wording every refusal
    quotes back.
    """

    usage: str
    dimension_kwargs: tuple[str, ...] = ()
    relation_kwargs: tuple[str, ...] = ()
    #: Kwargs naming a column of the relation ``by=`` names — ``over=`` and
    #: ``into=`` — which resolution folds into the join the call makes.
    role_kwargs: tuple[str, ...] = ()
    #: Kwargs naming a dimension on their own and a column of the relation where
    #: ``by=`` names one. ``sum(x, over=generator)`` reduces the dimension
    #: away; ``sum(x, by=l, over=c)`` names the column the call joins on and sums away.
    #: One meaning — what leaves the frame — read in the namespace ``by=``
    #: decides.
    dimension_or_role_kwargs: tuple[str, ...] = ()
    edge_kwargs: tuple[str, ...] = ()
    required_value_kwargs: tuple[str, ...] = ()
    #: Kwargs the call may omit. Their *kind* still comes from the tuples
    #: above — this says only that the operator has an answer without them.
    optional_kwargs: tuple[str, ...] = ()
    #: Kwargs required exactly when the call addresses a relation. A call
    #: names both of its ends and a partition names the columns it groups by,
    #: so that adding a value column to the relation cannot change what an
    #: existing call means.
    with_relation: tuple[str, ...] = ()

    @property
    def required(self) -> frozenset[str]:
        """Every keyword the call must carry."""
        return (
            frozenset(self.dimension_kwargs) | frozenset(self.relation_kwargs) | frozenset(self.required_value_kwargs)
        ) - frozenset(self.optional_kwargs)

    def kind_of(
        self, kwarg: str, *, with_relation: bool = False
    ) -> Literal['dimension', 'relation', 'role', 'edge', 'value'] | None:
        """What resolution turns the value of *kwarg* into, or ``None`` where the operator does not declare it.

        A dimension, a relation, a column of it, an edge policy, or a plain value.
        *with_relation* says whether the call carries a ``by=``, which is what
        decides the kind of a :attr:`dimension_or_role_kwargs` member.
        """
        if kwarg in self.dimension_or_role_kwargs:
            return 'role' if with_relation else 'dimension'
        if kwarg in self.dimension_kwargs:
            return 'dimension'
        if kwarg in self.relation_kwargs:
            return 'relation'
        if kwarg in self.role_kwargs:
            return 'role'
        if kwarg in self.edge_kwargs:
            return 'edge'
        if kwarg in self.required_value_kwargs:
            return 'value'
        return None


#: The closed operator set. ``by=`` is the one keyword that addresses a relation,
#: and a relation carries its own dimensions, so no sibling kwarg restates them.
#: On ``shift`` and ``sum_back`` it partitions the axis the operator steps along: it
#: says which rows are neighbours, not which group a term is added to, and
#: ``within=`` names the value columns the group is made of, on every call
#: that names a ``by=``.
BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        'sum(<expr>), sum(<expr>, over=<dim>) or sum(<expr>, by=<relation>, over=<column>, into=<column>)',
        relation_kwargs=('by',),
        role_kwargs=('into',),
        dimension_or_role_kwargs=('over',),
        optional_kwargs=('by',),
        with_relation=('over', 'into'),
    ),
    'at': Builtin(
        'at(<expr>, by=<relation>, over=<column>, into=<column>)',
        relation_kwargs=('by',),
        role_kwargs=('over', 'into'),
        with_relation=('over', 'into'),
    ),
    'sum_back': Builtin(
        "sum_back(<expr>, along=<dim>, window=<n|parameter>[, edge='wrap'][, by=<relation>, within=<column>])",
        dimension_kwargs=('along',),
        relation_kwargs=('by',),
        role_kwargs=('within',),
        required_value_kwargs=('window',),
        edge_kwargs=('edge',),
        optional_kwargs=('by',),
        with_relation=('within',),
    ),
    'shift': Builtin(
        "shift(<expr>, along=<dim>, offset=<n>[, edge='wrap'|<number>][, by=<relation>, within=<column>])",
        dimension_kwargs=('along',),
        relation_kwargs=('by',),
        role_kwargs=('within',),
        required_value_kwargs=('offset',),
        edge_kwargs=('edge',),
        optional_kwargs=('by',),
        with_relation=('within',),
    ),
    'dual': Builtin('dual(<constraint>)'),
}

BUILTIN_NAMES = frozenset(BUILTINS)


class Amount(NamedTuple):
    """What the errors of an operator that steps along an axis say about the amount it takes."""

    #: The word for the amount.
    noun: str
    #: Why negating a named one at the call site is not what the caller means.
    negated: str
    #: What a named one that varies over the axis it steps along becomes.
    varies: str
    #: The least whole number a literal may be.
    minimum: float
    #: What a literal must be written as, after ``operator(kwarg=...)``.
    form: str


#: The amount each operator that steps along an axis takes, by operator name.
AMOUNTS: dict[str, Amount] = {
    'shift': Amount(
        'offset',
        'A named offset carries its sign in its values, so that one row pointing backwards says '
        'so where the data is read — negate the column instead.',
        'a permutation rather than a lag',
        -math.inf,
        'must be a whole number, or the name of an integer parameter when the offset differs per '
        'entity — a lead time, a transit time, a minimum up time.',
    ),
    'sum_back': Amount(
        'width',
        'A width counts positions and so has no direction; which way a window reaches is the '
        "operator's own name rather than the sign of its width.",
        'a different window at every position, which is no longer "the last n"',
        1,
        'needs a whole number of positions of at least 1, or the name of an integer parameter when '
        'the window differs per entity. A width of 1 is the operand itself.',
    ),
}

#: The one closed keyword an ``edge=`` accepts. Everything else in that
#: position is a number: the value the vacated positions contribute.
EDGE_WRAP = 'wrap'


def edge_error(name: str, given: str) -> str:
    """Why an ``edge=`` value is not one the language has."""
    return (
        f'{name}(edge={given}) is not an edge policy.\n'
        f"Write edge='{EDGE_WRAP}' for a cyclic translation, a number for the "
        f'value the vacated positions contribute, or omit it and they are '
        f'absent — which drops the row.'
    )


def call_shape_error(name: str, positional: int, kwargs: Iterable[str]) -> str | None:
    """Why a call to *name* does not fit its signature; ``None`` if it fits."""
    builtin = BUILTINS[name]
    keys = set(kwargs)
    optional = {*builtin.edge_kwargs, *builtin.optional_kwargs}
    reads = bool(keys & set(builtin.relation_kwargs))
    required = builtin.required | frozenset(builtin.with_relation) if reads else builtin.required
    optional |= set() if reads else set(builtin.with_relation)
    if reads and (unsaid := sorted(frozenset(builtin.with_relation) - keys)):
        return unsaid_ends_error(name, unsaid)
    fits = positional == 1 and keys - optional == required
    return None if fits else f'{name}() expects {builtin.usage}'


#: Why a partition writes ``within=`` whenever it writes ``by=``; ``position()``
#: in a where string says the same, so the sentence has one home.
PARTITION_NAMES_ITS_GROUP = (
    'A partition names the value columns it groups by, so that a relation may gain a value '
    'column without changing what this call means.'
)


def unsaid_ends_error(name: str, unsaid: list[str]) -> str:
    """Why a call through a relation has to write every column it reads: both ends of a read, the group of a partition."""
    reason = (
        PARTITION_NAMES_ITS_GROUP
        if 'within' in BUILTINS[name].with_relation
        else 'A call names both of its ends, so that a relation may gain a value column without changing what this call means.'
    )
    return (
        f'{name}() through a relation leaves {", ".join(f"{k}=" for k in unsaid)} unsaid.\n'
        f'{reason}\n'
        f'Write: {BUILTINS[name].usage}'
    )


def unknown_operator_message(name: str) -> str:
    """The one wording for "that is not an operator"."""
    return (
        f"Unknown operator '{name}'.\n"
        f'Available: {sorted(BUILTIN_NAMES)}\n'
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins. "
        f'A file cannot add an operator: see docs/about/limits.md.'
    )
