# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Several files into one model, before any of them is validated.

Two verbs, and they obey opposite laws. :func:`merge` composes **peers**: a
name two of them declare is a collision, and the order they are given in does
not matter. :func:`override` layers a **base and its patches**: a name the
patch declares is the point, and the order is the whole instruction. Neither
is a mode of the other — erroring on a shared name and letting the later one
win cannot both be true of one call.

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

**A patch is not a model either**, for the same reason a fragment is not: it is
read before validation, so it may carry ``null`` where a declaration would go
and name what only its base declares. That is what keeps the removal marker out
of every file a reviewer reads as a model — nothing in the schema gains a key,
and ``null`` never appears in a validated ``Spec``.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from math_spec._yaml import read_yaml
from math_spec.errors import LanguageError, did_you_mean
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

#: Every section a patch may touch, which is every section a model may declare.
#: A key outside them — ``version``, ``description``, ``objective`` — is a
#: single value the later file simply replaces.
SECTIONS = (*SHARED_SECTIONS, *OWNED_SECTIONS)


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


def override(
    base: str | Path | dict[str, Any] | Spec,
    patches: Mapping[str, str | Path | dict[str, Any] | Spec],
) -> dict[str, Any]:
    """*base* with each patch laid over it in turn, later winning.

    What a framework ships and a project extends. The patch says only what it
    changes, so a constraint whose dimensions grew is the one line that grew::

        flow_out_max: {foreach: [node, tech, carrier, snapshot, investstep]}

    **A declaration the patch sets to** ``null`` **is removed**, which is the
    one thing an ordered list of files cannot say for itself: a declaration the
    patch does not mention is left alone, so without a marker there is no way
    to spell a deletion. The marker is positional and means nothing deeper
    down — ``constraints: {ramp: null}`` removes the constraint, where
    ``variables: {p: {where: null}}`` sets that variable's mask to none, which
    is an ordinary value the schema already takes.

    Everything else is laid over a declaration at a time and a **field** at a
    time: a mapping is merged into the mapping below it and anything else
    replaces, so a patch naming one field keeps the rest of the declaration it
    lands on. That is what lets a patch be short, and the reason to read the
    composed model rather than the patch: :meth:`~math_spec.model.Spec.to_yaml`
    on the result is the artifact a reviewer diffs against the base.

    Args:
        base: The model being extended — whatever every other verb takes.
        patches: What each patch is called, to the patch, **in the order they
            are laid on**. The name is what an error calls it. Order is the
            instruction, so this is the one verb here where giving the same
            arguments differently means a different model.

    Returns:
        One mapping, ready for :func:`~math_spec.validation.to_spec`. Composes
        with :func:`merge`, both taking and returning what the other does.

    Raises:
        LanguageError: A patch removes a declaration its base does not have,
            named with the near miss — a stale patch, or a section confused
            for another.
    """
    result = deepcopy(_sections(base))
    for name, patch in patches.items():
        result = _lay_over(result, deepcopy(_sections(patch)), name)
    return result


def _lay_over(base: dict[str, Any], patch: dict[str, Any], name: str) -> dict[str, Any]:
    """One patch over one base: sections declaration by declaration, the rest wholesale."""
    laid = dict(base)
    for key, value in patch.items():
        if key in SECTIONS:
            laid[key] = _patched(laid.get(key) or {}, value or {}, key, name)
        else:
            laid[key] = value
    return laid


def _patched(declared: dict[str, Any], patch: dict[str, Any], section: str, name: str) -> dict[str, Any]:
    """One section, with the patch's declarations laid over it and the ones it nulls removed."""
    out = dict(declared)
    for key, block in patch.items():
        if block is None:
            if key not in out:
                raise LanguageError(
                    f"patch '{name}' removes the {_singular(section)} '{key}', which its base does not declare. "
                    f'A removal is a claim about what is there, so a stale one is a patch that no longer '
                    f'describes the model it lands on. ' + did_you_mean(key, list(out))
                )
            del out[key]
        else:
            out[key] = _field_by_field(out.get(key), block)
    return out


def _field_by_field(under: Any, over: Any) -> Any:
    """*over* laid on *under*: mappings merge, everything else replaces.

    A patch naming one field of a declaration keeps the rest of it, which is
    the whole reason a patch can be short. ``None`` replaces here rather than
    removing — removal is the declaration-level marker and reaches no deeper,
    so ``where: null`` is the mask the schema already lets a file write.
    """
    if isinstance(under, dict) and isinstance(over, dict):
        merged = dict(under)
        for key, value in over.items():
            merged[key] = _field_by_field(merged.get(key), value)
        return merged
    return over
