# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Several files into one spec, each checked as a spec where it is one.

Two verbs, and they answer different questions. [`merge`][] composes
**peers**: fragments that each own part of the math, where a name two of them
declare is a collision and the order they are given in means nothing.
[`override`][] lays **patches** over a **base**: what a framework ships and a
project extends, where a name the patch declares is the point. They compose as
``override(merge({...}), {...})``, which builds the spec and then configures
the run.

[`merge`][] writes nothing a fragment did not write, except a ``+``. It
joins two fragments' text in two places, the objective and a named expression
that terms add to; every other block is copied as written, refused where two
fragments own it, or held identical where it is a dimension or a relation.
What that means for each section:

* **A dimension or a relation every fragment may declare**, and the ones that
  do have to say the same thing about it. Prose is not a claim, so two
  descriptions of one dimension agree, and the first in the fragments' name
  order is carried: the order they are passed in reaches no description.
* **Every other declaration is owned.** A name two fragments declare is refused,
  both named.
* **The objectives are summed**, each term in parentheses, in the fragments'
  name order, and the senses have to agree.
* **A term is added to the expression it names.** A ``given: expressions:``
  entry with a ``term:`` names the expression its fragment adds to the name.
  The name is an ``expressions:`` block of one other fragment: a sum with a
  frame and no body, or a definition. The composed spec writes its body as
  that body, if it has one, plus every term by its name, in the fragments'
  name order, and keeps each term as the named expression its fragment
  declares. A definition written as ``cases:`` is refused, since it is summed
  as written. A later merge adds to the composed body the same way. A term
  that names no ``expressions:`` block of any fragment is refused: merge
  fills or extends what a file declared, and never invents a name.
* **A given declaration is folded** into the declaration that introduces the
  name, once the reader is checked to say the same as the introducer or less.
  A given expression's body may carry no dimension its reader does not state,
  and a name read as one kind and introduced as another is refused. A
  reader's description fills a declaration its owner left undescribed.
  Two fragments that both read a name have to read it over one frame, as a
  set. What no fragment introduces stays under ``given:`` until a host model
  provides it.

A patch says only what it changes, because declarations are laid over a field
at a time::

    constraints:
      ramp: {dims: [snapshot, generator, investment_period]}

A fragment is a [`Spec`][mathspec.spec.Spec] of its own, and a base is one
too: each goes through [`to_spec`][mathspec.validation.to_spec] before anything is
composed, so a composed spec never hides a file that does not load alone. A
patch is not one. It names only what it changes and may carry ``null`` where a
declaration would go, so it is laid over as written, and the result goes
through [`to_spec`][mathspec.validation.to_spec] like any other file.

What a patch may say, and what is refused:

* **A partial entry edits, and a whole one creates.** An entry that does not
  validate as a declaration on its own has to land on one the base declares,
  and a miss is refused with the near miss named.
* **Sibling patches are disjoint.** Two patches writing one field is refused,
  both named, so the order they are given in never decides a spec. Layering
  is written out as ``override(override(base, …), …)``.
* **A patch adjusts the math, not the coordinate space.** A ``dimensions`` or
  ``relations`` entry may be added or restated word for word, never changed and
  never removed.
* ``null`` **makes what it names absent.** A declaration set to ``null`` is
  removed, and a removal of what the base does not declare is refused. A field
  set to ``null`` is dropped, and takes its default when the result loads:
  ``variables: {p: {bounds: {upper: null}}}`` opens that bound. A whole section
  set to ``null`` is refused, because it removes nothing.
* **``given:`` is laid over one kind at a time**, by the same rules as any
  owned section.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError

from mathspec._yaml import read_spec
from mathspec.dimensions import dims_of
from mathspec.errors import LanguageError, did_you_mean, schema_error
from mathspec.spec import GivenBlock, Spec
from mathspec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

#: The declarations that are the coordinate space rather than the math. A patch
#: may add one, and may restate one its base already declares word for word; it
#: may not say something else about it, and it may not remove it.
SHARED_SECTIONS = ('dimensions', 'relations')

