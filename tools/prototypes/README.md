<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: MIT
-->

# A hand-written parser, priced and not taken

Two parsers written by hand against the grammars in `src/math_spec/`, so that
"replace pyparsing" could be decided on numbers rather than on the feeling that
a parser ought to be faster than that. **Nothing here is wired into the
package**, and the conclusion was not to wire it in. It is kept so the next
person to ask does not have to build it again.

```bash
pixi run python -m tools.prototypes.benchmark     # what it would be worth
pixi run python -m tools.prototypes.differential  # whether it is the same parser
```

## What it is worth

`pyparsing` charges about 100 µs to parse the single character `p`, and a model
writes a couple of hundred distinct expressions. So a cold load spends 77% of
its time in the parser and 15 ms doing everything else — pydantic, macro
expansion, resolution, dimensions, degree — over 258 declarations.

| a cold `to_spec(examples/pypsa.yaml)` |   ms |      |
| ------------------------------------- | ---: | ---: |
| pyparsing, today                      | 86.1 | 1.0× |
| expression grammar replaced           | 35.0 | 2.5× |
| both grammars replaced                | 22.6 | 3.8× |
| nothing left to parse                 | 19.3 | 4.5× |

The parser step itself is **23×**. The load is 3.8×, and no parser can beat
4.5×, because a quarter of the work is not parsing. Those are different
questions and it is easy to quote the first while meaning the second.

## Why it was not taken

**The prize is bounded and the package is already fast enough.** 3.8× on the
largest model in the tree, on top of the 4–5× that memoising the parse and
taking libyaml's scanner already bought. Nothing in the repository is waiting
on 60 ms.

**The cost is 300 lines in the files that define the language.** Not the
happy path — that was an afternoon, and it agrees with pyparsing on every one
of the 207 expressions and 84 where strings the repository contains. The cost
is the tail, and the tail is where a language quietly changes shape:

- The tokenizer first spelt whitespace `\s`, which is 28 characters where this
  language allows four. `x +\xa01` — a non-breaking space, one paste away in
  YAML — parsed. It failed **open**, widening the language by one regex
  character, and 300,000 fuzz inputs did not find it because they were ASCII.
- `pp.Keyword` checks the character _before_ the word as well as after, so
  `0AND y` is not the `AND` keyword. A tokenizer that splits `0` and `AND`
  loses that adjacency. Three of these survive in `differential.py` today.
- A bare `NOT` is a _parameter named_ `NOT`, because `NOT` is only the
  connective when an atom follows it. Matching that needed real backtracking,
  and no reading of the grammar had suggested it.

Each is small, each fails towards accepting more than the specification, and
none was found by reading. That is the argument: the language's definition is
this repository's whole product, and 60 ms does not buy the right to risk it.

**If it is ever taken**, `pyparsing` should move to the test feature rather than
be deleted, and `differential.py` should run in CI. The oracle is what makes the
tail tractable, and it costs one dependency that no longer ships to users.

## What was rejected along the way

`ast.parse` with a walk into these node types is **29×** — all 207 corpus
expressions parse as Python expressions, and produce identical trees. It was
rejected even though it is marginally faster than writing one by hand, because
it buys 15% over a parser we own and costs the grammar:

- It cannot spell `.inf`, which is in the published EBNF
  (`docs/reference/language/expressions.md`). The language would have had to
  change to suit the tool.
- The grammar would stop being a declaration and become "Python's expression
  grammar, minus whatever a walk rejects" — a subtractive definition, with no
  correspondence to the published EBNF.
- Closure would stop being checkable. `expansion.py`, `degree.py` and
  `boundedness.py` close their walks with `assert_never` over this package's
  own unions, and pyrefly verifies exhaustiveness. CPython's node set is not
  ours and grows between releases.

## Two things found while measuring, worth their own issues

- **`to_spec` raises `RecursionError`** on a deeply nested expression — 300
  nested parens is enough — where its docstring promises `LanguageError`.
  `parse_expression` catches only `pp.ParseException`. A depth guard cannot be
  added inside pyparsing; a parser we own is what would make it fixable.
- **The documented grammar and the implemented one disagree about names.**
  `expressions.md` says `NAME ::= [a-zA-Z][a-zA-Z0-9_]*`; the code is
  `[a-zA-Z_][a-zA-Z0-9_]*`, and `_x + 1` parses today.
