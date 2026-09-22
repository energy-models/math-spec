# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Expand ``sos:`` blocks into the binaries and rows that state the same restriction.

A set becomes ordinary declarations under names prefixed with the block's own,
the way a ``piecewise:`` block becomes weights and rows; what it emits is
tabled in ``docs/reference/language/piecewise.md``. An unpicked member is held
at zero from both sides, so the rewrite states the same feasible set whatever
sign the member takes — what it needs is a coefficient on each side, which a
model declaring a set without is refused at load for
(:meth:`math_spec.model.Spec` validates it) rather than here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from math_spec.model import SosType, Spec


#: One member's two linking coefficients, below and above. ``None`` on a side is
#: a side the model leaves open, where no rewrite can hold the member at zero.
Coefficients = tuple[float | str | None, float | str | None]


def coefficients(domain: str, lower: float | str, upper: float | str) -> Coefficients:
    """What a member's two linking rows multiply its binary by, ``None`` on a side the model leaves open.

    The 0 and 1 a binary's domain fixes, which no bounds block carries;
    otherwise the member's own declared bounds, each a number or the name of a
    parameter. A parameter is a coefficient like any other: it is what the row
    multiplies by, and no rewrite needs to know its value. Nothing else is a
    coefficient: a number below the bound would cap a picked member the set
    does not cap, and one above it is a looser row than the bound already
    states.
    """
    fixed = domain == 'binary'
    below = 0.0 if fixed else (None if lower == float('-inf') else lower)
    return below, (1.0 if fixed else (None if upper == float('inf') else upper))


@dataclass(frozen=True)
class Emitted:
    """Every name one set's expansion writes, spelled once for the emitter and the collision check.

    The linking row is named after what it says, which the two orders do not
    share: order 2 admits a member in either half of one segment, and order 1
    admits it alone. ``below`` is the same row from underneath, written only
    where the member may be nonzero below zero.
    """

    seg: str
    pick: str
    link: str

    @classmethod
    def of(cls, name: str, order: SosType) -> Emitted:
        """The names set *name* of *order* writes."""
        admits = 'adjacency' if order == 2 else 'nonzero'
        return cls(f'{name}_seg', f'{name}_pick', f'{name}_{admits}')

    @property
    def below(self) -> str:
        """The linking row from underneath."""
        return f'{self.link}_below'

    @property
    def by_kind(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each name by the kind of declaration it would collide with."""
        return (('variable', (self.seg,)), ('constraint', (self.pick, self.link, self.below)))


#: What the binary says, per order — the description its legend entry carries.
_SEGMENTS = {
    1: 'a binary per member, 1 where that member may be nonzero',
    2: 'a binary per segment, 1 where the two members it spans may be nonzero',
}


def expand_sets(schema: Spec) -> Spec:
    """*schema* with every ``sos:`` block written out as binaries and the rows that link them.

    The curves an expansion wrote out ride along, because a model whose
    curves are already written out is the one this is usually asked of.
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
    below, above = _coefficients(member)
    constraints[emitted.link] = {'dims': dims, 'expression': f'{variable} <= {_scaled(above, picked)}'}
    if below != 0.0:
        constraints[emitted.below] = {'dims': dims, 'expression': f'{variable} >= {_scaled(below, picked)}'}


def _scaled(factor: float | str, picked: str) -> str:
    """The binaries a member is admitted by, times *factor*.

    A coefficient of 1 is left out. It is the common one — a weight and a binary
    are both bounded by 1 — and ``x <= 1 * (seg)`` is a factor every reader of
    the row has to work out means nothing.
    """
    return f'({picked})' if factor == 1.0 else f'{factor} * ({picked})'


def _coefficients(member: dict[str, object]) -> tuple[float | str, float | str]:
    """The two coefficients as an expression writes them, read off the member."""
    bounds: dict[str, object] = {'lower': float('-inf'), 'upper': float('inf')}
    declared = member.get('bounds')
    assert declared is None or isinstance(declared, dict), 'a validated model carries a bounds block as a mapping'
    bounds.update(declared or {})
    lower, upper = bounds['lower'], bounds['upper']
    assert isinstance(lower, float | str) and isinstance(upper, float | str), (
        'a bound is a number or the name of a parameter'
    )
    below, above = coefficients(str(member.get('domain', 'continuous')), lower, upper)
    assert below is not None and above is not None, 'a set with a side left open is refused at load'
    return below, above


def _section(raw: dict[str, object], name: str) -> dict[str, object]:
    """The *name* section of the raw model, created empty where the file declares none."""
    section = raw.setdefault(name, {})
    assert isinstance(section, dict), f'{name}: is a mapping in a validated model'
    return section
