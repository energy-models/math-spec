<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Check a model without data

Refuse a broken model file before any data or solver is involved, on your
machine and in CI.

1. **Run the check on one file.**

   ```bash
   python -m math_spec check model.yaml
   ```

   A refusal prints its message on stderr and exits with status 1:

   ```text
   variables.p: unknown key 'boundz' in a variable declaration. Did you mean 'bounds'?
   ```

   Advice prints on stdout and exits with status 0. A model the language
   accepts with nothing to advise prints nothing.

   ```text
   Variable 'slack' makes this model unbounded: no constraint names it, and bounds.lower is -inf, which is the direction a +slack term improves a minimize objective in. No data can change that, so the solve would answer `unbounded` and name nothing.
   Give it a finite bounds.lower, or the constraint that was meant to define it.
   ```

2. **Run it over every model in CI.** The exit status is the gate, so a shell
   loop is the whole job:

   ```bash
   for model in models/*.yaml; do python -m math_spec check "$model" || exit 1; done
   ```

3. **Ask from Python** where the check is one step of a longer script.
   `to_spec` raises a `MathSpecError` for anything the language refuses, and
   `advice` returns what it would print:

   ```python
   import math_spec as ms

   spec = ms.to_spec('model.yaml')
   for note in ms.advice(spec):
       print(note)
   ```

**Without Python**, the JSON schema checks the file's structure and nothing
inside an `expression:` or `where:` string:
[editor completion and offline checking](installation.md#editor-completion-and-offline-checking).
What each refusal and each piece of advice means is under
[reading a loaded model](../reference/language/reading.md#what-the-loader-refuses).
