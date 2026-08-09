"""The closed set of built-in helpers and their call shapes.

The set is closed: there is no Python registry. Both lanes therefore accept
exactly the same language, which is what makes the differential tests a
meaningful oracle (docs/ARCHITECTURE.md, hard rule 3). Compositions of these
built-ins belong in ``macros:``; math the language cannot say belongs in a
declared ``escape:`` island (#38), not in a helper that reads like a
built-in on the page.

This module is the *language* side of a helper — its name and its signature,
and nothing else. The signature lives here because four passes need it
(resolution types the dimension arguments, validation name-checks macro
bodies, lowering and the eager builder consume the call), and a helper whose
arity is spelled out once per pass is a helper the passes can disagree about.
It is imported by the linopy-free lane, so it must stay dependency-free — it
knows nothing of the AST, only counts and keyword names. The eager
evaluations live with the eager backend (``builder.py``); the relational ones
are lowering cases and SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Builtin:
    """The call shape of one built-in helper.

    Keyword arguments come in four kinds, and which kind a name is decides what
    resolution turns its value into. ``dimension_kwargs`` name a dimension in
    the *value* (``sum(x, over=generator)``); ``coordinate_kwargs`` name a
    coordinate carried by the sibling ``over=`` dimension
    (``sum(x, over=line, group_by=to)``), so they are only meaningful together;
    ``edge_kwargs`` take a closed keyword or a number
    (``shift(x, over=t, by=1, edge='wrap')``). ``usage`` is the one wording every
    lane quotes back.

    The remaining two are ordinary values — a number, never a name that has to
    resolve. ``required_value_kwargs`` must be present (``shift(..., by=1)``),
    ``value_kwargs`` are optional. Every dimension a helper names now arrives in
    a kwarg *value*, which is what lets a macro pass one as a formal.
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
    value_kwargs: tuple[str, ...] = ()

    @property
    def keywords(self) -> frozenset[str]:
        """Every keyword the call must carry, when they are named at all."""
        return (
            frozenset(self.dimension_kwargs) | frozenset(self.coordinate_kwargs) | frozenset(self.required_value_kwargs)
        )

    @property
    def optional(self) -> frozenset[str]:
        """Every keyword the call may carry but need not."""
        return frozenset(self.edge_kwargs) | frozenset(self.value_kwargs) | frozenset(self.optional_coordinate_kwargs)


BUILTINS: dict[str, Builtin] = {
    'sum': Builtin(
        1,
        'sum(<expr>, over=<dim>[, group_by=<coord>])',
        dimension_kwargs=('over',),
        # `group_by` rather than a bare `by`: with the grouping folded into
        # `sum`, the verb no longer says a regrouping happened, so the keyword
        # has to. `sum(x, over=flow, group_by=component)` reads as what it is.
        optional_coordinate_kwargs=('group_by',),
    ),
    'at': Builtin(
        1,
        'at(<expr>, onto=<dim>, by=<coord>)',
        # `onto`, not `over`: everywhere else `over=` is the dim a helper
        # *consumes*, and this one produces it. One keyword meaning two
        # directions would be worse than two keywords meaning one each.
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
