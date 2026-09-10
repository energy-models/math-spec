# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Write `index.html` from the models in `models/` and the output in `evidence.json`.

Every YAML block on the page is a file that `verify.py` loaded on the branch of
the proposal it sits under, every frame is the one the loader reported, and every
equation is the one that branch's typesetter printed. Nothing on the page is
typed by hand except the prose.

    python comparison/verify.py && python comparison/build.py
"""

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent

PROPOSALS = ('per', 'keys', 'relations')

#: The pull request each proposal is open on, and how it says a map.
ABOUT = {
    'per': {
        'pr': 428,
        'name': 'per: conditioning',
        'line': 'The declaration keeps its arrow and names the dimensions the map varies along.',
        'state': 'draft',
    },
    'keys': {
        'pr': 433,
        'name': 'keys and a dot',
        'line': 'The declaration takes a list of keys, and the call names the key it walks.',
        'state': 'open, review requested',
    },
    'relations': {
        'pr': 437,
        'name': 'relations',
        'line': 'The declaration is a table of columns with a key, and the call names both ends of the walk.',
        'state': 'open, review requested',
    },
}

#: A line carries the proposal where it declares a lookup or walks one.
FOCUS = re.compile(r'\bby=|\bover:|\bkey:|\binto:|\bper:|\bwhere:')

PROBLEMS = [
    {
        'id': 'p1',
        'demands': 'a map that varies along a second dimension',
        'title': 'A generator bids in a zone, and the zone changes by period',
        'prose': (
            'Zonal demand must be met by the generators bidding in that zone. Which zone a '
            'generator bids in is not fixed: it is agreed per investment period. So the map from '
            'generator to zone is read at a period as well as at a generator. This is the case '
            '#161 opened, and the one all three proposals were written for.'
        ),
        'show': ['zone_balance'],
        'verdict': {
            'per': ('one table', 'The call is unchanged from a one-key lookup.'),
            'keys': ('one table', 'The call names the key it walks.'),
            'relations': ('one table', 'The call names the column it consumes.'),
        },
    },
    {
        'id': 'p2',
        'demands': 'the same table, walked from its other key',
        'title': 'A cap on what one generator produced across its stay in a zone',
        'prose': (
            'The same map, read the other way: hold a generator and a zone, and sum its output '
            'over the periods it bid there. The table is the one the constraint above already '
            'uses. What differs between the proposals is whether the file can say so.'
        ),
        'show': ['zone_balance', 'history'],
        'verdict': {
            'per': (
                'two declarations',
                'per: fixes which dimension is consumed, so the other direction is a second '
                'lookup. Nothing ties the two declarations together: to the loader they are two '
                'maps, and a consumer binds two tables.',
            ),
            'keys': ('one table', 'The dot picks the other key. One declaration, two walks.'),
            'relations': ('one table', 'from= picks the other key column. One declaration, two walks.'),
        },
    },
    {
        'id': 'p3',
        'demands': 'two columns over one dimension',
        'title': 'Nodal balance, where a line has two ends',
        'prose': (
            'Flow leaves one bus and arrives at another, so a line carries two bus labels. The '
            'balance at a bus sums generation there, plus flow arriving, minus flow leaving. The '
            'guard below drops any line whose two ends are the same bus.'
        ),
        'show': ['nodal', 'no_loop'],
        'verdict': {
            'per': (
                'two tables',
                'A lookup has one target, so the two ends are two lookups. This is what the '
                'language does today, and per: adds nothing to it.',
            ),
            'keys': (
                'two tables',
                'Same as per:. A column named after its dimension cannot appear twice, so the two '
                'ends stay two lookups.',
            ),
            'relations': (
                'one table',
                'Roles name the two columns, so both ends are one table with one key. The legend '
                'prints one map into a product.',
            ),
        },
    },
    {
        'id': 'p4',
        'demands': 'landing on two value columns at once',
        'title': 'A capacity cap per bus and technology',
        'prose': (
            'Each generator sits on a bus and has a technology. The cap applies to the pair, so '
            'the sum must land on both dimensions in one grouping — a generator is counted once, '
            'at its own bus and its own technology.'
        ),
        'show': ['by_bus_and_tech'],
        'verdict': {
            'per': ('two tables', 'One lookup per value, and a by= list joins them at the call.'),
            'keys': ('two tables', 'Same as per:.'),
            'relations': (
                'one table',
                'One table carries both value columns, and into= lands on both in one join.',
            ),
        },
    },
    {
        'id': 'p5',
        'demands': 'a relation between two members of one dimension',
        'title': 'Which regions are neighbours',
        'prose': (
            'A region is capped on what its neighbours produce. Neighbourhood is symmetric and '
            'carries no number: two regions touch, or they do not. Both columns of the relation '
            'are regions, and that is what makes this case different from every one above.'
        ),
        'show': ['neighbourhood'],
        'caption': (
            'Only #437 prints this. The other two columns have no file that loads, so there is '
            'nothing to compare the math against.'
        ),
        'verdict': {
            'per': (
                'no rewrite',
                'The fallback for a relation is a parameter over the pair, and a parameter cannot '
                'name one dimension twice. There is nothing to fall back to.',
            ),
            'keys': (
                'no rewrite',
                'The same refusal. #436 adds the self-map to this proposal, but a self-map is one '
                'neighbour per region; neighbourhood is many.',
            ),
            'relations': (
                'one table',
                'Two roles over one dimension, and no key: each region has many neighbours and '
                'nothing is single-valued.',
            ),
        },
    },
]

#: What each proposal costs, beyond what it can say. Every row is quoted from the
#: pull request that proposes it, and none of it is measured here.
PRICE = [
    ('Rules the reference states', {'per': '7', 'keys': '7', 'relations': '10'}),
    ('Call syntax beyond by=', {'per': 'none', 'keys': 'a dot', 'relations': 'from=, into='}),
    (
        'Existing declarations rewritten',
        {'per': 'none', 'keys': 'none', 'relations': 'all, once'},
    ),
    (
        'Diff against main',
        {'per': '+394 −67', 'keys': '+601 −161', 'relations': '+2026 −723'},
    ),
]

MATRIX = [
    ('A map that varies along a second dimension', 'p1', {'per': 1, 'keys': 1, 'relations': 1}),
    ('The same table walked from its other key', 'p2', {'per': 0, 'keys': 1, 'relations': 1}),
    ("A line's two ends in one table", 'p3', {'per': 0, 'keys': 0, 'relations': 1}),
    ('Landing on two value columns at once', 'p4', {'per': 0, 'keys': 0, 'relations': 1}),
    ('A masked sum: the produced dimension already carried', 'masked', {'per': -1, 'keys': -1, 'relations': 1}),
    ('Unweighted many-to-many, as structure not data', 'kinds', {'per': 0, 'keys': 0, 'relations': 1}),
    ('A relation between two members of one dimension', 'p5', {'per': -1, 'keys': -1, 'relations': 1}),
]

#: Every kind of pairing a model needs, in the order a reader meets them: what it
#: is in everyday terms, what it is in a model, how it is spelled, and what each
#: proposal does with it. Each `says` entry is measured — the file is under
#: `models/` or `probes/` and the branch's own answer is in `evidence.json`.
KINDS = [
    {
        'shape': 'one each',
        'everyday': 'Every pupil is in one class.',
        'model': 'Every generator sits on one bus.',
        'code': [
            ('relations', 'gen_bus: { over: [generator, bus], key: generator }'),
            ('per: and keys', 'gen_bus: { over: generator, into: bus }'),
        ],
        'says': {
            'per': ('yes', 'a lookup'),
            'keys': ('yes', 'a lookup'),
            'relations': ('yes', 'a lookup with a key'),
        },
    },
    {
        'shape': 'one each, and it changes',
        'everyday': 'Every pupil is in one class, and the class changes each school year.',
        'model': 'Every generator bids in one zone, and the zone changes by period.',
        'code': [
            ('relations', 'zone_of: { over: [generator, period, zone], key: [generator, period] }'),
            ('keys', 'zone_of: { over: [generator, period], into: zone }'),
        ],
        'says': {
            'per': ('yes', 'per: [period]'),
            'keys': ('yes', 'a second key'),
            'relations': ('yes', 'a second key column'),
        },
    },
    {
        'shape': 'two named slots',
        'everyday': 'A seesaw has a left seat and a right seat, and a pupil sits on each.',
        'model': 'A line has one bus at each end, and the two ends are not interchangeable.',
        'code': [('relations', 'ends: { over: { line: line, bus0: bus, bus1: bus }, key: line }')],
        'says': {
            'per': ('workaround', 'two lookups'),
            'keys': ('workaround', 'two lookups'),
            'relations': ('yes', 'one table, two roles'),
        },
    },
    {
        'shape': 'one of its own kind',
        'everyday': 'Every pupil has one buddy, who is also a pupil.',
        'model': 'Every snapshot has one representative snapshot that stands in for it.',
        'code': [
            ('relations', 'represents: { over: { snapshot: snapshot, stand_in: snapshot }, key: snapshot }'),
            ('keys, with #436', 'rep_of: { over: snapshot, into: snapshot }'),
        ],
        'says': {
            'per': ('no', 'refused: maps into itself'),
            'keys': ('workaround', 'only with #436'),
            'relations': ('yes', 'a keyed self-map'),
        },
    },
    {
        'shape': 'many each, nothing to count',
        'everyday': 'A pupil can be in several clubs, and a club has several pupils.',
        'model': 'A generator can bid into several reserve products, and each product has many.',
        'code': [
            ('relations', 'eligible: { over: [generator, product] }'),
            ('per: and keys', 'eligible: { dims: [generator, product], dtype: int }  # a table of ones'),
        ],
        'says': {
            'per': ('workaround', 'ones, and int not bool'),
            'keys': ('workaround', 'ones, and int not bool'),
            'relations': ('yes', 'a lookup with no key'),
        },
    },
    {
        'shape': 'many each, of its own kind',
        'everyday': 'Which pupils sit next to each other.',
        'model': 'Which regions are neighbours.',
        'code': [('relations', 'adjacent: { over: { region: region, neighbour: region } }')],
        'says': {
            'per': ('no', 'no rewrite exists'),
            'keys': ('no', 'no rewrite exists'),
            'relations': ('yes', 'a bare self-relation'),
        },
    },
    {
        'shape': 'many each, with a number on the pair',
        'everyday': 'How many biscuits each pupil gets at each club.',
        'model': 'The efficiency with which a generator feeds a bus.',
        'code': [('every proposal', 'efficiency: { dims: [generator, bus] }')],
        'says': {
            'per': ('yes', 'a parameter'),
            'keys': ('yes', 'a parameter'),
            'relations': ('yes', 'a parameter'),
        },
    },
]

#: The caption under a problem's math, where every proposal reaches the same rows.
SAME_MATH = (
    'The math is the same under all three proposals. Only the name of the map changes, so the '
    'file is what the choice is about, not the printed model.'
)

CELL = {
    1: ('one table', 'yes'),
    0: ('two of them', 'workaround'),
    -1: ('refused', 'no'),
}


def excerpt(yaml: str) -> str:
    """The lines that carry the proposal: the `lookups:` block, and every constraint that walks one.

    The three files differ only here, so the side-by-side view shows this and the
    tabbed view shows the whole file. A constraint keeps its name, or the reader
    cannot tell which row an `expression:` belongs to.
    """
    out: list[str] = []
    block = ''
    pending = ''
    declares = 'lookups' if 'lookups:' in yaml else 'parameters'
    for line in yaml.splitlines():
        if line and not line[0].isspace():
            block = line.split(':')[0]
            pending = ''
            if block == declares:
                out.extend(['', line] if out else [line])
            continue
        if block == declares and line.strip():
            out.append(line)
        elif block == 'constraints' and line.strip():
            key = line.strip().split(':')[0]
            if line.startswith('  ') and not line.startswith('    '):
                pending = line
            elif key in ('expression', 'where'):
                if pending:
                    out.extend(['', pending] if out else [pending])
                    pending = ''
                out.append(line)
    return '\n'.join(out).strip()


def strip_header(yaml: str) -> str:
    body = yaml.split('\n')
    while body and (body[0].startswith('#') or not body[0].strip()):
        body.pop(0)
    return '\n'.join(body).rstrip()


def yaml_html(text: str) -> str:
    """One `<pre>`'s worth of YAML, with the lines that carry the proposal marked."""
    rows = []
    for line in text.split('\n'):
        classes = 'line' + (' focus' if FOCUS.search(line) else '')
        rows.append(f'<span class="{classes}">{colour(line)}</span>')
    return '<pre class="yaml"><code>' + '\n'.join(rows) + '</code></pre>'


