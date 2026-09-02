# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The golden document: the one test that notices a change nobody pinned."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator, Mapping
from dataclasses import is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args

import pytest

from math_spec.expression_parser import ArithmeticNode, ComparisonNode, FunctionCallNode
from math_spec.operators import BUILTIN_NAMES
from math_spec.program import WhereNode
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.typesetting import FORMATS, to_latex, typeset, walk
from math_spec.typesetting.format import OPERATOR_NAMES
from math_spec.validation import to_spec
from tests.typesetting import golden
from tests.typesetting.fixtures import LATEX

if TYPE_CHECKING:
    from math_spec.typesetting.format import Format


@pytest.mark.parametrize('name', list(FORMATS), ids=list(FORMATS))
def test_the_output_matches_the_committed_golden_file(name: str):
    """One model, every format, byte for byte.

    Fragment assertions pin the constructs someone thought to pin, and survive
    anything leaving those substrings intact — a stray prefix, a lost space, a
    changed separator. Perturbing `TypstFormat.summation` to emit `~sum_(...)`
    failed *no test* before this existed, because every Typst assertion was a
    substring check and a `~` compiles fine.

    The same trade `examples/walkthrough.out` makes: the committed file is the
    output, so a format that starts saying something different shows up as a
    diff instead of as nothing at all.
    """
    expected = golden.path_for(name)
    actual = typeset(golden.MODEL, FORMATS[name], standalone=True)
    assert actual == expected.read_text(), (
        f'tests/typesetting/golden/{expected.name} is stale.\n'
        f'If the change was intended: `pixi run python -m tests.typesetting.golden`, then read the diff.'
    )


class _Recorded:
    """*fmt*, spelling exactly as it does, remembering what it was asked to spell.

    The walk reaches every operator through ``format.operators[name]``, so a
    recording mapping in that one place is the whole census — and it is a
    census of what the *walk asked for*, not of what appears in the output,
    where ``min`` is a substring of a parameter called ``min_up`` and a symbol
    that never rendered would pass.
    """

    def __init__(self, fmt: Format) -> None:
        self._fmt = fmt
        self.asked: set[str] = set()
        self.operators = _Asked(fmt.operators, self.asked)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fmt, name)


class _Asked(Mapping):
    def __init__(self, operators: Mapping[str, str], asked: set[str]) -> None:
        self._operators, self._asked = operators, asked

    def __getitem__(self, key: str) -> str:
        self._asked.add(key)
        return self._operators[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._operators)

    def __len__(self) -> int:
        return len(self._operators)


def test_the_golden_model_asks_for_every_operator_the_vocabulary_spells():
    """The fixture reaches every symbol, so the committed output shows them all.

    Without this the fixture is only exhaustive on the day someone read it:
    ``sum_back``, the three ``where`` predicates over lookups and both
    constant masks were all in the language and in none of the golden output,
    and nothing failed. A symbol a format spells and no model prints is either
    a construct the fixture is missing or vocabulary nothing needs, and both
    are worth being told about.

    The one exemption is derived rather than listed: a model declares one
    objective sense, so the other one cannot be asked for from here.
    """
    recorder = _Recorded(LATEX)
    typeset(golden.MODEL, recorder, standalone=True)
    sense = to_spec(golden.MODEL).objective.sense
    unreachable = {'minimize', 'maximize'} - {sense}
    assert recorder.asked == OPERATOR_NAMES - unreachable, (
        f'tests/typesetting/golden/model.yaml no longer prints every operator: '
        f'{sorted(OPERATOR_NAMES - unreachable - recorder.asked)} unrendered, '
        f'{sorted(recorder.asked - OPERATOR_NAMES)} unspelled. '
        f'Add the construct that prints it, or drop the spelling.'
    )


def _nodes(tree: object) -> Iterator[object]:
    """Every dataclass node in *tree*, the root first, through fields holding one, a tuple or a mapping of them."""
    yield tree
    for value in vars(tree).values():
        for child in value.values() if isinstance(value, Mapping) else value if isinstance(value, tuple) else [value]:
            if is_dataclass(child):
                yield from _nodes(child)


def _rendered_trees() -> Iterator[object]:
    """Every resolved tree the walk is handed for the golden model."""
    schema = to_spec(golden.MODEL)
    namespace = Namespace.of(schema)
    yield expression_of(schema.objective.expression, schema, namespace, 'the objective')
    for name, block in schema.constraints.items():
        yield expression_of(block.expression, schema, namespace, f'constraint {name!r}')
        if (mask := where_of(block.where, namespace, f'constraint {name!r}')) is not None:
            yield mask.root
    for name, block in schema.variables.items():
        if (mask := where_of(block.where, namespace, f'variable {name!r}', self_variable=name)) is not None:
            yield mask.root


#: What resolution never hands the walk: the three nodes it types away, and the
#: three an expression only carries before names are resolved. The walk raises on
#: each rather than rendering it, so a fixture reaching one would be a bug in
#: resolution rather than a case worth committing output for.
UNRESOLVED = {
    'UnresolvedNameNode',
    'UnresolvedComparisonNode',
    'UnresolvedPositionNode',
    'NameNode',
    'NameListNode',
    'KeywordNode',
}

