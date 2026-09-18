<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# How a call through a relation is spelled: the options

This page compares spellings. The rules are settled, and every option here
writes the same language under them, so nothing below changes what a model can
say. It exists to make the choice of words a decision rather than a habit.

Only the first option was run. It is what the tree holds today, and its calls,
frames and math were loaded and printed on this branch. Every other option is
transcribed by hand into the same cases.

## The rules a spelling has to keep

1. **A relation does not change its meaning when a value column is added.**
   Every call gives the same result after the edit.
2. **A relation's key is fixed.** Adding or removing a key column makes a
   different relation, which is a new declaration.
3. **A relation works the same when the operand gains a dimension** the
   relation does not name.
4. **The frame law.** `result = (operand − consumed) ∪ produced`, and the
   operand carries `consumed ∪ joined`, where
   `joined = key − (consumed ∪ produced)`. The result gains a dimension from a
   change of the operand, never from a change of the relation.
5. **A call is refused when `(produced ∩ operand) − consumed` is not empty.**
6. **Both ends are always written.**

Rule 6 decides the comparison before it starts. Every shortcut that let a call
leave one side to a default is out, so each option below names what it consumes
and what it produces, or determines both from what it does name.

## The options

| option | the shape                     | the walk in case 3                           |
| ------ | ----------------------------- | -------------------------------------------- |
| **A**  | two keywords, today's words   | `by=slot_of, over=generator, into=bus`       |
| **B**  | two keywords, the law's words | `by=slot_of, consume=generator, produce=bus` |
| **C**  | one keyword, an arrow         | `by=slot_of, direction=generator -> bus`     |
| **D**  | the arrow inside `by=`        | `by=slot_of(generator -> bus)`               |
| **E**  | dotted columns, both ends     | `over=slot_of.generator, into=slot_of.bus`   |
| **F**  | dotted columns, the kept set  | `by=slot_of.[period, bus]`                   |

**F names what the call keeps.** What it consumes is `key` minus the key
columns it names, which the reader takes from the declaration.

One more question is independent of all six, and is answered on its own:

| option | the shape          | the read in case 8                              |
| ------ | ------------------ | ----------------------------------------------- |
| **G**  | a read is an index | `price[gen_bus.bus]` in place of `at(price, …)` |

## A, B, C and D: what is replaced by what

A walk puts three facts on the line: the relation **R**, the columns consumed
**X**, and the columns produced **Y**. All four write those three, and only
those three.

```
A   sum(<expr>, by=R, over=X, into=Y)         at(<expr>, by=R, over=X, into=Y)
B   sum(<expr>, by=R, consume=X, produce=Y)   at(<expr>, by=R, consume=X, produce=Y)
C   sum(<expr>, by=R, direction=X -> Y)       at(<expr>, by=R, direction=X -> Y)
D   sum(<expr>, by=R(X -> Y))                 at(<expr>, by=R(X -> Y))
```

So every pair is one textual edit, and each row reads in both directions:

| between   | the edit                                           |
| --------- | -------------------------------------------------- |
| **A ↔ B** | `over=X` ↔ `consume=X`, and `into=Y` ↔ `produce=Y` |
| **A ↔ C** | `over=X, into=Y` ↔ `direction=X -> Y`              |
| **A ↔ D** | `by=R, over=X, into=Y` ↔ `by=R(X -> Y)`            |
| **B ↔ C** | `consume=X, produce=Y` ↔ `direction=X -> Y`        |
| **B ↔ D** | `by=R, consume=X, produce=Y` ↔ `by=R(X -> Y)`      |
| **C ↔ D** | `by=R, direction=X -> Y` ↔ `by=R(X -> Y)`          |

`X` and `Y` are copied across unchanged, whether each is one column or a list.
Nothing is read from the declarations to make the edit, and no call gains or
loses a fact.

**Two calls are not a walk, and there the rewrite is not this clean.**

