# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The closed set of built-in operators and their call shapes.

One home for each signature: a composition is a macro, and math the language
cannot say is a declared ``escape:``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Builtin:
    """The call shape of one built-in operator.

    Keyword arguments come in four kinds, and the kind decides what resolution
    turns the value into: ``dimension_kwargs`` name a dimension
    (``sum(x, over=generator)``) or a relation's key column
    (``sum(x, over=zone_of.generator)``); ``relation_kwargs`` name a relation
    and the columns the call lands on (``sum(x, by=zone_of.zone)``);
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
    #: Kwargs naming value columns of the relation another kwarg names —
    #: ``within=`` on a partition, and both ends of an ``at``.
    role_kwargs: tuple[str, ...] = ()
    edge_kwargs: tuple[str, ...] = ()
    required_value_kwargs: tuple[str, ...] = ()
    #: Kwargs the call may omit. Their *kind* still comes from the tuples
    #: above — this says only that the operator has an answer without them.
    optional_kwargs: tuple[str, ...] = ()
    #: Kwargs of which the call carries at most one — ``over=`` and ``by=`` on
    #: ``sum``, which name the two ends of one grouping.
    at_most_one_of: tuple[str, ...] = ()
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

    def kind_of(self, kwarg: str) -> Literal['dimension', 'relation', 'role', 'edge', 'value'] | None:
        """What resolution turns the value of *kwarg* into, or ``None`` where the operator does not declare it.

        A dimension — or the key column of a relation, which names one — a
        relation, a value column of one, an edge policy, or a plain value.
        """
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


#: The closed operator set. A relation is addressed through the dot, which
#: names its columns beside it: ``over=`` names the columns a sum reads from,
#: ``by=`` the columns it lands on, and a dotted ``along=`` the key column
#: ``shift`` and ``sum_back`` step along, where ``within=`` names the value
#: columns the group is made of. ``at`` still names both of its ends with
#: ``over=`` and ``into=`` beside a bare ``by=``.
BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        'sum(<expr>), sum(<expr>, over=<dim|relation.columns>) or sum(<expr>, by=<relation.columns>)',
        dimension_kwargs=('over',),
        relation_kwargs=('by',),
        optional_kwargs=('over', 'by'),
        at_most_one_of=('over', 'by'),
    ),
    'at': Builtin(
        'at(<expr>, by=<relation>, over=<column>, into=<column>)',
        relation_kwargs=('by',),
        role_kwargs=('over', 'into'),
        with_relation=('over', 'into'),
    ),
    'sum_back': Builtin(
        "sum_back(<expr>, along=<dim|relation.key column>, window=<n|parameter>[, edge='wrap'][, within=<column>])",
        dimension_kwargs=('along',),
        role_kwargs=('within',),
        required_value_kwargs=('window',),
        edge_kwargs=('edge',),
        optional_kwargs=('within',),
    ),
    'shift': Builtin(
        "shift(<expr>, along=<dim|relation.key column>, offset=<n>[, edge='wrap'|<number>][, within=<column>])",
        dimension_kwargs=('along',),
        role_kwargs=('within',),
        required_value_kwargs=('offset',),
        edge_kwargs=('edge',),
        optional_kwargs=('within',),
    ),
    'dual': Builtin('dual(<constraint>)'),
}

BUILTIN_NAMES = frozenset(BUILTINS)

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
    if len(keys & set(builtin.at_most_one_of)) > 1:
        return both_ends_error(name)
    optional = {*builtin.edge_kwargs, *builtin.optional_kwargs}
    reads = bool(keys & set(builtin.relation_kwargs))
    required = builtin.required | frozenset(builtin.with_relation) if reads else builtin.required
    optional |= set() if reads else set(builtin.with_relation)
    if reads and (unsaid := sorted(frozenset(builtin.with_relation) - keys)):
        return unsaid_ends_error(name, unsaid)
    fits = positional == 1 and keys - optional == required
    return None if fits else f'{name}() expects {builtin.usage}'


#: Why a partition writes ``within=`` whenever it names a relation;
#: ``position()`` in a where string says the same, so the sentence has one home.
PARTITION_NAMES_ITS_GROUP = (
    'A partition names the value columns it groups by, so that a relation may gain a value '
    'column without changing what this call means.'
)


def both_ends_error(name: str) -> str:
    """Why a grouping names one end of itself: ``over=`` and ``by=`` are the two ways to say the same grouping."""
    return (
        f'{name}() names both ends of one grouping: over= says which columns it reads from and '
        f'by= says which columns it lands on, and the relation supplies the other end.\n'
        f'Write: {BUILTINS[name].usage}'
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
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins; "
        f'if the math is not sayable in the language, use a declared escape.'
    )
