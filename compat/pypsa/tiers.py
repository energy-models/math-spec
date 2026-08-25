# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The tier ladder as a registry — see ``compat/pypsa/README.md``.

A rung is a model file and nothing else: the glob over ``models/`` *is* the
registry, so a tier cannot be added to one list and forgotten in another. What
each rung binds is read off the model itself.

Ported from lpspec's ``compat/pypsa/`` as proof-of-concept groundwork for
mathspec, which states the math and nothing downstream of it — there is no
source-binding step here, so a rung's declared tables are advisory only, read
by whatever consumer eventually builds against them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from compat.pypsa.network import write_tables
from math_spec import load_model

if TYPE_CHECKING:
    from compat.pypsa.network import Shape

MODELS = Path(__file__).resolve().parent / 'models'


@dataclass(frozen=True)
class Tier:
    """One rung, named by its model's stem."""

    name: str

    @property
    def model(self) -> Path:
        return MODELS / f'{self.name}.yaml'

    @cached_property
    def sources(self) -> tuple[str, ...]:
        """The tables this rung binds, read off the model.

        A dimension needs a source wherever the file declares no ``values:``,
        and a lookup wherever it declares no ``values:`` either; a parameter
        always does, having no way to declare one.
        """
        model = load_model(self.model)
        return (
            tuple(d for d, block in model.dimensions.items() if block.values is None)
            + tuple(n for n, block in model.lookups.items() if block.values is None)
            + tuple(model.parameters)
        )

    @cached_property
    def components(self) -> frozenset[str]:
        """The PyPSA components this rung asks for, read off the model.

        Every declaration is named ``<Component>_<attribute>`` after the PyPSA
        statement it stands for, so the half before the first underscore *is*
        the component and no second list can drift from the file. What comes
        out is handed to ``build_network``, which is what keeps a rung's two
        lanes on one problem.
        """
        model = load_model(self.model)
        named = (*model.parameters, *model.lookups, *model.variables, *model.constraints)
        return frozenset(name.split('_', 1)[0] for name in named)


TIERS: dict[str, Tier] = {path.stem: Tier(path.stem) for path in sorted(MODELS.glob('*.yaml'))}


def bind(tier: Tier, shape: Shape, out: Path) -> dict[str, str]:
    """Write *shape*'s tables to *out* and return only what *tier* declares."""
    paths = write_tables(shape, out)
    return {name: str(paths[name]) for name in tier.sources}