def colour(line: str) -> str:
    """Colour a YAML line: comments, keys and the operator words a call is made of."""
    if not line.strip():
        return ''
    comment = ''
    if '#' in line and not line.strip().startswith('- '):
        head, _, tail = line.partition('#')
        if head.count('"') % 2 == 0:
            line, comment = head, '#' + tail
    out = html.escape(line)
    out = re.sub(r'^(\s*)([\w.]+)(:)', r'\1<b class="k">\2</b>\3', out)
    out = re.sub(r'\b(sum|at|shift|position|sum_back)\(', r'<b class="fn">\1</b>(', out)
    out = re.sub(r'\b(by|from|into|over|key|per)=', r'<b class="kw">\1</b>=', out)
    if comment:
        out += f'<i class="c">{html.escape(comment)}</i>'
    return out


def math(latex: str) -> str:
    return f'<div class="math">$$ {html.escape(latex)} $$</div>'


#: The script capitals the typesetter uses for a set, as Unicode. Six of the
#: twenty-six live in the letterlike block rather than the mathematical one.
SCRIPT = {
    'B': 'ℬ',
    'E': 'ℰ',
    'F': 'ℱ',
    'H': 'ℋ',
    'I': 'ℐ',
    'L': 'ℒ',
    'M': 'ℳ',
    'R': 'ℛ',
}


