"""Regenerate the committed golden output.

    uv run python -m tests.typeset.golden

Then **read the diff**. That is the review: a golden file is only worth having
if a change to it is looked at, and the reason the output is generated rather
than hand-written is that the diff is where human judgement belongs — at
review time, not at authoring time.
"""

from __future__ import annotations

from math_spec.typeset import FORMATS, typeset
from tests.typeset.golden import MODEL, path_for


def main() -> int:
    for name, fmt in FORMATS.items():
        path = path_for(name)
        path.write_text(typeset(MODEL, fmt, standalone=True))
        print(f'wrote {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
