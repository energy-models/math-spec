"""The closed set of built-in helpers and their call shapes.

Closed: there is no Python registry, so both lanes accept exactly the same
language and the differential tests are a meaningful oracle (hard rule 3).
Compositions belong in ``macros:``; math the language cannot say belongs in a
declared ``escape:`` island (#38), not in a helper that reads like a built-in.

The *language* side of a helper — its name and signature, nothing else. The
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
    """The call shape of one built-in helper.

    Keyword arguments come in four kinds, and the kind decides what resolution
    turns the value into: ``dimension_kwargs`` name a dimension
    (``sum(x, over=generator)``); ``coordinate_kwargs`` name a coordinate
    carried by the sibling ``over=`` dimension, so they are only meaningful
    together; ``edge_kwargs`` take a closed keyword or a number;
    ``required_value_kwargs`` are ordinary values that must be present — a
    number, never a name to resolve (``shift(..., by=1)``).

    Every dimension a helper names arrives in a kwarg *value*, which is what
    lets a macro pass one as a formal. ``usage`` is the wording every lane
    quotes back.
    """

    positional: int
    usage: str
    dimension_kwargs: tuple[str, ...] = ()
    coordinate_kwargs: tuple[str, ...] = ()
    #: A coordinate kwarg the call *may* carry. ``sum`` is one helper whose
    #: result shape depends on whether it is there: absent, the dim is reduced
    #: away; present, it is reduced into the dim the coordinate targets.
    optional_coordinate_kwargs: tuple[str, ...] = ()
    edge_kwargs: tuple[str, ...] = ()
    required_value_kwargs: tuple[str, ...] = ()

    @property
    def keywords(self) -> frozenset[str]:
        """Every keyword the call must carry, when they are named at all."""
        return (
            frozenset(self.dimension_kwargs) | frozenset(self.coordinate_kwargs) | frozenset(self.required_value_kwargs)
        )

    @property
    def optional(self) -> frozenset[str]:
        """Every keyword the call may carry but need not."""
        return frozenset(self.edge_kwargs) | frozenset(self.optional_coordinate_kwargs)


#: The closed helper set. Two keyword spellings are deliberate. ``sum`` takes
#: ``group_by`` rather than a bare ``by``: with the grouping folded into
#: ``sum``, the verb no longer says a regrouping happened, so the keyword has
#: to — ``sum(x, over=flow, group_by=component)`` reads as what it is. And
#: ``at`` takes ``onto``, not ``over``: everywhere else ``over=`` is the dim a
#: helper *consumes*, and this one produces it. One keyword meaning two
#: directions would be worse than two keywords meaning one each.
BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        1,
        'sum(<expr>, over=<dim>[, group_by=<coord>])',
        dimension_kwargs=('over',),
        optional_coordinate_kwargs=('group_by',),
    ),
    'at': Builtin(
        1,
        'at(<expr>, onto=<dim>, by=<coord>)',
        dimension_kwargs=('onto',),
        coordinate_kwargs=('by',),
    ),
    'shift': Builtin(
        1,
        "shift(<expr>, over=<dim>, by=<n>[, edge='wrap'|<number>])",
        dimension_kwargs=('over',),
        required_value_kwargs=('by',),
        edge_kwargs=('edge',),
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
    wants to state it again.
    """
    builtin = BUILTINS[name]
    keys = set(kwargs)
    fits = positional == builtin.positional and keys - builtin.optional == builtin.keywords
    return None if fits else f'{name}() expects {builtin.usage}'


#: Spellings that were once helpers, and what replaced them. A retired name
#: fails at load naming its rewrite — there is no alias and no deprecation
#: cycle, so the error *is* the migration story (CONTRIBUTING, "breaking
#: changes are free").
RETIRED: dict[str, str] = {
    'group_sum': 'sum(<expr>, over=<dim>, group_by=<coord>)',
}


def unknown_helper_message(name: str) -> str:
    """The one wording for "that is not a helper", shared by both lanes."""
    if name in RETIRED:
        return (
            f"'{name}' is no longer a helper — the grouping moved into `sum`, "
            f'so one verb covers reducing a dim away and reducing it into '
            f'another.\nWrite: {RETIRED[name]}'
        )
    return (
        f"Unknown helper function '{name}'.\n"
        f'Available: {sorted(BUILTIN_NAMES)}\n'
        f"Define '{name}' as a macro under 'macros:' if it composes built-ins; "
        f'if the math is not sayable in the language, use a declared escape.'
    )