def legend_text(latex: str) -> str:
    """A legend entry as text — `zone_of: 𝒢 × ℰ → 𝒵` — rather than as math to typeset.

    Each panel carries one, so 24 of them would otherwise wait on MathJax to read
    at all. The six display equations still do.
    """
    out = latex
    out = re.sub(r'\\mathcal\{([A-Z])\}', lambda m: SCRIPT.get(m[1], chr(0x1D49C + ord(m[1]) - 65)), out)
    out = re.sub(r'\\mathrm\{(.+?)\}', lambda m: m[1].replace(r'\_', '_'), out)
    for tex, char in ((r'\times', '×'), (r'\to', '→'), (r'\subseteq', '⊆'), (r'\in', '∈')):
        out = out.replace(tex, char)
    return re.sub(r'\s+', ' ', out.replace(r'\ ', ' ')).strip()


def legend_html(entries: list[str]) -> str:
    maps: list[str] = []
    for entry in entries:
        for one in re.split(r',\s+(?=[A-Za-z_][\w]*:)', legend_text(entry)):
            if one not in maps:
                maps.append(one)
    cells = ''.join(f'<code class="map">{html.escape(one)}</code>' for one in maps)
    return f'<div class="legend-line"><span class="frame-label">legend prints</span>{cells}</div>'


