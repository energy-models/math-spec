<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The file and the program

This page explains why a loaded model is two objects, and which one each tool
reads. You need none of it to write a model.
[Reading a loaded model](../reference/reading.md) is the reference for both.

```text
file  ── to_spec ──▶  Spec  ── .program ──▶  Program
                       │
                       └── .expand() ──▶  Spec of the rows  ── .program ──▶  Program of the rows
```

## Two states

**A `Spec` is the file as written**, checked against every rule that needs no
data. **A `Program` is what the file means**: every name typed, every operator
resolved to a node, every macro expanded, and each `piecewise:` or `sos:` block
kept as one declaration.

## Which tool reads which

| Tool                       | Reads                                       | Because                                           |
| -------------------------- | ------------------------------------------- | ------------------------------------------------- |
| The typesetter             | `spec.program`, or a `Program` handed to it | it prints each curve as the curve the file states |
| `advice`                   | `spec.program`                              | its notes are about the model the author wrote    |
| An engine that builds rows | the program of `spec.expand()`              | a solver takes rows                               |
| A tool that rewrites files | the `Spec`                                  | only the spec holds the text and the macros       |

## Why the split falls here

- **A reader after load needs one typed object.** Printing a model needs the
  typed trees, the descriptions and the curves together. The program carries
  all three, so no reader parses text again or reads two objects.
- **The program keeps the model the author wrote.** A curve is one declaration
  to print and one to explain. Its rows are one formulation of it, so the rows
  are a second model, which a caller asks for with
  [`spec.expand()`](../reference/reading.md#formulations-written-out).
- **The spec keeps the text.** A tool that rewrites a model needs the file as
  written: `to_yaml()` writes it back, and `expand()` rewrites it. A tree does
  not give the text back.
- **The program does not hold its spec.** Nothing reads the file from a
  program, and two objects that own each other form a cycle. A tool handed a
  bare `Program` has the model, not the file.
