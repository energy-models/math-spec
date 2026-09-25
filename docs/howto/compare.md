<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compare two models

Diff two model files so that the diff shows only what the models mean
differently. A plain text diff also shows the order of declarations, spacing
and the order of the terms in a sum. The canonical form removes those
differences. [Comparing two models](../reference/reading.md#comparing-two-models)
lists what the form sorts and what it keeps.

1. **Write one model in the canonical form.**

   ```bash
   python -m mathspec canonical model.yaml
   ```

   The form goes to stdout. `-o canonical.yaml` writes it to a file instead. A
   file the language refuses prints its message on stderr and exits with
   status 1.

2. **Diff two files once.** Give each file to the command, and diff the two
   outputs:

   ```bash
   diff <(python -m mathspec canonical before.yaml) <(python -m mathspec canonical after.yaml)
   ```

3. **Make `git diff` show the canonical form.** Tell git which files are
   models, and which command writes them out:

   ```bash
   echo 'models/*.yaml diff=mathspec' >> .gitattributes
   git config diff.mathspec.textconv "python -m mathspec canonical"
   ```

   The files in the repository stay as you wrote them. Only the diff changes.
   A commit that writes `sum(dispatch * cost)` as `sum(cost * dispatch)` shows
   no difference. A commit that changes a coefficient shows one line:

   ```diff
    objective:
      sense: minimize
   -  expression: sum(cost * dispatch)
   +  expression: sum((2 * cost) * dispatch)
   ```

   Match only model files in `.gitattributes`. Git runs the command on every
   file the pattern matches, and a YAML file that is not a model fails to load.

4. **Keep models in the canonical form in CI.** Then the files themselves
   diff the way the form does, with no git setup. `--write` rewrites a file in
   the form. The form holds no YAML comments, so `--write` drops them:

   ```bash
   python -m mathspec canonical --write model.yaml
   ```

   `--check` writes nothing. It exits with status 1 if the file is not in the
   form, and names the rewrite:

   ```text
   model.yaml is not in the canonical form. Run `python -m mathspec canonical --write model.yaml` to rewrite it.
   ```

   Check every model, and fail the job if one of them fails:

   ```bash
   status=0
   for model in models/*.yaml; do python -m mathspec canonical --check "$model" || status=1; done
   exit $status
   ```

5. **Compare from Python** where the comparison is one step of a longer
   script. [`to_yaml`](../reference/api.md#mathspec.Spec.to_yaml) writes the
   same text with `canonical=True`:

   ```python
   import mathspec as ms

   before = ms.to_spec('before.yaml').to_yaml(canonical=True)
   after = ms.to_spec('after.yaml').to_yaml(canonical=True)
   print(before == after)
   ```
