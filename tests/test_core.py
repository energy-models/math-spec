# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT


def test_hard():
    import math_spec  # noqa

    # this is just a demo that pytest can produce good error messages just by
    # parsing assert statements
    assert {"a": 1, "b": 2} == {"a": 1, "b": 2}
