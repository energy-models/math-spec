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
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent

PROPOSALS = ('per', 'keys', 'relations')

#: The pull request each proposal is open on, and how it says a map.
ABOUT = {
    'per': {
        'pr': 428,
        'name': 'per: conditioning',
        'line': 'The declaration keeps its arrow and names the dimensions the lookup varies along.',
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
FOCUS = re.compile(r'\bby=|\bover:|\bcolumns:|\bkey:|\binto:|\bper:|\bwhere:')

PROBLEMS = [
    {
        'id': 'p1',
        'demands': 'a lookup that varies along a second dimension',
        'title': 'A zone that changes by period',
        'prose': (
            'The generators bidding in a zone must meet its demand. Which zone a generator bids '
            'in changes by investment period, so the lookup is read at a period as well as at a '
            'generator. #161 opened this case, and all three proposals were written for it.'
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
        'title': 'A cap across a stay in a zone',
        'prose': (
            'This constraint reads the lookup of problem 1 the other way. Hold a generator and a '
            'zone, then sum its output over the periods it bid there. The table is the one the '
            'constraint above already uses. What differs is whether the file can say so with one '
            'declaration.'
        ),
        'show': ['zone_balance', 'history'],
        'verdict': {
            'per': (
                'two declarations',
                'per: fixes which dimension is consumed, so the other direction needs a second '
                'lookup. Nothing ties the two declarations together. To the loader they are two '
                'lookups, and a consumer binds two tables.',
            ),
            'keys': ('one table', 'The dot picks the other key. One declaration, two walks.'),
            'relations': ('one table', 'consume= picks the other key column. One declaration, two walks.'),
        },
    },
    {
        'id': 'p3',
        'demands': 'two columns over one dimension',
        'title': 'Nodal balance over lines',
        'prose': (
            'Flow leaves one bus and arrives at another, so a line carries two bus labels. The '
            'balance at a bus sums generation there, plus flow arriving, minus flow leaving. The '
            'second constraint drops any line whose two ends are the same bus.'
        ),
        'show': ['nodal', 'no_loop'],
        'verdict': {
            'per': (
                'two tables',
                'A lookup has one target, so the two ends are two lookups. per: adds nothing '
                'here, and the file is the one the language accepts today.',
            ),
            'keys': (
                'two tables',
                'The same file as per:. A column is named after its dimension and cannot appear '
                'twice, so the two ends stay two lookups.',
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
        'title': 'A cap per bus and technology',
        'prose': (
            'Each generator sits on a bus and has a technology. The cap applies to the pair, so '
            'the sum lands on both dimensions in one grouping. Each generator is counted once, '
            'at its own bus and its own technology.'
        ),
        'show': ['by_bus_and_tech'],
        'verdict': {
            'per': ('two tables', 'One lookup per value, and a by= list joins them at the call.'),
            'keys': ('two tables', 'The same file as per:.'),
            'relations': (
                'one table',
                'One table carries both value columns, and produce= lands on both in one join.',
            ),
        },
    },
    {
        'id': 'p5',
        'demands': 'a relation between two members of one dimension',
        'title': 'Neighbouring regions',
        'prose': (
            'A region is capped on what its neighbours produce. Neighbourhood carries no number. '
            'Two regions touch, or they do not, and each region touches several. Both columns of '
            'the lookup are regions, and that is what separates this case from every one above.'
        ),
        'show': ['neighbourhood'],
        'caption': (
            'Only #437 prints this. The other two columns have no file that loads, so there is '
            'nothing to compare it against.'
        ),
        'verdict': {
            'per': (
                'no rewrite',
                'The fallback for a relation is a parameter over the pair, and a parameter cannot '
                'name one dimension twice. There is nothing to fall back to.',
            ),
            'keys': (
                'no rewrite',
                'The same refusal. #436 adds the self-map to this proposal, and a self-map gives '
                'each region one neighbour. Neighbourhood gives it several.',
            ),
            'relations': (
                'one table',
                'Two roles over one dimension, and no key. Each region has many neighbours, so '
                'nothing is single-valued.',
            ),
        },
    },
]

#: What each proposal costs, quoted from its pull request and not measured here.
PRICE = {
    'per': '7 rules · no new call syntax · no declaration rewritten · +394 −67',
    'keys': '7 rules · a dot at the call · no declaration rewritten · +601 −161',
    'relations': '10 rules · consume=, produce=, within= · every declaration rewritten once · +2325 −1000',
}

#: What each proposal does with each capability, written out for every proposal
#: even where two of them do the same thing. The anchor links to the model that
#: measured it.
MATRIX = [
    (
        'A lookup that varies along a second dimension',
        'p1',
        {
            'per': 'one table, with per: [period] on the declaration',
            'keys': 'one table, with a second key and a dot at the call',
            'relations': 'one table, with a second key column',
        },
    ),
    (
        'The same table walked from its other key',
        'p2',
        {
            'per': 'a second declaration of the same table, which nothing ties to the first',
            'keys': 'one table, walked by=zone_of.period',
            'relations': 'one table, walked consume=period',
        },
    ),
    (
        "A line's two ends in one table",
        'p3',
        {
            'per': 'two lookups, one per end',
            'keys': 'two lookups, one per end',
            'relations': 'one table, with the roles bus0 and bus1',
        },
    ),
    (
        'Landing on two value columns at once',
        'p4',
        {
            'per': 'two lookups, joined by a by=[…] list at the call',
            'keys': 'two lookups, joined by a by=[…] list at the call',
            'relations': 'one table, landed by produce=[bus, technology]',
        },
    ),
    (
        'A masked sum: the produced dimension already carried',
        'masked',
        {
            'per': 'refused — the result would need bus twice',
            'keys': 'refused — the result would need bus twice',
            'relations': 'accepted — the produced column is joined on instead',
        },
    ),
    (
        'Unweighted many-to-many, as structure rather than data',
        'kinds',
        {
            'per': 'a table of ones, declared dtype: int because a flag cannot be multiplied',
            'keys': 'a table of ones, declared dtype: int because a flag cannot be multiplied',
            'relations': 'a lookup with no key',
        },
    ),
    (
        'A relation between two members of one dimension',
        'p5',
        {
            'per': 'no rewrite — a parameter cannot name one dimension twice',
            'keys': 'no rewrite — a parameter cannot name one dimension twice',
            'relations': 'one table, two roles over one dimension, no key',
        },
    ),
]

#: Every kind of pairing a model needs, in the order a reader meets them: what it
#: is in everyday terms, what it is in a model, and what each proposal writes for
#: it. Every line quoted here is a line of a file that was loaded: it is under
#: `models/` or `probes/`, and that branch's answer to it is in `evidence.json`.
#: Two proposals that spell a pairing the same way each carry their own copy,
#: because the page shows every proposal in every place.
KINDS = [
    {
        'shape': 'one each',
        'everyday': 'Every pupil is in one class.',
        'model': 'Every generator sits on one bus.',
        'by': {
            'per': ('a lookup', 'lookups:\n  gen_bus: { over: generator, into: bus }'),
            'keys': ('a lookup', 'lookups:\n  gen_bus: { over: generator, into: bus }'),
            'relations': (
                'a lookup with a key',
                'lookups:\n  gen_bus: { columns: [generator, bus], key: generator }',
            ),
        },
    },
    {
        'shape': 'one each, and it changes',
        'everyday': 'Every pupil is in one class, and the class changes each school year.',
        'model': 'Every generator bids in one zone, and the zone changes by period.',
        'by': {
            'per': (
                'the second dimension is a per:',
                'lookups:\n  zone_of: { over: generator, into: zone, per: [period] }',
            ),
            'keys': (
                'the second dimension is a second key',
                'lookups:\n  zone_of: { over: [generator, period], into: zone }',
            ),
            'relations': (
                'the second dimension is a second key column',
                'lookups:\n  zone_of: { columns: [generator, period, zone], key: [generator, period] }',
            ),
        },
    },
    {
        'shape': 'two named slots',
        'everyday': 'A journey has the station it leaves and the station it reaches.',
        'model': 'A line has a bus at each end, and the flow leaves one and arrives at the other.',
        'by': {
            'per': (
                'two lookups, so a line may sit in one table and not the other, which leaves an end open',
                'lookups:\n  line_bus0: { over: line, into: bus }\n  line_bus1: { over: line, into: bus }',
            ),
            'keys': (
                'two lookups, so a line may sit in one table and not the other, which leaves an end open',
                'lookups:\n  line_bus0: { over: line, into: bus }\n  line_bus1: { over: line, into: bus }',
            ),
            'relations': (
                'one table, each end a named role, and a row carries every column — so both ends exist',
                'lookups:\n  ends: { columns: { line: line, bus0: bus, bus1: bus }, key: line }',
            ),
        },
    },
    {
        'shape': 'one of its own kind',
        'everyday': 'Every pupil has one buddy, who is also a pupil.',
        'model': 'Every snapshot has one representative snapshot standing in for it.',
        'by': {
            'per': (
                'refused — a lookup maps into a different dimension',
                'lookups:\n  rep_of: { over: snapshot, into: snapshot }',
            ),
            'keys': (
                'the same file, refused on #433 and accepted on the #436 draft stacked on it',
                'lookups:\n  rep_of: { over: snapshot, into: snapshot }',
            ),
            'relations': (
                'a keyed self-map, where each end is a named role',
                'lookups:\n  represents: { columns: { snapshot: snapshot, stand_in: snapshot }, key: snapshot }',
            ),
        },
    },
    {
        'shape': 'many each, nothing to count',
        'everyday': 'A pupil can be in several clubs, and a club has several pupils.',
        'model': 'A generator bids into several reserve products, and each product takes many.',
        'by': {
            'per': (
                'a table of ones, declared int because a flag cannot be multiplied',
                'parameters:\n  eligible: { dims: [generator, product], dtype: int }',
            ),
            'keys': (
                'a table of ones, declared int because a flag cannot be multiplied',
                'parameters:\n  eligible: { dims: [generator, product], dtype: int }',
            ),
            'relations': (
                'a lookup with no key, which is the structure itself',
                'lookups:\n  eligible: { columns: [generator, product] }',
            ),
        },
    },
    {
        'shape': 'many each, of its own kind',
        'everyday': 'A pupil sits next to several others.',
        'model': 'A region touches several other regions.',
        'by': {
            'per': (
                'refused — a parameter cannot name one dimension twice, and no other rewrite is left',
                'parameters:\n  adjacent: { dims: [region, region], dtype: int }',
            ),
            'keys': (
                'refused — a parameter cannot name one dimension twice, and no other rewrite is left',
                'parameters:\n  adjacent: { dims: [region, region], dtype: int }',
            ),
            'relations': (
                'a bare self-relation, with a role for each side',
                'lookups:\n  adjacent: { columns: { region: region, neighbour: region } }',
            ),
        },
    },
    {
        'shape': 'many each, with a number on the pair',
        'everyday': 'Each pupil gets a number of biscuits at each club.',
        'model': 'Each generator delivers to each bus at some efficiency.',
        'by': {
            'per': (
                'a parameter, whose own rows are the pairing',
                'parameters:\n  efficiency: { dims: [generator, bus] }',
            ),
            'keys': (
                'a parameter, whose own rows are the pairing',
                'parameters:\n  efficiency: { dims: [generator, bus] }',
            ),
            'relations': (
                'a parameter, whose own rows are the pairing',
                'parameters:\n  efficiency: { dims: [generator, bus] }',
            ),
        },
    },
]

#: The caption under a problem's math, where every proposal reaches the same rows.
SAME_MATH = (
    'All three proposals print this. Only the name of the lookup changes, so the choice is about '
    'the file and not about the model it stands for.'
)


def option_row(proposal: str, body: str, *, pr: bool = False) -> str:
    """One proposal's own row: its colour, its name, and what it says here.

    The page shows every proposal in every place, even where two of them say
    the same thing, so a reader compares rows rather than decoding a mark.
    """
    link = (
        f'<a class="option-pr" href="https://github.com/energy-models/math-spec/pull/{ABOUT[proposal]["pr"]}">'
        f'#{ABOUT[proposal]["pr"]}</a>'
        if pr
        else ''
    )
    return (
        f'<div class="option" data-proposal="{proposal}">'
        f'<div class="option-name">{html.escape(ABOUT[proposal]["name"])}{link}</div>'
        f'<div class="option-body">{body}</div>'
        f'</div>'
    )


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


def model_row(problem: dict, ev: dict, proposal: str) -> str:
    """One proposal's own row for one problem: its verdict, its file, and what the loader said."""
    record = ev['models'][f'{problem["id"]}/{proposal}']
    body = strip_header(record['yaml'])
    verdict, note = problem['verdict'][proposal]
    word = 'verdict-word out' if not record['ok'] else 'verdict-word'
    if record['ok']:
        evidence = legend_html(list(dict.fromkeys(record['maps']))) + frame(record['constraints'], problem['show'])
    else:
        evidence = (
            f'<div class="frame refusal-frame"><span class="frame-label">the loader refuses it</span>'
            f'<pre>{html.escape(record["error"])}</pre></div>'
        )
    whole = (
        ''
        if excerpt(body) == body
        else f'<details class="whole"><summary>the whole file</summary>{yaml_html(body)}</details>'
    )
    return option_row(
        proposal,
        f'<p class="verdict"><span class="{word}">{html.escape(verdict)}</span>{html.escape(note)}</p>'
        f'{yaml_html(excerpt(body))}{whole}{evidence}',
        pr=True,
    )


def problem_section(problem: dict, ev: dict, index: int) -> str:
    latex = ev['models'][f'{problem["id"]}/relations']['latex']
    equations = ''.join(math(latex[name]) for name in problem['show'])
    rows = '\n'.join(model_row(problem, ev, proposal) for proposal in PROPOSALS)
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
  <div class="options">{rows}</div>
</section>"""


def refusal(ev: dict, probe: str, proposal: str) -> str:
    record = ev['probes'][probe]['by'][proposal]
    assert not record['ok'], f'{probe} loads under {proposal}, so it is not a refusal'
    return html.escape(record['error'])


def kinds_html() -> str:
    """One full-width row per kind, and inside every row the file that proposal writes.

    Two proposals that spell a pairing the same way each print it in full, because
    a reader comparing three files should not have to infer the third from a note.
    """
    cards = []
    for kind in KINDS:
        rows = ''
        for proposal in PROPOSALS:
            says, code = kind['by'][proposal]
            rows += option_row(
                proposal,
                f'<p class="kind-says">{html.escape(says)}</p><div class="kind-code">{yaml_html(code)}</div>',
            )
        cards.append(
            f'<article class="kind">'
            f'<p class="kind-shape">{html.escape(kind["shape"])}</p>'
            f'<p class="kind-everyday">{html.escape(kind["everyday"])}</p>'
            f'<p class="kind-model">{html.escape(kind["model"])}</p>'
            f'<div class="options tight">{rows}</div>'
            f'</article>'
        )
    return f'<div class="kinds">{"".join(cards)}</div>'


def masked_rows(ev: dict) -> str:
    """The masked sum, as a row per proposal: the same file, accepted once and refused twice."""
    source = yaml_html(excerpt(strip_header(ev['probes']['masked_rel']['yaml'])))
    rows = []
    for proposal in PROPOSALS:
        probe = 'masked_rel' if proposal == 'relations' else 'masked_flat'
        record = ev['probes'][probe]['by'][proposal]
        if record['ok']:
            body = (
                f'<p class="verdict"><span class="verdict-word">accepted</span>'
                f'The join on the produced column restricts each term to its own bus.</p>'
                f'{source}<div class="legend-line">{math(record["latex"]["masked"])}</div>'
            )
        else:
            body = (
                f'<p class="verdict"><span class="verdict-word out">refused</span>'
                f"The result would need bus twice, once as the operand's own dimension and once as "
                f'the group it is placed into.</p>'
                f'<div class="frame refusal-frame"><span class="frame-label">the loader refuses it</span>'
                f'<pre>{html.escape(record["error"])}</pre></div>'
            )
        rows.append(option_row(proposal, body, pr=True))
    return ''.join(rows)


def capabilities_html() -> str:
    """Every capability, with all three proposals written out under it."""
    blocks = []
    for label, anchor, says in MATRIX:
        heading = (
            f'<a href="#{anchor}">{html.escape(label)}</a>' if anchor not in ('masked', 'kinds') else html.escape(label)
        )
        rows = ''.join(option_row(p, html.escape(says[p])) for p in PROPOSALS)
        blocks.append(
            f'<section class="capability"><h3>{heading}</h3><div class="options tight">{rows}</div></section>'
        )
    price = ''.join(option_row(p, html.escape(PRICE[p]), pr=True) for p in PROPOSALS)
    blocks.append(
        f'<section class="capability price"><h3>What it costs, quoted from each pull request</h3>'
        f'<div class="options tight">{price}</div></section>'
    )
    return ''.join(blocks)


def build() -> str:
    """The page, with every slot in `template.html` filled from the evidence."""
    ev = json.loads((HERE / 'evidence.json').read_text())
    slots = {
        'sections': '\n'.join(problem_section(p, ev, i + 1) for i, p in enumerate(PROBLEMS)),
        'matrix': capabilities_html(),
        'kinds': kinds_html(),
        'eligible-bool': refusal(ev, 'eligible_ones_bool', 'keys'),
        'self-map-436': refusal(ev, 'self_map_into_itself', 'keys'),
        'adjacency-436': refusal(ev, 'adjacency_param', 'keys_436'),
        'built': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'),
        'base': ev['base'],
        'shas': ' · '.join(f'{ABOUT[p]["name"]} <code>{ev["branches"][p]["sha"]}</code>' for p in PROPOSALS),
        'keys-no-dot': refusal(ev, 'keys_no_dot', 'keys'),
        'rel-no-from': refusal(ev, 'rel_no_from', 'relations'),
        'per-history': refusal(ev, 'per_history', 'per'),
        'masked-refusal': refusal(ev, 'masked_flat', 'per'),
        'masked-rows': masked_rows(ev),
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
    # The pre-commit hooks strip trailing whitespace and demand a final
    # newline from every text file, generated or not, so emit the page that way
    # rather than let the hook rewrite what the generator wrote.
    page = '\n'.join(line.rstrip() for line in build().split('\n')).rstrip() + '\n'
    (HERE / 'index.html').write_text(page)
    print('comparison/index.html written')
