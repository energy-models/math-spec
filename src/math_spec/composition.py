# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Several files into one model, before any of them is validated.

Two verbs, and they answer different questions. :func:`merge` composes
**peers**: templates that each own part of the math, where a name two of them
declare is a collision and the order they are given in means nothing.
:func:`override` layers a **base and its patches**: what a framework ships and a
project extends, where a name the patch declares is the point. Neither is a
mode of the other, and they compose —
``override(merge({...}), {...})`` builds the model and then configures the run.

A patch says only what it changes, because declarations are laid over a field
at a time::

    constraints:
      ramp: {dims: [snapshot, generator, investment_period]}

**A patch is not a** :class:`~math_spec.model.Spec`. It is read before
validation, so it may carry ``null`` where a declaration would go and may name
what only its base declares. Nothing here resolves a name or checks a dim: the
laid mapping goes through :func:`~math_spec.validation.to_spec` like any other
file, and every rule the language has applies to it there and nowhere else.

The verb is designed to collide, so what keeps it predictable is that a
collision is refused everywhere the caller did not ask for one:

* **A partial entry edits, and a whole one creates.** An entry that does not
  validate as a declaration on its own has to land on one the base declares,
  named with the near miss. A mistyped name then refuses instead of quietly
  inventing a declaration nothing refers to.
* **Sibling patches are disjoint.** Two patches writing one field is refused,
  both named, so the order they are given in never decides a model. Layering
  is written out — ``override(override(base, …), …)`` — where it is on the page
  rather than in an argument's position.
* **A patch adjusts the math, not the axes.** A ``dimensions`` or ``relations``
  entry may be added or restated exactly; changing one under the expressions
  already written over it is refused.

**A declaration the patch sets to** ``null`` **is removed**, which is the one
thing an ordered list of files cannot say for itself: a declaration a patch
does not mention is left alone, so without a marker a deletion has no spelling.
The marker is positional and means nothing deeper down — ``constraints: {ramp:
null}`` removes the constraint, where ``variables: {p: {where: null}}`` sets
that variable's mask to none, which is a value the schema already takes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, NamedTuple, get_args

from pydantic import BaseModel, ValidationError

from math_spec._yaml import read_model
from math_spec.errors import LanguageError, did_you_mean
from math_spec.model import Spec

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

#: The declarations that are the coordinate space rather than the math. A patch
#: may add one, and may restate one its base already declares; it may not say
#: something else about it.
SHARED_SECTIONS = ('dimensions', 'relations')

#: The declarations a patch edits, creates or removes.
OWNED_SECTIONS = ('parameters', 'variables', 'constraints', 'expressions', 'macros', 'piecewise', 'sos')

#: The declarations a file reads and does not introduce. Peers must agree
#: about one, and :func:`merge` folds it into the declaration that introduces
#: it, so a composed library carries none.
GIVEN_SECTIONS = ('given_variables', 'given_constraints')

#: Every section keyed by declaration name. ``objective`` is one declaration
#: rather than a mapping of them, and is laid over field by field beside these.
SECTIONS = (*SHARED_SECTIONS, *OWNED_SECTIONS, *GIVEN_SECTIONS)

#: What one entry is called where dropping the key's last letter does not say
#: it: two sections that are not plurals, and the objective, which is one
#: declaration rather than a mapping of them.
IRREGULAR = {
    'piecewise': 'piecewise curve',
    'sos': 'special-ordered set',
    'objective': 'objective',
    'given_variables': 'given variable',
}


class _Change(NamedTuple):
    """One declaration a patch added, edited or removed, for the shell front's summary."""

    action: str
    section: str
    name: str
    patch: str


