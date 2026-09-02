# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Regenerate the committed golden output.

pixi run python -m tests.typesetting.golden
"""

from __future__ import annotations

from math_spec import to_spec
from math_spec.typesetting import FORMATS, typeset
from tests.typesetting.golden import MODEL, path_for


def main() -> int:
    model = to_spec(MODEL)
    for name, fmt in FORMATS.items():
        path = path_for(name)
        path.write_text(typeset(model, fmt, standalone=True))
        print(f'wrote {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