#: The declarations a patch edits, creates or removes: every other section of
#: the schema keyed by declaration name, read off it so that none is left out.
OWNED_SECTIONS = tuple(
    name
    for name, field in Spec.model_fields.items()
    if get_origin(field.annotation) is dict and name not in SHARED_SECTIONS
)

#: What ``given:`` holds, by the key each kind sits under and what one entry of
#: it is called. The key is the introducing section's name too, which is what
#: lets [`merge`][] fold a given declaration into the one that introduces it.
GIVEN_KINDS = {
    'parameters': 'given parameter',
    'variables': 'given variable',
    'constraints': 'given constraint',
    'expressions': 'given expression',
}

#: Every section keyed by declaration name. ``objective`` is one declaration
#: rather than a mapping of them, and is laid over field by field beside these.
SECTIONS = (*SHARED_SECTIONS, *OWNED_SECTIONS, 'given')

#: What one entry is called where dropping the key's last letter does not say it.
IRREGULAR = {
    'piecewise': 'piecewise curve',
    'sos': 'special-ordered set',
    'objective': 'objective',
}


def merge(fragments: Mapping[str, str | Path | Mapping[str, object] | Spec], description: str | None = None) -> Spec:
    """*fragments* composed as peers, each owning the math it declares.

    Args:
        fragments: What each fragment is called, to the fragment: a YAML path,
            YAML text, a mapping, or a loaded [`Spec`][mathspec.spec.Spec].
            The name is what an error calls it. The order they are given in
            does not reach the result.
        description: What the composed spec is. A fragment's own
            ``description`` is about the fragment, and is not carried.

    Returns:
        The composed spec, loaded. A given declaration a sibling introduces is
        folded away; one nothing introduces stays under ``given:``.

    Raises:
        LanguageError: A fragment does not load on its own; two fragments
            declare one name; two fragments say different things about one
            dimension, relation or given declaration; a fragment reads a name as
            something other than what its sibling introduces, as another kind
            of thing, or over fewer dimensions than its body carries; two fragments are
            written against different language versions; their objectives run
            opposite ways; or the composed spec does not load.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    loaded = {name: _fragment(name, fragment) for name, fragment in fragments.items()}
    read = {name: spec.to_dict() for name, spec in loaded.items()}
    merged: dict[str, object] = {'version': _one_version(read)}
    if description is not None:
        merged['description'] = description
    for section in SHARED_SECTIONS:
        if agreed := _agreed(read, section, _singular(section), 'give one of them a name of its own'):
            merged[section] = agreed
    asked = {name: _readings(sections) for name, sections in read.items()}
    readings = {
        kind: _agreed(asked, kind, label, 'read it over one frame', claims=_reading_claims)
        for kind, label in GIVEN_KINDS.items()
    }
    for section in OWNED_SECTIONS:
        if claimed := _claimed(read, section):
            merged[section] = claimed
    if summed := _summed(read, loaded, _mapping(merged.get('expressions')), readings['expressions']):
        merged['expressions'] = {**_mapping(merged.get('expressions')), **summed}
    if given := _folded(read, merged, loaded, readings):
        merged['given'] = given
    if (objective := _summed_objective(read)) is not None:
        merged['objective'] = objective
    return to_spec(merged)


def _fragment(name: str, source: str | Path | Mapping[str, object] | Spec) -> Spec:
    """One fragment loaded as the spec it is on its own, refused under its own name where it is not one."""
    try:
        return to_spec(source)
    except LanguageError as e:
        msg = (
            f"fragment '{name}' does not load on its own. A fragment is a whole spec: it declares "
            f"what it builds, and reads what a sibling builds under 'given:'.\n{e}"
        )
        raise type(e)(msg) from None


def _one_version(read: Mapping[str, dict[str, object]]) -> int:
    """The language version every fragment is written against."""
    declared = {name: cast('int', sections['version']) for name, sections in read.items()}
    if len(set(declared.values())) > 1:
        spelled = ', '.join(f"'{name}' says {version}" for name, version in sorted(declared.items()))
        raise LanguageError(
            f'the fragments are written against different language versions: {spelled}. One spec has '
            f'one version, so write every fragment against the same one.'
        )
    return next(iter(declared.values()), 0)


def _author_of(read: Mapping[str, dict[str, object]], section: str, key: str) -> str:
    """The first fragment declaring *key* under *section*, for a message that names both sides."""
    return next(name for name, sections in read.items() if key in _mapping(sections.get(section)))


def _said(read: Mapping[str, dict[str, object]], section: str, key: str) -> object:
    """The first description of *key* under *section* in the fragments' name order, which no argument order changes."""
    return next(
        (
            said
            for name in sorted(read)
            if (said := _mapping(_mapping(read[name].get(section)).get(key)).get('description'))
        ),
        None,
    )


