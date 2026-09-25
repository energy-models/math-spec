# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Cut `examples/pypsa.yaml` into topic fragments, and check that `merge` gives the same spec back (experiment, #722).

Run from the repository root::

    python -m tools.pypsa_split split OUT   # write the topic fragments into OUT
    python -m tools.pypsa_split check OUT   # load each fragment, merge them, compare

The one file writes each hub, a row or a named expression that every component
adds its share to, as the sum of named terms: `Bus_injection` is
`Generator_injection + … + Transformer_injection`, and `Bus_nodal_balance`
reads `Bus_injection == 0`. A fragment owns the declarations of its topic, its
terms among them, and reads what another topic declares under `given:`; the
entry for a hub names the fragment's term. One fragment reads each hub with its
description, so a term always lands, and a new component is one new fragment.

`merge` then writes each hub as the file does, so `check` is one comparison:
the merged fragments and the one file have one canonical form.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import itertools
import re
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mathspec import merge, to_spec
from mathspec._expression_parser import BinaryOperatorNode, NumberNode, UnaryOperatorNode, operand, parse_expression
from mathspec.canonical import canonical_yaml
from mathspec.errors import LanguageError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from mathspec._expression_parser import ArithmeticNode

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
    'Kirchhoff': 'power_flow',
    'Cycle': 'power_flow',
    'CVaR': 'cost',
    'Carrier': 'carrier',
    'GlobalConstraint': 'global_constraints',
    'Outage': 'security',
}

#: The system totals, whose names carry no component, and the data every
#: topic reads: the risk preference, and how a snapshot counts in a global
#: constraint, which a component's share of one reads.
NAME_TOPIC = {
    'CVaR_omega': 'settings',
    'GlobalConstraint_counts_snapshot': 'settings',
    'GlobalConstraint_energy_weight': 'settings',
    'GlobalConstraint_snapshot_closes': 'settings',
    'scenario_opex': 'cost',
    'primary_energy': 'global_constraints',
    'operational_limit': 'global_constraints',
    'transmission_volume_expansion': 'global_constraints',
    'transmission_expansion_cost': 'global_constraints',
    'tech_capacity_expansion': 'global_constraints',
}

#: The hubs: the named expressions the one file writes as the sum of one term
#: per component. Two are what a balance row reads, the rest are totals.
HUBS = (
    'Bus_injection',
    'Cycle_angle_sum',
    'scenario_opex',
    'Carrier_additions',
    'primary_energy',
    'operational_limit',
    'tech_capacity_expansion',
    'transmission_volume_expansion',
    'transmission_expansion_cost',
)

#: The fragment that reads a hub with its description: the reader where a
#: model without it is never wanted, so the terms land nowhere without it, and
#: `settings` where the reader may go.
SUM_HOME = {'Bus_injection': 'network', 'Cycle_angle_sum': 'power_flow'}

#: The component each topic that adds a term is named after.
TOPIC_PREFIX = {topic: prefix for prefix, topic in PREFIX_TOPIC.items() if prefix[0].isupper()} | {
    'power_flow': 'Cycle'
}

Key = tuple[str, str]
Term = tuple[str, 'ArithmeticNode']


#: The components with unit commitment, whose declarations are cut by feature.
COMMITTABLE = ('Generator', 'Link', 'Process')

#: A feature of a committable component, by a pattern on the rest of the name;
#: the first that matches wins, and a name none matches is the component's own.
FEATURES = (
    ('maintenance', re.compile(r'maint')),
    ('ramping', re.compile(r'ramp|_rate$|allowance|previous_p$|p_init|came_in_running')),
    ('commitment', re.compile(r'status|start_up|shut_down|stand_by|committable|com_|must_stay|min_up|min_down|big_m')),
)


def topic(name: str) -> str:
    """The fragment a declaration of *name* goes to."""
    if 'security' in name or 'BODF' in name:
        return 'security'
    prefix, _, rest = name.partition('_')
    base = NAME_TOPIC.get(name) or PREFIX_TOPIC.get(prefix, 'settings')
    if prefix in COMMITTABLE:
        return next((f'{base}_{feature}' for feature, pattern in FEATURES if pattern.search(rest)), base)
    return base


# ---------------------------------------------------------------------------
# the source file
# ---------------------------------------------------------------------------


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


def _names_in(value: object, known: Mapping[str, str]) -> set[str]:
    """Every name in *known* that *value* reads, prose left out."""
    if isinstance(value, str):
        return {token for token in IDENT.findall(value) if token in known}
    if isinstance(value, dict):
        return set().union(*(_names_in(v, known) for k, v in value.items() if k != 'description'))
    if isinstance(value, list):
        return set().union(*(_names_in(v, known) for v in value))
    return set()


