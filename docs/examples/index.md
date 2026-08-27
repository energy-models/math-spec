<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Examples

Whole models, each shown as the file and as the math it prints. The reference
pages take the language a construct at a time; these take it a **model** at a
time, which is the form anyone writing one actually needs.

Every model here is a real file under `examples/` in the repository, not a
fragment written for the page. They are the same files the test suite loads and
the LaTeX gate compiles, so a model that stopped being valid — or that started
printing different math — fails CI rather than going stale here.

- [Least-cost dispatch](dispatch.md) — the smallest model that is a model: a
  balance, a bound, and a cost to minimise.
- [Unit commitment](commitment.md) — a start-up ramp, and the quantity
  defined by region that lets one inequality cover both regimes.
- [One construct per model](operators.md) — the operator probes: the smallest
  file that declares each built-in, beside the equation it renders.
- [PyPSA in one file](pypsa.md) — the model `n.optimize()` builds, a
  declaration at a time: PyPSA's name for the row, the YAML, the equation.

The math on these pages is written by the typesetter, from the file above it —
see [Typeset the math](../reference/typeset.md) for how to print your own.