def merge(
    fragments: Mapping[str, str | Path | dict[str, Any] | Spec], description: str | None = None
) -> dict[str, Any]:
    """*fragments* composed as peers, each owning the math it declares.

    A component library is a set of templates that agree on a coupling
    surface — one flow per port, one balance per bus — and wiring a system is
    rows in a table rather than generated YAML. This is what takes the
    templates and hands back one model.

    Args:
        fragments: What each fragment is called, to the fragment. The name is
            what an error calls it, so it is the template's name rather than a
            path. The order they are given in does not reach the result.
        description: What the *composed* model is. A fragment's own
            ``description`` is about the fragment, so it is neither carried nor
            joined.

    Returns:
        One mapping, ready for :func:`~math_spec.validation.to_spec`. Nothing
        in it has been resolved, name-checked or lowered.

    Raises:
        LanguageError: Two fragments declare one name; two fragments say
            different things about one dimension or relation; two fragments
            pin different language versions; or their objectives run opposite
            ways.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    read = {name: _declarations(fragment) for name, fragment in fragments.items()}
    merged: dict[str, Any] = {'version': _one_version(read)}
    if description is not None:
        merged['description'] = description

    for section in SHARED_SECTIONS:
        if agreed := _agreed(read, section):
            merged[section] = agreed
    for section in OWNED_SECTIONS:
        if claimed := _claimed(read, section):
            merged[section] = claimed
    for section in GIVEN_SECTIONS:
        if unintroduced := _folded(read, section, merged):
            merged[section] = unintroduced
    if (objective := _summed_objective(read)) is not None:
        merged['objective'] = objective
    return merged


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
            f'the fragments are written against different language versions: {spelled}. One model has '
            f'one version, so write the same one in each — a fragment that declares none is version 0.'
        )
    return next(iter(declared.values()), 0)


def _agreed(read: Mapping[str, dict[str, Any]], section: str) -> dict[str, Any]:
    """One ``dimensions`` or ``relations`` block, peers that say the same thing folded together.

    Equality rather than :func:`_agrees`: between peers neither declaration is
    the one being restated, so a field only one of them writes is a difference
    nothing settles.
    """
    merged: dict[str, Any] = {}
    author: dict[str, str] = {}
    for name, sections in read.items():
        for key, block in (sections.get(section) or {}).items():
            if key in merged and _claims(merged[key]) != _claims(block):
                raise LanguageError(
                    f"fragments '{author[key]}' and '{name}' say different things about "
                    f'{_singular(section)} {key!r}: {merged[key]!r} against {block!r}. A declaration two '
                    f'fragments share is one both of them say the same thing about — make the two '
                    f'identical, or give one of them a name of its own.'
                )
            merged.setdefault(key, block)
            author.setdefault(key, name)
    return merged


def _claims(block: Any) -> Any:
    """*block* without its prose, which is what the declaration says rather than a claim about it.

    Two fragments describing one shared declaration in their own words agree
    about the declaration, so the first one's wording is carried and neither is
    the disagreement this refuses.
    """
    return {key: value for key, value in block.items() if key != 'description'} if isinstance(block, dict) else block


def _claimed(read: Mapping[str, dict[str, Any]], section: str) -> dict[str, Any]:
    """One block of owned declarations, a name claimed twice being the error."""
    merged: dict[str, Any] = {}
    author: dict[str, str] = {}
    for name, sections in read.items():
        for key, block in (sections.get(section) or {}).items():
            if key in merged:
                raise LanguageError(
                    f"fragments '{author[key]}' and '{name}' both declare the {_singular(section)} "
                    f'{key!r}. Two of the same kind of thing are two rows of a dimension rather than '
                    f'two fragments: merge the template once, and let the data carry both. Different '
                    f'math under one spelling is a rename — call one of them something else.'
                )
            merged[key] = block
            author[key] = name
    return merged


def _folded(read: Mapping[str, dict[str, Any]], section: str, merged: Mapping[str, Any]) -> dict[str, Any]:
    """The given declarations no fragment introduces, the rest folded into the ones that do.

    A fragment's given declaration is what it expects of a column a sibling
    owns, so where the sibling is in the composition the expectation is checked
    and then spent: the composed model declares the column once, and a name
    that is both given and introduced would otherwise read as a collision.
    """
    given = _agreed(read, section)
    introduced = merged.get(section.removeprefix('given_'), {})
    for key, block in list(given.items()):
        if key not in introduced:
            continue
        if not _agrees(_claims(introduced[key]), _claims(block)):
            reader, owner = _author_of(read, section, key), _author_of(read, section.removeprefix('given_'), key)
            raise LanguageError(
                f"fragment '{reader}' reads {_singular(section)} {key!r} as {block!r}, where '{owner}' "
                f'introduces it as {introduced[key]!r}. A given declaration is what the file expects of '
                f'a column somebody else owns, so it says the same as the declaration it is folded '
                f'into, or less.'
            )
        del given[key]
    return given


def _author_of(read: Mapping[str, dict[str, Any]], section: str, key: str) -> str:
    """The first fragment declaring *key* in *section*, for a message that names both sides."""
    return next(name for name, sections in read.items() if key in (sections.get(section) or {}))


def _summed_objective(read: Mapping[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Every fragment's objective, summed, or ``None`` where none declares one.

    Summing is what composing costs: each template prices what it owns, and the
    system pays for all of it. The senses must agree, because a sum of two
    objectives has one sense and nothing in the files says which — negating the
    minority would be this function deciding what a model means.
    """
    declared = {name: sections['objective'] for name, sections in read.items() if sections.get('objective')}
    if not declared:
        return None
    senses = {name: objective.get('sense', 'minimize') for name, objective in declared.items()}
    if len(set(senses.values())) > 1:
        spelled = ', '.join(f"'{name}' {sense}s" for name, sense in sorted(senses.items()))
        raise LanguageError(
            f'the fragments disagree about which way the objective runs: {spelled}. A composed model '
            f'has one objective and one sense, so write every fragment against the same one — negate '
            f'the terms of the odd one out rather than its sense.'
        )
    terms = [objective['expression'] for objective in declared.values()]
    joined = terms[0] if len(terms) == 1 else ' + '.join(f'({term})' for term in terms)
    return {'sense': next(iter(senses.values())), 'expression': joined}


