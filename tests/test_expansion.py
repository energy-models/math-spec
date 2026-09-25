# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and macros — YAML-defined, schema-local, expanded to core AST at load."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from functools import partial

import pytest

from mathspec.errors import LanguageError
from mathspec.expansion import parse_and_expand
from mathspec.program import Multiply, Named, Parameter, Sum, Translate, Variable
from mathspec.resolution import Namespace
from tests.fixtures import DISPATCH_MODEL, SMALL_MODEL, comparison_of, expression_of, schema_of

WEIGHTED_SUM = {
    'args': ['array', 'weights'],
    'kwargs': ['over'],
    'template': 'sum(array * weights, over=over)',
}

schema = partial(schema_of, DISPATCH_MODEL)


def _resolved(text, ns):
    """*text* as its program tree, or as its two sides and the sense between them where it compares."""
    if any(op in text for op in ('<=', '>=', '==')):
        return comparison_of(text, ns, 'expression')
    return expression_of(text, ns, 'expression')


def _bodies(resolved):
    """*resolved* with every named expression's body standing bare where its name was."""
    if isinstance(resolved, Named):
        return _bodies(resolved.body)
    if isinstance(resolved, tuple):
        return tuple(_bodies(part) for part in resolved)
    if is_dataclass(resolved) and not isinstance(resolved, type):
        return replace(resolved, **{f.name: _bodies(getattr(resolved, f.name)) for f in fields(resolved) if f.init})
    return resolved


@pytest.mark.parametrize(
    ('expressions', 'macros', 'call', 'want'),
    [
        pytest.param(
            {'gen_cost': 'p * cost'},
            {},
            'sum(gen_cost, over=generator)',
            'sum(p * cost, over=generator)',
            id='a-named-expression-splices',
        ),
        pytest.param(
            {'gen_cost': 'p * cost', 'total_cost': 'sum(gen_cost, over=generator)'},
            {},
            'total_cost + 1',
            'sum(p * cost, over=generator) + 1',
            id='named-expressions-nest',
        ),
        pytest.param(
            {'total_gen': 'sum(p, over=generator)'},
            {},
            'total_gen == load',
            'sum(p, over=generator) == load',
            id='a-comparison-at-the-top',
        ),
        pytest.param(
            {},
            {'weighted_sum': WEIGHTED_SUM},
            'weighted_sum(p, cost, over=generator)',
            'sum(p * cost, over=generator)',
            id='a-macro-expands',
        ),
        pytest.param(
            {},
            {'double': {'args': ['load'], 'template': 'load + load'}},
            'double(p)',
            'p + p',
            id='a-formal-shadows-the-model-name-it-shares',
        ),
        pytest.param(
            {'gen_cost': 'p * cost'},
            {'twice': {'args': ['x'], 'template': 'x + x'}},
            'twice(gen_cost)',
            '(p * cost) + (p * cost)',
            id='a-macro-argument-may-be-a-named-expression',
        ),
        pytest.param(
            {},
            {
                'total': {'args': ['x'], 'template': 'sum(x, over=generator)'},
                'total_cost': {'template': 'total(p * cost)'},
            },
            'total_cost()',
            'sum(p * cost, over=generator)',
            id='a-macro-body-may-call-a-macro',
        ),
        pytest.param(
            {'sc': 'm(p)'},
            {'m': {'args': ['sc'], 'template': 'sc + 1'}},
            'sc',
            'p + 1',
            id='a-formal-shadows-a-named-expression-so-it-is-not-a-cycle',
        ),
        pytest.param(
            {f'e{i}': f'e{i + 1} + 1' for i in range(80)} | {'e80': 'p'},
            {},
            'e0',
            ' + '.join(['p', *['1'] * 80]),
            id='a-long-acyclic-chain-expands',
        ),
    ],
)
def test_a_call_expands_to_core_ast(expressions, macros, call, want):
    """The math a call expands to is what `want` spells; a named expression's
    body arrives under the `Named` node carrying its name, which `_bodies`
    inlines, as lowering does."""
    ns = Namespace(schema(expressions=expressions, macros=macros))
    assert _bodies(_resolved(call, ns)) == _resolved(want, ns)