def _claims(block: object) -> object:
    """*block* without its prose, which is what the declaration says rather than a remark about it."""
    return {key: value for key, value in block.items() if key != 'description'} if isinstance(block, dict) else block


def _reading_claims(block: object) -> object:
    """What a reading claims: its fields but the prose, with the frame as a set, since two files read one name over one frame however they list it."""
    claims = _mapping(_claims(block))
    return {**claims, 'dims': frozenset(cast('list[str]', claims.get('dims', [])))}


def _readings(sections: Mapping[str, object]) -> dict[str, object]:
    """The ``given:`` block of one fragment, each entry without its term: what the fragment reads, apart from what it adds."""
    return {
        kind: {key: {f: v for f, v in _mapping(entry).items() if f != 'term'} for key, entry in _mapping(group).items()}
        for kind, group in _mapping(sections.get('given')).items()
    }


def _agreed(
    read: Mapping[str, dict[str, object]],
    section: str,
    label: str,
    repair: str,
    *,
    claims: Callable[[object], object] = _claims,
) -> dict[str, object]:
    """One block every fragment may declare, peers that say the same thing folded together.

    Equality of the claims rather than "the same or less": between peers
    neither declaration is the one being restated, so a field only one of them
    writes is a difference nothing settles. *claims* says what a block claims;
    a reading's frame is a set. Prose is not a claim, so the first description
    in the fragments' name order is carried, whatever order they are passed in.
    """
    merged: dict[str, object] = {}
    for name, sections in read.items():
        for key, block in _mapping(sections.get(section)).items():
            if key in merged and claims(merged[key]) != claims(block):
                raise LanguageError(
                    f"fragments '{_author_of(read, section, key)}' and '{name}' say different things about "
                    f'the {label} {key!r}: {merged[key]!r} against {block!r}. A declaration two fragments '
                    f'share is one both say the same thing about: make the two identical, or {repair}.'
                )
            merged.setdefault(key, block)
    for key, block in merged.items():
        if said := _said(read, section, key):
            merged[key] = {**_mapping(block), 'description': said}
    return merged


def _claimed(read: Mapping[str, dict[str, object]], section: str) -> dict[str, object]:
    """One block of owned declarations, a name claimed twice being the refusal."""
    merged: dict[str, object] = {}
    for name, sections in read.items():
        for key, block in _mapping(sections.get(section)).items():
            if key in merged:
                author = _author_of(read, section, key)
                if section == 'expressions' and (target := _adds(read[author], key) or _adds(sections, key)):
                    raise LanguageError(
                        f"fragments '{author}' and '{name}' both declare the expression {key!r}, which a fragment "
                        f'adds to {target!r} as a term. A term shares one namespace with every named expression: '
                        f"name each fragment's term apart, such as after its component."
                    )
                hint = (
                    " If one fragment adds to the other's definition, write what it adds as `term:` under "
                    '`given: expressions:`.'
                    if section == 'expressions'
                    else ''
                )
                raise LanguageError(
                    f"fragments '{author}' and '{name}' both declare the "
                    f'{_singular(section)} {key!r}. Two of the same kind of thing are two rows of a dimension '
                    f'rather than two fragments: merge the fragment once, and let the data carry both. '
                    f'Different math under one spelling is a rename: call one of them something else.{hint}'
                )
            merged[key] = block
    return merged


def _adds(sections: Mapping[str, object], key: str) -> str | None:
    """The name one fragment adds *key* to as a term, or ``None`` where it adds no term by that name."""
    given = _mapping(_mapping(sections.get('given')).get('expressions'))
    return next((target for target, entry in given.items() if _mapping(entry).get('term') == key), None)