def _signed_terms(node: ArithmeticNode, sign: str = '+') -> Iterator[Term]:
    """*node* as a flat sum, each term with the sign it is written under, a minus carried into a bracket."""
    flip = {'+': '-', '-': '+'}
    if isinstance(node, BinaryOperatorNode) and node.op in ('+', '-'):
        yield from _signed_terms(node.left, sign)
        yield from _signed_terms(node.right, sign if node.op == '+' else flip[sign])
    elif isinstance(node, UnaryOperatorNode) and node.op == '-':
        yield from _signed_terms(node.operand, flip[sign])
    elif not (isinstance(node, NumberNode) and node.value == 0):
        yield sign, node


def _entry(block: object) -> dict[str, Any]:
    """A named expression as a mapping, however the file wrote it."""
    return dict(block) if isinstance(block, dict) else {'expression': block}


class Model:
    """`examples/pypsa.yaml`, with each hub's terms and the topic each term belongs to."""

    def __init__(self, path: Path = SOURCE) -> None:
        text = path.read_text()
        self.data: dict[str, Any] = yaml.safe_load(text)
        self.blocks = _sliced(text)
        self.kind = {n: s for s in SECTIONS if s not in ('constraints', 'assumptions') for n in self.data.get(s, {})}
        #: hub -> the topic of each term -> the term, in the order the topics sort in.
        self.shares: dict[str, dict[str, str]] = {}
        for hub in HUBS:
            terms = IDENT.findall(_entry(self.data['expressions'][hub])['expression'])
            by_topic = {self._owner(_entry(self.data['expressions'][term])['expression']): term for term in terms}
            assert len(by_topic) == len(terms), f'{hub}: one term per topic'
            self.shares[hub] = dict(sorted(by_topic.items()))
        #: term -> the hub it adds to.
        self.terms = {term: hub for hub, by_topic in self.shares.items() for term in by_topic.values()}
        frames = self.frames()
        self.sums = {
            hub: {'dims': list(frames[hub]), 'description': _entry(self.data['expressions'][hub]).get('description')}
            for hub in HUBS
        }

    def _owner(self, text: str) -> str:
        """The topic of a term: the component whose variable it reads, else whose expression or data."""
        read = [n for n in IDENT.findall(text) if n in self.kind and self.kind[n] not in FRAME]
        return topic(min(read, key=lambda n: ('variables', 'expressions', 'parameters').index(self.kind[n])))

    def names_in(self, value: object) -> set[str]:
        return _names_in(value, self.kind)

    def key(self, name: str) -> Key:
        return self.kind[name], name

    @property
    def keys(self) -> list[Key]:
        """Every declaration, in the order of the source file."""
        return list(self.blocks)

    def frames(self) -> dict[str, tuple[str, ...]]:
        """The frame of every named expression, read off the one file."""
        return {name: e.dims for name, e in to_spec(self.data).program.expressions.items()}

    def home(self, name: str) -> str:
        """The fragment that reads the hub *name* with its description."""
        return SUM_HOME.get(name, 'settings')


# ---------------------------------------------------------------------------
# the fragments
# ---------------------------------------------------------------------------


def fragments(model: Model) -> dict[str, str]:
    """Each topic's fragment as YAML text: what it owns, its terms among it, and what it reads under `given:`."""
    frames = model.frames()
    owned: dict[str, set[Key]] = collections.defaultdict(set)
    for key in model.keys:
        if key[0] not in FRAME and not (key[0] == 'expressions' and (key[1] in HUBS or key[1] in model.terms)):
            owned[topic(key[1])].add(key)
    for by_topic in model.shares.values():
        for name, term in by_topic.items():
            owned[name].add(('expressions', term))
    terms = _objective_terms(model)
    homes = {model.home(hub) for hub in HUBS}

    written = {}
    for name in sorted({*owned, *terms, *homes}):
        mine = owned[name]
        adds = {hub: by_topic[name] for hub, by_topic in model.shares.items() if name in by_topic}
        homes_here = {hub for hub in HUBS if model.home(hub) == name}
        read = set().union(
            *(model.names_in(model.data[s][n]) for s, n in mine), *map(model.names_in, terms[name]), homes_here, adds
        )
        given = {model.key(n) for n in read if model.key(n)[0] not in FRAME and model.key(n) not in mine}
        stated = {
            **{n: model.data[s][n]['dims'] for s, n in given if s in ('parameters', 'variables')},
            **{n: list(frames[n]) for s, n in given if s == 'expressions'},
        }
        frame_reads = read | set().union(*(model.names_in(dims) for dims in stated.values()))
        frame = {model.key(n) for n in frame_reads if model.key(n)[0] in FRAME}
        frame |= {model.key(n) for key in list(frame) for n in model.names_in(model.data[key[0]][key[1]])}
        written[name] = _fragment(model, mine | frame, given, stated, terms[name], adds, homes_here)
    return written


def _objective_terms(model: Model) -> dict[str, list[str]]:
    """The objective's terms by topic, the operating cost and its tail with the risk rows."""
    terms: dict[str, list[str]] = collections.defaultdict(list)
    for sign, node in _signed_terms(parse_expression(model.data['objective']['expression'])):
        names = model.names_in(str(node))
        if 'CVaR_omega' in names:
            owner = 'cost'
        else:
            owner = topic(next(n for n in sorted(names) if model.kind[n] == 'variables'))
        terms[owner].append(str(node) if sign == '+' else f'-{operand(node)}')
    return terms


