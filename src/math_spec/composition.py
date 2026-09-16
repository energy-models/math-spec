# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""A base and its patches into one model, before any of them is validated.

What a framework ships and a project extends. The patch says only what it
changes, because declarations are laid over a field at a time::

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

from pydantic import ValidationError

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

#: Every section keyed by declaration name. ``objective`` is one declaration
#: rather than a mapping of them, and is laid over field by field beside these.
SECTIONS = (*SHARED_SECTIONS, *OWNED_SECTIONS)

#: What one entry is called where dropping the key's last letter does not say
#: it: two sections that are not plurals, and the objective, which is one
#: declaration rather than a mapping of them.
IRREGULAR = {'piecewise': 'piecewise curve', 'sos': 'special-ordered set', 'objective': 'objective'}


class _Change(NamedTuple):
    """One declaration a patch added, edited or removed, for the shell front's summary."""

    action: str
    section: str
    name: str
    patch: str


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


def _block(section: str) -> type[Any]:
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
    return under == over


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