| the call            | A                        | B                           | C    | D              |
| ------------------- | ------------------------ | --------------------------- | ---- | -------------- |
| a sum with no `by=` | `sum(p, over=generator)` | `sum(p, consume=generator)` | as A | as A           |
| a partition         | `by=cal, within=week`    | as A                        | as A | `by=cal(week)` |

**B reaches calls that name no relation**, because it renames the keyword those
calls share with a walk. **D gives its parentheses a second job**, holding a
group here and a direction above.

**E and F are not on this list.** E copies the relation's name onto each
column, so the edit writes `R` once per side instead of once per call. F names
the columns the call keeps, so the edit has to open the declarations to work
out which of them are key columns. Neither is a search and replace.

## The model every case uses

```yaml
dimensions:
  generator: { dtype: str }
  period: { dtype: int }
  zone: { dtype: str }
  bus: { dtype: str }
  technology: { dtype: str }
  line: { dtype: str }
  t: { dtype: int }
  day: { dtype: int }
  week: { dtype: int }

relations:
  gen_bus: { key: generator, values: bus } # 1 key, 1 value
  zone_of: { key: [generator, period], values: zone } # 2 keys, 1 value
  slot_of: { key: [generator, period], values: [bus, technology] } # 2 keys, 2 values
  ends: { key: line, values: { bus0: bus, bus1: bus } } # 2 values over one dimension
  cal: { key: t, values: [day, week] } # a calendar, grouped by either column
  connection: { key: [generator, bus] } # a bare relation: every column is key

parameters:
  cap: { dims: [bus] }
  price: { dims: [bus] }
  zone_cap: { dims: [zone, period] }
  bus_cap: { dims: [bus, period] }
  bus_total: { dims: [bus] }
  bt_cap: { dims: [bus, technology] }
  btp_cap: { dims: [bus, technology, period] }

variables:
  p: { dims: [generator, period], bounds: { lower: 0 } }
  f: { dims: [line], bounds: { lower: 0 } }
  x: { dims: [t], bounds: { lower: 0 } }
  u: { dims: [generator], bounds: { lower: 0 } }
```

Each case is one constraint over these. The heading carries the frame the
operation itself produces, which is a property of the language and not of the
spelling.

## The calls with no relation

Five of the six options leave these alone. They are the majority of the calls
in any model: of the 136 sums in `examples/`, 96 carry no `by=`.

| option | 0a       | 0b                          | 0c                                    | 0d                               | 0e            |
| ------ | -------- | --------------------------- | ------------------------------------- | -------------------------------- | ------------- |
| **A**  | `sum(p)` | `sum(p, over=generator)`    | `shift(x, along=t, offset=1, edge=0)` | `sum_back(x, along=t, window=4)` | `position(t)` |
| **B**  | same     | `sum(p, consume=generator)` | same                                  | same                             | same          |
| **C**  | same     | same                        | same                                  | same                             | same          |
| **D**  | same     | same                        | same                                  | same                             | same          |
| **E**  | same     | same                        | same                                  | same                             | same          |
| **F**  | same     | same                        | same                                  | same                             | same          |

| case | what it is                 | frame                                    |
| ---- | -------------------------- | ---------------------------------------- |
| 0a   | a sum of everything        | `p[generator, period]` → `[]`            |
| 0b   | a sum of one dimension     | `p[generator, period]` → `[period]`      |
| 0c   | a `shift` with no `by=`    | `x[t]` → `[t]`                           |
| 0d   | a `sum_back` with no `by=` | `x[t]` → `[t]`                           |
| 0e   | a `position` with no `by=` | a `where` predicate, so the frame stands |

**0b is where B stands alone, and it is the most ordinary call there is.** It
is the whole price of that option: 40 calls in `examples/` write `over=` with
no relation anywhere in the file.

## The walks

### 1 — sum through a one-key table

`p[generator, period]` → `[bus, period]` · consumes `generator`, produces `bus`

| option | the call                                             |
| ------ | ---------------------------------------------------- |
| **A**  | `sum(p, by=gen_bus, over=generator, into=bus)`       |
| **B**  | `sum(p, by=gen_bus, consume=generator, produce=bus)` |
| **C**  | `sum(p, by=gen_bus, direction=generator -> bus)`     |
| **D**  | `sum(p, by=gen_bus(generator -> bus))`               |
| **E**  | `sum(p, over=gen_bus.generator, into=gen_bus.bus)`   |
| **F**  | `sum(p, by=gen_bus.bus)`                             |