def _terms(read: Mapping[str, dict[str, object]], key: str) -> list[tuple[str, str]]:
    """Every term the fragments add to *key*, with the fragment that adds it, in the fragments' name order."""
    found = []
    for name, sections in sorted(read.items()):
        entry = _mapping(_mapping(_mapping(sections.get('given')).get('expressions')).get(key))
        if entry.get('term') is not None:
            found.append((name, cast('str', entry['term'])))
    return found


def _summed(
    read: Mapping[str, dict[str, object]],
    loaded: Mapping[str, Spec],
    defined: Mapping[str, object],
    readings: Mapping[str, object],
) -> dict[str, object]:
    """Every name a fragment adds a term to, its body written as the owner's body plus the terms.

    The owner's body comes first where it has one, in parentheses where it is
    more than a name, then every term by its name in the fragments' name
    order; one body alone is carried as written. An empty sum keeps its frame,
    so the composed load holds the terms to it. A definition written as
    ``cases:`` is refused, since it is summed as written and a set of cases is
    no one body. The block keeps the owner's description, or takes the first
    a reader wrote.
    """
    summed: dict[str, object] = {}
    for key, reading in readings.items():
        entry = _mapping(reading)
        terms = _terms(read, key)
        if not terms:
            continue
        _landed(read, defined, key, [name for name, _ in terms])
        bodies = [term for _, term in terms]
        base = _as_mapping(defined[key])
        if base.get('cases'):
            raise LanguageError(
                f"fragment '{_author_of(read, 'expressions', key)}' defines {key!r} as `cases:`, and fragment "
                f"'{terms[0][0]}' adds a term to it. The definition is summed as written, and a set of cases is no "
                f'one body: name the cased body as its own expression, and define {key!r} as that name.'
            )
        block: dict[str, object] = {}
        if base.get('dims'):
            block['dims'] = base['dims']
        if base.get('expression') is not None:
            bodies.insert(0, cast('str', base['expression']))
        if base.get('description'):
            block['description'] = base['description']
        block['expression'] = bodies[0] if len(bodies) == 1 else ' + '.join(_summand(body) for body in bodies)
        if 'description' not in block and entry.get('description'):
            block['description'] = entry['description']
        summed[key] = block
    return summed


def _landed(
    read: Mapping[str, dict[str, object]],
    defined: Mapping[str, object],
    key: str,
    contributors: list[str],
) -> None:
    """Refuse terms that name no ``expressions:`` block of any fragment.

    A term adds to a name another file declares: a sum with a frame and no
    body, or a definition. Terms alone would define a name nothing declared,
    which is what a mistyped name looks like, so the refusal names the near
    miss among the names a term could land on, which a term is not.
    """
    if key in defined:
        return
    known = {name for sections in read.values() for name in _mapping(sections.get('expressions'))} - {key}
    terms = {
        _mapping(entry).get('term')
        for sections in read.values()
        for entry in _mapping(_mapping(sections.get('given')).get('expressions')).values()
    }
    known -= terms
    spelled = ', '.join(f"'{name}'" for name in contributors[:-1])
    who = f"fragments {spelled} and '{contributors[-1]}' add" if spelled else f"fragment '{contributors[0]}' adds"
    near = f' {hint}' if (hint := did_you_mean(key, known, listing=False)) else ''
    raise LanguageError(
        f'{who} a term to {key!r}, which no fragment declares. A term adds to a name another file declares '
        f"under 'expressions:': declare it there, with a `dims:` and no body where the files add every term, "
        f'or fix the spelling.{near}'
    )


def _summand(body: str) -> str:
    """*body* as one operand of a sum: a term is a name and needs no brackets, and a definition may."""
    return body if body.isidentifier() else f'({body})'


def _as_mapping(block: object) -> dict[str, object]:
    """A named expression as ``to_dict`` wrote it, the one-line form read as its mapping."""
    return cast('dict[str, object]', block) if isinstance(block, dict) else {'expression': block}


