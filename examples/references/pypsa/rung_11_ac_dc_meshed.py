# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 11: PyPSA's own `ac_dc_meshed` example, whole — meshed AC and DC, extendable lines, links and generators, carriers, a CO2 budget."""

from __future__ import annotations

from datetime import datetime

#: Ten hourly stamps, the example's own. Every weighting column there is 1.0, which is
#: also the default, so no row below sets one.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(10)]

#: Wind availability per snapshot, for the three generators that carry a profile.
P_MAX_PU = {
    'Manchester Wind': [0.930019875, 0.4857475804, 0.2336917351, 0.2576042221, 0.6269055694, 0.6035984088, 0.6789075462, 0.3613026112, 0.6216040549, 0.5215183715],
    'Norway Wind': [0.9745832033, 0.4812903778, 0.4072258018, 0.5999649628, 0.524468219, 0.0096927054, 0.2204533621, 0.8239185004, 0.5562297265, 0.4394160378],
    'Frankfurt Wind': [0.5590784039, 0.7529103711, 0.1234650887, 0.9666766524, 0.8590078044, 0.5261537924, 0.077893008, 0.0590234716, 0.2485544952, 0.1080601728],
}  # fmt: skip

#: Demand per snapshot, for each of the six loads.
P_SET = {
    'London': [35.7962441027, 976.8245614698, 250.5873120464, 130.7531445827, 151.1001686, 931.857051942, 289.8482871447, 864.3433217147, 689.5772637703, 627.8789859434],
    'Frankfurt': [398.0478469638, 432.4361062425, 379.8039282662, 868.3617642835, 548.7707546221, 828.6652426012, 449.2907519075, 699.1637663734, 915.8667802518, 414.8876464034],
    'Norway': [820.035835936, 854.8340468618, 42.550744351, 647.5482327851, 884.0738733306, 509.0624485516, 595.6079648147, 291.6424496984, 2.1534925491, 760.7401765038],
    'Norwich': [415.4625642653, 262.6061464526, 418.4763531902, 552.9595393098, 218.159858091, 791.9762655836, 531.8706808219, 23.5134667186, 970.0590684572, 0.9248336907],
    'Bremen': [640.0863775411, 703.554333706, 440.8361303183, 612.5763056818, 803.4367808051, 605.4006873582, 641.0905902397, 408.0085411725, 912.2477761646, 898.0530916423],
    'Manchester': [857.5514402011, 750.5996237166, 156.5648760141, 527.8708221189, 83.8977589634, 676.6233193474, 731.1371004827, 553.3448891847, 298.338082262, 768.2905859888],
}  # fmt: skip


