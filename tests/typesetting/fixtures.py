# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The formats under test, and the one symbol table more than one module renders through."""

from __future__ import annotations

import pytest

from math_spec.typesetting import FORMATS

LATEX, TYPST = FORMATS['latex'], FORMATS['typst']
EVERY_FORMAT = pytest.mark.parametrize('fmt', list(FORMATS.values()), ids=list(FORMATS))

TYPST_SYMBOLS = {
    'notation': 'typst',
    'dimensions': {'generator': {'index': 'u', 'set': 'cal(U)'}},
    'names': {'p': 'pi', 'p_max': 'bar(p)'},
}
