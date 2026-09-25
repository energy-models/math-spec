# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""`docs/several-files.md` shows what each step prints, and each step prints that.

The page writes its files as YAML blocks with a title, checks some of them from
a shell, and runs Python blocks one after another. A text block or a rendered
output right after a step is what that step prints; a check with none after it
prints nothing.
"""

from __future__ import annotations

import contextlib
import io
import re
import textwrap
from pathlib import Path

import pytest

from mathspec import LanguageError
from mathspec.__main__ import main

PAGE = Path(__file__).resolve().parent.parent / 'docs' / 'several-files.md'
TEXT = PAGE.read_text()

#: A fenced block at the start of a line, with its language and its title.
FENCE = re.compile(r'^```(\w+)(?: title="([^"]+)")?\n(.*?)^```$', re.MULTILINE | re.DOTALL)
#: A rendered output: an admonition whose indented body is what the step printed.
RENDERED = re.compile(r'^!!! example "Rendered output"\n\n((?:    .*\n|\n)+)', re.MULTILINE)


def _steps() -> list[tuple[str, str | None, str]]:
    """Every fenced block and rendered output on the page, in page order, as kind, title and body."""
    found = [(m.start(), m.group(1), m.group(2), m.group(3)) for m in FENCE.finditer(TEXT)]
    found += [
        (m.start(), 'rendered', None, textwrap.dedent(m.group(1)).strip() + '\n') for m in RENDERED.finditer(TEXT)
    ]
    return [(kind, title, body) for _, kind, title, body in sorted(found)]


STEPS = _steps()
FILES = {title: body for kind, title, body in STEPS if kind == 'yaml' and title}


@pytest.fixture
def folder(tmp_path, monkeypatch):
    for name, body in FILES.items():
        (tmp_path / name).write_text(body)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _output_after(index: int) -> str | None:
    """What the page says step *index* prints: the text or rendered output right after it, or None."""
    if index + 1 < len(STEPS) and STEPS[index + 1][0] in ('text', 'rendered'):
        return STEPS[index + 1][2]
    return None


def test_the_page_writes_the_files_it_merges():
    assert sorted(FILES) == ['emissions.yaml', 'generators.yaml', 'imports.yaml', 'loads.yaml', 'network.yaml']


@pytest.mark.parametrize(
    'index', [i for i, (kind, _, body) in enumerate(STEPS) if kind == 'bash' and 'mathspec check' in body]
)
def test_a_check_prints_what_the_page_shows(folder, index):
    (argv,) = [line.split()[4:] for line in STEPS[index][2].splitlines() if 'mathspec check' in line]
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        status = main(['check', *argv])
    assert status == 0, 'every check on the page accepts its file'
    assert printed.getvalue().strip() == (_output_after(index) or '').strip()


def test_every_python_step_prints_what_the_page_shows(folder):
    """The steps share one namespace, as a reader running them in order does."""
    namespace: dict[str, object] = {}
    ran = 0
    for index, (kind, _, body) in enumerate(STEPS):
        if kind != 'python':
            continue
        expected = _output_after(index)
        printed = io.StringIO()
        try:
            with contextlib.redirect_stdout(printed):
                exec(body, namespace)
        except LanguageError as e:
            assert expected is not None and str(e).strip() == expected.strip(), f'step {index} refused otherwise'
        else:
            assert printed.getvalue().strip() == (expected or '').strip(), f'step {index} printed otherwise'
        ran += 1
    assert ran == 5, 'every Python block on the page ran'