def frame(dims: dict[str, list[str]], names: list[str]) -> str:
    cells = ''.join(
        f'<div class="frame-row"><code>{html.escape(n)}</code>'
        f'<span class="arrow">→</span>'
        f'<code class="dims">[{", ".join(html.escape(d) for d in dims[n])}]</code></div>'
        for n in names
    )
    return f'<div class="frame"><span class="frame-label">loader reports</span>{cells}</div>'


def refused_panel(proposal: str, verdict: str, note: str, source: str, error: str) -> str:
    """A panel for a model the branch refuses: the attempt, and what it said."""
    return (
        f'<article class="panel refused" data-proposal="{proposal}">'
        f'<header class="panel-head">'
        f'<span class="chip">{html.escape(ABOUT[proposal]["name"])}</span>'
        f'<a class="pr" href="https://github.com/energy-models/math-spec/pull/{ABOUT[proposal]["pr"]}">#{ABOUT[proposal]["pr"]}</a>'
        f'</header>'
        f'<p class="verdict"><span class="verdict-word out">{html.escape(verdict)}</span>'
        f'{html.escape(note)}</p>'
        f'{yaml_html(source)}'
        f'<div class="frame refusal-frame"><span class="frame-label">the loader refuses it</span>'
        f'<pre>{html.escape(error)}</pre></div>'
        f'</article>'
    )


