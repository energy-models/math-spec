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
- [PyPSA in one file](pypsa.md) states the model `n.optimize()` builds, one
  declaration at a time. PyPSA's name for each row sits beside the YAML and the
  equation.
- [A component library](library/index.md) is several files that compose into
  one model. Each file reads the coupling surface and prints on its own, and the
  composed page shows what `merge` returns.

The math on these pages is printed by the typesetter from the file above it. See
[Typeset the math](../reference/typeset.md) to print your own.
