<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Examples

Each page here shows one whole model as the file and as the math it prints.
Every model is a file under `examples/` in the repository.

- [Least-cost dispatch](dispatch.md) is the smallest whole model. It has a
  balance, a bound and a cost to minimise.
- [Unit commitment](commitment.md) adds a start-up ramp. One quantity is defined
  by region, so a single inequality covers both regimes.
- [One construct per model](operators.md) declares each operator in the smallest
  file that can, and prints the equation beside it.

The PyPSA parity pages, from [PyPSA in one file](pypsa.md) on, are a proof of
concept. They sit in the Development section.

[Typeset the math](../reference/typeset.md) prints your own.
