<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Examples

Each page here shows one whole model as the file and as the math it prints. The
reference pages take the language one construct at a time; these take it one
model at a time.

Every model is a file under `examples/` in the repository. The test suite loads
the same files, and the LaTeX gate compiles them, so a model that stops loading
or starts printing different math fails CI.

- [Least-cost dispatch](dispatch.md) is the smallest whole model. It has a
  balance, a bound and a cost to minimise.
- [Unit commitment](commitment.md) adds a start-up ramp. One quantity is defined
  by region, so a single inequality covers both regimes.
- [One construct per model](operators.md) declares each operator in the smallest
  file that can, and prints the equation beside it.
- [PyPSA in one file](pypsa.md) states the model `n.optimize()` builds, one
  declaration at a time. PyPSA's name for each row sits beside the YAML and the
  equation.

The math on these pages is printed by the typesetter from the file above it. See
[Typeset the math](../reference/typeset.md) to print your own.
