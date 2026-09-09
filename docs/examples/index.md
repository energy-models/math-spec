<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Examples

These pages show whole models, each as its file and as the math the
typesetter prints from it. The reference pages take the language a construct at a time;
these take it a model at a time.

Every model is a file under `examples/` in the repository. The test suite
loads each one and the LaTeX gate compiles it, so a model that stops loading,
or starts printing different math, fails CI.

- [Least-cost dispatch](dispatch.md) — the smallest model that is a model: a
  balance, a bound, and a cost to minimise.
- [Unit commitment](commitment.md) — a start-up ramp, and the quantity
  defined by region that lets one inequality cover both regimes.
- [One construct per model](operators.md) — the operator probes: the smallest
  file that declares each built-in, beside the equation it renders.
- [PyPSA in one file](pypsa.md) — the model `n.optimize()` builds, a
  declaration at a time: PyPSA's name for the row, the YAML, the equation.
- [PyPSA, the quadratic class](pypsa_quadratic.md) — rung 10,
  `marginal_cost_quadratic`, in a file of its own.
- [PyPSA, the relaxed commitment](pypsa_linearized_uc.md) — rung 12,
  `linearized_unit_commitment=True`.
- [PyPSA, the lossy lines](pypsa_losses.md) — rung 13, `transmission_losses`
  as tangent segments.
- [PyPSA, the two-stage class](pypsa_stochastic.md) — rung 14, scenarios with a
  risk preference.
- [PyPSA, the multi-period class](pypsa_multi_period.md) — rung 15,
  `multi_investment_periods=True` over build years and lifetimes.

[Typeset the math](../reference/typeset.md) says how to print your own.
