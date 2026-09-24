# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The front door: a model definition read and validated into a :class:`~math_spec.model.Spec`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from math_spec._yaml import read_model
from math_spec.errors import SchemaError
from math_spec.model import Spec

if TYPE_CHECKING:
    from pathlib import Path


def to_spec(model: str | Path | Mapping[str, object] | Spec) -> Spec:
    """Load and validate a model definition — the language's front door.

    Everything decidable without data is decided here: schema shape, every
    expression and where string, every macro template, and every declaration a
    formulation emits.

    Args:
        model: A YAML path — a :class:`~pathlib.Path`, or a ``str`` with no
            newline in it — the YAML text itself as a ``str`` with one, a
            mapping, or a loaded :class:`Spec`.

    Returns:
        The schema *as the file declares it*, ``piecewise:`` intact.

    Raises:
        LanguageError: Anything the language does not accept, a text that is
            not a mapping of sections included.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    if isinstance(model, (list, tuple)):
        msg = 'a model is one file, one dict or one Spec, never a list of them; merge the declarations into one dict.'
        raise SchemaError(msg)
    if isinstance(model, Spec):
        return model
    return Spec.model_validate(model if isinstance(model, Mapping) else read_model(model))