def test_a_named_expression_arrives_under_the_node_carrying_its_name():
    ns = Namespace(schema(expressions={'gen_cost': 'p * cost'}))
    resolved = expression_of('sum(gen_cost, over=generator)', ns, 'e')
    assert resolved == Sum(Named('gen_cost', Multiply(Variable('p'), Parameter('cost'))), ('generator',)), (
        'the body is inlined resolved and the name kept, for the typesetter to define it once'
    )
    assert isinstance(resolved, Sum)
    assert resolved.operand is expression_of('gen_cost', ns, 'another use'), 'every use reads the one node'


@pytest.mark.parametrize(
    ('expressions', 'match'),
    [
        pytest.param({'a': 'b + 1', 'b': 'a + 1'}, 'circular expression reference: a -> b -> a', id='a-cycle'),
        pytest.param({'bad': 'p == load'}, 'must not contain a comparison', id='a-comparison'),
        pytest.param({'load': 'p * cost'}, 'collides with the parameter of the same name', id='a-parameter-collision'),
        pytest.param(
            {'broken': 'sum(nope, over=generator)'},
            "Named expression 'broken'",
            id='a-typo-in-a-named-expression',
        ),
    ],
)
def test_a_bad_named_expression_is_refused_at_load(expressions, match):
    with pytest.raises(LanguageError, match=match):
        schema(expressions=expressions)


@pytest.mark.parametrize(
    ('expressions', 'macros', 'chain'),
    [
        pytest.param({'a': 'b + 1', 'b': 'a + 1'}, {}, 'a -> b -> a', id='through-an-entry'),
        pytest.param(
            {'a': 'm(load)'}, {'m': {'args': ['x'], 'template': 'x + a'}}, 'a -> m -> a', id='through-a-macro'
        ),
        pytest.param(
            {'a': 'b + 1', 'b': 'm(1)'},
            {'m': {'args': ['x'], 'template': 'x + a'}},
            'a -> b -> m -> a',
            id='through-an-entry-and-a-macro',
        ),
        pytest.param(
            {
                'a': {'dims': ['snapshot'], 'cases': {'x': {'when': 'b > 0', 'expression': '1'}}, 'otherwise': '2'},
                'b': 'a + 1',
            },
            {},
            'a -> b -> a',
            id='through-the-when-of-a-case',
        ),
    ],
)
def test_a_cycle_is_reported_with_the_chain_that_closes_it(expressions, macros, chain):
    """A cycle closed through a macro was reported as `a -> a`, the macro left out, and one closed through a case's `when` was a `RecursionError`."""
    with pytest.raises(LanguageError, match=f'circular expression reference: {chain}$') as exc:
        schema(expressions=expressions, macros=macros)
    assert str(exc.value).count('circular') == 1, 'the cycle is reported once, where it closes'


def test_a_refusal_names_its_context_once():
    with pytest.raises(LanguageError) as exc:
        schema(expressions={'a': 'a + 1'})
    assert str(exc.value).count("Named expression 'a'") == 1, 'the context is prefixed once, not once per pass'


@pytest.mark.parametrize(
    ('call', 'match'),
    [
        pytest.param('ws(p, over=generator)', 'expects 2 positional', id='too-few-positionals'),
        pytest.param('ws(p, cost)', 'keyword argument', id='a-missing-keyword'),
    ],
)
def test_macro_arity_errors(call, match):
    with pytest.raises(LanguageError, match=match):
        parse_and_expand(call, Namespace(schema(macros={'ws': WEIGHTED_SUM})), 'expression')


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'macros': {'load': {'args': ['a'], 'template': 'a'}}},
            'collides with the parameter of the same name',
            id='a-parameter',
        ),
        pytest.param(
            {'expressions': {'thing': 'p * cost'}, 'macros': {'thing': {'args': ['a'], 'template': 'a'}}},
            'collides with the named expression',
            id='a-named-expression',
        ),
        pytest.param(
            {'macros': {'sum': {'args': ['a'], 'template': 'a'}}},
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator',
        ),
        pytest.param(
            {'dimensions.sum': {'dtype': 'int'}},
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator-taken-by-a-dimension',
        ),
        pytest.param(
            {'macros': {'m': {'args': ['generator'], 'template': 'p * generator'}}},
            "formal 'generator' collides with declared dimension 'generator'",
            id='a-formal-named-after-a-dimension',
        ),
    ],
)
def test_macro_collisions_rejected(patch, match):
    """Helper names are reserved for every kind of declaration, not just macros."""
    with pytest.raises(LanguageError, match=match):
        schema(**patch)


