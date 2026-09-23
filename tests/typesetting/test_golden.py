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

from math_spec.operators import BUILTIN_NAMES
from math_spec.program import Dual, Expression, Join, Named, Predicate, Sum, Translate, WindowSum
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
    actual = typeset(golden.MODEL, name, standalone=True)
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


def test_the_golden_model_asks_for_every_operator_the_vocabulary_spells(monkeypatch: pytest.MonkeyPatch):
    """The fixture reaches every symbol, so the committed output shows them all.

    A symbol a format spells and no model prints is either a construct the
    fixture is missing or vocabulary nothing needs. The line census below is
    the stronger claim; this one runs without `coverage` installed, and its
    failure names the operator rather than a line.

    The one exemption is derived rather than listed: a model declares one
    objective sense, so the other one cannot be asked for from here.
    """
    recorder = _Recorded(LATEX)
    monkeypatch.setitem(FORMATS, 'latex', recorder)
    typeset(golden.MODEL, 'latex', standalone=True)
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
    """Every resolved tree the walk is handed for the golden model.

    The model as the file declares it, because that is what the walk prints: a
    curve's links are trees of its own, and the rows it stands for are not
    printed at all.
    """
    resolved = to_spec(golden.MODEL).resolved
    assert resolved.objective is not None
    yield resolved.objective.expression
    for constraint in resolved.constraints.values():
        yield constraint.lhs
        yield constraint.rhs
        if constraint.where is not None:
            yield constraint.where.root
    for mask in resolved.variables.values():
        if mask is not None:
            yield mask.root
    for assumption in resolved.assumptions.values():
        yield assumption.predicate.root
        if assumption.where is not None:
            yield assumption.where.root
    yield from resolved.expressions.values()
    for links in resolved.piecewise.values():
        yield from links


#: A dataclass the walk steps *through* rather than renders: a region has no
#: branch of its own — its ``when`` and ``value`` do — the columns a join
#: names and the relation it reads are the facts a node carries rather than
#: nodes, and a ``Mask`` is the wrapper a leaf carries a predicate in. None is a
#: member of any node union, so they are subtracted from what the tree walk
#: finds rather than added to what the vocabulary declares.
CARRIERS = {'Region', 'JoinColumns', 'Mask', 'Partition', 'RelationDeclaration'}


def test_the_golden_model_carries_every_node_kind_the_walk_renders():
    """A construct added to the language is a case this fixture owes output for.

    Two constructs can share every symbol and still render differently —
    ``at`` and ``sum(by=)`` both print a coordinate map — so this counts node
    kinds rather than symbols. Like the operator census it runs without
    `coverage` installed, and its failure names the construct rather than a line.
    """
    kinds = {type(node).__name__ for tree in _rendered_trees() for node in _nodes(tree)} - CARRIERS
    declared = {node.__name__ for node in (*get_args(Predicate), *get_args(Expression), Named)}
    assert kinds == declared, (
        f'tests/typesetting/golden/model.yaml reaches {sorted(kinds - declared)} and misses '
        f'{sorted(declared - kinds)}. Every node the walk renders needs a case here, '
        f'or its arm ships output nobody has read.'
    )


def test_the_golden_model_calls_every_operator_in_the_language():
    """``BUILTINS`` is the closed set, so a new operator lands with its case here.

    Each operator resolves to the node it is, so the census counts the nodes
    by the verb the file writes them with.
    """
    verbs = {Sum: 'sum', Translate: 'shift', WindowSum: 'sum_back', Dual: 'dual'}
    nodes = [node for tree in _rendered_trees() for node in _nodes(tree)]
    calls = {verb for node in nodes for kind, verb in verbs.items() if isinstance(node, kind)}
    calls |= {'at' for node in nodes if isinstance(node, Join) and not node.columns.axes}
    assert calls == BUILTIN_NAMES, (
        f'tests/typesetting/golden/model.yaml never calls {sorted(BUILTIN_NAMES - calls)}. '
        f'An operator with no case here renders untested.'
    )


#: What the fixture cannot reach, by the source text of the line. A bare
#: ``Cases`` stands under the ``Named`` node resolution builds for its entry
#: and nowhere else, so the arm that would print one in place is the type's
#: closure rather than a case. The absent objective is the arm a *different*
#: model takes — a file declares at most one — and
#: `test_a_model_with_no_objective_prints_the_rest` covers it.
UNREACHABLE = {
    'return self.format.cases(self._arms(node, ctx)), _ATOM',
    'assert_never(node)',
    'assert_never(check)',
    'if block is None:',
    'return []',
}


def test_the_golden_model_reaches_every_line_of_the_walk(tmp_path: Path):
    """The strongest form of what the fixture claims about itself: the arm itself
    is counted, where the two censuses above see neither a width taken from a
    parameter nor an integer variable with no bounds.

    The render runs in a subprocess because the walk is imported long before
    any test starts, and a measurement that begins after the import counts
    every ``def`` and ``import`` line as unreached.
    """
    coverage = pytest.importorskip(
        'coverage', reason='the bare-install job has no dev tools; the guard runs wherever they are'
    )
    data = tmp_path / 'walk.coverage'
    render = tmp_path / 'render.py'
    render.write_text(
        'from math_spec import to_latex, to_spec, typeset_declaration\n'
        f'model = {str(golden.MODEL)!r}\n'
        'to_latex(model)\n'
        'to_latex(model, inline_expressions=True)\n'
        'spec = to_spec(model)\n'
        'for name in (*spec.expressions, *spec.constraints, *spec.assumptions, *spec.piecewise, *spec.variables):\n'
        "    typeset_declaration(model, name, 'latex')\n"
        'to_latex(spec.expand())\n'
    )
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
        'variables': {'x': {'dims': ['t'], 'bounds': {'lower': 0}}},
        'constraints': {'cap': {'dims': ['t'], 'expression': 'x <= 1'}},
    }
    rendered = to_latex(model)
    assert 'Objective' not in rendered, 'no objective was declared, so no section says one was'
    assert 'Subject to' in rendered