$$\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{g,e} \le \mathrm{bus\_cap}_{b,e} \qquad \forall\, b \in \mathcal{B},\ e \in \mathcal{E}$$

### 2 — sum one key away, join the other

`p[generator, period]` → `[period, zone]` · consumes `generator`, joins `period`, produces `zone`

| option | the call                                              |
| ------ | ----------------------------------------------------- |
| **A**  | `sum(p, by=zone_of, over=generator, into=zone)`       |
| **B**  | `sum(p, by=zone_of, consume=generator, produce=zone)` |
| **C**  | `sum(p, by=zone_of, direction=generator -> zone)`     |
| **D**  | `sum(p, by=zone_of(generator -> zone))`               |
| **E**  | `sum(p, over=zone_of.generator, into=zone_of.zone)`   |
| **F**  | `sum(p, by=zone_of.[period, zone])`                   |

$$\sum_{g \in \mathcal{G} \,:\, \mathrm{zone\_of}(g,\ e) = z} p_{g,e} \le \mathrm{zone\_cap}_{z,e} \qquad \forall\, z \in \mathcal{Z},\ e \in \mathcal{E}$$

### 3 — the same, onto one of two value columns

`p[generator, period]` → `[bus, period]` · `technology` is not read

| option | the call                                             |
| ------ | ---------------------------------------------------- |
| **A**  | `sum(p, by=slot_of, over=generator, into=bus)`       |
| **B**  | `sum(p, by=slot_of, consume=generator, produce=bus)` |
| **C**  | `sum(p, by=slot_of, direction=generator -> bus)`     |
| **D**  | `sum(p, by=slot_of(generator -> bus))`               |
| **E**  | `sum(p, over=slot_of.generator, into=slot_of.bus)`   |
| **F**  | `sum(p, by=slot_of.[period, bus])`                   |

$$\sum_{g \in \mathcal{G} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b} p_{g,e} \le \mathrm{bus\_cap}_{b,e} \qquad \forall\, b \in \mathcal{B},\ e \in \mathcal{E}$$

### 4 — the same, onto both value columns

`p[generator, period]` → `[bus, period, technology]`

| option | the call                                                           |
| ------ | ------------------------------------------------------------------ |
| **A**  | `sum(p, by=slot_of, over=generator, into=[bus, technology])`       |
| **B**  | `sum(p, by=slot_of, consume=generator, produce=[bus, technology])` |
| **C**  | `sum(p, by=slot_of, direction=generator -> [bus, technology])`     |
| **D**  | `sum(p, by=slot_of(generator -> [bus, technology]))`               |
| **E**  | `sum(p, over=slot_of.generator, into=slot_of.[bus, technology])`   |
| **F**  | `sum(p, by=slot_of.[period, bus, technology])`                     |

$$\sum_{g \in \mathcal{G} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b \wedge \mathrm{slot\_of.technology}(g,\ e) = t} p_{g,e} \le \mathrm{btp\_cap}_{b,t,e} \qquad \forall\, b \in \mathcal{B},\ t \in \mathcal{T},\ e \in \mathcal{E}$$

### 5 — sum the whole key away, onto one value column

`p[generator, period]` → `[bus]` · nothing is joined on, so `period` leaves with `generator`

| option | the call                                                       |
| ------ | -------------------------------------------------------------- |
| **A**  | `sum(p, by=slot_of, over=[generator, period], into=bus)`       |
| **B**  | `sum(p, by=slot_of, consume=[generator, period], produce=bus)` |
| **C**  | `sum(p, by=slot_of, direction=[generator, period] -> bus)`     |
| **D**  | `sum(p, by=slot_of([generator, period] -> bus))`               |
| **E**  | `sum(p, over=slot_of.[generator, period], into=slot_of.bus)`   |
| **F**  | `sum(p, by=slot_of.bus)`                                       |