def panels(problem: dict, ev: dict, mode: str) -> str:
    out = []
    for proposal in PROPOSALS:
        record = ev['models'][f'{problem["id"]}/{proposal}']
        body = strip_header(record['yaml'])
        verdict, note = problem['verdict'][proposal]
        source = excerpt(body) if mode == 'grid' else body
        if not record['ok']:
            out.append(refused_panel(proposal, verdict, note, source, record['error']))
            continue
        maps = legend_html(list(dict.fromkeys(record['maps'])))
        out.append(
            f'<article class="panel" data-proposal="{proposal}">'
            f'<header class="panel-head">'
            f'<span class="chip">{html.escape(ABOUT[proposal]["name"])}</span>'
            f'<a class="pr" href="https://github.com/energy-models/math-spec/pull/{ABOUT[proposal]["pr"]}">#{ABOUT[proposal]["pr"]}</a>'
            f'</header>'
            f'<p class="verdict"><span class="verdict-word">{html.escape(verdict)}</span>'
            f'{html.escape(note)}</p>'
            f'{yaml_html(source)}'
            f'{maps}'
            f'{frame(record["constraints"], problem["show"])}'
            f'</article>'
        )
    return '\n'.join(out)


def problem_section(problem: dict, ev: dict, index: int) -> str:
    latex = ev['models'][f'{problem["id"]}/relations']['latex']
    equations = ''.join(math(latex[name]) for name in problem['show'])
    return f"""
<section class="problem" id="{problem['id']}">
  <div class="prose">
    <p class="eyebrow"><span class="num">{index}</span><span class="what">demands</span>
      {html.escape(problem['demands'])}</p>
    <h2>{html.escape(problem['title'])}</h2>
    <p>{html.escape(problem['prose'])}</p>
  </div>
  <div class="math-block">
    {equations}
    <p class="caption">{html.escape(problem.get('caption', SAME_MATH))}</p>
  </div>
  <div class="compare grid-view">{panels(problem, ev, 'grid')}</div>
  <div class="compare tab-view">{panels(problem, ev, 'full')}</div>
</section>"""


def refusal(ev: dict, probe: str, proposal: str) -> str:
    record = ev['probes'][probe]['by'][proposal]
    assert not record['ok'], f'{probe} loads under {proposal}, so it is not a refusal'
    return html.escape(record['error'])


def kinds_html() -> str:
    """One card per kind of pairing, with the everyday reading above the model one."""
    cards = []
    for kind in KINDS:
        code = ''.join(
            f'<div class="kind-code"><span class="kind-code-label">{html.escape(label)}</span>{yaml_html(line)}</div>'
            for label, line in kind['code']
        )
        says = ''.join(
            f'<span class="says" data-proposal="{p}">'
            f'<span class="mark {kind["says"][p][0]}"></span>'
            f'<b>{html.escape(ABOUT[p]["name"].replace(": conditioning", ":").replace(" and a dot", ""))}</b>'
            f'{html.escape(kind["says"][p][1])}</span>'
            for p in PROPOSALS
        )
        cards.append(
            f'<article class="kind">'
            f'<p class="kind-shape">{html.escape(kind["shape"])}</p>'
            f'<p class="kind-everyday">{html.escape(kind["everyday"])}</p>'
            f'<p class="kind-model">{html.escape(kind["model"])}</p>'
            f'{code}'
            f'<div class="kind-says">{says}</div>'
            f'</article>'
        )
    return f'<div class="kinds">{"".join(cards)}</div>'


