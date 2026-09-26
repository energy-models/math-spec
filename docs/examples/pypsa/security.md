<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Security

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the security-constrained flows over the outages. It reads `Line_s_max_pu`, `Line_s_monitored`, `Line_s_nom`, `Line_s_nom_ext`, `Line_s_nom_extendable`, `Transformer_s_max_pu` and 4 more under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  line:
    description: passive branches, each between two buses, their flow set by impedance
  transformer:
    description: passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised
  outage:
    description: >-
      the passive branches a security-constrained run takes out one at a time
      — PyPSA's `branch_outages`, each a line or a transformer; none on a
      plain run

relations:
  Outage_line:
    description: the line an outage takes out; an outage of a transformer has no row
    key: outage
    values: line
  Outage_transformer:
    description: the transformer an outage takes out; an outage of a line has no row
    key: outage
    values: transformer

parameters:
  Line_BODF:
    description: >-
      the share of an outaged branch's flow a line takes on when that branch
      goes out — PyPSA's `BODF`, from the sub-network's PTDF, data prep; a row
      only where the line and the outage share a sub-network, -1 at the
      outaged line itself
    dims: [line, outage]
  Transformer_BODF:
    description: >-
      the share of an outaged branch's flow a transformer takes on when that
      branch goes out, as a line's; a row only where the transformer and the
      outage share a sub-network
    dims: [transformer, outage]

given:
  parameters:
    Line_s_nom: { dims: [scenario, line] }
    Line_s_nom_extendable: { dims: [line], dtype: bool }
    Line_s_max_pu: { dims: [scenario, snapshot, line] }
    Transformer_s_nom: { dims: [scenario, transformer] }
    Transformer_s_nom_extendable: { dims: [transformer], dtype: bool }
    Transformer_s_max_pu: { dims: [scenario, snapshot, transformer] }
  variables:
    Line_s_nom_ext: { dims: [line] }
    Transformer_s_nom_ext: { dims: [transformer] }
  expressions:
    Line_s_monitored: { dims: [scenario, snapshot, line] }
    Transformer_s_monitored: { dims: [scenario, snapshot, transformer] }

expressions:
  Outage_s:
    description: >-
      the flow an outage takes off its branch — the outaged line's or
      transformer's flow before it goes out
    dims: [scenario, snapshot, outage]
    cases:
      line: { when: Outage_line, expression: "at(Line_s_monitored, by=Outage_line, over=line, into=outage)" }
    otherwise: at(Transformer_s_monitored, by=Outage_transformer, over=transformer, into=outage)