$$\sum_{g \in \mathcal{G},\ e \in \mathcal{E} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b} p_{g,e} \le \mathrm{bus\_total}_{b} \qquad \forall\, b \in \mathcal{B}$$

### 6 — sum the whole key away, onto both

`p[generator, period]` → `[bus, technology]`

| option | the call                                                                     |
| ------ | ---------------------------------------------------------------------------- |
| **A**  | `sum(p, by=slot_of, over=[generator, period], into=[bus, technology])`       |
| **B**  | `sum(p, by=slot_of, consume=[generator, period], produce=[bus, technology])` |
| **C**  | `sum(p, by=slot_of, direction=[generator, period] -> [bus, technology])`     |
| **D**  | `sum(p, by=slot_of([generator, period] -> [bus, technology]))`               |
| **E**  | `sum(p, over=slot_of.[generator, period], into=slot_of.[bus, technology])`   |
| **F**  | `sum(p, by=slot_of.[bus, technology])`                                       |

$$\sum_{g \in \mathcal{G},\ e \in \mathcal{E} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b \wedge \mathrm{slot\_of.technology}(g,\ e) = t} p_{g,e} \le \mathrm{bt\_cap}_{b,t} \qquad \forall\, b \in \mathcal{B},\ t \in \mathcal{T}$$

### 7 — sum onto one of two columns over one dimension

`f[line]` → `[bus]` · producing `bus1` produces the dimension `bus`; `bus0` is not read

| option | the call                                      |
| ------ | --------------------------------------------- |
| **A**  | `sum(f, by=ends, over=line, into=bus1)`       |
| **B**  | `sum(f, by=ends, consume=line, produce=bus1)` |
| **C**  | `sum(f, by=ends, direction=line -> bus1)`     |
| **D**  | `sum(f, by=ends(line -> bus1))`               |
| **E**  | `sum(f, over=ends.line, into=ends.bus1)`      |
| **F**  | `sum(f, by=ends.bus1)`                        |

$$\sum_{l \in \mathcal{L} \,:\, \mathrm{ends.bus1}(l) = b} f_{l} \le \mathrm{bus\_total}_{b} \qquad \forall\, b \in \mathcal{B}$$

### 8 — read at the key

`price[bus]` → `[generator]` · a read runs the other way from a sum: it consumes the value column and produces the key

| option | the call                                                |
| ------ | ------------------------------------------------------- |
| **A**  | `at(price, by=gen_bus, over=bus, into=generator)`       |
| **B**  | `at(price, by=gen_bus, consume=bus, produce=generator)` |
| **C**  | `at(price, by=gen_bus, direction=bus -> generator)`     |
| **D**  | `at(price, by=gen_bus(bus -> generator))`               |
| **E**  | `at(price, over=gen_bus.bus, into=gen_bus.generator)`   |
| **F**  | `at(price, by=gen_bus.bus)`                             |
| **G**  | `price[gen_bus.bus]`                                    |

$$u_{g} \le \mathrm{price}_{\mathrm{gen\_bus}(g)} \qquad \forall\, g \in \mathcal{G}$$

### 9 — read one of two columns over one dimension

`cap[bus]` → `[line]`

| option | the call                                       |
| ------ | ---------------------------------------------- |
| **A**  | `at(cap, by=ends, over=bus0, into=line)`       |
| **B**  | `at(cap, by=ends, consume=bus0, produce=line)` |
| **C**  | `at(cap, by=ends, direction=bus0 -> line)`     |
| **D**  | `at(cap, by=ends(bus0 -> line))`               |
| **E**  | `at(cap, over=ends.bus0, into=ends.line)`      |
| **F**  | `at(cap, by=ends.bus0)`                        |
| **G**  | `cap[ends.bus0]`                               |

$$f_{l} \le \mathrm{cap}_{\mathrm{ends.bus0}(l)} \qquad \forall\, l \in \mathcal{L}$$

### 13 — sum through a bare relation

