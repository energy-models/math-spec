# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
"""Load one model per claim about lookups, and print what the loader said.

Each probe is a whole model. A probe that claims a capability is expected to
load, and the evidence is the frame the loader gives its constraint. A probe
that claims a refusal is expected to fail, and the evidence is the message.
Run it against any ref: the table is the answer that ref gives, so a claim
that stops holding shows up as a row whose verdict flipped.

    python gams_probes.py [--write-yaml DIR] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from math_spec import LanguageError, to_markdown, to_program

BASE: dict[str, Any] = {
    'dimensions': {
        'generator': {},
        'bus': {},
        'zone': {},
        'technology': {},
        'line': {},
        'snapshot': {'dtype': 'int'},
        'period': {'dtype': 'int'},
    },
    'lookups': {
        'gen_bus': {'columns': ['generator', 'bus'], 'key': 'generator'},
        'gen_bt': {'columns': ['generator', 'bus', 'technology'], 'key': 'generator'},
        'zone_of': {'columns': ['generator', 'period', 'zone'], 'key': ['generator', 'period']},
        'ends': {'columns': {'line': 'line', 'bus0': 'bus', 'bus1': 'bus'}, 'key': 'line'},
        'connection': {'columns': ['generator', 'bus']},
    },
    'parameters': {
        'cost': {'dims': ['generator']},
        'demand': {'dims': ['zone', 'period']},
        'price': {'dims': ['zone', 'period']},
        'bus_price': {'dims': ['bus', 'period']},
        'load': {'dims': ['bus', 'period']},
        'weight': {'dims': ['snapshot', 'bus']},
        'tech_cap': {'dims': ['bus', 'technology']},
    },
    'variables': {
        'p': {'foreach': ['generator', 'period'], 'bounds': {'lower': 0}},
        'f': {'foreach': ['line', 'period']},
        'q': {'foreach': ['generator', 'snapshot']},
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}

# id, the claim the probe stands for, expectation, the constraint block
PROBES: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        'A1-roles',
        "a lookup's columns: may carry one dimension twice, given roles",
        'loads',
        {'no_loop': {'foreach': ['line', 'period'], 'where': 'ends.bus0 != ends.bus1', 'expression': 'f <= 10'}},
    ),
    (
        'A2-group-pair',
        "a partition's group may carry one dimension twice: lines between the same two buses are neighbours",
        'loads',
        {
            'parallel': {
                'foreach': ['line', 'period'],
                'expression': 'f <= shift(f, over=line, offset=1, edge=0, by=ends)',
            }
        },
    ),
    (
        'A3-frame-pair',
        'a frame may NOT carry one dimension twice',
        'refused',
        {'arc': {'foreach': ['bus', 'bus'], 'expression': 'load >= 0'}},
    ),
    (
        'A4-produce-pair',
        'a walk may NOT produce one dimension twice',
        'refused',
        {'both_ends': {'foreach': ['bus', 'period'], 'expression': 'sum(f, by=ends, produce=[bus0, bus1]) <= load'}},
    ),
    (
        'B1-at-keyless',
        'at() refuses a keyless relation — the read GAMS writes as a sum',
        'refused',
        {
            'revenue': {
                'foreach': ['generator', 'period'],
                'expression': 'at(bus_price, by=connection, produce=generator) * p <= 1000',
            }
        },
    ),
    (
        'B2-at-keyed',
        'at() reads through a keyed lookup',
        'loads',
        {
            'revenue': {
                'foreach': ['generator', 'period'],
                'expression': 'at(bus_price, by=gen_bus, produce=generator) * p <= 1000',
            }
        },
    ),
    (
        'B3-partition-keyless',
        'a partition refuses a keyless relation: no key, no group',
        'refused',
        {
            'neighbour': {
                'foreach': ['generator', 'period'],
                'expression': 'p <= shift(p, over=generator, offset=1, edge=0, by=connection)',
            }
        },
    ),
    (
        'B1b-at-keyless-named',
        'at() refuses a keyless relation even when the call names both ends',
        'refused',
        {
            'revenue': {
                'foreach': ['generator', 'period'],
                'expression': 'at(bus_price, by=connection, consume=bus, produce=generator) * p <= 1000',
            }
        },
    ),
    (
        'B4-sum-keyless',
        'sum() walks a keyless relation, with both ends named',
        'loads',
        {
            'reachable': {
                'foreach': ['bus', 'period'],
                'expression': 'sum(p, by=connection, consume=generator, produce=bus) <= 2 * load',
            }
        },
    ),
    (
        'C1-within',
        'a group-relative shift: the previous generator on the same bus',
        'loads',
        {
            'within_bus': {
                'foreach': ['generator', 'period'],
                'expression': 'p <= shift(p, over=generator, offset=1, edge=0, by=gen_bt, within=bus)',
            }
        },
    ),
    (
        'C2-position',
        'a group-relative position: the first period of each generator-and-zone group',
        'loads',
        {
            'first_in_zone': {
                'foreach': ['generator', 'period'],
                'where': 'position(period, by=zone_of) == 0',
                'expression': 'p <= 10',
            }
        },
    ),
    (
        'D1-masked-sum',
        'a masked sum: the produced dimension is already carried, so it is joined on',
        'loads',
        {'masked': {'foreach': ['snapshot', 'bus'], 'expression': 'sum(weight * q, by=gen_bus) <= weight'}},
    ),
    (
        'D2-consume-two',
        'two key columns consumed at once',
        'loads',
        {'total': {'foreach': ['zone'], 'expression': 'sum(p, by=zone_of, consume=[generator, period]) <= 100'}},
    ),
    (
        'D3-produce-two',
        'one table landed on a product of two value columns, in one join',
        'loads',
        {
            'by_bus_and_tech': {
                'foreach': ['bus', 'technology', 'period'],
                'expression': 'sum(p, by=gen_bt, produce=[bus, technology]) <= tech_cap',
            }
        },
    ),
    (
        'D4-other-key',
        'the same table walked from its other key column',
        'loads',
        {'history': {'foreach': ['generator', 'zone'], 'expression': 'sum(p, by=zone_of, consume=period) <= 100'}},
    ),
]


def model_for(constraints: dict[str, Any]) -> dict[str, Any]:
    """A whole model: the shared base, plus this probe's constraints."""
    return {**BASE, 'constraints': constraints}


