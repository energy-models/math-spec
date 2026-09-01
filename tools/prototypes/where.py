# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Prototype: the where grammar by hand, to price the second half. Measurement only."""

import re

from math_spec._where_parser import (
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
)
from math_spec.program import AndNode, BooleanLiteralNode, NotNode, OrNode

_TOKEN = re.compile(
    r"""
    [ \t\n\r]*(?:
      (?P<number>-?(?:\d+\.\d*(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+|\d+))
    | (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)
    | (?P<quoted>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
    | (?P<op><=|>=|==|!=|[<>(),=])
    )""",
    re.VERBOSE,
)
_CMP = ('<=', '>=', '==', '!=', '<', '>')


class _Scan:
    __slots__ = ('i', 't')

    def __init__(self, text):
        toks, pos = [], 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if m is None:
                if not text[pos:].strip():
                    break
                raise SyntaxError(f'unexpected {text[pos]!r}')
            toks.append((m.lastgroup, m.group(m.lastgroup)))
            pos = m.end()
        self.t, self.i = toks, 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def kw(self, word):
        k, v = self.peek()
        if k == 'name' and v.upper() == word:
            self.i += 1
            return True
        return False

    def op(self, val):
        if self.peek() == ('op', val):
            self.i += 1
            return True
        return False

    def expect(self, val):
        if not self.op(val):
            raise SyntaxError(f'expected {val!r}')


def _unquote(s):
    return re.sub(r'\\(.)', r'\1', s[1:-1])


def _atom(s):
    if s.kw('TRUE'):
        return BooleanLiteralNode(True)
    if s.kw('FALSE'):
        return BooleanLiteralNode(False)
    if s.op('('):
        node = _or(s)
        s.expect(')')
        return node
    k, v = s.peek()
    if k != 'name':
        raise SyntaxError(f'expected a predicate, found {v!r}')
    if v == 'position' and s.peek(1) == ('op', '('):
        s.i += 2
        dk, dim = s.peek()
        if dk != 'name':
            raise SyntaxError('position() names a dimension')
        s.i += 1
        by = None
        if s.op(','):
            if not s.kw('BY'):
                raise SyntaxError('position() takes by=')
            s.expect('=')
            bk, by = s.peek()
            if bk != 'name':
                raise SyntaxError('by= names a lookup')
            s.i += 1
        s.expect(')')
        ok, opv = s.peek()
        if ok != 'op' or opv not in _CMP:
            raise SyntaxError('a comparator must follow position()')
        s.i += 1
        nk, nv = s.peek()
        if nk != 'number' or '.' in nv or 'e' in nv.lower():
            raise SyntaxError('a position is a whole number')
        s.i += 1
        return UnresolvedPositionNode(dim, opv, int(nv), by)
    s.i += 1
    ok, opv = s.peek()
    if ok == 'op' and opv in _CMP:
        s.i += 1
        rk, rv = s.peek()
        if rk == 'number':
            s.i += 1
            return UnresolvedComparisonNode(v, opv, float(rv), False)
        if rk == 'quoted':
            s.i += 1
            return UnresolvedComparisonNode(v, opv, _unquote(rv), True)
        if rk == 'name':
            s.i += 1
            return UnresolvedComparisonNode(v, opv, rv, False)
        raise SyntaxError('a comparison needs a value')
    return UnresolvedNameNode(v)


def _not(s):
    """`NOT` is only the connective when an atom follows: a bare `NOT` is a parameter of that name."""
    mark = s.i
    if s.kw('NOT'):
        try:
            return NotNode(_atom(s))
        except SyntaxError:
            s.i = mark
    return _atom(s)


def _and(s):
    node = _not(s)
    while s.kw('AND'):
        node = AndNode(node, _not(s))
    return node


def _or(s):
    node = _and(s)
    while s.kw('OR'):
        node = OrNode(node, _and(s))
    return node


def parse(text):
    s = _Scan(text)
    node = _or(s)
    if s.i != len(s.t):
        raise SyntaxError(f'unexpected {s.peek()[1]!r}')
    return node
