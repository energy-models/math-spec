# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Every PyPSA reference script has a recorded solve, taken with the versions it pins.

The scripts under ``examples/references/pypsa/`` run out of band — PyPSA is
not a dependency of this project — so what the suite can hold them to is the
bookkeeping: one record per script, stamped by the pypsa the script pins, with
a finite objective. The page blocks they feed are held current by
``tests/test_docs.py`` through ``tools.gallery``.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

REFERENCES = Path(__file__).resolve().parent.parent / 'examples' / 'references' / 'pypsa'
SCRIPTS = sorted(REFERENCES.glob('rung*.py'))
RECORDED: dict[str, dict] = json.loads((REFERENCES / 'references.json').read_text())


def test_every_reference_script_has_a_recorded_solve():
    assert {script.stem for script in SCRIPTS} == set(RECORDED), (
        'a reference script without a record, or a record without a script — run the scripts, or delete the orphan'
    )


@pytest.mark.parametrize('script', SCRIPTS, ids=[script.stem for script in SCRIPTS])
def test_the_record_is_from_the_pinned_pypsa(script: Path):
    pinned = re.search(r'"pypsa==([^"]+)"', script.read_text())
    assert pinned is not None, 'a reference script pins pypsa in its PEP 723 block'
    assert RECORDED[script.stem]['pypsa'] == pinned.group(1), (
        'the recorded solve is from another pypsa than the script pins — re-run it in the pinned environment'
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_the_recorded_solve_is_usable_as_an_oracle(stem: str):
    recorded = RECORDED[stem]
    assert math.isfinite(recorded['objective']), 'an oracle needs a finite objective'
    assert recorded['rows'], 'an oracle needs the row counts a parity gate would compare'
