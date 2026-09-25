# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Cut `examples/pypsa.yaml` into topic fragments, and check that `merge` gives the same model back (experiment, #722).

Run from the repository root::

    python -m tools.pypsa_split split OUT   # write the topic fragments into OUT
    python -m tools.pypsa_split check OUT   # load each fragment, merge them, compare

A fragment reads what another topic declares under `given:`. A row or a named
expression that sums one term per component (a hub) becomes an additive
expression, and each component defines its own share of it, so a new
component is one new fragment.

`check` compares twice. The merged fragments against the one file with its
hubs written as additive expressions, in the canonical form. And that file
against `examples/pypsa.yaml`, row by row: every hub substituted back where it
is read, and every term of a row moved to one side.
"""

from __future__ import annotations

import argparse
import collections
import copy
import difflib
import itertools
import re
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mathspec import merge, to_spec
from mathspec._expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    operand,
    parse_expression,
    with_children,
)
from mathspec.canonical import canonical_dict, canonical_yaml, normalised
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
    'CVaR_omega': 'core',
    'GlobalConstraint_counts_snapshot': 'core',
    'GlobalConstraint_energy_weight': 'core',
    'GlobalConstraint_snapshot_closes': 'core',
    'scenario_opex': 'cost',
    'primary_energy': 'global_constraints',
    'operational_limit': 'global_constraints',
    'transmission_volume_expansion': 'global_constraints',
    'transmission_expansion_cost': 'global_constraints',
    'tech_capacity_expansion': 'global_constraints',
}

#: The rows that sum a term per component: each becomes `name == 0` over an
#: additive expression, which every component adds its terms to.
HUB_ROWS = {
    'Bus_nodal_balance': (
        'Bus_injection',
        'what every component puts into a bus, less what it takes out of it; PyPSA writes each term into '
        'the balance, and a load on its right-hand side',
    ),
    'Kirchhoff_Voltage_Law': (
        'Cycle_angle_sum',
        'the voltage angle differences around a cycle: every branch flow times its cycle weight, and every '
        'transformer phase shift',
    ),
}

#: The named expressions that sum a term per component, each made additive.
HUB_EXPRESSIONS = (
    'scenario_opex',
    'Carrier_additions',
    'primary_energy',
    'operational_limit',
    'tech_capacity_expansion',
    'transmission_volume_expansion',
    'transmission_expansion_cost',
)

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
    base = NAME_TOPIC.get(name) or PREFIX_TOPIC.get(prefix, 'core')
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


def _written(terms: list[Term]) -> str:
    """Signed terms as one expression, one term per line of a folded block."""
    (sign, head), *rest = terms
    first = str(head) if sign == '+' else f'-{operand(head)}'
    return '\n'.join([first, *(f'{s} {operand(node)}' for s, node in rest)])


def _entry(block: object) -> dict[str, Any]:
    """A named expression as a mapping, however the file wrote it."""
    return dict(block) if isinstance(block, dict) else {'expression': block}


class Model:
    """`examples/pypsa.yaml` with every hub written as an additive expression, and each hub's terms by topic."""

    def __init__(self, path: Path = SOURCE) -> None:
        text = path.read_text()
        self.original: dict[str, Any] = yaml.safe_load(text)
        self.data: dict[str, Any] = copy.deepcopy(self.original)
        self.blocks = _sliced(text)
        self.generated: set[Key] = set()
        for row, (name, description) in HUB_ROWS.items():
            block = self.data['constraints'][row]
            compared = parse_expression(block['expression'])
            assert isinstance(compared, ComparisonNode), f'{row} is a comparison'
            assert compared.op == '==', f'{row} is a balance'
            terms = [*_signed_terms(compared.left), *_signed_terms(compared.right, '-')]
            self.data['expressions'][name] = {
                'additive': True,
                'description': description,
                'expression': _written(terms),
            }
            self.data['constraints'][row] = {**block, 'expression': f'{name} == 0'}
            self.generated |= {('constraints', row), ('expressions', name)}
        for name in HUB_EXPRESSIONS:
            self.data['expressions'][name] = {'additive': True, **_entry(self.data['expressions'][name])}
            self.generated.add(('expressions', name))
        self.kind = {n: s for s in SECTIONS if s not in ('constraints', 'assumptions') for n in self.data.get(s, {})}
        self.shares: dict[str, dict[str, list[Term]]] = {}
        for name in (*(n for n, _ in HUB_ROWS.values()), *HUB_EXPRESSIONS):
            by_topic: dict[str, list[Term]] = collections.defaultdict(list)
            for sign, node in _signed_terms(parse_expression(self.data['expressions'][name]['expression'])):
                by_topic[self._owner(node)].append((sign, node))
            self.shares[name] = dict(by_topic)

    def _owner(self, node: ArithmeticNode) -> str:
        """The topic of a hub's term: the component whose variable it reads, else whose expression or data."""
        read = [n for n in IDENT.findall(str(node)) if n in self.kind and self.kind[n] not in FRAME]
        return topic(min(read, key=lambda n: ('variables', 'expressions', 'parameters').index(self.kind[n])))

    def names_in(self, value: object) -> set[str]:
        return _names_in(value, self.kind)

    def key(self, name: str) -> Key:
        return self.kind[name], name

    @property
    def keys(self) -> list[Key]:
        """Every declaration, in the order of the source file, the new hubs after the source's own."""
        return [*self.blocks, *sorted(k for k in self.generated if k not in self.blocks)]

    def frames(self) -> dict[str, tuple[str, ...]]:
        """The frame of every named expression, read off the one file with its hubs made additive."""
        return {name: e.dims for name, e in to_spec(self.data).program.expressions.items()}