def _folded(
    read: Mapping[str, dict[str, object]],
    merged: Mapping[str, object],
    loaded: Mapping[str, Spec],
    readings: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    """The ``given:`` block the composition still carries, once every reading a sibling introduces is spent.

    A given declaration is what a fragment expects of a name a sibling owns.
    Where the sibling is in the composition the expectation is checked and
    then dropped, so the composed spec declares the name once. A reader's
    description fills a declaration its owner left undescribed, and yields to
    one the owner wrote.
    """
    left: dict[str, object] = {}
    for kind, agreed in readings.items():
        introduced = _mapping(merged.get(kind))
        for key, block in agreed.items():
            _same_kind(read, merged, kind, key)
            if key in introduced:
                _fits(read, loaded, kind, key, block, introduced[key])
            if key in introduced and (said := _mapping(block).get('description')):
                owned = _as_mapping(introduced[key])
                if not owned.get('description'):
                    introduced[key] = {**owned, 'description': said}
        kept = {key: block for key, block in agreed.items() if key not in introduced}
        if kept:
            left[kind] = kept
    return left


def _reader_of(read: Mapping[str, dict[str, object]], kind: str, key: str) -> str:
    """The first fragment reading *key* under ``given: {kind}:``."""
    return next(name for name, sections in read.items() if key in _mapping(_readings(sections).get(kind)))


def _fits(
    read: Mapping[str, dict[str, object]],
    loaded: Mapping[str, Spec],
    kind: str,
    key: str,
    reading: object,
    introduced: object,
) -> None:
    """Refuse a reading that says more than the declaration it folds into.

    A reading states the frame its introducer declares, and every other field
    it writes is the introducer's. A given expression is the one kind whose
    frame may be wider than the composed body: a body over fewer dimensions
    broadcasts, and the composed load refuses a row it would repeat.
    """
    stated = set(cast('list[str]', _mapping(reading)['dims']))
    if kind == 'expressions':
        frame = set(_definer_frame(loaded, key))
        fits = frame <= stated
    else:
        frame = set(cast('list[str]', _mapping(introduced)['dims']))
        fits = frame == stated
    fields = {f: v for f, v in _mapping(_claims(reading)).items() if f != 'dims'}
    if fits and all(_mapping(introduced).get(f) == v for f, v in fields.items()):
        return
    how = f'over {sorted(frame)}' if kind == 'expressions' else f'as {introduced!r}'
    raise LanguageError(
        f"fragment '{_reader_of(read, kind, key)}' reads the {GIVEN_KINDS[kind]} {key!r} as {reading!r}, where "
        f"'{_author_of(read, kind, key)}' introduces it {how}. A given declaration says the same as the "
        f'declaration it is folded into, or less: restate the frame as the introducer declares it, or leave '
        f'the field out.'
    )


def _definer_frame(loaded: Mapping[str, Spec], key: str) -> frozenset[str]:
    """The frame of the composed body of *key*: the frame its owner declares, else its body's with every term's."""
    frame: set[str] = set()
    for spec in loaded.values():
        declared = spec.expressions[key].dims if key in spec.expressions else None
        if declared is not None:
            return frozenset(declared)
        if key in spec.program.expressions:
            frame |= set(spec.program.expressions[key].dims)
        given = spec.program.given.expressions.get(key)
        if given is not None and given.term is not None:
            frame |= dims_of(given.term, spec, f"Given expression '{key}'")
    return frozenset(frame)


#: The given kinds whose names share the flat namespace an expression reads.
#: A row family is named only in ``dual()``, apart from it.
READ_KINDS = ('parameters', 'variables', 'expressions')


def _same_kind(read: Mapping[str, dict[str, object]], merged: Mapping[str, object], kind: str, key: str) -> None:
    """Refuse a given declaration whose name a sibling introduces as another kind of thing."""
    if kind not in READ_KINDS:
        return
    for other in READ_KINDS:
        if other != kind and key in _mapping(merged.get(other)):
            raise LanguageError(
                f"fragment '{_reader_of(read, kind, key)}' reads {key!r} as a {GIVEN_KINDS[kind]}, where "
                f"'{_author_of(read, other, key)}' introduces it under '{other}:'. A given declaration reads a "
                f"name as the kind of thing its introducer declares: move it under 'given: {other}:'."
            )


def _summed_objective(read: Mapping[str, dict[str, object]]) -> dict[str, object] | None:
    """Every fragment's objective summed, each term in parentheses, or ``None`` where none declares one.

    The terms are summed in the fragments' name order, so the order they were
    passed in does not reach the expression. The first description in that
    order is carried, as a shared dimension's is. The senses have to agree: a sum has
    one sense, and negating the odd one out would be this function deciding what
    a spec means.
    """
    declared = {name: _mapping(sections['objective']) for name, sections in read.items() if sections.get('objective')}
    if not declared:
        return None
    senses = {name: objective.get('sense', 'minimize') for name, objective in declared.items()}
    if len(set(senses.values())) > 1:
        spelled = ', '.join(f"'{name}' {sense}s" for name, sense in sorted(senses.items()))
        raise LanguageError(
            f'the fragments disagree about which way the objective runs: {spelled}. A composed spec has '
            f'one objective and one sense, so write every fragment against the same one: negate the terms '
            f'of the odd one out rather than its sense.'
        )
    ordered = [objective for _, objective in sorted(declared.items())]
    terms = [objective['expression'] for objective in ordered]
    joined = terms[0] if len(terms) == 1 else ' + '.join(f'({term})' for term in terms)
    summed: dict[str, object] = {'sense': next(iter(senses.values())), 'expression': joined}
    if description := next((o['description'] for o in ordered if o.get('description')), None):
        summed['description'] = description
    return summed


def override(
    base: str | Path | Mapping[str, object] | Spec,
    patches: Mapping[str, str | Path | Mapping[str, object] | Spec],
) -> Spec:
    """*base* with each patch laid over it, and nothing laid over another patch.

    Args:
        base: The spec being extended: a YAML path, YAML text, a mapping, or a
            loaded [`Spec`][mathspec.spec.Spec].
        patches: What each patch is called, to the patch. The name is what an
            error calls it. The patches must write disjoint fields, so the
            order they are given in cannot change the result.

    Returns:
        The patched spec, loaded.

    Raises:
        LanguageError: The base does not load; the patched spec does not
            load; a patch edits or removes a declaration its base does not
            declare; a patch creates one that is not whole; a patch redeclares
            or removes a dimension or a relation; a patch sets a whole section
            to ``null``; or two patches write one field.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    read = {name: _declarations(patch) for name, patch in patches.items()}
    _disjoint(read)

    result = to_spec(base).to_dict()
    for name, patch in read.items():
        result = _lay_over(result, deepcopy(patch), name)
    return to_spec(result)


def _declarations(source: str | Path | Mapping[str, object] | Spec) -> dict[str, object]:
    """A patch as the mapping it declares, whatever shape it arrived in.

    Deliberately not [`to_spec`][mathspec.validation.to_spec]: a patch carrying a
    ``null`` or naming only the field it changes is not a spec.
    """
    if isinstance(source, Spec):
        return source.to_dict()
    if isinstance(source, Mapping):
        return dict(source)
    return read_spec(source)


def _mapping(value: object) -> dict[str, object]:
    """*value* as the mapping a section or a declaration is, an absent one read as empty.

    A file is read before it is validated, so nothing here has checked the
    shape; the closed schema refuses any other shape when the result loads.
    """
    return cast('dict[str, object]', value or {})


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


def _whole(cls: type[BaseModel], block: object) -> bool:
    """Whether *block* is a declaration on its own, which is what lets a patch create one."""
    try:
        cls.model_validate(block)
    except ValidationError:
        return False
    return True


def _incomplete(label: str, cls: type[BaseModel], block: object) -> str:
    """What *block* is short of, in the schema's own words rather than a second list."""
    fields = cls.model_fields
    missing = sorted(name for name, field in fields.items() if field.is_required() and name not in _mapping(block))
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


def _writes(patch: Mapping[str, object]) -> list[tuple[str, ...]]:
    """Every field *patch* writes, as a path.

    A removal is the declaration's own path, so it overlaps every edit inside
    that declaration: removing and editing one declaration is two patches
    disagreeing, whichever order they would have been laid in.
    """
    paths: list[tuple[str, ...]] = []
    for key, value in patch.items():
        if key in SECTIONS:
            for name, block in _mapping(value).items():
                paths.extend(_leaves((key, name), block))
        elif key == 'objective':
            paths.extend(_leaves(('objective',), value))
        else:
            paths.append((key,))
    return paths


def _leaves(prefix: tuple[str, ...], value: object) -> list[tuple[str, ...]]:
    """The paths *value* writes under *prefix*, a mapping being walked into and anything else a leaf."""
    if isinstance(value, dict) and value:
        return [leaf for key, inner in value.items() for leaf in _leaves((*prefix, key), inner)]
    return [prefix]


def _disjoint(read: Mapping[str, dict[str, object]]) -> None:
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


def _lay_over(base: dict[str, object], patch: dict[str, object], name: str) -> dict[str, object]:
    """One patch over one base, a section at a time, the base left as it was."""
    laid = dict(base)
    for key, value in patch.items():
        if key == 'given':
            laid[key] = _given(_mapping(laid.get(key)), _section(value, key, name), name)
        elif key in SHARED_SECTIONS:
            laid[key] = _shared(_mapping(laid.get(key)), _section(value, key, name), key, name)
        elif key in OWNED_SECTIONS:
            block = _section(value, key, name)
            laid[key] = _owned(_mapping(laid.get(key)), block, _singular(key), _entry_class(Spec, key), name)
        elif key == 'objective':
            laid = _objective(laid, value, name)
        elif value is None:
            laid.pop(key, None)
        else:
            laid[key] = value
    return laid


def _section(value: object, where: str, name: str) -> dict[str, object]:
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
    return cast('dict[str, object]', value)


def _given(declared: dict[str, object], patch: dict[str, object], name: str) -> dict[str, object]:
    """The ``given:`` block, one kind laid over at a time, so naming the columns keeps the row families.

    A kind the block does not have is carried as written, and the closed
    schema refuses it at load.
    """
    out = dict(declared)
    for kind, block in patch.items():
        if kind in GIVEN_KINDS:
            cls = _entry_class(GivenBlock, kind)
            entries = _section(block, f'given: {kind}:', name)
            out[kind] = _owned(_mapping(out.get(kind)), entries, GIVEN_KINDS[kind], cls, name)
        else:
            out[kind] = block
    return out


def _shared(declared: dict[str, object], patch: dict[str, object], section: str, name: str) -> dict[str, object]:
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
    declared: dict[str, object], patch: dict[str, object], label: str, cls: type[BaseModel], name: str
) -> dict[str, object]:
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