constraints:
  Line_fix_s_lower_security:
    description: >-
      `Line-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}` —
      after any one outage, a fixed line carries at least the negative
      of its rating: its flow takes on its share of the outaged branch's
      flow. PyPSA names one row per outaged component `c` and
      sub-network `n`; this block states them all over the outage
      dimension
    dims: [scenario, snapshot, line, outage]
    where: not Line_s_nom_extendable AND Line_BODF
    expression: Line_s_monitored + Line_BODF * Outage_s >= -Line_s_max_pu * Line_s_nom
  Line_fix_s_upper_security:
    description: >-
      `Line-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}` —
      after any one outage, a fixed line carries at most its rating: its
      flow takes on its share of the outaged branch's flow. PyPSA names
      one row per outaged component `c` and sub-network `n`; this block
      states them all over the outage dimension
    dims: [scenario, snapshot, line, outage]
    where: not Line_s_nom_extendable AND Line_BODF
    expression: Line_s_monitored + Line_BODF * Outage_s <= Line_s_max_pu * Line_s_nom
  Line_ext_s_lower_security:
    description: >-
      `Line-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}` —
      after any one outage, an extendable line carries at least the
      negative of its rating of the chosen build: its flow takes on its
      share of the outaged branch's flow. PyPSA names one row per
      outaged component `c` and sub-network `n`; this block states them
      all over the outage dimension
    dims: [scenario, snapshot, line, outage]
    where: Line_s_nom_extendable AND Line_BODF
    expression: Line_s_monitored + Line_BODF * Outage_s >= -Line_s_max_pu * Line_s_nom_ext
  Line_ext_s_upper_security:
    description: >-
      `Line-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}` —
      after any one outage, an extendable line carries at most its rating
      of the chosen build: its flow takes on its share of the outaged
      branch's flow. PyPSA names one row per outaged component `c` and
      sub-network `n`; this block states them all over the outage
      dimension
    dims: [scenario, snapshot, line, outage]
    where: Line_s_nom_extendable AND Line_BODF
    expression: Line_s_monitored + Line_BODF * Outage_s <= Line_s_max_pu * Line_s_nom_ext
  Transformer_fix_s_lower_security:
    description: >-
      `Transformer-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}`
      — after any one outage, a fixed transformer carries at least the
      negative of its rating: its flow takes on its share of the outaged
      branch's flow. PyPSA names one row per outaged component `c` and
      sub-network `n`; this block states them all over the outage
      dimension
    dims: [scenario, snapshot, transformer, outage]
    where: not Transformer_s_nom_extendable AND Transformer_BODF
    expression: Transformer_s_monitored + Transformer_BODF * Outage_s >= -Transformer_s_max_pu * Transformer_s_nom
  Transformer_fix_s_upper_security:
    description: >-
      `Transformer-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}`
      — after any one outage, a fixed transformer carries at most its
      rating: its flow takes on its share of the outaged branch's flow.
      PyPSA names one row per outaged component `c` and sub-network `n`;
      this block states them all over the outage dimension
    dims: [scenario, snapshot, transformer, outage]
    where: not Transformer_s_nom_extendable AND Transformer_BODF
    expression: Transformer_s_monitored + Transformer_BODF * Outage_s <= Transformer_s_max_pu * Transformer_s_nom
  Transformer_ext_s_lower_security:
    description: >-
      `Transformer-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}`
      — after any one outage, an extendable transformer carries at least
      the negative of its rating of the chosen build: its flow takes on
      its share of the outaged branch's flow. PyPSA names one row per
      outaged component `c` and sub-network `n`; this block states them
      all over the outage dimension
    dims: [scenario, snapshot, transformer, outage]
    where: Transformer_s_nom_extendable AND Transformer_BODF
    expression: Transformer_s_monitored + Transformer_BODF * Outage_s >= -Transformer_s_max_pu * Transformer_s_nom_ext
  Transformer_ext_s_upper_security:
    description: >-
      `Transformer-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}`
      — after any one outage, an extendable transformer carries at most
      its rating of the chosen build: its flow takes on its share of the
      outaged branch's flow. PyPSA names one row per outaged component
      `c` and sub-network `n`; this block states them all over the
      outage dimension
    dims: [scenario, snapshot, transformer, outage]
    where: Transformer_s_nom_extendable AND Transformer_BODF
    expression: Transformer_s_monitored + Transformer_BODF * Outage_s <= Transformer_s_max_pu * Transformer_s_nom_ext
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{K}`$ | index $`k`$ — `line` with $`\mathrm{Outage\_line}: \mathcal{K}^{\mathrm{out}} \to \mathcal{K}`$ — passive branches, each between two buses, their flow set by impedance |
| $`\mathcal{M}`$ | index $`m`$ — `transformer` with $`\mathrm{Outage\_transformer}: \mathcal{K}^{\mathrm{out}} \to \mathcal{M}`$ — passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised |
| $`\mathcal{K}^{\mathrm{out}}`$ | index $`\kappa`$ — `outage` with $`\mathrm{Outage\_line}: \mathcal{K}^{\mathrm{out}} \to \mathcal{K},\ \mathrm{Outage\_transformer}: \mathcal{K}^{\mathrm{out}} \to \mathcal{M}`$ — the passive branches a security-constrained run takes out one at a time — PyPSA's `branch_outages`, each a line or a transformer; none on a plain run |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\beta`$ | `Line_BODF` over $`\mathcal{K} \times \mathcal{K}^{\mathrm{out}}`$ — the share of an outaged branch's flow a line takes on when that branch goes out — PyPSA's `BODF`, from the sub-network's PTDF, data prep; a row only where the line and the outage share a sub-network, -1 at the outaged line itself |
| $`\beta^{\sigma}`$ | `Transformer_BODF` over $`\mathcal{M} \times \mathcal{K}^{\mathrm{out}}`$ — the share of an outaged branch's flow a transformer takes on when that branch goes out, as a line's; a row only where the transformer and the outage share a sub-network |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{s}^{\mathrm{nom}}`$ | `Line_s_nom` over $`\Xi \times \mathcal{K}`$, data another file declares |
| $`\mathrm{ext}^{s}`$ | `Line_s_nom_extendable` over $`\mathcal{K}`$, data another file declares |
| $`\overline{\mathrm{s}}`$ | `Line_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$, data another file declares |
| $`\sigma^{\mathrm{nom}}`$ | `Transformer_s_nom` over $`\Xi \times \mathcal{M}`$, data another file declares |
| $`\mathrm{ext}^{\sigma}`$ | `Transformer_s_nom_extendable` over $`\mathcal{M}`$, data another file declares |
| $`\overline{\sigma}`$ | `Transformer_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$, data another file declares |
| $`S`$ | `Line_s_nom_ext` over $`\mathcal{K}`$ |
| $`\Sigma`$ | `Transformer_s_nom_ext` over $`\mathcal{M}`$ |
| $`\check{s}`$ | `Line_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$, an expression another file defines |
| $`\check{\sigma}`$ | `Transformer_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$, an expression another file defines |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\hat{s}`$ | `Outage_s` over $`\Xi \times \mathcal{T} \times \mathcal{K}^{\mathrm{out}}`$ — the flow an outage takes off its branch — the outaged line's or transformer's flow before it goes out |

#### Subject to

**`Line_fix_s_lower_security`**

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

**`Line_fix_s_upper_security`**

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

**`Line_ext_s_lower_security`**

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

**`Line_ext_s_upper_security`**

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

**`Transformer_fix_s_lower_security`**

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

**`Transformer_fix_s_upper_security`**

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

**`Transformer_ext_s_lower_security`**

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

**`Transformer_ext_s_upper_security`**

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

#### Definitions

**`Outage_s`**

```math
\hat{s}_{\xi,t,\kappa} = \begin{cases} \check{s}_{\xi,t,\mathrm{Outage\_line}(\kappa)} & \text{if } \mathrm{Outage\_line}(\kappa) \text{ is defined} \\ \check{\sigma}_{\xi,t,\mathrm{Outage\_transformer}(\kappa)} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ \kappa \in \mathcal{K}^{\mathrm{out}}
```
<!-- gallery:end -->
