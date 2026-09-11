<!--
SPDX-FileCopyrightText: math-spec Contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The lookup claims, as models that load or refusals that print

`gams_probes.py` holds one whole model per claim made in
[the GAMS comparison issue](https://github.com/energy-models/math-spec/issues).
A probe that claims a capability is expected to load, and the evidence is the
frame the loader gives its constraint. A probe that claims a refusal is
expected to fail, and the evidence is the message.

This is a decision aid, not part of the language. It is not for `main`.

## Run it

The script needs `math_spec` importable and nothing else.

```bash
git switch --detach <the ref to measure>
pixi run python comparison-gams/gams_probes.py
```

It prints one row per probe and exits non-zero if any verdict is
`CONTRADICTED`. `--write-yaml DIR` writes each probe as a standalone model
file, and `--json OUT` writes the rows.

## Contradict it

A claim that stops holding shows up as a row whose verdict flipped. Two kinds
of flip mean different things:

- **A refusal that starts loading** means the language grew. Move the row to
  the capability half and say which change did it.
- **A capability that starts refusing** means either a rule tightened or the
  probe was wrong. Read the message before you read the claim.

Add a probe for a claim the table does not carry yet. A claim with no probe is
an opinion.

## What this cannot check

The GAMS side. No GAMS runs here, so every GAMS claim in the issue comes from
the documentation and from idiom, and none of it is measured. That half is the
part most in need of contradiction by somebody with a licence.
