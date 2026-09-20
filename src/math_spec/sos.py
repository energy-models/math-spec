# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``sos:`` blocks into the binaries and rows that state the same restriction.

A set becomes ordinary declarations under names prefixed with the block's own,
the way a ``piecewise:`` block becomes weights and rows; what it emits is
tabled in ``docs/reference/language/piecewise.md``. The rewrite states the same
feasible set as the set itself only for a member at or above zero linked by a
finite coefficient, so a model declaring a set without those is refused at load
(:meth:`math_spec.model.Spec` validates it) rather than here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from math_spec.model import SosType, Spec


def coefficient(bound: float | None, domain: str, upper: float | str) -> float | str | None:
    """What a member's linking row multiplies its binary by, or ``None`` where the model states none that is finite.

    The set's own ``bound:`` first, so the coefficient a reader sees is the one
    the file chose rather than the tighter of two; then the 1 a binary's domain
    fixes, which no bounds block carries; then the member's declared ``upper``,
    a number or the name of a parameter.
    """
    if bound is not None:
        return bound
    if domain == 'binary':
        return 1.0
    return None if upper == float('inf') else upper


@dataclass(frozen=True)
class Emitted:
    """Every name one set's expansion writes, spelled once for the emitter and the collision check.

    The linking row is named after what it says, which the two orders do not
    share: order 2 admits a member in either half of one segment, and order 1
    admits it alone.
    """

    seg: str
    pick: str
    link: str

    @classmethod
    def of(cls, name: str, order: SosType) -> Emitted:
        """The names set *name* of *order* writes."""
        return cls(f'{name}_seg', f'{name}_pick', f'{name}_{"adjacency" if order == 2 else "nonzero"}')

    @property
    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each name by the kind of declaration it would collide with."""
        return (('variable', (self.seg,)), ('constraint', (self.pick, self.link)))


#: What the binary says, per order — the description its legend entry carries.
_SEGMENTS = {
    1: 'a binary per member, 1 where that member may be nonzero',
    2: 'a binary per segment, 1 where the two members it spans may be nonzero',
}


def expand_sets(schema: Spec) -> Spec:
    """*schema* with every ``sos:`` block written out as binaries and the rows that link them.

    The record of what an expanded curve derived rides along, because a model
    whose curves are already written out is the one this is usually asked of.
    """
    from math_spec.model import Spec as Model

    raw = schema.model_dump()
    for name in list(schema.sos):
        emit(raw, name)
    expanded = Model.model_validate(raw)
    expanded._expanded_piecewise = dict(schema._expanded_piecewise)
    return expanded


def emit(raw: dict[str, object], name: str) -> None:
    """Write what the set *name* states as declarations of *raw*, and drop the block.

    Args:
        raw: A model as data, mid-expansion, declaring the set and the variable
            it runs over.
        name: Which set to lower.
    """
    sets = _section(raw, 'sos')
    block = sets.pop(name)
    assert isinstance(block, dict), 'a validated model carries each set as a mapping'
    variable, over, order = block['variable'], block['over'], block['type']
    member = _section(raw, 'variables')[variable]
    assert isinstance(member, dict), 'a validated model carries each variable as a mapping'
    dims = list(member['dims'])
    emitted = Emitted.of(name, order)

    _section(raw, 'variables')[emitted.seg] = {
        'dims': dims,
        **({'where': member['where']} if member.get('where') else {}),
        'domain': 'binary',
        'description': _SEGMENTS[order],
    }
    picked = emitted.seg if order == 1 else f'{emitted.seg} + shift({emitted.seg}, along={over}, offset=1, edge=0)'
    constraints = _section(raw, 'constraints')
    constraints[emitted.pick] = {
        'dims': [d for d in dims if d != over],
        'expression': f'sum({emitted.seg}, over={over}) <= 1',
    }
    constraints[emitted.link] = {'dims': dims, 'expression': f'{variable} <= {_linked(block, member, picked)}'}


def _linked(block: dict[str, object], member: dict[str, object], picked: str) -> str:
    """What a member is at most: the binaries it is admitted by, times the coefficient.

    A coefficient of 1 is left out. It is the common one — a weight and a binary
    are both bounded by 1 — and ``x <= 1 * (seg)`` is a factor every reader of
    the row has to work out means nothing.
    """
    factor = _multiplier(block, member)
    return f'({picked})' if factor == 1.0 else f'{factor} * ({picked})'


def _multiplier(block: dict[str, object], member: dict[str, object]) -> float | str:
    """The coefficient as an expression writes it, read off the set and its member."""
    bounds: dict[str, object] = {'upper': float('inf')}
    declared = member.get('bounds')
    assert declared is None or isinstance(declared, dict), 'a validated model carries a bounds block as a mapping'
    bounds.update(declared or {})
    upper, bound = bounds['upper'], block.get('bound')
    assert isinstance(upper, float | str), 'a bound is a number or the name of a parameter'
    assert bound is None or isinstance(bound, float), 'the schema holds bound: to a number'
    found = coefficient(bound, str(member.get('domain', 'continuous')), upper)
    assert found is not None, 'a set whose member has no finite coefficient is refused at load'
    return found


def _section(raw: dict[str, object], name: str) -> dict[str, object]:
    """The *name* section of the raw model, created empty where the file declares none."""
    section = raw.setdefault(name, {})
    assert isinstance(section, dict), f'{name}: is a mapping in a validated model'
    return section
