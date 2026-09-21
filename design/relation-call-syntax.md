<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# How a call through a relation is spelled: the options

Six spellings of a walk, and one question about reads. The rules are settled,
and every option writes the same language under them, so nothing here changes
what a model can say. The page makes the choice of words a decision rather
than a habit.

Only option A was run. It is what the tree holds, and its calls, frames and
math were loaded and printed on this branch. Every other column is transcribed
by hand into the same cases.

## The rules a spelling has to keep

1. A relation does not change its meaning when a value column is added.
2. A relation's key is fixed. A key column added or removed is a new relation.
3. A relation works the same when the operand gains a dimension it does not
   name.
4. The frame law: `result = (operand − consumed) ∪ produced`, and the operand
   carries `consumed ∪ joined`, where `joined = key − (consumed ∪ produced)`.
5. A call is refused when `(produced ∩ operand) − consumed` is not empty.
6. Both ends are always written.

Rule 6 decides the comparison before it starts. Every shortcut that let a call
leave one side to a default is out, so each option names what it consumes and
what it produces, or determines both from what it does name.

## The options

Each is shown on case 3: sum `p[generator, period]` through
`slot_of: {key: [generator, period], values: [bus, technology]}`, consuming
`generator`, joining on `period`, landing on `bus`.

| option                                  | the call                                             | what it buys, and what it costs                                                                                             |
| --------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **A** — `by=`, `over=`, `into=`         | `sum(p, by=slot_of, over=generator, into=bus)`       | What the tree and every file in `examples/` hold, so it costs nothing to adopt.                                             |
| **B** — `by=`, `consume=`, `produce=`   | `sum(p, by=slot_of, consume=generator, produce=bus)` | A's shape in the frame law's own words. It is the one option that reaches a call with no relation in it.                    |
| **C** — the direction is one keyword    | `sum(p, by=slot_of, direction=generator -> bus)`     | An arrow cannot be half written, so the grammar refuses the call that names one end. It is new grammar.                     |
| **D** — the direction sits inside `by=` | `sum(p, by=slot_of(generator -> bus))`               | One keyword, and the relation and its direction read as one phrase. The parentheses also hold a group, as `by=cal(week)`.   |
| **E** — a column names its relation     | `sum(p, over=slot_of.generator, into=slot_of.bus)`   | `into=ends.bus1` says on its own what `into=bus1` needs the rest of the call to say. The relation is written once per side. |
| **F** — the call names what it keeps    | `sum(p, by=slot_of.[period, bus])`                   | The shortest. It names the columns that survive, so what is consumed is read off the declaration.                           |
| **G** — a read is an index              | `price[gen_bus.bus]`, on case 8                      | Not a way of spelling the walk, so it stacks with any of the six. It replaces `at()` for every read and retires that name.  |

## A, B, C and D are one language

A walk puts three facts on the line: the relation **R**, the columns consumed
**X**, and the columns produced **Y**. Four options write those three, and only
those three.

```
A   sum(<expr>, by=R, over=X, into=Y)         at(<expr>, by=R, over=X, into=Y)
B   sum(<expr>, by=R, consume=X, produce=Y)   at(<expr>, by=R, consume=X, produce=Y)
C   sum(<expr>, by=R, direction=X -> Y)       at(<expr>, by=R, direction=X -> Y)
D   sum(<expr>, by=R(X -> Y))                 at(<expr>, by=R(X -> Y))
```

So every pair is one textual edit, in either direction, with `X` and `Y` copied
across unchanged, whether each is one column or a list. Nothing is read from the
declarations to make the edit, and no call gains or loses a fact.

Two calls are not a walk, and there the rewrite is not this clean.

| the call            | A                        | B                           | C    | D              |
| ------------------- | ------------------------ | --------------------------- | ---- | -------------- |
| a sum with no `by=` | `sum(p, over=generator)` | `sum(p, consume=generator)` | as A | as A           |
| a partition         | `by=cal, within=week`    | as A                        | as A | `by=cal(week)` |

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

Each case is one constraint over these declarations. Each frame below is the
one the operation itself produces, which is a property of the language and not
of the spelling.

## The calls with no relation

They are the majority of the calls in any model: of the 136 sums in
`examples/`, 96 carry no `by=`.

