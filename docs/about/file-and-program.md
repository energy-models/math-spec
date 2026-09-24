<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The file and the program

This page explains why a loaded model is two objects, and which one each tool
reads. Read it before you write a tool that reads models. You need none of it
to write a model.

```text
file  ── to_spec ──▶  Spec  ── .program ──▶  Program
                       │
                       └── .expand() ──▶  Spec of the rows  ── .program ──▶  Program of the rows
```

## Two states

**A `Spec` is the file as written.** `to_spec` reads the YAML into a `Spec`
and checks every rule that needs no data. The spec keeps the file's own
spelling: an expression is a string, a bound is a number or a parameter's
name, and a macro is its template.

**A `Program` is what the file means.** `spec.program` holds every declaration
of the file, section for section, with every name typed and every operator
resolved to a node. The macros are expanded into the trees. A
[`piecewise:`](../reference/language/piecewise.md) block stays one curve, and a
`sos:` block stays one set. Every description is there.

Lowering builds the program once, while the spec loads. A spec in hand has
already passed every rule, and `spec.program` returns the same object on every
ask.

|                  | `Spec`                   | `Program`                                   |
| ---------------- | ------------------------ | ------------------------------------------- |
| An expression    | the text the file wrote  | a typed tree of nodes                       |
| A macro          | its template             | expanded into every tree that calls it      |
| A curve          | the block as written     | one `PiecewiseDeclaration`, its links typed |
| A set            | the block as written     | one `SosDeclaration`                        |
| A description    | as written               | on each declaration                         |
| Written back out | `to_yaml()`, `to_dict()` | not at all: trees do not give the text back |

## The rows

A curve or a set stands for plain variables and constraints.
`spec.expand('piecewise')` writes each curve out as those rows, and
`spec.expand()` writes the sets out too. Each returns a new `Spec`, checked as
any other, with a program of its own. It is a different model from the one it
came from, and the two do not compare equal. The spec keeps no expansion, so a
caller that needs the rows twice holds the result.

**Nothing in the package expands a model unasked.** Each tool reads the model
as it arrives. A caller that wants the rows asks for them, and
[see what a curve or a set expands to](../howto/see-an-expansion.md) shows how.

## Which tool reads which

| Tool                       | Reads                                                          | Because                                                       |
| -------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------- |
| The typesetter             | `spec.program`, or a `Program` handed to it                    | it prints each curve as the curve the file states             |
| `advice`                   | `spec.program`                                                 | its notes are about the model the author wrote                |
| An engine that builds rows | `spec.expand('piecewise').program`, or `spec.expand().program` | a solver takes rows, and the engine knows which sets it takes |
| A tool that rewrites files | the `Spec`                                                     | only the spec holds the text and the macros                   |

**The typesetter never reads the spec.** A `Program` handed to it prints the
same as the spec it came from.

**A program's `footprint`, `separability` and `roots` describe the rows that
program holds.** A curve still on the program is not a row, so it counts once
it is written out. An engine asks these of the program of the expansion, which
is the one it builds.

**`advice` reads a curve's links as the rows they state.** Its notes are
claims, and a curve that holds a variable keeps that variable out of the
unbounded note. So advice on the spec and advice on its expansion agree.

## Why the split falls here

- **A reader after load needs one typed object.** Printing a model needs the
  typed trees, the descriptions and the curves together. The program carries
  all three, so no reader parses text again or reads two objects.
- **The program keeps the model the author wrote.** A curve is one declaration
  to print and one to explain. Its rows are one formulation of it, so the rows
  are a second model that a caller asks for.
- **The spec keeps the text.** A tool that rewrites a model needs the file as
  written: `to_yaml()` writes it back, and `expand()` rewrites it. A tree does
  not give the text back.
- **The program does not hold its spec.** Nothing reads the file from a
  program, and two objects that own each other form a cycle. A tool handed a
  bare `Program` has the model, not the file.

[Reading a loaded model](../reference/reading.md) is the reference for both
objects: their fields, the nodes, and the questions a program answers.
