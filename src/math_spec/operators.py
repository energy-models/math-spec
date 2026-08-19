"""The closed set of built-in operators and their call shapes.

Closed: there is no Python registry, so both lanes accept exactly the same
language and the differential tests are a meaningful oracle (hard rule 3).
Compositions belong in ``macros:``; math the language cannot say belongs in a
declared ``escape:`` island (#38), not in an operator that reads like a built-in.

The *language* side of an operator — its name and signature, nothing else. The
signature lives here because four passes need it (resolution types the
dimension arguments, validation name-checks macro bodies, lowering and the
eager builder consume the call), and an arity spelled out once per pass is one
the passes can disagree about. Imported by the linopy-free lane, so it stays
dependency-free: counts and keyword names, no AST.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    every lane quotes back.
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
    def keywords(self) -> frozenset[str]:
        """Every keyword the call must carry, when they are named at all."""
        return (
            (frozenset(self.dimension_kwargs) | frozenset(self.lookup_kwargs) | frozenset(self.required_value_kwargs))
            - frozenset(self.at_most_one_of)
            - frozenset(self.optional_kwargs)
        )

    @property
    def optional(self) -> frozenset[str]:
        """Every keyword the call may carry but need not."""
        return frozenset(self.edge_kwargs) | frozenset(self.at_most_one_of) | frozenset(self.optional_kwargs)


#: The closed operator set. ``by=`` is the one keyword that addresses a lookup,
#: and a lookup carries its own dimensions, so the sibling kwargs that used to
#: restate them (``sum``'s ``over=`` beside ``group_by=``, ``at``'s ``onto=``)
#: are gone — what the two-keyword spelling once said, the name's *kind* now
#: says, checked at load. ``by=`` on ``shift`` and
#: ``sum_back`` partitions the axis the operator walks, which is the same
#: lookup in a different position: it says which rows are neighbours, not which
#: group a term lands in.
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
        "sum_back(<expr>, over=<dim>, within=<n|parameter>[, edge='wrap'])",
        dimension_kwargs=('over',),
        required_value_kwargs=('within',),
        edge_kwargs=('edge',),
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
    """Why a call to *name* does not fit its signature; ``None`` if it fits.

    Arity is a language rule, so it is checked in resolution — the pass every
    consumer goes through — and the same wording is available to any lane that
    wants to state it again. A retired kwarg speaks before the generic
    mismatch: naming the rewrite is the migration story.
    """
    builtin = BUILTINS[name]
    keys = set(kwargs)
    if len(keys & set(builtin.at_most_one_of)) > 1:
        alternatives = ' or '.join(f'{k}=' for k in builtin.at_most_one_of)
        return (
            f'{name}() takes at most one of {alternatives} — a lookup carries '
            f'its own dimensions, so by= leaves over= nothing to add.\n'
            f'Write: {builtin.usage}'
        )
    fits = positional == builtin.positional and keys - builtin.optional == builtin.keywords
    return None if fits else f'{name}() expects {builtin.usage}'


def unknown_operator_message(name: str) -> str:
    """The one wording for "that is not an operator", shared by both lanes."""
    return (
        f"Unknown operator '{name}'.\n"
        f'Available: {sorted(BUILTIN_NAMES)}\n'
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins; "
        f'if the math is not sayable in the language, use a declared escape.'
    )