`p[generator, period]` → `[bus, period]` · the transform is case 1's, but a generator may stand against several buses, so a term can land in more than one group

| option | the call                                                 |
| ------ | -------------------------------------------------------- |
| **A**  | `sum(p, by=connection, over=generator, into=bus)`        |
| **B**  | `sum(p, by=connection, consume=generator, produce=bus)`  |
| **C**  | `sum(p, by=connection, direction=generator -> bus)`      |
| **D**  | `sum(p, by=connection(generator -> bus))`                |
| **E**  | `sum(p, over=connection.generator, into=connection.bus)` |
| **F**  | `sum(p, by=connection.bus)`                              |

$$\sum_{g \in \mathcal{G} \,:\, \left( g,\ b \right) \in \mathrm{connection}} p_{g,e} \le \mathrm{bus\_cap}_{b,e} \qquad \forall\, b \in \mathcal{B},\ e \in \mathcal{E}$$

This is the one case whose math is a membership rather than a function read.
A bare relation has no value column, so there is no `rel.col(g)` to write, and
the condition is the row itself.

## The partitions

A partition keeps the axis it walks, so the frame does not move, and nothing
is consumed or produced. **Every option that spells the walk as an arrow has
nothing to say here**, and E and F collapse into one spelling.

### 10 — shift inside a group

`x[t]` → `[t]`

| option | the call                                           |
| ------ | -------------------------------------------------- |
| **A**  | `shift(x, along=t, offset=1, by=cal, within=week)` |
| **B**  | same                                               |
| **C**  | same                                               |
| **D**  | `shift(x, along=t, offset=1, by=cal(week))`        |
| **E**  | `shift(x, along=cal.t, offset=1, within=cal.week)` |
| **F**  | as E                                               |

$$x_{a} \le x_{a -^{\mathrm{cal.week}(a)} 1} \qquad \forall\, a \in \mathcal{A}$$

### 11 and 12 — position inside a group

A `where` predicate, so the frame stands.

| option | 11                                             | 12                                      |
| ------ | ---------------------------------------------- | --------------------------------------- |
| **A**  | `position(t, by=cal, within=[day, week]) == 0` | `position(t, by=cal, within=week) == 0` |
| **B**  | same                                           | same                                    |
| **C**  | same                                           | same                                    |
| **D**  | `position(t, by=cal([day, week])) == 0`        | `position(t, by=cal(week)) == 0`        |
| **E**  | `position(cal.t, within=cal.[day, week]) == 0` | `position(cal.t, within=cal.week) == 0` |
| **F**  | as E                                           | as E                                    |

$$x_{a} \le 1 \qquad \forall\, a \in \mathcal{A} \,:\, \mathrm{pos}_{\left( \mathrm{cal.day}(a),\ \mathrm{cal.week}(a) \right)}(a) = 0$$

$$x_{a} \le 1 \qquad \forall\, a \in \mathcal{A} \,:\, \mathrm{pos}_{\mathrm{cal.week}(a)}(a) = 0$$

## The macro

### 14 — a template, and what it binds

Called `through(p, l=zone_of, a=generator, b=zone)`. It expands to case 2 and
prints case 2's math.

| option | the template                            | binds         |
| ------ | --------------------------------------- | ------------- |
| **A**  | `sum(y, by=l, over=a, into=b)`          | `l`, `a`, `b` |
| **B**  | `sum(y, by=l, consume=a, produce=b)`    | `l`, `a`, `b` |
| **C**  | `sum(y, by=l, direction=a -> b)`        | `l`, `a`, `b` |
| **D**  | `sum(y, by=l(a -> b))`                  | `l`, `a`, `b` |
| **E**  | `sum(y, over=l.generator, into=l.zone)` | `l` only      |
| **F**  | `sum(y, by=l.[period, zone])`           | `l` only      |

`_substitute` in `src/math_spec/expansion.py` replaces formal-name nodes. A
column after a dot is part of a name and not a node of its own, so it is not a
binding point. A template in E or F fixes its column names, and serves one
relation rather than any relation of that shape.

## What actually differs

