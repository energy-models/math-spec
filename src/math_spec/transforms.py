# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rewriting a model into the one a decomposition solves.

A myopic pathway, a rolling horizon and a Benders subproblem share one move:
**a variable stops being a decision and becomes a number somebody else chose.**
The subproblem is the same model at a capacity someone picked; the myopic step
is the same model with what earlier periods already built. Written by hand that
is a second file to keep in step with the first, and the drift between them is
a bug nothing catches.

It is not every half of a decomposition. A Benders *master* is not the model
with the dispatch fixed — it is the model with the dispatch **gone**, which is
a different move and not this one. Fixing every variable a constraint names
leaves a row that decides nothing, and the language says so.

It reads like a rename and it is not, which is why it is here rather than four
lines in every driver. A fixed variable's *mask* becomes a claim about its
data, and its *domain* becomes a dtype — two decisions a driver would each make
differently, and one of them silently:

- A variable masked by ``where:`` has rows that do not exist. As a parameter
  those rows have no value, so it is ``coverage: masked``. The obvious
  rewrite leaves it ``total``, which claims every coordinate has a number and
  is the wrong answer that binds cleanly.
- A ``binary`` or ``integer`` variable becomes an ``int`` parameter, never a
  ``float`` one: the values are whole and a consumer reading the declaration
  is entitled to know it.

Bounds are dropped, and that is the one thing lost. They constrained a decision
this model no longer makes; whether the numbers supplied respect them is a
question about data, which this package does not have.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from math_spec.errors import did_you_mean
from math_spec.validation import to_spec

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec.model import Coverage, ParameterDtype, Spec

#: What a fixed variable's values are, by the domain it decided over. ``binary``
#: is ``int`` rather than ``bool``: a flag masks and a number multiplies, and a
#: fixed commitment is multiplied by.
_DTYPE_OF_DOMAIN: dict[str, ParameterDtype] = {'continuous': 'float', 'integer': 'int', 'binary': 'int'}


def fix(model: str | Path | dict[str, Any] | Spec, *names: str) -> Spec:
    """*model* with each variable in *names* turned into a parameter of the same name.

    Every expression naming one goes on reading, because the name does not
    move — which is what makes the rewrite mechanical. A myopic step fixes
    what earlier periods built, which is many at once, so the whole set is
    named in one call and validated once at the end of it.

    Args:
        model: Whatever every other verb takes.
        names: Variables the model declares. Naming none is the model itself.

    Returns:
        The model as a :class:`~math_spec.model.Spec`, revalidated — so a fix
        that made the model unsayable says so here rather than downstream.

    Raises:
        KeyError: One of *names* is not a variable, named with the near miss.
        LanguageError: The fixed model is not one the language accepts — a
            constraint every variable of which is now a number, a set over one
            of them, or a curve linking one.
    """
    spec = to_spec(model).to_dict()
    variables = spec.get('variables') or {}
    for name in names:
        if name not in variables:
            raise KeyError(f"unknown variable '{name}'. " + did_you_mean(name, list(variables)))
        spec.setdefault('parameters', {})[name] = _as_parameter(variables.pop(name))
    return to_spec(spec)


def _as_parameter(decided: dict[str, Any]) -> dict[str, Any]:
    """The parameter declaration a fixed variable becomes.

    The two translations that are decisions rather than copies are ``where:``
    into ``coverage:`` and ``domain:`` into ``dtype:``; the module docstring
    says why each is the one it is.
    """
    coverage: Coverage = 'masked' if decided.get('where') is not None else 'total'
    declaration: dict[str, Any] = {
        'dims': decided['foreach'],
        'dtype': _DTYPE_OF_DOMAIN[decided.get('domain', 'continuous')],
        'coverage': coverage,
    }
    if (description := decided.get('description')) is not None:
        declaration['description'] = description
    return declaration
