# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Several files into one model, before any of them is validated.

A component library is a fixed set of templates agreeing on a port and flow
convention, and wiring a specific system is rows in a connectivity table rather
than generated YAML. What that needs of the language is one function: take the
templates and hand back **one model**, so the whole thing is validated,
resolved and lowered exactly once, as a file is.

**A fragment is not a :class:`~math_spec.model.Spec`.** It is read as YAML and
merged unvalidated, so a template may name what a sibling declares — a shared
``bus``, the flow every component writes into — without being a model on its
own. Nothing here resolves a name or checks a dim: the merged mapping goes
through :func:`~math_spec.validation.to_spec` like any other, against one flat
namespace, and every rule the language has applies to it there and nowhere
else.

Two kinds of declaration, and the split is what merging *means*:

* ``dimensions`` and ``lookups`` are the **coordinate space**, which templates
  share on purpose. Declared twice and agreeing, they are one declaration;
  declared twice and disagreeing, the disagreement is the error.
* Everything else is the **math**, which a template owns. Declared twice it is
  a collision, whichever fragment wrote it second, because two templates
  claiming one name is the composition being wrong rather than the file.

Names are **not rewritten** here. Qualified names are their own question
(``#29``), and until they land a library keeps its templates apart by naming
them apart — which the collision error above is what enforces.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from math_spec._yaml import read_yaml
from math_spec.errors import LanguageError
from math_spec.model import Spec

if TYPE_CHECKING:
    from collections.abc import Mapping

#: The declarations that are the coordinate space rather than the math. Two
#: fragments may each declare one, and agreeing costs nothing — that agreement
#: is how a template says which axis it couples on.
SHARED_SECTIONS = ('dimensions', 'lookups')

#: The declarations a template owns. A second fragment declaring one of these
#: under a name already taken is refused, both fragments named.
OWNED_SECTIONS = ('parameters', 'variables', 'constraints', 'expressions', 'macros', 'piecewise', 'sos')

#: The sections whose plural key does not become the singular by dropping an
#: ``s``, for the noun a collision or a disagreement prints.
IRREGULAR = {'piecewise': 'piecewise curve', 'sos': 'special-ordered set'}


def merge(
    fragments: Mapping[str, str | Path | dict[str, Any] | Spec], description: str | None = None
) -> dict[str, Any]:
    """Compose *fragments* into one unvalidated model mapping.

    Args:
        fragments: What each fragment is called, to the fragment — the same
            ``str | Path | dict | Spec`` every other verb takes, a ``str``
            being a path as it is there. The name is what an error calls it,
            so it is the template's name rather than a path. Order is the
            order given, and the merged model's declarations keep it.
        description: What the *composed* model is. A fragment's own
            ``description`` is about the fragment, so it is not carried and not
            joined — the composition is a different thing from its parts and
            says so itself, or says nothing.

    Returns:
        One mapping, ready for :func:`~math_spec.validation.to_spec`. Nothing
        in it has been resolved, name-checked or lowered: merging decides what
        the declarations *are*, and the language decides whether they say
        anything.

    Raises:
        LanguageError: Two fragments declare one owned name; two fragments
            disagree about a shared declaration; two fragments pin different
            language versions; or the objectives disagree about ``sense``.
    """
    read = {name: _sections(fragment) for name, fragment in fragments.items()}
    merged: dict[str, Any] = {'version': _one_version(read)}
    if description is not None:
        merged['description'] = description

    for section in SHARED_SECTIONS:
        if block := _shared(read, section):
            merged[section] = block
    for section in OWNED_SECTIONS:
        if block := _owned(read, section):
            merged[section] = block
    if (objective := _objective(read)) is not None:
        merged['objective'] = objective
    return merged


def _sections(fragment: str | Path | dict[str, Any] | Spec) -> dict[str, Any]:
    """A fragment as the mapping it declares, whatever shape it arrived in.

    Deliberately not :func:`~math_spec.validation.to_spec`: a fragment naming
    what a sibling declares is not a model, and validating one here would
    refuse exactly the templates this function exists to compose.
    """
    if isinstance(fragment, Spec):
        return fragment.to_dict()
    if isinstance(fragment, dict):
        return fragment
    return read_yaml(Path(fragment))


def _one_version(read: Mapping[str, dict[str, Any]]) -> int:
    """The language version every fragment is written against.

    A fragment saying nothing is version 0 like any file, so a library pinning
    one and a template pinning none is the disagreement it looks like rather
    than a default quietly winning.
    """
    declared = {name: sections.get('version', 0) for name, sections in read.items()}
    if len(set(declared.values())) > 1:
        spelled = ', '.join(f"'{name}' says {version}" for name, version in sorted(declared.items()))
        raise LanguageError(
            f'the fragments are written against different language versions: {spelled}. '
            f'One model has one version, so write the same one in each — a fragment that '
            f'declares none is version 0.'
        )
    return next(iter(declared.values()), 0)


def _singular(section: str) -> str:
    """What one entry in *section* is called, ``sos`` and ``piecewise`` not being plurals."""
    return IRREGULAR.get(section, section[:-1])


def _shared(read: Mapping[str, dict[str, Any]], section: str) -> dict[str, Any]:
    """One ``dimensions`` or ``lookups`` block, agreeing fragments folded together."""
    merged: dict[str, Any] = {}
    author: dict[str, str] = {}
    for name, sections in read.items():
        for key, block in (sections.get(section) or {}).items():
            if key in merged and merged[key] != block:
                raise LanguageError(
                    f"fragments '{author[key]}' and '{name}' disagree about {_singular(section)} '{key}': "
                    f'{merged[key]!r} against {block!r}. A shared axis is shared because both '
                    f'fragments say the same thing about it — make the two declarations identical, '
                    f'or give one of them an axis of its own under a name of its own.'
                )
            merged.setdefault(key, block)
            author.setdefault(key, name)
    return merged


def _owned(read: Mapping[str, dict[str, Any]], section: str) -> dict[str, Any]:
    """One block of owned declarations, a name claimed twice being the error."""
    merged: dict[str, Any] = {}
    author: dict[str, str] = {}
    for name, sections in read.items():
        for key, block in (sections.get(section) or {}).items():
            if key in merged:
                raise LanguageError(
                    f"fragments '{author[key]}' and '{name}' both declare the {_singular(section)} '{key}'. "
                    f'Two of the same kind of thing are two rows of a dimension rather than two '
                    f'fragments: merge the template once, and let the data carry both. Different '
                    f'math under one spelling is a rename — call one of them something else.'
                )
            merged[key] = block
            author[key] = name
    return merged


def _objective(read: Mapping[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Every fragment's objective, summed, or ``None`` where none declares one.

    Summing is what composing costs: each template prices what it owns, and the
    system pays for all of it. The senses must agree because a sum of two
    objectives has one sense and nothing in the file says which — negating the
    minority would be this function deciding a model's meaning.
    """
    declared = {name: sections['objective'] for name, sections in read.items() if sections.get('objective') is not None}
    if not declared:
        return None
    senses = {name: objective.get('sense', 'minimize') for name, objective in declared.items()}
    if len(set(senses.values())) > 1:
        spelled = ', '.join(f"'{name}' {sense}s" for name, sense in sorted(senses.items()))
        raise LanguageError(
            f'the fragments disagree about which way the objective runs: {spelled}. '
            f'A composed model has one objective and one sense, so write every fragment '
            f'against the same one — negate the terms of the odd one out rather than its sense.'
        )
    expressions = [objective['expression'] for objective in declared.values()]
    return {'sense': next(iter(senses.values())), 'expression': _summed(expressions)}


def _summed(expressions: list[str]) -> str:
    """The terms as one expression, parenthesised only where there is a sum to protect.

    One fragment's objective is returned as it was written, which is what makes
    merging a single fragment give back that fragment: a wrapper nothing needs
    would leave the composition of one differing from the thing composed, and
    every nested merge would add another pair.
    """
    if len(expressions) == 1:
        return expressions[0]
    return ' + '.join(f'({term})' for term in expressions)