@pytest.mark.parametrize(
    ('macros', 'match'),
    [
        pytest.param(
            {'loop_a': {'template': 'loop_b() + 1'}, 'loop_b': {'template': 'loop_a() + 1'}},
            'circular macro reference',
            id='a-cycle',
        ),
        pytest.param(
            {'m': {'args': ['a'], 'kwargs': ['a'], 'template': 'a'}}, 'duplicate formal', id='a-duplicate-formal'
        ),
        pytest.param(
            {'unused': {'args': ['x'], 'template': 'x * cots'}},
            r"Macro 'unused'.*'cots' not found",
            id='a-typo-in-a-template-nothing-calls',
        ),
        pytest.param(
            {'bad': {'args': ['a', 'b'], 'template': 'a == b'}},
            'must not contain a comparison',
            id='a-comparison-in-a-template',
        ),
        pytest.param(
            {'lag': {'args': ['x'], 'template': 'shift(x, along=snapshot, offset=nope)'}},
            r"Macro 'lag'.*'nope' not found",
            id='a-typo-in-an-amount',
        ),
        pytest.param(
            {'grouped': {'args': ['x'], 'template': 'sum(x, by=nope)'}},
            r"Macro 'grouped'.*sum\(by=nope\) does not name a relation",
            id='a-typo-in-a-relation-kwarg',
        ),
        pytest.param(
            {'grouped': {'args': ['x'], 'template': 'sum(x, by=[nope, also])'}},
            r"Macro 'grouped'.*sum\(by=\[nope, also\]\) names 2 relations",
            id='a-list-of-relations',
        ),
        pytest.param(
            {'grouped': {'args': ['x', 'a', 'b'], 'template': 'sum(x, by=nope, over=a, into=b)'}},
            r"Macro 'grouped'.*sum\(by=nope\) does not name a relation or a formal of this macro",
            id='a-typo-in-a-relation-beside-formal-columns',
        ),
        pytest.param(
            {'reduced': {'args': ['x'], 'template': 'sum(x, over=nope)'}},
            r"Macro 'reduced'.*sum\(over=nope\) does not name a declared dimension or a formal of this macro",
            id='a-typo-in-a-dimension',
        ),
        pytest.param(
            {'lag': {'args': ['x'], 'template': 'shift(x, along=snapshot, offset=0.5)'}},
            r"Macro 'lag'.*shift\(offset=...\) must be a whole number",
            id='a-fractional-offset',
        ),
    ],
)
def test_macro_templates_validated_even_when_unused(macros, match):
    """A typo in a template the model never calls is still caught at load.

    The relation beside formal columns loaded once the columns were formals,
    because the formals sent the call back before the relation's name was
    read; a fractional offset in a template nothing calls loaded before the
    form of an amount was decided in resolution.
    """
    with pytest.raises(LanguageError, match=match):
        schema(macros=macros)


def test_an_entry_nothing_reads_is_held_to_the_rules_a_use_is():
    """`sum(k)` over a scalar loaded as an unread entry, since the bare sum was only decided where the math read it."""
    with pytest.raises(LanguageError, match=r"Named expression 'e1': sum\(\) with no over= or by=.*already a scalar"):
        schema_of(SMALL_MODEL, expressions={'e1': 'sum(k)'})


@pytest.mark.parametrize(
    ('template', 'match'),
    [
        pytest.param('x * tag', "Macro 'm': 'tag' is declared dtype: str", id='a-label-parameter-as-a-value'),
        pytest.param('sum(x, by=lk, over=nope, into=h)', "over=nope names no column of 'lk'", id='a-typo-in-a-column'),
    ],
)
def test_a_template_is_held_to_the_rules_a_call_site_is(template, match):
    """A template nothing calls was checked for names only: a label parameter or an unknown column passed load."""
    with pytest.raises(LanguageError, match=match):
        schema_of(SMALL_MODEL, macros={'m': {'args': ['x'], 'template': template}})