def run(probe: tuple[str, str, str, dict[str, Any]]) -> dict[str, Any]:
    """Load one probe, and report the frame it reached or the message that refused it."""
    pid, claim, expected, constraints = probe
    model = model_for(constraints)
    row: dict[str, Any] = {'id': pid, 'claim': claim, 'expected': expected}
    try:
        program = to_program(model)
    except LanguageError as exc:
        row['actual'] = 'refused'
        row['message'] = ' '.join(str(exc).split())
    else:
        row['actual'] = 'loads'
        row['frames'] = {n: list(c.dims) for n, c in program.constraints.items()}
        row['math'] = to_markdown(model, legend=False, numbered=False).strip()
    row['verdict'] = 'as claimed' if row['actual'] == expected else 'CONTRADICTED'
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-yaml', type=Path, help='write each probe as a standalone model file')
    parser.add_argument('--json', type=Path, help='write the rows as JSON')
    args = parser.parse_args()

    rows = [run(p) for p in PROBES]
    if args.write_yaml:
        args.write_yaml.mkdir(parents=True, exist_ok=True)
        for pid, _claim, _expected, constraints in PROBES:
            (args.write_yaml / f'{pid}.yaml').write_text(yaml.safe_dump(model_for(constraints), sort_keys=False))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2))

    for row in rows:
        print(f'{row["id"]:<22} {row["actual"]:<8} {row["verdict"]}')
        print(f'  claim: {row["claim"]}')
        if 'frames' in row:
            print(f'  frame: {row["frames"]}')
        if 'message' in row:
            print(f'  message: {row["message"]}')
        print()
    contradicted = [r['id'] for r in rows if r['verdict'] == 'CONTRADICTED']
    print(f'{len(rows) - len(contradicted)}/{len(rows)} as claimed')
    if contradicted:
        print(f'contradicted: {", ".join(contradicted)}')
    return 1 if contradicted else 0


if __name__ == '__main__':
    sys.exit(main())
