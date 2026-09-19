# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Several files into one model, before any of them is validated.

:func:`override` lays **patches** over a **base**: what a framework ships and a
project extends. A patch says only what it changes, because declarations are
laid over a field at a time::

    constraints:
      ramp: {dims: [snapshot, generator, investment_period]}

A patch is not a :class:`~math_spec.model.Spec`. It is read before validation,
so it may carry ``null`` where a declaration would go and may name what only
its base declares. Nothing here resolves a name or checks a dim: the laid
mapping goes through :func:`~math_spec.validation.to_spec` like any other file.

What a patch may say, and what is refused:

* **A partial entry edits, and a whole one creates.** An entry that does not
  validate as a declaration on its own has to land on one the base declares,
  and a miss is refused with the near miss named.
* **Sibling patches are disjoint.** Two patches writing one field is refused,
  both named, so the order they are given in never decides a model. Layering
  is written out as ``override(override(base, …), …)``.
* **A patch adjusts the math, not the coordinate space.** A ``dimensions`` or
  ``relations`` entry may be added or restated word for word, never changed and
  never removed.
* **A declaration set to** ``null`` **is removed**, and a removal of what the
  base does not declare is refused. The marker is positional: ``constraints:
  {ramp: null}`` removes the constraint, where ``variables: {p: {where: null}}``
  sets that variable's mask to none, which is a value the schema takes. A whole
  section set to ``null`` is refused, because it removes nothing.
* **``given:`` is laid over one kind at a time**, by the same rules as any
  owned section.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast, get_args

from pydantic import BaseModel, ValidationError

from math_spec._yaml import read_model
from math_spec.errors import LanguageError, did_you_mean, schema_error
from math_spec.model import GivenBlock, Spec

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

#: The declarations that are the coordinate space rather than the math. A patch
#: may add one, and may restate one its base already declares word for word; it
#: may not say something else about it, and it may not remove it.
SHARED_SECTIONS = ('dimensions', 'relations')

#: The declarations a patch edits, creates or removes.
OWNED_SECTIONS = ('parameters', 'variables', 'constraints', 'expressions', 'macros', 'piecewise', 'sos')

#: What ``given:`` holds, by the key each kind sits under and what one entry of it is called.
GIVEN_KINDS = {'variables': 'given variable', 'constraints': 'given constraint'}

#: Every section keyed by declaration name. ``objective`` is one declaration
#: rather than a mapping of them, and is laid over field by field beside these.
SECTIONS = (*SHARED_SECTIONS, *OWNED_SECTIONS, 'given')

#: What one entry is called where dropping the key's last letter does not say it.
IRREGULAR = {
    'piecewise': 'piecewise curve',
    'sos': 'special-ordered set',
    'objective': 'objective',
}


