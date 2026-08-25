# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the typesetter tests render, and the helpers that read the result."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.typesetting import FORMATS
from tests.fixtures import OPERATOR_PROBES

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec.typesetting.format import Format


LATEX, TYPST = FORMATS['latex'], FORMATS['typst']
EVERY_FORMAT = pytest.mark.parametrize('fmt', list(FORMATS.values()), ids=list(FORMATS))

DISPATCH = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot']},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {
        'power_balance': {
            'foreach': ['snapshot'],
            'expression': 'sum(p, over=generator) == load',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


#: An objective whose two terms carry different dims — dispatch over (t, g)
#: and a capital cost over (g) alone. No constraints, so every summation in the
#: rendered document is one the objective asked for.
MIXED = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {'cost': {'dims': ['generator']}, 'capex': {'dims': ['generator']}},
    'variables': {
        'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0}},
        'p_nom': {'foreach': ['generator'], 'bounds': {'lower': 0}},
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost) + sum(p_nom * capex)'},
}


def summations(text: str, fmt: Format) -> int:
    """How many summations *text* opens, derived from the format's own spelling."""
    return text.count(fmt.summation('DOMAIN', 'BODY').split('DOMAIN')[0])


def over_generators(fmt: Format) -> str:
    """``sum over g in G``, opened but not filled — what the capital term is under."""
    return fmt.summation(f'g {fmt.operators["in"]} {fmt.script("G")}', '').rstrip()


SYMBOLS = {
    'notation': 'latex',
    'dimensions': {'generator': {'index': 'u', 'set': r'\mathcal{U}'}},
    'names': {'p': r'\pi', 'marginal_cost': r'c^{\mathrm{marg}}'},
}

TYPST_SYMBOLS = {
    'notation': 'typst',
    'dimensions': {'generator': {'index': 'u', 'set': 'cal(U)'}},
    'names': {'p': 'pi', 'p_max': 'bar(p)'},
}


def probe(name: str) -> Path:
    """One operator probe by stem, wherever the suite is run from."""
    return next(p for p in OPERATOR_PROBES if p.stem == name)


#: Two frames over generators, a lookup onto buses and a boolean mask — what the
#: scope and bracketing cases are written against.
BUSES = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'lookups': {'bus_of': {'over': 'generator', 'into': 'bus'}},
    'parameters': {'load': {'dims': ['snapshot']}, 'k': {'dims': []}, 'flag': {'dims': ['snapshot'], 'dtype': 'bool'}},
    'variables': {'p': {'foreach': ['snapshot', 'generator']}, 'q': {'foreach': ['snapshot', 'generator']}},
}