def matrix_html() -> str:
    head = ''.join(
        f'<th data-proposal="{p}">{html.escape(ABOUT[p]["name"])}<span class="th-pr">#{ABOUT[p]["pr"]}</span></th>'
        for p in PROPOSALS
    )
    rows = []
    for label, anchor, cells in MATRIX:
        tds = ''
        for p in PROPOSALS:
            word, kind = CELL[cells[p]]
            tds += f'<td data-proposal="{p}"><span class="mark {kind}">{word}</span></td>'
        link = f'<a href="#{anchor}">{html.escape(label)}</a>' if anchor != 'masked' else html.escape(label)
        rows.append(f'<tr><th scope="row">{link}</th>{tds}</tr>')
    price = []
    for label, cells in PRICE:
        tds = ''.join(
            f'<td data-proposal="{p}"><span class="price">{html.escape(cells[p])}</span></td>' for p in PROPOSALS
        )
        price.append(f'<tr class="price-row"><th scope="row">{html.escape(label)}</th>{tds}</tr>')
    return f"""
<table class="matrix">
  <thead><tr><th scope="col">What the file can say</th>{head}</tr></thead>
  <tbody>{''.join(rows)}</tbody>
  <tbody class="price-body">
    <tr class="section-row"><th scope="row" colspan="4">What it costs — quoted from the pull requests, not measured here</th></tr>
    {''.join(price)}
  </tbody>
</table>"""


def build() -> str:
    """The page, with every slot in `template.html` filled from the evidence."""
    ev = json.loads((HERE / 'evidence.json').read_text())
    masked = ev['probes']['masked_rel']
    masked_load = masked['by']['relations']
    slots = {
        'sections': '\n'.join(problem_section(p, ev, i + 1) for i, p in enumerate(PROBLEMS)),
        'matrix': matrix_html(),
        'kinds': kinds_html(),
        'eligible-bool': refusal(ev, 'eligible_ones_bool', 'keys'),
        'self-map-436': refusal(ev, 'self_map_into_itself', 'keys'),
        'adjacency-436': refusal(ev, 'adjacency_param', 'keys_436'),
        'base': ev['base'],
        'shas': ' · '.join(f'{ABOUT[p]["name"]} <code>{ev["branches"][p]["sha"]}</code>' for p in PROPOSALS),
        'keys-no-dot': refusal(ev, 'keys_no_dot', 'keys'),
        'rel-no-from': refusal(ev, 'rel_no_from', 'relations'),
        'per-history': refusal(ev, 'per_history', 'per'),
        'masked-refusal': refusal(ev, 'masked_flat', 'per'),
        'masked-yaml': yaml_html(excerpt(strip_header(masked['yaml']))),
        'masked-math': math(masked_load['latex']['masked']),
        'tabs': ''.join(
            f'<button class="tab" type="button" id="tab-{p}" data-proposal="{p}" '
            f'aria-pressed="false">{html.escape(ABOUT[p]["name"])}'
            f'<span class="tab-pr">#{ABOUT[p]["pr"]}</span></button>'
            for p in PROPOSALS
        ),
        'cards': ''.join(
            f'<div class="card" data-proposal="{p}">'
            f'<a class="card-pr" href="https://github.com/energy-models/math-spec/pull/{ABOUT[p]["pr"]}">#{ABOUT[p]["pr"]}</a>'
            f'<h3>{html.escape(ABOUT[p]["name"])}</h3>'
            f'<p>{html.escape(ABOUT[p]["line"])}</p>'
            f'<p class="state">{html.escape(ABOUT[p]["state"])}</p>'
            f'</div>'
            for p in PROPOSALS
        ),
    }
    page = (HERE / 'template.html').read_text()
    for name, value in slots.items():
        page = page.replace(f'<!--{{{name}}}-->', value)
    left = re.findall(r'<!--\{[a-z-]+\}-->', page)
    assert not left, f'template slots left unfilled: {left}'
    return page


if __name__ == '__main__':
    (HERE / 'index.html').write_text(build())
    print('comparison/index.html written')