def _dumped(name: str, block: Mapping[str, object]) -> str:
    """A generated declaration, its long text folded one term per line."""
    lines = [f'  {name}:']
    for field, value in block.items():
        if value is None:
            continue
        if isinstance(value, str) and field in ('expression', 'description') and ('\n' in value or len(value) > 80):
            body = (
                value.split('\n')
                if field == 'expression'
                else textwrap.wrap(value, 72, break_on_hyphens=False, break_long_words=False)
            )
            lines += [f'    {field}: >-', *(f'      {line}' for line in body)]
        else:
            dumped = yaml.safe_dump(value, default_flow_style=True, width=1000).removesuffix('\n...\n')
            lines.append(f'    {field}: {dumped.strip()}')
    return '\n'.join(lines)


def _fragment(
    model: Model,
    included: set[Key],
    given: set[Key],
    stated: Mapping[str, list[str]],
    terms: list[str],
    adds: Mapping[str, str],
    homes: set[str],
) -> str:
    """One fragment as YAML text, its sections and declarations in the order of the source file."""
    parts = [HEADER]
    for section in SECTIONS:
        blocks = [model.blocks[key] for key in model.keys if key[0] == section and key in included]
        if blocks:
            parts.append(f'{section}:\n' + '\n'.join(blocks) + '\n')
        if section == 'variables' and given:
            parts.append('given:\n' + ''.join(_given(model, kind, given, stated, adds, homes) for kind in GIVEN_KINDS))
    if terms:
        objective = model.data['objective']
        said = f'  description: >-\n    {objective["description"]}\n' if 'CVaR_omega' in ''.join(terms) else ''
        joined = '\n    + '.join(terms)
        parts.append(f'objective:\n  sense: minimize\n{said}  expression: >-\n    {joined}\n')
    return '\n'.join(parts)


#: The kinds a fragment reads under `given:`, and the fields of the source
#: declaration each restates beside the frame.
GIVEN_KINDS = {'parameters': ('dtype',), 'variables': ('domain',), 'expressions': ()}


def _given(
    model: Model, kind: str, given: set[Key], stated: Mapping[str, list[str]], adds: Mapping[str, str], homes: set[str]
) -> str:
    """One kind of a fragment's `given:` block, an entry per line in source order: a term it adds, a hub's prose."""
    names = [n for s, n in model.keys if s == kind and (s, n) in given]
    if not names:
        return ''
    lines = [f'  {kind}:']
    for n in names:
        if kind == 'expressions' and n in homes:
            entry = {
                'dims': stated[n],
                **({'term': adds[n]} if n in adds else {}),
                'description': model.sums[n]['description'],
            }
            lines.append(_dumped(n, entry).replace('\n', '\n  ').replace(f'  {n}:', f'    {n}:', 1))
            continue
        extra = {f: _entry(model.data[kind][n])[f] for f in GIVEN_KINDS[kind] if f in _entry(model.data[kind][n])}
        if kind == 'expressions' and n in adds:
            extra['term'] = adds[n]
        fields = {'dims': stated[n], **extra}
        spelled = ', '.join(f'{k}: [{", ".join(v)}]' if isinstance(v, list) else f'{k}: {v}' for k, v in fields.items())
        lines.append(f'    {n}: {{ {spelled} }}')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# the check
# ---------------------------------------------------------------------------


def check(folder: Path) -> int:
    """Load each fragment in *folder*, merge them, and compare the canonical form with `examples/pypsa.yaml`."""
    paths = {path.stem: path for path in sorted(folder.glob('*.yaml'))}
    failed = 0
    for name, path in paths.items():
        try:
            to_spec(path)
        except LanguageError as e:
            failed += 1
            print(f'{name} does not load alone: {e}')
    print(f'{len(paths) - failed}/{len(paths)} fragments load alone')
    one = to_spec(SOURCE)
    try:
        merged = merge(paths, description=one.description)
    except LanguageError as e:
        print(f'merge refuses the fragments: {e}')
        return 1
    diff = list(
        difflib.unified_diff(
            canonical_yaml(one).splitlines(), canonical_yaml(merged).splitlines(), 'one file', 'merged', lineterm=''
        )
    )
    print('\n'.join(diff) if diff else 'the merged fragments and the one file have one canonical form')
    return 1 if diff or failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m tools.pypsa_split', description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('split').add_argument('out', type=Path)
    commands.add_parser('check').add_argument('folder', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'split':
        args.out.mkdir(parents=True, exist_ok=True)
        for name, text in fragments(Model()).items():
            (args.out / f'{name}.yaml').write_text(text)
            print(f'{name:20} {len(text.splitlines()):5} lines')
        return 0
    return check(args.folder)


if __name__ == '__main__':
    sys.exit(main())
