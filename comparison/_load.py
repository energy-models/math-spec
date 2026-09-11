# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Load one model and report what the loader made of it, as JSON on stdout.

Run under a `PYTHONPATH` that points at one proposal's `src/`. The three
proposals define incompatible `lookups:` schemas, so each has to be loaded in an
interpreter of its own — which is why `verify.py` calls this file as a child
process rather than importing it.
"""

import json
import re
import sys
from pathlib import Path

from math_spec import to_markdown, to_program


def constraints_latex(md: str) -> dict[str, str]:
    """The math the typesetter printed, per constraint name, from Markdown output."""
    found: dict[str, str] = {}
    for name, body in re.findall(r'\*\*`([^`]+)`\*\*\n\n```math\n(.*?)\n```', md, re.DOTALL):
        found.setdefault(name, body.strip())
    return found


def legend_maps(md: str) -> list[str]:
    """The lookup declarations the legend printed, in first-seen order."""
    seen: list[str] = []
    for entry in re.findall(r'with \$`(.*?)`\$', md):
        if entry not in seen:
            seen.append(entry)
    return seen


def main() -> None:
    path = Path(sys.argv[1])
    try:
        program = to_program(path)
        markdown = to_markdown(path, legend=True, numbered=False)
    except Exception as e:  # every refusal is evidence, whatever class it arrives as
        print(json.dumps({'ok': False, 'error_type': type(e).__name__, 'error': str(e)}))
        return
    print(
        json.dumps(
            {
                'ok': True,
                'constraints': {n: list(c.dims) for n, c in program.constraints.items()},
                'latex': constraints_latex(markdown),
                'maps': legend_maps(markdown),
            }
        )
    )


if __name__ == '__main__':
    main()