# ---------------------------------------------------------------------------
# the fragments
# ---------------------------------------------------------------------------


def fragments(model: Model) -> dict[str, str]:
    """Each topic's fragment as YAML text: what it owns, its shares of the hubs, and what it reads under `given:`."""
    frames = model.frames()
    owned: dict[str, set[Key]] = collections.defaultdict(set)
    for key in model.keys:
        if key[0] not in FRAME and not (key[0] == 'expressions' and key[1] in model.shares):
            owned[topic(key[1])].add(key)
    sharing = {t for by_topic in model.shares.values() for t in by_topic}
    terms = _objective_terms(model)

    written = {}
    for name in sorted({*owned, *sharing, *terms}):
        mine = owned[name]
        my_shares = {hub: by_topic[name] for hub, by_topic in model.shares.items() if name in by_topic}
        read = set().union(
            *(model.names_in(model.data[s][n]) for s, n in mine),
            *(model.names_in(_written(t)) for t in my_shares.values()),
            *map(model.names_in, terms[name]),
        )
        defined = mine | {('expressions', hub) for hub in my_shares}
        given = {model.key(n) for n in read if model.key(n)[0] not in FRAME and model.key(n) not in defined}
        stated = {
            **{n: model.data[s][n]['dims'] for s, n in given if s in ('parameters', 'variables')},
            **{n: list(frames[n]) for s, n in given if s == 'expressions'},
        }
        frame_reads = read | set().union(*(model.names_in(dims) for dims in stated.values()))
        frame = {model.key(n) for n in frame_reads if model.key(n)[0] in FRAME}
        frame |= {model.key(n) for key in list(frame) for n in model.names_in(model.data[key[0]][key[1]])}
        written[name] = _fragment(model, mine | frame, my_shares, given, stated, terms[name])
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


def _block(model: Model, key: Key) -> str:
    """One declaration as the source wrote it, or as the hub rewrite wrote it."""
    if key not in model.generated:
        return model.blocks[key]
    section, name = key
    return _dumped(name, _entry(model.data[section][name]))


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
    shares: Mapping[str, list[Term]],
    given: set[Key],
    stated: Mapping[str, list[str]],
    terms: list[str],
) -> str:
    """One fragment as YAML text, its sections and declarations in the order of the source file."""
    parts = [HEADER]
    for section in SECTIONS:
        blocks = [_block(model, key) for key in model.keys if key[0] == section and key in included]
        if section == 'expressions':
            blocks += [_share(model, hub, share) for hub, share in shares.items()]
        if blocks:
            parts.append(f'{section}:\n' + '\n'.join(blocks) + '\n')
        if section == 'variables' and given:
            parts.append('given:\n' + ''.join(_given(model, kind, given, stated) for kind in GIVEN_KINDS))
    if terms:
        objective = model.data['objective']
        said = f'  description: >-\n    {objective["description"]}\n' if 'CVaR_omega' in ''.join(terms) else ''
        joined = '\n    + '.join(terms)
        parts.append(f'objective:\n  sense: minimize\n{said}  expression: >-\n    {joined}\n')
    return '\n'.join(parts)


def _share(model: Model, hub: str, terms: list[Term]) -> str:
    """One topic's share of a hub, under the hub's name, with the hub's description."""
    description = model.data['expressions'][hub].get('description')
    return _dumped(hub, {'additive': True, 'description': description, 'expression': _written(terms)})


#: The kinds a fragment reads under `given:`, and the fields of the source
#: declaration each restates beside the frame.
GIVEN_KINDS = {'parameters': ('dtype',), 'variables': ('domain',), 'expressions': ()}


