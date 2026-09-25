# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Regenerate the committed golden output.

pixi run python -m tests.typesetting.golden
"""

from __future__ import annotations

from mathspec import to_spec
from mathspec.typesetting import FORMATS, typeset
from tests.typesetting.golden import MODEL, path_for


def main() -> int:
    model = to_spec(MODEL)
    for name in FORMATS:
        path = path_for(name)
        path.write_text(typeset(model, name, standalone=True))
        print(f'wrote {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
