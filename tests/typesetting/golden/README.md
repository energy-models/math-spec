<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# Golden output

`model.yaml`, rendered in every format, committed and asserted byte for byte.
The model is synthetic on purpose: it reaches every rendering path, and
`tests/typesetting/test_golden.py` holds it to that — every operator a format
spells, every node kind the parsers produce, every line of `walk.py`.

Regenerate after an intended change, then **read the diff** — that is the
review:

    pixi run python -m tests.typesetting.golden