def override(
    base: str | Path | dict[str, Any] | Spec,
    patches: Mapping[str, str | Path | dict[str, Any] | Spec],
) -> dict[str, Any]:
    """*base* with each patch laid over it, and nothing laid over another patch.

    Args:
        base: The model being extended: a YAML path, YAML text, a mapping, or a
            loaded :class:`~math_spec.model.Spec`.
        patches: What each patch is called, to the patch. The name is what an
            error calls it. The patches must write disjoint fields, so the
            order they are given in cannot change the result.

    Returns:
        One mapping, ready for :func:`~math_spec.validation.to_spec`. Nothing
        in it has been resolved, name-checked or lowered, and it shares no
        object with *base* or any patch.

    Raises:
        LanguageError: A patch edits or removes a declaration its base does not
            declare; a patch creates one that is not whole; a patch redeclares
            or removes a dimension or a relation; a patch sets a whole section
            to ``null``; or two patches write one field.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    read = {name: _declarations(patch) for name, patch in patches.items()}
    _disjoint(read)

    result = deepcopy(_declarations(base))
    for name, patch in read.items():
        result = _lay_over(result, deepcopy(patch), name)
    return result


def _declarations(source: str | Path | dict[str, Any] | Spec) -> dict[str, Any]:
    """A base or a patch as the mapping it declares, whatever shape it arrived in.

    Deliberately not :func:`~math_spec.validation.to_spec`: a patch carrying a
    ``null`` or naming only the field it changes is not a model, and validating
    it here would refuse the files this module exists to read.
    """
    if isinstance(source, Spec):
        return source.to_dict()
    if isinstance(source, dict):
        return source
    return read_model(source)


def _singular(section: str) -> str:
    """What one entry in *section* is called, ``sos`` and ``piecewise`` not being plurals."""
    return IRREGULAR.get(section, section[:-1])


def _entry_class(owner: type[BaseModel], field: str) -> type[BaseModel]:
    """The schema's own class for one entry under *field* of *owner*.

    Read off the annotation rather than listed here, so a section added to the
    schema cannot be laid over by a rule that does not know what it is made of.
    """
    annotation = owner.model_fields[field].annotation
    inner = [arg for arg in get_args(annotation) if arg is not type(None)]
    return cast('type[BaseModel]', inner[-1] if inner else annotation)


def _whole(cls: type[BaseModel], block: Any) -> bool:
    """Whether *block* is a declaration on its own, which is what lets a patch create one."""
    try:
        cls.model_validate(block)
    except ValidationError:
        return False
    return True


def _incomplete(label: str, cls: type[BaseModel], block: Any) -> str:
    """What *block* is short of, in the schema's own words rather than a second list."""
    fields = cls.model_fields
    missing = sorted(name for name, field in fields.items() if field.is_required() and name not in (block or {}))
    if missing:
        return f'{_a(label)} needs {_and_list(missing)}'
    try:
        cls.model_validate(block)
    except ValidationError as e:
        return str(schema_error(e))
    raise AssertionError(f'{_a(label)} asked what it is short of is whole: {block!r}')


def _a(noun: str) -> str:
    """*noun* under the article that reads: an objective, a constraint."""
    return f'an {noun}' if noun[0] in 'aeiou' else f'a {noun}'


