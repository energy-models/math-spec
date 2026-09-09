<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# Golden output

This directory holds `model.yaml` rendered in every format. The output is
committed, and it is asserted byte for byte.

The model is synthetic on purpose, because it has to reach every rendering path.
`tests/typesetting/test_golden.py` holds it to that. It checks every operator
that a format spells, every node kind that the parsers produce, and every line
of `walk.py`.

After an intended change, regenerate the output and then **read the diff**. The
diff is the review:

    pixi run python -m tests.typesetting.golden