def _removed(out: dict[str, object], key: str, label: str, name: str) -> None:
    """Delete what the patch nulled, refusing a removal its base cannot satisfy."""
    if key not in out:
        raise LanguageError(
            f"patch '{name}' removes the {label} '{key}', which its base does not declare. "
            f'A removal is a claim about what is there, so a stale one is a patch that no longer describes '
            f'the spec it lands on. ' + did_you_mean(key, list(out))
        )
    del out[key]


def _objective(laid: dict[str, object], patch: object, name: str) -> dict[str, object]:
    """The one declaration that is not keyed by a name, laid over by the same three rules."""
    out = dict(laid)
    standing = out.get('objective')
    cls = _entry_class(Spec, 'objective')
    if patch is None:
        if standing is None:
            raise LanguageError(
                f"patch '{name}' removes the objective, which its base does not declare. A removal is a "
                f'claim about what is there, and a spec with no objective is already the feasibility '
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


def _field_by_field(under: object, over: object) -> object:
    """*over* laid on *under*: mappings merge, ``None`` drops the field, and everything else replaces.

    A dropped field takes the schema's default when the result loads, which
    is what makes ``upper: null`` an open bound and ``domain: null`` a
    continuous variable, whatever the schema lets a file write there.
    """
    if isinstance(under, dict) and isinstance(over, dict):
        merged = dict(under)
        for key, value in over.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = _field_by_field(merged.get(key), value)
        return merged
    return over