def override(
    base: str | Path | dict[str, Any] | Spec,
    patches: Mapping[str, str | Path | dict[str, Any] | Spec],
) -> dict[str, Any]:
    """*base* with each patch laid over it, and nothing laid over another patch.

    Args:
        base: The model being extended — whatever every other verb takes.
        patches: What each patch is called, to the patch. The name is what an
            error calls it, so it is the patch's own name rather than a path.
            The patches must write disjoint fields, which is why the order they
            are given in cannot change the result.

    Returns:
        One mapping, ready for :func:`~math_spec.validation.to_spec`. Nothing
        in it has been resolved, name-checked or lowered.

    Raises:
        LanguageError: A patch edits or removes a declaration its base does not
            declare; a patch creates one that is not whole; a patch redeclares
            a dimension or a relation as something else; or two patches write
            one field.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    return _compose(base, patches)[0]


def _compose(
    base: str | Path | dict[str, Any] | Spec,
    patches: Mapping[str, str | Path | dict[str, Any] | Spec],
) -> tuple[dict[str, Any], list[_Change]]:
    """:func:`override`, and what it did — the shell front prints the second half.

    Kept apart from the public verb so that the return type a caller composes
    with stays the mapping every other verb takes.
    """
    read = {name: _declarations(patch) for name, patch in patches.items()}
    _disjoint(read)

    result = deepcopy(_declarations(base))
    log: list[_Change] = []
    for name, patch in read.items():
        result = _lay_over(result, deepcopy(patch), name, log)
    return result, log


def _declarations(source: str | Path | dict[str, Any] | Spec) -> dict[str, Any]:
    """A base or a patch as the mapping it declares, whatever shape it arrived in.

    Deliberately not :func:`~math_spec.validation.to_spec`: a patch carrying a
    ``null`` or naming only the field it changes is not a model, and validating
    one here would refuse exactly the files this function exists to read.
    """
    if isinstance(source, Spec):
        return source.to_dict()
    if isinstance(source, dict):
        return source
    return read_model(source)


def _singular(section: str) -> str:
    """What one entry in *section* is called, ``sos`` and ``piecewise`` not being plurals."""
    return IRREGULAR.get(section, section[:-1])


def _block(section: str) -> type[BaseModel]:
    """The schema's own class for one entry in *section*.

    Read off :class:`~math_spec.model.Spec`'s annotations rather than listed
    here, so a section added to the schema cannot be laid over by a rule that
    does not know what it is made of.
    """
    annotation = Spec.model_fields[section].annotation
    inner = [arg for arg in get_args(annotation) if arg is not type(None)]
    return inner[-1] if inner else annotation  # pyrefly: ignore[bad-return] — a section is always one block class


def _whole(section: str, block: Any) -> bool:
    """Whether *block* is a declaration on its own, which is what lets a patch create one."""
    try:
        _block(section).model_validate(block)
    except ValidationError:
        return False
    return True


def _incomplete(section: str, block: Any) -> str:
    """What *block* is short of, in the schema's own words rather than a second list."""
    fields = _block(section).model_fields
    missing = sorted(name for name, field in fields.items() if field.is_required() and name not in (block or {}))
    if missing:
        return f'{_a(_singular(section))} needs {_and_list(missing)}'
    try:
        _block(section).model_validate(block)
    except ValidationError as e:
        return str(e).splitlines()[-1].strip()
    return 'it is whole'  # pragma: no cover — only reached if the caller asks about a whole block


