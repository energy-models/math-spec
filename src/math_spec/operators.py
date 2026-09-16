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
    #: Kwargs whose value is a dimension, or a relation's key column written
    #: ``rel.k`` — ``over=`` and ``along=``. Resolution branches on the value:
    #: a bare name is the dimension it reduces or slides; a dotted name is the
    #: key column summed away, and the relation joins in its other columns.
    dimension_kwargs: tuple[str, ...] = ()
    #: Kwargs whose value is a relation, bare or with a dotted value column —
    #: ``by=``. The dot picks the value column the sum lands on.
    relation_kwargs: tuple[str, ...] = ()
    #: Kwargs naming value columns of the relation another kwarg names —
    #: ``within=`` names the columns a partition groups by.
    role_kwargs: tuple[str, ...] = ()
    edge_kwargs: tuple[str, ...] = ()
    required_value_kwargs: tuple[str, ...] = ()
    #: Kwargs of which the call carries at most one — ``over=`` and ``by=`` on
    #: ``sum``, which are the two forms of one grouping and contradict each other.
    at_most_one_of: tuple[str, ...] = ()
    #: Kwargs the call may omit. Their *kind* still comes from the tuples
    #: above — this says only that the operator has an answer without them.
    optional_kwargs: tuple[str, ...] = ()

    @property
    def required(self) -> frozenset[str]:
        """Every keyword the call must carry."""
        return (
            frozenset(self.dimension_kwargs) | frozenset(self.relation_kwargs) | frozenset(self.required_value_kwargs)
        ) - frozenset(self.optional_kwargs)

    def kind_of(self, kwarg: str) -> Literal['dimension', 'relation', 'role', 'edge', 'value']:
        """What resolution turns the value of *kwarg* into.

        A dimension (or a relation's key column), a relation, a value column of
        one, an edge policy, or a plain value.
        """
        if kwarg in self.dimension_kwargs:
            return 'dimension'
        if kwarg in self.relation_kwargs:
            return 'relation'
        if kwarg in self.role_kwargs:
            return 'role'
        if kwarg in self.edge_kwargs:
            return 'edge'
        return 'value'


#: The closed operator set. ``over=`` sums a key column away, ``by=`` groups
#: onto a value column, and both name the relation through the dot. ``index`` is
#: the internal operator ``x[rel]`` resolves to — it has no surface call form, so
#: its ``by=`` arrives from the index node rather than a written keyword. On
#: ``shift`` and ``sum_back`` a dotted ``along=`` partitions the axis: it says
#: which rows are neighbours, and ``within=`` names the value columns that group
#: is made of.
BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        'sum(<expr>), sum(<expr>, over=<dim|relation.key>) or sum(<expr>, by=<relation[.value]>)',
        dimension_kwargs=('over',),
        relation_kwargs=('by',),
        at_most_one_of=('over', 'by'),
        optional_kwargs=('by', 'over'),
    ),
    'index': Builtin(
        'x[<relation[.value]>]',
        relation_kwargs=('by',),
    ),
    'sum_back': Builtin(
        "sum_back(<expr>, along=<dim|relation.key>, window=<n|parameter>[, edge='wrap'][, within=<column>])",
        dimension_kwargs=('along',),
        role_kwargs=('within',),
        required_value_kwargs=('window',),
        edge_kwargs=('edge',),
        optional_kwargs=('within',),
    ),
    'shift': Builtin(
        "shift(<expr>, along=<dim|relation.key>, offset=<n>[, edge='wrap'|<number>][, within=<column>])",
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
        alternatives = ' or '.join(f'{k}=' for k in builtin.at_most_one_of)
        return (
            f'{name}() takes at most one of {alternatives} — over= sums a key column away and by= '
            f'groups onto a value column, and one call does one of the two.\n'
            f'Write: {builtin.usage}'
        )
    optional = {*builtin.edge_kwargs, *builtin.at_most_one_of, *builtin.optional_kwargs}
    fits = positional == 1 and keys - optional == builtin.required
    return None if fits else f'{name}() expects {builtin.usage}'


def unknown_operator_message(name: str) -> str:
    """The one wording for "that is not an operator"."""
    return (
        f"Unknown operator '{name}'.\n"
        f'Available: {sorted(BUILTIN_NAMES)}\n'
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins; "
        f'if the math is not sayable in the language, use a declared escape.'
    )
