# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The curves the piecewise tests are written against.

`piecewise:` expansion is the language's — a formulation emits declarations, and
declarations are language — so its load-time tests live beside it. The curves
are a module of their own rather than a fixture in one test file because more
than one file reads them: one model text, whichever test judges it.

They are larger than a minimal probe on purpose: a curve that exercises
adjacency binaries, links and a gate is not something a smaller one can stand
in for, and shrinking it would change what the tests test.
"""

from __future__ import annotations

from tests.fixtures import override, raw_of

NONCONVEX_YAML = """
dimensions:
  snapshot: {dtype: int}
  bp: {dtype: int}

parameters:
  load: {dims: [snapshot]}
  bp_x: {dims: [bp]}
  bp_y: {dims: [bp]}

variables:
  p:
    foreach: [snapshot]
    bounds: {lower: 0, upper: 100}
  op_cost:
    foreach: [snapshot]
    bounds: {lower: 0}

piecewise:
  cost_curve:
    over: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y]

constraints:
  balance:
    foreach: [snapshot]
    expression: p == load

objective:
  sense: minimize
  expression: sum(op_cost, over=snapshot)
"""
#: And the same restriction as the default's, said as a set rather than built
#: out of binaries. The two must reach the same optimum on every sink.
SOS2_MODEL = override(raw_of(NONCONVEX_YAML), **{'piecewise.cost_curve.method': 'sos2'})
#: two dims in the frame, so the emitted ``foreach`` has an order to get wrong.
TWO_DIM_YAML = """
dimensions:
  snapshot: {dtype: int}
  generator: {dtype: str}
  bp: {dtype: int}

parameters:
  load: {dims: [snapshot]}
  bp_x: {dims: [generator, bp]}
  bp_y: {dims: [generator, bp]}

variables:
  p:
    foreach: [snapshot, generator]
    bounds: {lower: 0, upper: 100}
  op_cost:
    foreach: [snapshot, generator]
    bounds: {lower: 0}

piecewise:
  cost_curve:
    over: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y]

constraints:
  balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load

objective:
  sense: minimize
  expression: sum(sum(op_cost, over=generator), over=snapshot)
"""
CHP_YAML = """
dimensions:
  snapshot: {dtype: int}
  bp: {dtype: int}

parameters:
  load: {dims: [snapshot]}
  power_bp: {dims: [bp]}
  fuel_bp: {dims: [bp]}
  heat_bp: {dims: [bp]}

variables:
  power:
    foreach: [snapshot]
    bounds: {lower: 0, upper: 100}
  fuel:
    foreach: [snapshot]
    bounds: {lower: 0}
  heat:
    foreach: [snapshot]
    bounds: {lower: 0}

piecewise:
  chp:
    over: bp
    links:
      - [power, power_bp]
      - [fuel, fuel_bp]
      - [heat, heat_bp]

constraints:
  balance:
    foreach: [snapshot]
    expression: power == load

objective:
  sense: minimize
  expression: sum(fuel, over=snapshot)
"""
GATED_YAML = """
dimensions:
  snapshot: {dtype: int}
  bp: {dtype: int}

parameters:
  load: {dims: [snapshot]}
  on_flag: {dims: [snapshot]}
  bp_x: {dims: [bp]}
  bp_y: {dims: [bp]}

variables:
  u:
    foreach: [snapshot]
    domain: binary
  p:
    foreach: [snapshot]
    bounds: {lower: 0, upper: 100}
  op_cost:
    foreach: [snapshot]
    bounds: {lower: 0}

piecewise:
  cost_curve:
    over: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y]
    activity: u

constraints:
  commit:
    foreach: [snapshot]
    expression: u == on_flag
  balance:
    foreach: [snapshot]
    expression: p == load * on_flag

objective:
  sense: minimize
  expression: sum(op_cost, over=snapshot)
"""


LP_MODEL = """
description: dispatch whose cost is read off a convex curve, stated as its segment lines

dimensions:
  snapshot: {dtype: int, description: dispatch periods}
  bp: {dtype: int, description: breakpoints of the cost curve}

parameters:
  load: {dims: [snapshot], description: demand to be met}
  bp_x: {dims: [bp], description: breakpoint output levels}
  bp_y: {dims: [bp], description: cost at each breakpoint}

variables:
  p:
    foreach: [snapshot]
    bounds: {lower: 0, upper: 100}
    description: dispatched power
  op_cost:
    foreach: [snapshot]
    bounds: {lower: 0}
    description: operating cost, read off the curve
  running:
    foreach: [snapshot]
    domain: binary
    description: unused here; a gate for the case lp cannot take one

piecewise:
  cost_curve:
    description: cost bounded below by the curve, which is exact where the curve is convex
    over: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y, '>=']
    method: lp

constraints:
  balance:
    foreach: [snapshot]
    expression: p == load
    description: output meets demand

objective:
  sense: minimize
  expression: sum(op_cost, over=snapshot)
  description: total operating cost
"""
