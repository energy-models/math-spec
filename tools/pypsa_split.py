# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Cut `examples/pypsa.yaml` into topic fragments, and check that `merge` gives the one file back (experiment, #722).

Three commands, each run from the repository root::

    python -m tools.pypsa_split groups             # what forces declarations into one file
    python -m tools.pypsa_split split OUT          # write the topic fragments into OUT
    python -m tools.pypsa_split check OUT [--share]  # load each fragment, merge, compare canonical forms

``--share`` lets fragments declare one parameter or expression if the
declarations are the same, as `merge` allows for a dimension. Without it,
`merge` refuses the split. The flag patches `mathspec.composition` in this
process only.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import itertools
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from mathspec import composition, to_spec
from mathspec.canonical import canonical_yaml
from mathspec.errors import LanguageError

SOURCE = Path('examples/pypsa.yaml')
SECTIONS = ('dimensions', 'relations', 'parameters', 'variables', 'expressions', 'constraints', 'assumptions')
FRAME = ('dimensions', 'relations')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
HEADER = '# SPDX-FileCopyrightText: mathspec Contributors\n#\n# SPDX-License-Identifier: MIT\n'

#: The topic a declaration goes to, by the first word of its name.
PREFIX_TOPIC = {
    'Generator': 'generator',
    'Link': 'link',
    'Process': 'process',
    'StorageUnit': 'storage_unit',
    'Store': 'store',
    'Line': 'line',
    'Transformer': 'transformer',
    'Load': 'load',
    'Bus': 'network',
    'Kirchhoff': 'network',
    'CVaR': 'cvar',
    'Carrier': 'carrier',
    'GlobalConstraint': 'global_constraints',
    'Outage': 'security',
}

#: The system totals, whose names carry no component.
NAME_TOPIC = {
    'scenario_opex': 'cvar',
    'primary_energy': 'global_constraints',
    'operational_limit': 'global_constraints',
    'transmission_volume_expansion': 'global_constraints',
    'transmission_expansion_cost': 'global_constraints',
    'tech_capacity_expansion': 'global_constraints',
}

Key = tuple[str, str]


class Source:
    """`examples/pypsa.yaml` as parsed data, as source text per declaration, and as what each declaration reads."""

    def __init__(self, path: Path = SOURCE) -> None:
        text = path.read_text()
        self.data: dict[str, Any] = yaml.safe_load(text)
        self.blocks = _sliced(text)
        self.kind = {name: section for section, name in self.blocks if section not in ('constraints', 'assumptions')}
        self.reads = {key: self.names_in(self.data[key[0]][key[1]]) for key in self.blocks}

    def names_in(self, value: object) -> set[str]:
        """Every declared name *value* reads, prose left out."""
        if isinstance(value, str):
            return {token for token in IDENT.findall(value) if token in self.kind}
        if isinstance(value, dict):
            return set().union(*(self.names_in(v) for k, v in value.items() if k != 'description'))
        if isinstance(value, list):
            return set().union(*(self.names_in(v) for v in value))
        return set()

    def key(self, name: str) -> Key:
        return self.kind[name], name


def _sliced(text: str) -> dict[Key, str]:
    """The source lines of every declaration, cut where the next one at the same indent starts.

    Slicing text rather than dumping parsed data keeps each block's formatting,
    so a fragment reads like the file it was cut from.
    """
    lines = text.splitlines()
    starts: list[tuple[int, str | None, str | None]] = []
    section = None
    for i, line in enumerate(lines):
        if top := re.match(r'^([a-z_]+):', line):
            section = top.group(1)
            starts.append((i, section, None))
        elif (entry := re.match(r'^  ([A-Za-z_]\w*):', line)) and section in SECTIONS:
            starts.append((i, section, entry.group(1)))
    starts.append((len(lines), None, None))
    blocks = {}
    for (i, section, name), (j, _, _) in itertools.pairwise(starts):
        if section and name:
            blocks[section, name] = '\n'.join(lines[i:j]).rstrip()
    return blocks


def topic(name: str) -> str:
    """The fragment a declaration of *name* goes to."""
    if 'security' in name or 'BODF' in name:
        return 'security'
    return NAME_TOPIC.get(name) or PREFIX_TOPIC.get(name.split('_', maxsplit=1)[0], 'core')


def summands(expression: str) -> list[str]:
    """The top-level terms of a sum, split on each `+` outside brackets."""
    terms, depth, current = [], 0, ''
    for char in expression:
        depth += (char == '(') - (char == ')')
        if char == '+' and depth == 0:
            terms.append(current.strip())
            current = ''
        else:
            current += char
    return [*terms, current.strip()]


def groups(source: Source, shareable: tuple[str, ...]) -> list[list[Key]]:
    """The declarations that must share a file, when a fragment can read only *shareable* kinds from a sibling.

    The objective is left out: `merge` sums the objectives of the fragments.
    """
    parent = {key: key for key in source.blocks if key[0] not in FRAME}

    def root(key: Key) -> Key:
        while parent[key] != key:
            key = parent[key]
        return key

    for key in parent:
        for name in source.reads[key]:
            read = source.key(name)
            if read[0] not in (*FRAME, 'variables', 'constraints', *shareable):
                parent[root(key)] = root(read)
    joined = collections.defaultdict(list)
    for key in parent:
        joined[root(key)].append(key)
    return sorted(joined.values(), key=len, reverse=True)


