# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The program written as JSON, and read back as the same program.

The claim under test is exactness, not resemblance: a consumer in another
language is trusting this document instead of the language, so a field that
came back subtly different would be a model that means something else, with
nothing to compare it against.

`every_program_node.yaml` is the fixture that makes the coverage argument, and
it is not this module's to maintain — `tests/test_program_nodes.py` already
refuses a node no file lowers to, so a node added to the program lands in that
fixture or the suite goes red. Round-tripping it therefore covers every node
by construction rather than by a list somebody keeps in step.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import math_spec as ms
from math_spec import LanguageError, from_json, to_json
from math_spec.serialisation import WIRE_VERSION

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'
EXAMPLES = sorted((Path(__file__).resolve().parent.parent / 'examples').glob('*.yaml'))


def test_every_node_a_program_can_carry_survives_the_round_trip():
    assert from_json(to_json(FIXTURE)) == ms.to_program(FIXTURE), (
        'the fixture the node fence maintains comes back as the program it went in as'
    )


@pytest.mark.parametrize('model', EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_a_shipped_model_survives_the_round_trip(model: Path):
    assert from_json(to_json(model)) == ms.to_program(model), f'{model.stem} comes back as itself'


@pytest.mark.parametrize('model', EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_a_document_is_strict_json(model: Path):
    """`Infinity` and `NaN` are Python's extension and not JSON, and a reader
    whose parser is strict stops at one. An unbounded variable's bound is
    `-inf`, so this is every model with a one-sided bound rather than an
    exotic case."""
    text = to_json(model)
    assert 'Infinity' not in text and 'NaN' not in text, 'nothing a conforming reader refuses is written'
    json.loads(text)


def test_an_infinite_bound_is_written_and_read_as_one():
    """The landmine the strictness above is protecting: a variable with no
    upper bound carries `inf`, and it has to come back as `inf` rather than as
    a string or a null."""
    program = ms.to_program(
        {
            'dimensions': {'g': {}},
            'variables': {'x': {'foreach': ['g']}},
            'objective': {'sense': 'minimize', 'expression': 'sum(x)'},
        }
    )
    assert math.isinf(from_json(to_json(program)).variables['x'].upper.value), 'the bound is the infinity it was'


def test_a_program_is_what_the_verb_takes_as_well_as_what_it_gives():
    """Every other verb takes `str | Path | dict | Spec`, and this one takes a
    `Program` too — so a caller who already lowered does not lower twice."""
    program = ms.to_program(FIXTURE)
    assert to_json(program) == to_json(FIXTURE), 'a lowered program and the file it came from write one document'


def test_a_document_from_a_wire_version_this_release_does_not_know_is_refused():
    """The decision a format has to make before it has readers: what happens to
    a document written by a newer release. It is refused by number, never
    guessed at."""
    document = json.loads(to_json(FIXTURE))
    document['version'] = WIRE_VERSION + 1
    with pytest.raises(LanguageError) as exc:
        from_json(json.dumps(document))
    assert str(WIRE_VERSION + 1) in str(exc.value), 'the message names the version the document claims'
    assert 'read it with the release that wrote it' in str(exc.value), 'and what to do instead'


def test_a_tag_naming_no_node_is_refused_with_the_near_miss():
    """Reading is closed: a tag names a class in the registry or the document
    is refused. Nothing is imported or constructed by name from the text."""
    document = json.loads(to_json(FIXTURE))
    document['program']['objective']['expression']['$'] = 'Sumk'
    with pytest.raises(LanguageError) as exc:
        from_json(json.dumps(document))
    assert 'Sumk' in str(exc.value), 'the message names the tag the document used'
    assert 'Sum' in str(exc.value), 'and the node it was probably reaching for'
