# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One deterministic power system, built once and emitted two ways.

``build_network`` and ``write_tables`` both read off ``_instance``, so the
PyPSA lane and the lpspec lane can never be compared on different numbers. Dispatch, controllable transport and cyclic storage; no ramps, unit
commitment, KVL or extendable capacity. Which of those a lane actually gets is
the rung's business: ``build_network`` takes the components its model names,
and ``write_tables`` writes every table there is because a tier binds only the
ones it declares.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from pathlib import Path

    import pypsa


#: Components every rung carries, built whether or not a model names them.
CORE = frozenset({'Bus', 'Generator', 'Link', 'Load'})

#: Components a rung opts into by naming them, one per tier above T1.
OPTIONAL = frozenset({'StorageUnit'})


@dataclass(frozen=True)
class Shape:
    label: str
    snapshots: int = 24
    buses: int = 4
    gens_per_bus: int = 3

    @property
    def key(self) -> str:
        return f'{self.label}-t{self.snapshots}-b{self.buses}-g{self.gens_per_bus}'


def _seed(shape: Shape, stream: str) -> np.random.Generator:
    """Same shape, same numbers — on any machine, in either lane, forever.

    One generator per *stream* rather than one per instance, so a rung added
    later draws its own numbers and leaves every rung below it untouched. A
    single sequential generator would shift every array after the insertion
    point, and a size field added to ``Shape.key`` for one tier would reseed
    all of them — either way a rung below would silently stop being the
    instance its gates last ran on, and a parity failure found once would stop
    being reproducible. A field a later tier adds belongs in the seed of the
    stream that reads it, never in ``key``.

    ``hash()`` is salted per process, so it cannot be used here.
    """
    digest = hashlib.blake2b(f'{shape.key}/{stream}'.encode(), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(digest, 'big'))