def fragments(source: Source) -> dict[str, str]:
    """Each topic's fragment as YAML text: what it owns, the frame it uses, what it reads under `given:`, and copies.

    A parameter or expression a fragment reads from another topic is copied in,
    with everything it reads in turn, because `given:` takes only variables and
    constraints.
    """
    owned: dict[str, set[Key]] = collections.defaultdict(set)
    for key in source.blocks:
        if key[0] not in FRAME:
            owned[topic(key[1])].add(key)
    terms: dict[str, list[str]] = collections.defaultdict(list)
    for term in summands(source.data['objective']['expression']):
        names = source.names_in(term)
        if 'CVaR_omega' in names:
            terms['cvar'].append(term)
        else:
            terms[topic(next(name for name in sorted(names) if source.kind[name] == 'variables'))].append(term)

    written = {}
    for name in sorted(owned):
        included, given, seen = set(owned[name]), set(), set()
        todo = [*included, *(source.key(n) for n in set().union(*map(source.names_in, terms[name])))]
        while todo:
            key = todo.pop()
            if key in seen:
                continue
            seen.add(key)
            if key[0] == 'variables' and key not in owned[name]:
                given.add(key[1])
                todo += [source.key(n) for n in source.names_in(source.data['variables'][key[1]]['dims'])]
            else:
                included.add(key)
                todo += [source.key(n) for n in source.reads[key]]
        written[name] = _written(source, included, given, terms[name])
    return written


def _written(source: Source, included: set[Key], given: set[str], terms: list[str]) -> str:
    """One fragment as YAML text, its sections and declarations in the order of the source file."""
    parts = [HEADER]
    for section in SECTIONS:
        if keys := [key for key in source.blocks if key[0] == section and key in included]:
            parts.append(f'{section}:\n' + '\n'.join(source.blocks[key] for key in keys) + '\n')
        if section == 'variables' and given:
            frames = {
                name: {k: v for k, v in source.data['variables'][name].items() if k in ('dims', 'domain')}
                for name in sorted(given)
            }
            parts.append(yaml.safe_dump({'given': {'variables': frames}}, default_flow_style=None, sort_keys=False))
    if terms:
        parts.append('objective:\n  sense: minimize\n  expression: >-\n    ' + '\n    + '.join(terms) + '\n')
    return '\n'.join(parts)


def share_parameters_and_expressions() -> None:
    """Let `merge` take one parameter or expression from several fragments that declare it the same way."""
    shared = ('parameters', 'expressions')
    composition.SHARED_SECTIONS = (*composition.SHARED_SECTIONS, *shared)
    composition.OWNED_SECTIONS = tuple(s for s in composition.OWNED_SECTIONS if s not in shared)


def check(folder: Path, *, share: bool) -> int:
    """Load each fragment in *folder*, merge them, and print the canonical diff against `examples/pypsa.yaml`."""
    paths = {path.stem: path for path in sorted(folder.glob('*.yaml'))}
    failed = 0
    for name, path in paths.items():
        try:
            to_spec(path)
        except LanguageError as e:
            failed += 1
            print(f'{name} does not load alone: {e}')
    print(f'{len(paths) - failed}/{len(paths)} fragments load alone')
    if share:
        share_parameters_and_expressions()
    whole = to_spec(SOURCE)
    try:
        merged = composition.merge(paths, description=whole.description)
    except LanguageError as e:
        print(f'merge refuses the fragments: {e}')
        return 1
    diff = list(
        difflib.unified_diff(
            canonical_yaml(whole).splitlines(), canonical_yaml(merged).splitlines(), str(SOURCE), 'merged', lineterm=''
        )
    )
    print('\n'.join(diff) if diff else 'the canonical forms are identical')
    return 1 if diff or failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m tools.pypsa_split', description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('groups')
    commands.add_parser('split').add_argument('out', type=Path)
    checked = commands.add_parser('check')
    checked.add_argument('folder', type=Path)
    checked.add_argument('--share', action='store_true')
    args = parser.parse_args(argv)

    source = Source()
    if args.command == 'groups':
        for label, shareable in (
            ('variables, constraints', ()),
            ('and parameters', ('parameters',)),
            ('and parameters, expressions', ('parameters', 'expressions')),
        ):
            joined = groups(source, shareable)
            print(
                f'{label:32} {len(joined):4} groups, the largest {len(joined[0])} of {len(source.reads)} declarations'
            )
        return 0
    if args.command == 'split':
        args.out.mkdir(parents=True, exist_ok=True)
        for name, text in fragments(source).items():
            (args.out / f'{name}.yaml').write_text(text)
            print(f'{name:20} {len(text.splitlines()):5} lines')
        return 0
    return check(args.folder, share=args.share)


if __name__ == '__main__':
    sys.exit(main())