#: A dataclass the walk steps *through* rather than renders: an arm has no
#: branch of its own — its ``when`` and ``value`` do. Not a member of any node
#: union, so it is subtracted from what the tree walk finds rather than added
#: to what the vocabulary declares.
CARRIERS = {'CaseArm'}


def test_the_golden_model_carries_every_node_kind_the_walk_renders():
    """A construct added to the language is a case this fixture owes output for.

    The operator census above is about the *symbols*; this is about the
    *branches*. Two constructs can share every symbol and still render
    differently — ``at`` and ``sum(by=)`` both print a coordinate map — so a
    walk arm no fixture reaches is one whose output nobody has ever read.
    """
    kinds = {type(node).__name__ for tree in _rendered_trees() for node in _nodes(tree)} - CARRIERS
    declared = {node.__name__ for node in (*get_args(WhereNode), *get_args(ArithmeticNode), ComparisonNode)}
    assert kinds == declared - UNRESOLVED, (
        f'tests/typesetting/golden/model.yaml reaches {sorted(kinds - declared)} and misses '
        f'{sorted(declared - UNRESOLVED - kinds)}. Every node the walk renders needs a case here, '
        f'or its arm ships output nobody has read.'
    )


def test_the_golden_model_calls_every_operator_in_the_language():
    """``BUILTINS`` is the closed set, so a new operator lands with its case here."""
    calls = {node.name for tree in _rendered_trees() for node in _nodes(tree) if isinstance(node, FunctionCallNode)}
    assert calls == BUILTIN_NAMES, (
        f'tests/typesetting/golden/model.yaml never calls {sorted(BUILTIN_NAMES - calls)}. '
        f'An operator with no case here renders untested.'
    )


#: What the fixture cannot reach, by the source text of the line, in two
#: groups. The **guards** — every line of the two ``resolve … first`` arms and
#: the one asserting a constraint is a comparison — are what the walk raises
#: when resolution hands it something it types away, so a model reaching one is
#: a bug upstream rather than a case worth committing output for. The
#: **absent objective** is the arm a *different* model takes: a file declares
#: at most one, so a fixture that has one cannot also be a fixture that has
#: none, and `test_a_model_with_no_objective_prints_the_rest` covers it instead.
UNREACHABLE = {
    'if isinstance(node, UnresolvedNode | KwargNode):',
    "msg = f'{type(node).__name__} reached the typesetter; resolve the expression first.'",
    'if not isinstance(node, ComparisonNode):',
    "msg = f'{context}: expected a comparison, got {type(node).__name__}'",
    'raise AssertionError(msg)',
    'assert_never(node)',
    'if block is None:',
    'return []',
}


def test_the_golden_model_reaches_every_line_of_the_walk(tmp_path: Path):
    """The strongest form of what the fixture claims about itself.

    The two censuses above are about *symbols* and *node kinds*; nine of the
    fixture's cases differ from each other in neither. A width taken from a
    parameter rather than a number, a translation partitioned by a lookup, an
    integer variable with no bounds, a declaration with an empty ``foreach`` —
    each is an arm of the walk, each renders differently, and deleting any of
    them left both censuses green.

    So the arm itself is what gets counted. A branch added to the walk with no
    case here fails this the moment it lands, which is the point: output nobody
    has read is what a golden file is supposed to prevent.

    The render runs in a subprocess because the walk is imported long before
    any test starts, and a measurement that begins after the import counts
    every ``def`` and ``import`` line as unreached.
    """
    coverage = pytest.importorskip(
        'coverage', reason='the bare-install job has no dev tools; the guard runs wherever they are'
    )
    data = tmp_path / 'walk.coverage'
    render = tmp_path / 'render.py'
    render.write_text(f'from math_spec import to_latex\nto_latex({str(golden.MODEL)!r})\n')
    subprocess.run(
        [
            sys.executable,
            '-m',
            'coverage',
            'run',
            f'--data-file={data}',
            f'--source={Path(walk.__file__).parent}',
            str(render),
        ],
        check=True,
    )
    measured = coverage.Coverage(data_file=str(data))
    measured.load()
    _, _, missing, _ = measured.analysis(walk.__file__)
    source = Path(walk.__file__).read_text().splitlines()
    unread = {line: source[line - 1].strip() for line in missing if source[line - 1].strip() not in UNREACHABLE}
    assert not unread, (
        f'tests/typesetting/golden/model.yaml never renders {len(unread)} line(s) of the walk:\n'
        + '\n'.join(f'  {walk.__name__}:{line}  {text}' for line, text in sorted(unread.items()))
        + '\nAdd the case that reaches it, or say in UNREACHABLE why no model can.'
    )


def test_a_model_with_no_objective_prints_the_rest():
    """The one arm the fixture structurally cannot take. See :data:`UNREACHABLE`."""
    model = {
        'dimensions': {'t': {'dtype': 'int'}},
        'variables': {'x': {'foreach': ['t'], 'bounds': {'lower': 0}}},
        'constraints': {'cap': {'foreach': ['t'], 'expression': 'x <= 1'}},
    }
    rendered = to_latex(model)
    assert 'Objective' not in rendered
    assert 'Subject to' in rendered