def _and_list(names: Iterable[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``: the field names a message ends on."""
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


def _lay_over(base: dict[str, Any], patch: dict[str, Any], name: str) -> dict[str, Any]:
    """One patch over one base, a section at a time, the base left as it was."""
    laid = dict(base)
    for key, value in patch.items():
        if key == 'given':
            laid[key] = _given(laid.get(key) or {}, _section(value, key, name), name)
        elif key in SHARED_SECTIONS:
            laid[key] = _shared(laid.get(key) or {}, _section(value, key, name), key, name)
        elif key in OWNED_SECTIONS:
            block = _section(value, key, name)
            laid[key] = _owned(laid.get(key) or {}, block, _singular(key), _entry_class(Spec, key), name)
        elif key == 'objective':
            laid = _objective(laid, value, name)
        else:
            laid[key] = value
    return laid


def _section(value: Any, where: str, name: str) -> dict[str, Any]:
    """The block a patch writes under one section, a ``null`` section being refused rather than read as empty.

    A section is not a declaration, so the removal marker does not reach it. An
    empty mapping laid over a base says nothing either, and this is the spelling
    a writer reaches for when they mean to empty the section.
    """
    if value is None:
        raise LanguageError(
            f"patch '{name}' sets '{where}' to null, which removes nothing: the removal marker names one "
            f'declaration, and a section is not one. Remove the declarations one at a time, each under its '
            f'own name, or leave the section out of the patch.'
        )
    return cast('dict[str, Any]', value)


def _given(declared: dict[str, Any], patch: dict[str, Any], name: str) -> dict[str, Any]:
    """The ``given:`` block, one kind laid over at a time, so naming the columns keeps the row families.

    A kind the block does not have is carried as written, and the closed
    schema refuses it at load.
    """
    out = dict(declared)
    for kind, block in patch.items():
        if kind in GIVEN_KINDS:
            cls = _entry_class(GivenBlock, kind)
            entries = _section(block, f'given: {kind}:', name)
            out[kind] = _owned(out.get(kind) or {}, entries, GIVEN_KINDS[kind], cls, name)
        else:
            out[kind] = block
    return out


def _shared(declared: dict[str, Any], patch: dict[str, Any], section: str, name: str) -> dict[str, Any]:
    """One ``dimensions`` or ``relations`` block: a patch adds one or restates one, never changes or drops it.

    The restatement is compared for equality rather than field by field: a
    patch that names half a declaration is as much a second reading of the
    coordinate space as one that names another value.
    """
    out = dict(declared)
    singular = _singular(section)
    for key, block in patch.items():
        if block is None:
            raise LanguageError(
                f"patch '{name}' removes the {singular} '{key}'. The coordinate space is what the math is "
                f'written over, and a patch adjusts the math rather than the space: leave the {singular} out '
                f'of the patch, and remove the declarations written over it one at a time.'
            )
        if key not in out:
            out[key] = block
        elif out[key] != block:
            raise LanguageError(
                f"patch '{name}' declares the {singular} '{key}' as {block!r}, where its base "
                f'declares {out[key]!r}. A patch adjusts the math, not the coordinate space the math is '
                f'already written over: restate the declaration word for word, leave it out, or give the '
                f'patch {_a(singular)} of its own under a name of its own.'
            )
    return out


def _owned(
    declared: dict[str, Any], patch: dict[str, Any], label: str, cls: type[BaseModel], name: str
) -> dict[str, Any]:
    """One section of the math, each entry editing what is there or creating what is whole."""
    out = dict(declared)
    for key, block in patch.items():
        if block is None:
            _removed(out, key, label, name)
        elif key in out:
            out[key] = _field_by_field(out[key], block)
        elif _whole(cls, block):
            out[key] = block
        else:
            raise LanguageError(
                f"patch '{name}' edits the {label} '{key}', which its base does not declare. "
                f'{did_you_mean(key, list(out))} A patch creates a declaration only by writing it whole, '
                f'and this one is not: {_incomplete(label, cls, block)}.'
            )
    return out


def _removed(out: dict[str, Any], key: str, label: str, name: str) -> None:
    """Delete what the patch nulled, refusing a removal its base cannot satisfy."""
    if key not in out:
        raise LanguageError(
            f"patch '{name}' removes the {label} '{key}', which its base does not declare. "
            f'A removal is a claim about what is there, so a stale one is a patch that no longer describes '
            f'the model it lands on. ' + did_you_mean(key, list(out))
        )
    del out[key]


def _objective(laid: dict[str, Any], patch: Any, name: str) -> dict[str, Any]:
    """The one declaration that is not keyed by a name, laid over by the same three rules."""
    out = dict(laid)
    standing = out.get('objective')
    cls = _entry_class(Spec, 'objective')
    if patch is None:
        if standing is None:
            raise LanguageError(
                f"patch '{name}' removes the objective, which its base does not declare. A removal is a "
                f'claim about what is there, and a model with no objective is already the feasibility '
                f'problem this patch is asking for.'
            )
        del out['objective']
    elif standing is not None:
        out['objective'] = _field_by_field(standing, patch)
    elif _whole(cls, patch):
        out['objective'] = patch
    else:
        raise LanguageError(
            f"patch '{name}' edits the objective, which its base does not declare. A patch creates the "
            f'objective only by writing it whole, and this one is not: {_incomplete("objective", cls, patch)}.'
        )
    return out


def _field_by_field(under: Any, over: Any) -> Any:
    """*over* laid on *under*: mappings merge, everything else replaces.

    ``None`` replaces here rather than removing. Removal is the
    declaration-level marker and reaches no deeper, so ``where: null`` is the
    mask the schema already lets a file write.
    """
    if isinstance(under, dict) and isinstance(over, dict):
        merged = dict(under)
        for key, value in over.items():
            merged[key] = _field_by_field(merged.get(key), value)
        return merged
    return over
