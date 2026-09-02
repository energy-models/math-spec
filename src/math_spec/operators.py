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
    (``sum(x, over=generator)``); ``lookup_kwargs`` name a lookup, which
    carries its own dimensions, so it needs no sibling kwarg;
    ``edge_kwargs`` take a closed keyword or a number;
    ``required_value_kwargs`` are ordinary values that must be present — a
    number, never a name to resolve (``shift(..., offset=1)``).

    Every dimension or lookup an operator names arrives in a kwarg *value*,
    which is what lets a macro pass one as a formal. ``usage`` is the wording
    every refusal quotes back.
    """

    positional: int
    usage: str
    dimension_kwargs: tuple[str, ...] = ()
    lookup_kwargs: tuple[str, ...] = ()
    #: Kwargs of which the call carries at most one — ``sum`` takes ``over=``
    #: (reduce the dim away) or ``by=`` (reduce it into the lookup's target),
    #: never both, and neither means every dim the operand carries. Members are
    #: excluded from the required set; their kind still comes from the tuples
    #: above.
    at_most_one_of: tuple[str, ...] = ()
    edge_kwargs: tuple[str, ...] = ()
    required_value_kwargs: tuple[str, ...] = ()
    #: Kwargs the call may omit. Their *kind* still comes from the tuples
    #: above — this says only that the operator has an answer without them.
    optional_kwargs: tuple[str, ...] = ()

    @property
    def required(self) -> frozenset[str]:
        """Every keyword the call must carry."""
        return (
            (frozenset(self.dimension_kwargs) | frozenset(self.lookup_kwargs) | frozenset(self.required_value_kwargs))
            - frozenset(self.at_most_one_of)
            - frozenset(self.optional_kwargs)
        )

    def kind_of(self, kwarg: str) -> Literal['dimension', 'lookup', 'edge', 'value']:
        """What resolution turns the value of *kwarg* into: a dimension, a lookup, an edge policy, or a plain value."""
        if kwarg in self.dimension_kwargs:
            return 'dimension'
        if kwarg in self.lookup_kwargs:
            return 'lookup'
        if kwarg in self.edge_kwargs:
            return 'edge'
        return 'value'


#: The closed operator set. ``by=`` is the one keyword that addresses a lookup,
#: and a lookup carries its own dimensions, so no sibling kwarg restates them.
#: On ``shift`` and ``sum_back`` it partitions the axis the operator walks: it
#: says which rows are neighbours, not which group a term lands in.
BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        1,
        'sum(<expr>), sum(<expr>, over=<dim>) or sum(<expr>, by=<lookup>)',
        dimension_kwargs=('over',),
        lookup_kwargs=('by',),
        at_most_one_of=('over', 'by'),
    ),
    'at': Builtin(
        1,
        'at(<expr>, by=<lookup>)',
        lookup_kwargs=('by',),
    ),
    'sum_back': Builtin(
        1,
        "sum_back(<expr>, over=<dim>, within=<n|parameter>[, edge='wrap'][, by=<lookup>])",
        dimension_kwargs=('over',),
        lookup_kwargs=('by',),
        required_value_kwargs=('within',),
        edge_kwargs=('edge',),
        optional_kwargs=('by',),
    ),
    'shift': Builtin(
        1,
        "shift(<expr>, over=<dim>, offset=<n>[, edge='wrap'|<number>][, by=<lookup>])",
        dimension_kwargs=('over',),
        lookup_kwargs=('by',),
        required_value_kwargs=('offset',),
        edge_kwargs=('edge',),
        optional_kwargs=('by',),
    ),
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
            f'{name}() takes at most one of {alternatives} — a lookup carries '
            f'its own dimensions, so by= leaves over= nothing to add.\n'
            f'Write: {builtin.usage}'
        )
    optional = {*builtin.edge_kwargs, *builtin.at_most_one_of, *builtin.optional_kwargs}
    fits = positional == builtin.positional and keys - optional == builtin.required
    return None if fits else f'{name}() expects {builtin.usage}'


def unknown_operator_message(name: str) -> str:
    """The one wording for "that is not an operator"."""
    return (
        f"Unknown operator '{name}'.\n"
        f'Available: {sorted(BUILTIN_NAMES)}\n'
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins; "
        f'if the math is not sayable in the language, use a declared escape.'
    )