def _a(noun: str) -> str:
    """*noun* under the article that reads — an objective and an expression, against a constraint."""
    return f'an {noun}' if noun[0] in 'aeiou' else f'a {noun}'


def _and_list(names: Iterable[str]) -> str:
    """``a``, ``a and b``, ``a, b and c`` — the field names a message ends on."""
    spelled = [f'`{name}`' for name in names]
    if len(spelled) == 1:
        return spelled[0]
    return f'{", ".join(spelled[:-1])} and {spelled[-1]}'


def _writes(patch: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """Every field *patch* writes, as a path.

    A removal is the declaration's own path, so it overlaps every edit inside
    that declaration: removing and editing one declaration is two patches
    disagreeing, whichever order they would have been laid in.
    """
    paths: list[tuple[str, ...]] = []
    for key, value in patch.items():
        if key in SECTIONS:
            for name, block in (value or {}).items():
                paths.extend(_leaves((key, name), block))
        elif key == 'objective':
            paths.extend(_leaves(('objective',), value))
        else:
            paths.append((key,))
    return paths


def _leaves(prefix: tuple[str, ...], value: Any) -> list[tuple[str, ...]]:
    """The paths *value* writes under *prefix*, a mapping being walked into and anything else a leaf."""
    if isinstance(value, dict) and value:
        return [leaf for key, inner in value.items() for leaf in _leaves((*prefix, key), inner)]
    return [prefix]


def _disjoint(read: Mapping[str, dict[str, Any]]) -> None:
    """Refuse two patches that write one field, which is the only way order could matter."""
    claimed: dict[tuple[str, ...], str] = {}
    for name, patch in read.items():
        for path in _writes(patch):
            for other, owner in claimed.items():
                if path[: len(other)] == other or other[: len(path)] == path:
                    raise LanguageError(_overlap_message(owner, other, name, path))
            claimed[path] = name


def _overlap_message(owner: str, claimed: tuple[str, ...], name: str, path: tuple[str, ...]) -> str:
    """The refusal for two patches writing one field, naming both and the rewrite."""
    where = f"'{owner}' writes {'.'.join(claimed)} and '{name}' writes {'.'.join(path)}"
    if claimed == path:
        where = f'both write {".".join(path)}'
    return (
        f"patches '{owner}' and '{name}': {where}. Patches laid on one base are disjoint, so nothing "
        f'decides which of two writes wins. Write the change in one patch, or lay one patch on the '
        f"result of the other: override(override(base, {{'{owner}': …}}), {{'{name}': …}})."
    )


def _lay_over(base: dict[str, Any], patch: dict[str, Any], name: str, log: list[_Change]) -> dict[str, Any]:
    """One patch over one base, a section at a time, the base left as it was."""
    laid = dict(base)
    for key, value in patch.items():
        if key in SHARED_SECTIONS:
            laid[key] = _shared(laid.get(key) or {}, value or {}, key, name, log)
        elif key in OWNED_SECTIONS:
            laid[key] = _owned(laid.get(key) or {}, value or {}, key, name, log)
        elif key == 'objective':
            laid = _objective(laid, value, name, log)
        else:
            laid[key] = value
    return laid


def _shared(
    declared: dict[str, Any], patch: dict[str, Any], section: str, name: str, log: list[_Change]
) -> dict[str, Any]:
    """One ``dimensions`` or ``relations`` block: a patch adds an axis or restates one, never changes it."""
    out = dict(declared)
    for key, block in patch.items():
        if block is None:
            _removed(out, key, section, name, log)
        elif key not in out:
            out[key] = block
            log.append(_Change('added', section, key, name))
        elif not _agrees(out[key], block):
            raise LanguageError(
                f"patch '{name}' declares the {_singular(section)} '{key}' as {block!r}, where its base "
                f'declares {out[key]!r}. A patch adjusts the math, not the axes the math is already '
                f'written over: restate the declaration exactly, leave it out, or give the patch an '
                f'axis of its own under a name of its own.'
            )
    return out


def _agrees(under: Any, over: Any) -> bool:
    """Whether *over* says only what *under* already says, a field the patch omits being no claim."""
    if isinstance(over, dict):
        return isinstance(under, dict) and all(
            key in under and _agrees(under[key], value) for key, value in over.items()
        )
    return bool(under == over)


def _owned(
    declared: dict[str, Any], patch: dict[str, Any], section: str, name: str, log: list[_Change]
) -> dict[str, Any]:
    """One section of the math, each entry editing what is there or creating what is whole."""
    out = dict(declared)
    for key, block in patch.items():
        if block is None:
            _removed(out, key, section, name, log)
        elif key in out:
            out[key] = _field_by_field(out[key], block)
            log.append(_Change('edited', section, key, name))
        elif _whole(section, block):
            out[key] = block
            log.append(_Change('added', section, key, name))
        else:
            raise LanguageError(
                f"patch '{name}' edits the {_singular(section)} '{key}', which its base does not declare. "
                f'{did_you_mean(key, list(out))} A patch creates a declaration only by writing it whole, '
                f'and this one is not: {_incomplete(section, block)}.'
            )
    return out


def _removed(out: dict[str, Any], key: str, section: str, name: str, log: list[_Change]) -> None:
    """Delete what the patch nulled, refusing a removal its base cannot satisfy."""
    if key not in out:
        raise LanguageError(
            f"patch '{name}' removes the {_singular(section)} '{key}', which its base does not declare. "
            f'A removal is a claim about what is there, so a stale one is a patch that no longer describes '
            f'the model it lands on. ' + did_you_mean(key, list(out))
        )
    del out[key]
    log.append(_Change('removed', section, key, name))


def _objective(laid: dict[str, Any], patch: Any, name: str, log: list[_Change]) -> dict[str, Any]:
    """The one declaration that is not keyed by a name, laid over by the same three rules."""
    out = dict(laid)
    standing = out.get('objective')
    if patch is None:
        if standing is None:
            raise LanguageError(
                f"patch '{name}' removes the objective, which its base does not declare. A removal is a "
                f'claim about what is there, and a model with no objective is already the feasibility '
                f'problem this patch is asking for.'
            )
        del out['objective']
        log.append(_Change('removed', 'objective', 'objective', name))
    elif standing is not None:
        out['objective'] = _field_by_field(standing, patch)
        log.append(_Change('edited', 'objective', 'objective', name))
    elif _whole('objective', patch):
        out['objective'] = patch
        log.append(_Change('added', 'objective', 'objective', name))
    else:
        raise LanguageError(
            f"patch '{name}' edits the objective, which its base does not declare. A patch creates the "
            f'objective only by writing it whole, and this one is not: {_incomplete("objective", patch)}.'
        )
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