def build():
    """The example network, stated as the calls that build it.

    A rung states its data inline, so that the PyPSA model under review is the
    script — ``reference.py`` says so and ``test_pypsa_references.py`` checks
    it. The numbers here are PyPSA's own ``ac_dc_meshed``, which is where this
    rung's published objective comes from; ``reference.py`` pins the version
    they were read at.
    """
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    # Bus
    n.add('Bus', 'London', v_nom=380.0, x=-0.13, y=51.5)
    n.add('Bus', 'Norwich', v_nom=380.0, x=1.3, y=52.6)
    n.add('Bus', 'Norwich DC', v_nom=200.0, x=1.3, y=52.5, carrier='DC')
    n.add('Bus', 'Manchester', v_nom=380.0, x=-2.2, y=53.47)
    n.add('Bus', 'Bremen', v_nom=380.0, x=8.8, y=53.08)
    n.add('Bus', 'Bremen DC', v_nom=200.0, x=8.8, y=52.98, carrier='DC')
    n.add('Bus', 'Frankfurt', v_nom=380.0, x=8.7, y=50.12)
    n.add('Bus', 'Norway', v_nom=380.0, x=10.75, y=60.0)
    n.add('Bus', 'Norway DC', v_nom=200.0, x=10.75, y=60.0, carrier='DC')
    # Carrier
    n.add('Carrier', 'gas', co2_emissions=0.24, color='red')
    n.add('Carrier', 'wind', color='blue')
    n.add('Carrier', 'battery', color='green')
    n.add('Carrier', 'load', color='black')
    n.add('Carrier', 'AC', color='orange')
    n.add('Carrier', 'DC', color='purple')
    # Generator
    n.add(
        'Generator',
        'Manchester Wind',
        bus='Manchester',
        p_nom=80.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Manchester Wind'],
        carrier='wind',
        marginal_cost=0.11,
        capital_cost=2793.6516029328,
    )
    n.add(
        'Generator',
        'Manchester Gas',
        bus='Manchester',
        p_nom=50000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=4.5323676307,
        capital_cost=196.6151679691,
        efficiency=0.3500264336,
    )
    n.add(
        'Generator',
        'Norway Wind',
        bus='Norway',
        p_nom=100.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Norway Wind'],
        carrier='wind',
        marginal_cost=0.09,
        capital_cost=2184.3747960912,
    )
    n.add(
        'Generator',
        'Norway Gas',
        bus='Norway',
        p_nom=20000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=5.8928445406,
        capital_cost=158.2512497168,
        efficiency=0.3568363832,
    )
    n.add(
        'Generator',
        'Frankfurt Wind',
        bus='Frankfurt',
        p_nom=110.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Frankfurt Wind'],
        carrier='wind',
        marginal_cost=0.1,
        capital_cost=2129.4561224763,
    )
    n.add(
        'Generator',
        'Frankfurt Gas',
        bus='Frankfurt',
        p_nom=80000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=4.0863219899,
        capital_cost=102.6769530076,
        efficiency=0.3516658529,
    )
    # Line
    n.add(
        'Line',
        '0',
        bus0='London',
        bus1='Manchester',
        x=0.7968782824,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1367157553,
        carrier='AC',
    )
    n.add(
        'Line',
        '1',
        bus0='Manchester',
        bus1='Norwich',
        x=0.3915599178,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1334916779,
        carrier='AC',
    )
    n.add(
        'Line',
        '2',
        bus0='Bremen DC',
        bus1='Norwich DC',
        r=0.2126041927,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0086734246,
        carrier='AC',
    )
    n.add(
        'Line',
        '3',
        bus0='Norwich DC',
        bus1='Norway DC',
        r=0.4861637504,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1291260515,
        carrier='AC',
    )
    n.add(
        'Line',
        '4',
        bus0='Norway DC',
        bus1='Bremen DC',
        r=0.4287266497,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0624298729,
        carrier='AC',
    )
    n.add(
        'Line',
        '5',
        bus0='Norwich',
        bus1='London',
        x=0.2388003463,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0218524519,
        carrier='AC',
    )
    n.add(
        'Line',
        '6',
        bus0='Bremen',
        bus1='Frankfurt',
        x=0.4,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.2,
        carrier='AC',
    )
    # Link
    n.add(
        'Link',
        'Norwich Converter',
        bus0='Norwich',
        bus1='Norwich DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.21,
    )
    n.add(
        'Link',
        'Norway Converter',
        bus0='Norway',
        bus1='Norway DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.2,
    )
    n.add(
        'Link',
        'Bremen Converter',
        bus0='Bremen',
        bus1='Bremen DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.19,
    )
    n.add(
        'Link',
        'DC link',
        bus0='London',
        bus1='Bremen',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.8765342,
    )
    # Load
    n.add('Load', 'London', bus='London', carrier='load', p_set=P_SET['London'])
    n.add('Load', 'Frankfurt', bus='Frankfurt', carrier='load', p_set=P_SET['Frankfurt'])
    n.add('Load', 'Norway', bus='Norway', carrier='load', p_set=P_SET['Norway'])
    n.add('Load', 'Norwich', bus='Norwich', carrier='load', p_set=P_SET['Norwich'])
    n.add('Load', 'Bremen', bus='Bremen', carrier='load', p_set=P_SET['Bremen'])
    n.add('Load', 'Manchester', bus='Manchester', carrier='load', p_set=P_SET['Manchester'])
    # GlobalConstraint
    n.add('GlobalConstraint', 'co2_limit', sense='<=', constant=1000.0)
    return n
