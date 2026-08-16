# Expressions

Every `expression:` in the file — a constraint's, the objective's, a named
quantity's — is written in one small arithmetic language:

```text
expression  ::= arithmetic | arithmetic COMPARATOR arithmetic
arithmetic  ::= atom | unary_op arithmetic | arithmetic binary_op arithmetic
             |  function_call | "(" arithmetic ")"
atom        ::= NUMBER | NAME
unary_op    ::= "+" | "-"       binary_op ::= "+" | "-" | "*" | "/" | "**"
COMPARATOR  ::= "<=" | ">=" | "=="
function_call ::= NAME "(" [pos_arg ("," pos_arg)*] ["," kwarg ("," kwarg)*] ")"
kwarg       ::= NAME "=" (arithmetic | NAME)
NAME        ::= [a-zA-Z][a-zA-Z0-9_]*
NUMBER      ::= integer | float | "inf" | ".inf"
```

Precedence, highest first: `**`, then `*` `/`, then binary `+` `-`, then unary
`+` `-`. Parentheses override.

## Degree 1, always

Every expression is **affine in the variables**:

- `*` needs at least one variable-free factor — `p * cost` is fine, `p * on` is
  not;
- `/` needs a variable-free divisor, and a single factor rather than a sum;
- `**` parses but is **not in the language**. It is rejected at load time, so
  the refusal can name the operator and its rewrite. A variable base breaks
  degree 1; over parameters alone it is data prep.

This is the ceiling the whole design sits under, not a missing feature — what
that buys, and what it costs, is [the ceiling](../../about/ceiling.md).

## Name resolution

**One flat namespace** covers dimensions, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error
naming both declarations — there is no shadowing, because under it declaring a
parameter named `snapshot` would silently change what an existing
`where: "snapshot > 0"` means.

**Position decides which kinds of name are legal**, and every name's kind is
fixed when the file loads:

| Position | Legal kinds |
|---|---|
| expression (`p * cost`) | variable, parameter |
| dimension argument (`over=`) | dimension |
| lookup argument (`by=` on `sum` / `at`) | lookup — never a dimension |
| `where` string | parameter, variable, dimension, lookup ([where strings](absence.md#where-strings)) |
| `bounds.lower` / `bounds.upper` | parameter name, or a number |
| the `edge` key of `shift` | `'wrap'` **quoted**, or a bare number; never a dimension |

A bare word in a keyword-argument value is *a name to resolve*, which is why
`wrap` is quoted: `shift(x, over=wrap, edge='wrap')` reads unambiguously even
where a dimension is called `wrap`. `edge` is the one keyword whose *key* is
fixed rather than naming a dimension, so a dimension called `edge` does not
change what it means.

**A dimension in a value position is an error** — it is a coordinate space, not
data. To use its coordinates as data, declare a parameter over it.

**Constraints are outside the namespace**, no position resolving to one, so a
model may name a constraint after a variable. What reads a solve back keys on
the label space as well as the name for that reason. The objective carries no
name at all.

## Dim algebra

Parameter `dims` and variable `foreach` are declared, and dimension arguments
are name-checked, so **every expression's dim set is known before any data
binds**:

| Node | Dim set | Error |
|---|---|---|
| number | `{}` | |
| parameter / variable | its `dims` / its `foreach` | |
| `-x`, `+x` | `dims(x)` | |
| `a + b`, `a * b`, `a / b` | `dims(a) ∪ dims(b)` | |
| `sum(x, over=d)` | `dims(x) − {d}` | if `d ∉ dims(x)` |
| `sum(x, by=l)` | `(dims(x) − {over(l)}) ∪ {into(l)}` | if `over(l) ∉ dims(x)`, or `into(l) ∈ dims(x)` already |
| `at(x, by=l)` | `(dims(x) − {into(l)}) ∪ {over(l)}` | if `into(l) ∉ dims(x)`, or `over(l) ∈ dims(x)` already |
| `shift(x, over=d, by=n)` | `dims(x)` | if `d ∉ dims(x)` |

Binary operators **union**: an outer product is legitimate when the frame
declares the result. What must not be silent is a *declaration* that disagrees,
so:

- a **constraint** requires `dims(lhs) ∪ dims(rhs)` to **equal** its `foreach`.
  A stray dim multiplies rows and an unused `foreach` dim repeats one row
  across them — either way you would build a different model than the file
  reads as;
- a **`where` predicate**'s dims and a **bound parameter**'s dims must not
  *exceed* the frame they sit in.

Get it wrong and you are told at load time, not at solve time.

## Named expressions

A quantity the model names once and can read back after a solve:

```yaml
dimensions:
  generator: {dtype: str}
parameters:
  rate: {dims: [generator]}
variables:
  p: {foreach: [generator]}
expressions:
  total_generation: sum(p, over=generator)
  emissions:
    expression: sum(p * rate, over=generator)
    description: CO2 released, the quantity a cap would bound
```

Written as a bare string until it carries a `description:`, which is when it
gains the mapping form.

A named expression has **fixed dims** — they fall out of its body, so there is
no `foreach` — and an **observable identity**: after a solve,
`result.expression('emissions')` gives its value over its own dims
([reading a result](../api.md#reading-a-result)). That is the point of naming a
quantity: the CO₂ a constraint bounds and the CO₂ a summary reports are one
definition, validated once.

Where a constraint or the objective references one, it is substituted before
anything consumes the model, so a reference costs nothing at build time. It is
lowered only when it is *read*, so a model with fifty named expressions that
reads none pays for none.

## Macros

A **parameterised** template. It has no dims until it is called, and each call
site may give it different ones — so it has no value a solve could report, and
is never readable:

<!-- doctest: wrap=macros -->
```yaml
weighted_sum:
  args: [array, weights]  # positional formals, default []
  kwargs: [over]  # keyword formals, default []
  template: sum(array * weights, over=over)
```

Both blocks hold arithmetic and no comparison. Arguments expand before
substitution (call-by-value), so they may themselves use macros and named
expressions. Formals shadow model names inside a template but may not collide
with a declared **dimension**. Arity is checked per call site, and cycles are
reported with the reference chain.

**Every template is parsed and name-checked at load time even if it is never
called** — a macro nobody uses cannot hide a typo.

Anything composable out of the [built-in operators](operators.md) belongs here.
Math that is not sayable at all is out of scope
([limits](errors.md#what-the-language-will-not-say)).