def _instance(shape: Shape) -> dict[str, Any]:
    """The one instance both lanes build from — a bus x snapshot dispatch problem on a ring.

    Load at every bus in every snapshot is drawn against that bus's own
    available generation (``p_nom * p_max_pu``), so zero flow already serves
    it and the network is feasible whatever the link ratings turn out to be.
    """
    n_snap, n_bus, n_gpb = shape.snapshots, shape.buses, shape.gens_per_bus
    n_gen = n_bus * n_gpb

    buses = [f'b{i:03d}' for i in range(n_bus)]
    gens = [f'g{i:04d}' for i in range(n_gen)]
    gen_bus = [buses[i // n_gpb] for i in range(n_gen)]

    links = [f'lk{i:03d}' for i in range(n_bus)]
    link_from = buses
    link_to = [buses[(i + 1) % n_bus] for i in range(n_bus)]

    p_nom = _seed(shape, 'capacity').uniform(50.0, 150.0, n_gen)
    marginal_cost = _seed(shape, 'cost').uniform(10.0, 100.0, n_gen)
    p_max_pu = _seed(shape, 'availability').uniform(0.5, 1.0, (n_snap, n_gen))

    incidence = pd.get_dummies(pd.Series(gen_bus)).reindex(columns=buses, fill_value=0).to_numpy(dtype=float)
    available = (p_max_pu * p_nom[None, :]) @ incidence
    load = available * 0.6 * (0.8 + 0.4 * _seed(shape, 'load').random((n_snap, n_bus)))

    link_rating = _seed(shape, 'transport').uniform(20.0, 80.0, n_bus)

    stores = [f's{i:03d}' for i in range(n_bus)]
    store_p_nom = _seed(shape, 'storage capacity').uniform(20.0, 60.0, n_bus)
    store_max_hours = _seed(shape, 'storage energy').integers(2, 7, n_bus).astype(float)
    efficiency_store = _seed(shape, 'storage charge').uniform(0.85, 0.98, n_bus)
    efficiency_dispatch = _seed(shape, 'storage discharge').uniform(0.85, 0.98, n_bus)
    standing_loss = _seed(shape, 'storage decay').uniform(0.001, 0.01, n_bus)

    assert (load <= available + 1e-9).all(), 'load must not exceed own-bus generation at zero flow'

    return {
        'snapshots': np.arange(n_snap),
        'buses': buses,
        'gens': gens,
        'gen_bus': gen_bus,
        'links': links,
        'link_from': link_from,
        'link_to': link_to,
        'p_nom': p_nom,
        'marginal_cost': marginal_cost,
        'p_max_pu': p_max_pu,
        'load': load,
        'link_rating': link_rating,
        'stores': stores,
        'store_bus': buses,
        'store_p_nom': store_p_nom,
        'store_max_hours': store_max_hours,
        'store_soc_max': store_p_nom * store_max_hours,
        'efficiency_store': efficiency_store,
        'efficiency_dispatch': efficiency_dispatch,
        'standing_loss': standing_loss,
    }


def build_network(shape: Shape, components: frozenset[str] = frozenset()) -> pypsa.Network:
    """The instance as PyPSA components, ready for ``n.optimize``.

    Args:
        shape: The size of the instance.
        components: PyPSA components this rung asks for beyond the transport
            core every rung carries — ``Tier.components``. A component the
            rung's model declares and this function does not know is a lane
            that would silently solve a different problem, so it raises.

    ``legacy_string_dtype`` is set here rather than by every caller: pandas 3.0
    infers a str dtype that PyPSA warns about on any ``Network()``, and this
    repository runs with ``filterwarnings = ["error"]``, so the warning is a
    failure wherever a network is built.
    """
    unknown = components - CORE - OPTIONAL
    if unknown:
        raise ValueError(f'no PyPSA lane for {sorted(unknown)}; build_network knows {sorted(CORE | OPTIONAL)}')
    import pypsa

    pypsa.options.api.legacy_string_dtype = True
    data = _instance(shape)
    n = pypsa.Network()
    n.set_snapshots(data['snapshots'])

    n.add('Bus', data['buses'])
    n.add(
        'Generator',
        data['gens'],
        bus=data['gen_bus'],
        p_nom=data['p_nom'],
        marginal_cost=data['marginal_cost'],
        p_max_pu=pd.DataFrame(data['p_max_pu'], index=data['snapshots'], columns=data['gens']),
    )
    loads = [f'{b}-load' for b in data['buses']]
    n.add(
        'Load',
        loads,
        bus=data['buses'],
        p_set=pd.DataFrame(data['load'], index=data['snapshots'], columns=loads),
    )
    n.add(
        'Link',
        data['links'],
        bus0=data['link_from'],
        bus1=data['link_to'],
        p_nom=data['link_rating'],
        p_min_pu=-1.0,
        efficiency=1.0,
    )
    if 'StorageUnit' in components:
        n.add(
            'StorageUnit',
            data['stores'],
            bus=data['store_bus'],
            p_nom=data['store_p_nom'],
            max_hours=data['store_max_hours'],
            efficiency_store=data['efficiency_store'],
            efficiency_dispatch=data['efficiency_dispatch'],
            standing_loss=data['standing_loss'],
            cyclic_state_of_charge=True,
        )
    return n


def write_tables(shape: Shape, out: Path) -> dict[str, Path]:
    """The same instance as tidy parquet, one table per PyPSA attribute.

    Every table is named ``<Component>_<attribute>`` after the PyPSA statement
    it stands for, which is how a rung's YAML names it and therefore how a
    ``Tier`` asks for it. Index tables keep the bare dimension name, because a
    dimension is an index set rather than an attribute of anything.

    Each lookup (``Generator_bus``, ``Link_bus0``, ``Link_bus1``,
    ``StorageUnit_bus``) is a table of its own under its own name, two columns
    wide — the mapped dimension and its target — which is the one shape
    ``lpspec.sources`` reads a supplied map from.

    ``Generator_p_max`` is ``p_nom * p_max_pu`` already multiplied out, because
    a bound takes a name or a number and never arithmetic. It is what a tier's
    ``upper`` binds; ``Generator_p_nom`` is carried beside it for the tiers
    whose ramp and expansion limits are shares of it. For the same reason a
    storage unit's energy ceiling rides as ``StorageUnit_state_of_charge_max``
    rather than as PyPSA's ``max_hours``.

    Every table is written whatever the tier, and ``tiers.bind`` hands on the
    ones the model declares — a rung binding a table it never named is a
    ``DataError`` from lpspec itself.
    """
    data = _instance(shape)
    n_snap, n_bus, n_gen = len(data['snapshots']), len(data['buses']), len(data['gens'])

    frames = {
        'snapshot': pd.DataFrame({'snapshot': data['snapshots']}),
        'bus': pd.DataFrame({'bus': data['buses']}),
        'generator': pd.DataFrame({'generator': data['gens']}),
        'link': pd.DataFrame({'link': data['links']}),
        'Generator_bus': pd.DataFrame({'generator': data['gens'], 'bus': data['gen_bus']}),
        'Link_bus0': pd.DataFrame({'link': data['links'], 'bus': data['link_from']}),
        'Link_bus1': pd.DataFrame({'link': data['links'], 'bus': data['link_to']}),
        'Generator_p_nom': pd.DataFrame({'generator': data['gens'], 'value': data['p_nom']}),
        'Generator_p_max': pd.DataFrame(
            {
                'snapshot': np.repeat(data['snapshots'], n_gen),
                'generator': data['gens'] * n_snap,
                'value': (data['p_max_pu'] * data['p_nom'][None, :]).reshape(-1),
            }
        ),
        'Generator_marginal_cost': pd.DataFrame({'generator': data['gens'], 'value': data['marginal_cost']}),
        'Link_p_max': pd.DataFrame({'link': data['links'], 'value': data['link_rating']}),
        'Link_p_min': pd.DataFrame({'link': data['links'], 'value': -data['link_rating']}),
        'storage_unit': pd.DataFrame({'storage_unit': data['stores']}),
        'StorageUnit_bus': pd.DataFrame({'storage_unit': data['stores'], 'bus': data['store_bus']}),
        'StorageUnit_p_nom': pd.DataFrame({'storage_unit': data['stores'], 'value': data['store_p_nom']}),
        'StorageUnit_state_of_charge_max': pd.DataFrame(
            {'storage_unit': data['stores'], 'value': data['store_soc_max']}
        ),
        'StorageUnit_efficiency_store': pd.DataFrame(
            {'storage_unit': data['stores'], 'value': data['efficiency_store']}
        ),
        'StorageUnit_efficiency_dispatch': pd.DataFrame(
            {'storage_unit': data['stores'], 'value': data['efficiency_dispatch']}
        ),
        'StorageUnit_standing_loss': pd.DataFrame({'storage_unit': data['stores'], 'value': data['standing_loss']}),
        'Load_p_set': pd.DataFrame(
            {
                'snapshot': np.repeat(data['snapshots'], n_bus),
                'bus': data['buses'] * n_snap,
                'value': data['load'].reshape(-1),
            }
        ),
    }

    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, df in frames.items():
        path = (out / f'{name}.parquet').absolute()
        df.to_parquet(path, index=False)
        paths[name] = path
    return paths