def _given(model: Model, kind: str, given: set[Key], stated: Mapping[str, list[str]]) -> str:
    """One kind of a fragment's `given:` block, an entry per line in source order."""
    names = [n for s, n in model.keys if s == kind and (s, n) in given]
    if not names:
        return ''
    lines = [f'  {kind}:']
    for n in names:
        extra = {f: _entry(model.data[kind][n])[f] for f in GIVEN_KINDS[kind] if f in _entry(model.data[kind][n])}
        fields = {'dims': stated[n], **extra}
        spelled = ', '.join(f'{k}: [{", ".join(v)}]' if isinstance(v, list) else f'{k}: {v}' for k, v in fields.items())
        lines.append(f'    {n}: {{ {spelled} }}')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------


def _inlined(node: ArithmeticNode, bodies: Mapping[str, ArithmeticNode]) -> ArithmeticNode:
    """*node* with every name in *bodies* replaced by its body."""
    if isinstance(node, NameNode) and node.name in bodies:
        return bodies[node.name]
    return with_children(node, lambda child: _inlined(child, bodies))


def _row(text: str, bodies: Mapping[str, ArithmeticNode]) -> tuple[str, collections.Counter[tuple[str, str]]]:
    """A row or an expression as its operator and the multiset of its terms, every term on the left."""
    node = parse_expression(text)
    if isinstance(node, ComparisonNode):
        op = node.op
        terms = [*_signed_terms(_inlined(node.left, bodies)), *_signed_terms(_inlined(node.right, bodies), '-')]
    else:
        op, terms = '', list(_signed_terms(_inlined(node, bodies)))
    return op, collections.Counter((sign, str(normalised(term))) for sign, term in terms)


def same_rows(original: Mapping[str, Any], rewritten: Mapping[str, Any]) -> list[str]:
    """Every way *rewritten* states other rows than *original*, once the hubs *original* lacks are substituted.

    The declarations other than rows and named expressions are compared in the
    canonical form. A named expression is compared term by term, and one
    *original* does not declare has to be one of the hubs.
    """
    before, after = (canonical_dict(to_spec(dict(model))) for model in (original, rewritten))
    faults = [
        f'{section} differ'
        for section in ('dimensions', 'relations', 'parameters', 'variables', 'assumptions', 'macros')
        if before.get(section) != after.get(section)
    ]
    added = set(after['expressions']) - set(before['expressions'])
    faults += [f'{name} is new and is not a hub' for name in added - {n for n, _ in HUB_ROWS.values()}]
    bodies = {name: parse_expression(after['expressions'][name]['expression']) for name in added}

    def compared(label: str, one: Mapping[str, Any], two: Mapping[str, Any]) -> None:
        beside = [{k: v for k, v in side.items() if k not in ('expression', 'additive')} for side in (one, two)]
        if beside[0] != beside[1]:
            faults.append(f'{label} differs beside its expression')
        if _row(one['expression'], {}) != _row(two['expression'], bodies):
            faults.append(f'{label} states another row')

    if set(before['constraints']) != set(after['constraints']):
        faults.append('the constraints are not the same names')
    for name in before['constraints'].keys() & after['constraints'].keys():
        compared(f'constraint {name}', before['constraints'][name], after['constraints'][name])
    for name, entry in before['expressions'].items():
        one, two = _entry(entry), _entry(after['expressions'][name])
        if 'expression' in one:
            compared(f'expression {name}', one, two)
        elif one != two:
            faults.append(f'expression {name} differs')
    compared('the objective', before['objective'], after['objective'])
    return faults


def check(folder: Path) -> int:
    """Load each fragment in *folder*, merge them, and compare with the rewritten one file and with `examples/pypsa.yaml`."""
    model = Model()
    paths = {path.stem: path for path in sorted(folder.glob('*.yaml'))}
    failed = 0
    for name, path in paths.items():
        try:
            to_spec(path)
        except LanguageError as e:
            failed += 1
            print(f'{name} does not load alone: {e}')
    print(f'{len(paths) - failed}/{len(paths)} fragments load alone')
    rewritten = to_spec(model.data)
    try:
        merged = merge(paths, description=rewritten.description)
    except LanguageError as e:
        print(f'merge refuses the fragments: {e}')
        return 1
    one, composed = canonical_yaml(rewritten).splitlines(), canonical_yaml(merged).splitlines()
    diff = list(difflib.unified_diff(one, composed, 'one file', 'merged', lineterm=''))
    print('\n'.join(diff) if diff else 'the merged fragments and the one file have one canonical form')
    faults = same_rows(model.original, model.data)
    print('\n'.join(faults) if faults else f'the one file with additive hubs states the rows of {SOURCE}')
    return 1 if diff or failed or faults else 0


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
