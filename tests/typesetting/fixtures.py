# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The formats under test, and the one symbol table more than one module renders through."""

from __future__ import annotations

import pytest

from mathspec.typesetting import FORMATS

LATEX = FORMATS['latex']
#: Each format by the name a renderer takes and the object that spells it.
EVERY_FORMAT = pytest.mark.parametrize(('name', 'fmt'), list(FORMATS.items()), ids=list(FORMATS))

TYPST_SYMBOLS = {
    'typst': {
        'dimensions': {'generator': {'index': 'u', 'set': 'cal(U)'}},
        'names': {'p': 'pi', 'p_max': 'bar(p)'},
    }
}