| case | frame                                    | A                                     | B                           | C to F |
| ---- | ---------------------------------------- | ------------------------------------- | --------------------------- | ------ |
| 0a   | `p[generator, period]` → `[]`            | `sum(p)`                              | as A                        | as A   |
| 0b   | `p[generator, period]` → `[period]`      | `sum(p, over=generator)`              | `sum(p, consume=generator)` | as A   |
| 0c   | `x[t]` → `[t]`                           | `shift(x, along=t, offset=1, edge=0)` | as A                        | as A   |
| 0d   | `x[t]` → `[t]`                           | `sum_back(x, along=t, window=4)`      | as A                        | as A   |
| 0e   | a `where` predicate, so the frame stands | `position(t)`                         | as A                        | as A   |

**0b is where B stands alone, and it is the most ordinary call there is.** It
is the whole price of that option: 40 calls in `examples/` write `over=` with
no relation anywhere in the file.

## The walks

### 1 and 2 — sum onto a single value column

- **1** `p[generator, period]` → `[bus, period]` through `gen_bus`: consumes `generator`, produces `bus`.
- **2** `p[generator, period]` → `[period, zone]` through `zone_of`: the same, but the key holds `period` too, so it is joined on rather than carried along.

| option | 1                                                    | 2                                                     |
| ------ | ---------------------------------------------------- | ----------------------------------------------------- |
| **A**  | `sum(p, by=gen_bus, over=generator, into=bus)`       | `sum(p, by=zone_of, over=generator, into=zone)`       |
| **B**  | `sum(p, by=gen_bus, consume=generator, produce=bus)` | `sum(p, by=zone_of, consume=generator, produce=zone)` |
| **C**  | `sum(p, by=gen_bus, direction=generator -> bus)`     | `sum(p, by=zone_of, direction=generator -> zone)`     |
| **D**  | `sum(p, by=gen_bus(generator -> bus))`               | `sum(p, by=zone_of(generator -> zone))`               |
| **E**  | `sum(p, over=gen_bus.generator, into=gen_bus.bus)`   | `sum(p, over=zone_of.generator, into=zone_of.zone)`   |
| **F**  | `sum(p, by=gen_bus.bus)`                             | `sum(p, by=zone_of.[period, zone])`                   |

### 3 and 4 — sum one key away, onto one of two value columns, and onto both

- **3** `p[generator, period]` → `[bus, period]`: `technology` is not read.
- **4** `p[generator, period]` → `[bus, period, technology]`.

| option | 3                                                    | 4                                                                  |
| ------ | ---------------------------------------------------- | ------------------------------------------------------------------ |
| **A**  | `sum(p, by=slot_of, over=generator, into=bus)`       | `sum(p, by=slot_of, over=generator, into=[bus, technology])`       |
| **B**  | `sum(p, by=slot_of, consume=generator, produce=bus)` | `sum(p, by=slot_of, consume=generator, produce=[bus, technology])` |
| **C**  | `sum(p, by=slot_of, direction=generator -> bus)`     | `sum(p, by=slot_of, direction=generator -> [bus, technology])`     |
| **D**  | `sum(p, by=slot_of(generator -> bus))`               | `sum(p, by=slot_of(generator -> [bus, technology]))`               |
| **E**  | `sum(p, over=slot_of.generator, into=slot_of.bus)`   | `sum(p, over=slot_of.generator, into=slot_of.[bus, technology])`   |
| **F**  | `sum(p, by=slot_of.[period, bus])`                   | `sum(p, by=slot_of.[period, bus, technology])`                     |

### 5 and 6 — sum the whole key away

Nothing is joined on, so `period` leaves with `generator`.

- **5** `p[generator, period]` → `[bus]`.
- **6** `p[generator, period]` → `[bus, technology]`.

| option | 5                                                              | 6                                                                            |
| ------ | -------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **A**  | `sum(p, by=slot_of, over=[generator, period], into=bus)`       | `sum(p, by=slot_of, over=[generator, period], into=[bus, technology])`       |
| **B**  | `sum(p, by=slot_of, consume=[generator, period], produce=bus)` | `sum(p, by=slot_of, consume=[generator, period], produce=[bus, technology])` |
| **C**  | `sum(p, by=slot_of, direction=[generator, period] -> bus)`     | `sum(p, by=slot_of, direction=[generator, period] -> [bus, technology])`     |
| **D**  | `sum(p, by=slot_of([generator, period] -> bus))`               | `sum(p, by=slot_of([generator, period] -> [bus, technology]))`               |
| **E**  | `sum(p, over=slot_of.[generator, period], into=slot_of.bus)`   | `sum(p, over=slot_of.[generator, period], into=slot_of.[bus, technology])`   |
| **F**  | `sum(p, by=slot_of.bus)`                                       | `sum(p, by=slot_of.[bus, technology])`                                       |