@pytest.mark.parametrize('fragment', ['my_python_helper', 'macros:', 'docs/about/limits.md'])
def test_an_unknown_operator_is_refused_at_load_with_the_rewrite(fragment):
    with pytest.raises(LanguageError) as exc:
        schema(constraints={'c': {'dims': ['snapshot'], 'expression': 'my_python_helper(p) <= load'}})
    assert fragment in str(exc.value)


def test_an_unknown_operator_names_no_construct_the_language_lacks():
    """The refusal told the author to "use a declared escape", and the schema has no `escape:` key."""
    with pytest.raises(LanguageError) as exc:
        schema(constraints={'c': {'dims': ['snapshot'], 'expression': 'my_python_helper(p) <= load'}})
    assert 'escape' not in str(exc.value), 'the message points at a key the closed schema refuses'


@pytest.mark.parametrize(
    ('formals', 'template'),
    [
        pytest.param(['x', 'e'], 'shift(x, along=g, offset=1, edge=e)', id='an-edge'),
        pytest.param(['row'], 'dual(row)', id='a-constraint'),
        pytest.param(['x', 'rel', 'a', 'b'], 'sum(x, by=rel, over=a, into=b)', id='a-relation-and-its-columns'),
        pytest.param(['x', 'a', 'b'], 'sum(x, by=lk, over=a, into=b)', id='the-columns-of-a-declared-relation'),
        pytest.param(
            ['x', 'd'], 'shift(x, along=d, offset=1, by=lk, within=h)', id='the-dimension-a-partition-steps-along'
        ),
        pytest.param(
            ['x', 'd'], 'sum_back(x, along=d, window=2, by=lk, within=h)', id='the-dimension-a-window-runs-along'
        ),
    ],
)
def test_a_formal_stands_where_a_call_site_will_bind_it(formals, template):
    """A formal has no kind until a call binds it, so the template check leaves it bare in every slot.

    A formal `along=` beside a `by=` was handed to the partition as if it were
    a dimension, and refused as one the relation has no key column over.
    """
    assert (
        schema_of(SMALL_MODEL, macros={'m': {'args': formals, 'template': template}}).macros['m'].template == template
    )


def test_a_call_binding_the_dimension_a_partition_steps_along_builds_it():
    """The call site is where the formal gets its kind, so the partition is built there."""
    template = 'shift(x, along=d, offset=1, by=lk, within=h)'
    ns = Namespace(schema_of(SMALL_MODEL, macros={'m': {'args': ['x', 'd'], 'template': template}}))
    node = expression_of('m(p, g)', ns, 'expression')
    assert isinstance(node, Translate) and node.along == 'g'
    assert node.partition is not None and node.partition.name == 'lk', 'the relation is read once along= is bound'


def test_a_named_expression_is_resolved_once_however_many_uses(monkeypatch):
    """Every use parsed, expanded and resolved the entry again, and a cased one's arms with it."""
    from mathspec import resolution

    resolved: list[str] = []
    named = resolution._named

    def counted(name, *args):
        resolved.append(name)
        return named(name, *args)

    monkeypatch.setattr(resolution, '_named', counted)
    schema(
        expressions={'gen_cost': 'p * cost', 'total': 'sum(gen_cost, over=generator) + sum(gen_cost, over=generator)'},
        constraints={'balance': {'dims': ['snapshot'], 'expression': 'sum(gen_cost, over=generator) >= load'}},
    )
    assert sorted(resolved) == ['gen_cost', 'total'], 'three uses of gen_cost, one resolution'


def test_a_use_of_a_refused_named_expression_names_it_rather_than_repeating_its_fault():
    with pytest.raises(LanguageError) as exc:
        schema(expressions={'a': 'b + 1', 'b': 'nope'})
    message = str(exc.value)
    assert message.count("'nope' not found") == 1, 'the fault is the entry that holds it'
    assert "Named expression 'a': named expression 'b' does not load" in message
