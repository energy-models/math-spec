# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Prototype: the EBNF in docs/reference/language/expressions.md, by hand.

A regex tokenizer and a recursive descent. Written to measure, not to merge:
it produces the existing node types and nothing else, so it can be compared
tree-for-tree against the pyparsing grammar on the whole corpus.
"""

import re

from math_spec.expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    KeywordNode,
    NameListNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
)

_TOKEN = re.compile(
    r"""
    [ \t\n\r]*(?:
      (?P<number>\d+\.\d*(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+|\d+)
    | (?P<inf>\.inf\b)
    | (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)
    | (?P<quoted>'[^']*'|"[^"]*")
    | (?P<op>\*\*|<=|>=|==|[-+*/(),=\[\]])
    )""",
    re.VERBOSE,
)


class _Scan:
    __slots__ = ('i', 'toks')

    def __init__(self, text):
        toks, pos = [], 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if m is None:
                if text[pos:].strip() == '':
                    break
                raise SyntaxError(f'unexpected {text[pos]!r} at {pos}')
            kind = m.lastgroup
            toks.append((kind, m.group(kind)))
            pos = m.end()
        self.toks, self.i = toks, 0

    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def eat(self, val):
        if self.peek() == ('op', val):
            self.i += 1
            return True
        return False

    def expect(self, val):
        if not self.eat(val):
            raise SyntaxError(f'expected {val!r}, found {self.peek()[1]!r}')


def _atom(s):
    kind, val = s.peek()
    if kind == 'number':
        s.take()
        return NumberNode(float(val))
    if kind == 'inf':
        s.take()
        return NumberNode(float('inf'))
    if kind == 'name':
        s.take()
        if val == 'inf' and s.peek() != ('op', '('):
            return NumberNode(float('inf'))
        if s.eat('('):
            args, kwargs = [], {}
            if not s.eat(')'):
                while True:
                    args, kwargs = _arg(s, val, args, kwargs)
                    if s.eat(','):
                        continue
                    s.expect(')')
                    break
            return FunctionCallNode(val, tuple(args), kwargs)
        return NameNode(val)
    if s.eat('('):
        inner = _arith(s)
        s.expect(')')
        return inner
    raise SyntaxError(f'expected a value, found {val!r}')


def _arg(s, fname, args, kwargs):
    if s.peek()[0] == 'name' and s.peek(1) == ('op', '='):
        key = s.take()[1]
        s.take()
        kind, val = s.peek()
        if kind == 'quoted':
            s.take()
            value = KeywordNode(val[1:-1])
        elif s.eat('['):
            names = []
            while True:
                k, v = s.take()
                if k != 'name':
                    raise SyntaxError(f'a bracketed list holds names, found {v!r}')
                names.append(v)
                if s.eat(','):
                    continue
                s.expect(']')
                break
            value = NameListNode(tuple(names))
        else:
            value = _arith(s)
        if key in kwargs:
            raise SyntaxError(f'{fname}({key}=) is given twice.')
        kwargs[key] = value
    else:
        args.append(_arith(s))
    return args, kwargs


def _power(s):
    base = _atom(s)
    return BinaryOperatorNode('**', base, _unary(s)) if s.eat('**') else base


def _unary(s):
    for op in ('+', '-'):
        if s.eat(op):
            return UnaryOperatorNode(op, _unary(s))
    return _power(s)


def _mul_div(s):
    node = _unary(s)
    while True:
        for op in ('*', '/'):
            if s.peek() == ('op', op):
                s.take()
                node = BinaryOperatorNode(op, node, _unary(s))
                break
        else:
            return node


def _arith(s):
    node = _mul_div(s)
    while True:
        for op in ('+', '-'):
            if s.peek() == ('op', op):
                s.take()
                node = BinaryOperatorNode(op, node, _mul_div(s))
                break
        else:
            return node


def parse(text):
    s = _Scan(text)
    node = _arith(s)
    for op in ('<=', '>=', '=='):
        if s.eat(op):
            node = ComparisonNode(op, node, _arith(s))
            break
    if s.i != len(s.toks):
        raise SyntaxError(f'unexpected {s.peek()[1]!r}')
    return node