**A, B, C and D are one language in four spellings**, and the edit between any
two of them is [above](#a-b-c-and-d-what-is-replaced-by-what). Nothing in the
case set separates them except the words.

**B is the only option that reaches a model with no relation in it.** It costs
40 calls in `examples/` that write `over=` with no `by=`. What it buys is that
the call says the words the frame law says, and `over` then names one thing in
a file: the breakpoint axis of a `piecewise:` or `sos:` declaration.

**C and D buy a parse error where a load error already exists.** Their gain is
that an arrow cannot be half written. Today a missing end is refused like this:

```
sum() through a relation leaves into=, over= unsaid.
A walk names both of its ends, so that a relation may gain a value column
without changing what this call means.
Write: sum(<expr>), sum(<expr>, over=<dim>) or sum(<expr>, by=<relation>, over=<column>, into=<column>)
```

**D gives one bracket two meanings.** `by=slot_of(generator -> bus)` is a walk
and `by=cal(week)` is a group.

**E writes the relation twice** and buys that a column is never a bare word.
`into=bus1` means nothing without the `by=ends` beside it; `into=ends.bus1`
stands on its own.

**F states the complement.** It names what the call keeps, so what the call
consumes is read off the declaration. It holds every rule above — the key is
fixed, so the complement is stable — but it is the one option where the frame
law's own terms are not on the line. Its `by=` also carries two rules: in a sum
it names the columns kept, and in a read it names the column read through.

**The printed math rules nothing out.** It already spells a value column with a
dot, which is E's and F's character, and it already prints a read as a
subscript, which is G's:

$$\mathrm{slot\_of.bus}(g,\ e) \qquad \mathrm{ends.bus0}(l) \qquad \mathrm{cal.week}(a) \qquad \mathrm{price}_{\mathrm{gen\_bus}(g)}$$

## What is open

- **G is a separate decision.** Whether a read is a call or an index does not
  depend on which of A to F wins, and it retires the name `at`.
- **Whether `within=` takes a dotted column** in E and F. Its neighbours
  `over=`, `into=` and `along=` all would, and the relation is already fixed by
  the call, so a bare `within=week` is defensible. Whichever way it goes, the
  reference owes the reader that line.
- **Whether F's `by=` may hold two rules**, one for a sum and one for a read.

## The recommendation

Keep the shape and decide the words: the choice is A or B.

B, because the settled rules are written in _consumed_ and _produced_, and the
docs, the docstrings and the error messages now have to carry those rules. With
`over=` and `into=` every one of those messages spends a line translating. The
rename deletes the translation, adds no grammar, and leaves `over` with one
meaning in a file. Its price is the 40 relation-free sums, and that
`sum(p, over=generator)` reads like a sum sign where `sum(p, consume=generator)`
does not.

C and D pay a new piece of grammar for a refusal the loader already gives. E
pays a second copy of the relation name, and F pays the frame law's own terms,
and both pay the macro.

<details><summary>How the A column was measured</summary>

Each case is one constraint over the declarations above, loaded with
`to_spec`, and the math line is `typeset_declaration(model, 'c', 'latex')`.
All nineteen load.

Each frame is read off the loader's own refusal rather than derived: a scalar
variable `s: {dims: []}` is added, the operation is loaded as
`s + <the call> <= 100` under `dims: []`, and the message names the dims the
expression carries. The scalar contributes none, so what it names is the
operation's own frame.

The counts of calls in `examples/` come from matching each `sum(`, `at(`,
`shift(` and `sum_back(`, taking its argument text with nested calls blanked
out, and asking whether that text holds a `by=`. It gives 136 sums, 96 of them
with no `by=` and 40 of those writing `over=`; 53 walks, which is every `at(`
with a `by=` and 40 sums; and 2 partitions.

`pixi` does not install in the session this was written in, so the runs used a
`uv` venv on Python 3.13 with the project's runtime dependencies, and
`pixi run ci` was not run. The earlier measurement that every proposal prints
the same math for these cases is recorded in
[#516](https://github.com/energy-models/math-spec/issues/516) and was not
repeated here.

</details>