### 7 and 13 — two columns over one dimension, and a bare relation

- **7** `f[line]` → `[bus]` through `ends`: producing `bus1` produces the dimension `bus`, and `bus0` is not read.
- **13** `p[generator, period]` → `[bus, period]` through `connection`: the transform is case 1's, but a generator may stand against several buses, so a term can land in more than one group.

| option | 7                                             | 13                                                       |
| ------ | --------------------------------------------- | -------------------------------------------------------- |
| **A**  | `sum(f, by=ends, over=line, into=bus1)`       | `sum(p, by=connection, over=generator, into=bus)`        |
| **B**  | `sum(f, by=ends, consume=line, produce=bus1)` | `sum(p, by=connection, consume=generator, produce=bus)`  |
| **C**  | `sum(f, by=ends, direction=line -> bus1)`     | `sum(p, by=connection, direction=generator -> bus)`      |
| **D**  | `sum(f, by=ends(line -> bus1))`               | `sum(p, by=connection(generator -> bus))`                |
| **E**  | `sum(f, over=ends.line, into=ends.bus1)`      | `sum(p, over=connection.generator, into=connection.bus)` |
| **F**  | `sum(f, by=ends.bus1)`                        | `sum(p, by=connection.bus)`                              |

A bare relation has no value column, so there is no `rel.col(g)` to read. The
printed condition is the row itself, a membership rather than a function read,
and no spelling reads differently for it.

### 8 and 9 — the reads

A read runs the other way from a sum: it consumes the value column and
produces the key.

- **8** `price[bus]` → `[generator]` through `gen_bus`.
- **9** `cap[bus]` → `[line]` through `ends`, reading one of two columns over one dimension.

| option | 8                                                       | 9                                              |
| ------ | ------------------------------------------------------- | ---------------------------------------------- |
| **A**  | `at(price, by=gen_bus, over=bus, into=generator)`       | `at(cap, by=ends, over=bus0, into=line)`       |
| **B**  | `at(price, by=gen_bus, consume=bus, produce=generator)` | `at(cap, by=ends, consume=bus0, produce=line)` |
| **C**  | `at(price, by=gen_bus, direction=bus -> generator)`     | `at(cap, by=ends, direction=bus0 -> line)`     |
| **D**  | `at(price, by=gen_bus(bus -> generator))`               | `at(cap, by=ends(bus0 -> line))`               |
| **E**  | `at(price, over=gen_bus.bus, into=gen_bus.generator)`   | `at(cap, over=ends.bus0, into=ends.line)`      |
| **F**  | `at(price, by=gen_bus.bus)`                             | `at(cap, by=ends.bus0)`                        |
| **G**  | `price[gen_bus.bus]`                                    | `cap[ends.bus0]`                               |

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

## The printed math rules nothing out

Every option prints the same math, which
[#516](https://github.com/energy-models/math-spec/issues/516) measured. It
already spells a value column with a dot, which is E's and F's character, and
it already prints a read as a subscript, which is G's:

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
meaning in a file: the breakpoint axis of a `piecewise:` or `sos:` declaration.
Its price is the 40 relation-free sums, and that `sum(p, over=generator)` reads
like a sum sign where `sum(p, consume=generator)` does not.

C and D pay a new piece of grammar for a refusal the loader already gives: a
walk that leaves one end unsaid is refused today, and the message names the
rewrite. D also gives one bracket two meanings. E writes the relation twice,
and F is the one option where the frame law's own terms are not on the line.
Both fix a macro's columns.

<details><summary>How the A column was measured</summary>

Each case is one constraint over the declarations above, loaded with `to_spec`,
and the math line is `typeset_declaration(model, 'c', 'latex')`. All nineteen
load.

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
the same math was not repeated here.

</details>
