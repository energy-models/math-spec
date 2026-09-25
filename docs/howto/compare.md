<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compare two specs

Diff two spec files so that the diff shows only what the specs state
differently. A plain text diff also shows the order of declarations, spacing
and the order of the terms in a sum. The canonical form removes those
differences. [Comparing two specs](../reference/reading.md#comparing-two-specs)
lists what the form sorts and what it keeps.

1. **Write one spec in the canonical form.**

   ```bash
   python -m mathspec canonical spec.yaml
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
   specs, and which command writes them out:

   ```bash
   echo 'specs/*.yaml diff=mathspec' >> .gitattributes
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

   Match only spec files in `.gitattributes`. Git runs the command on every
   file the pattern matches, and a YAML file that is not a spec fails to load.

4. **Keep specs in the canonical form in CI.** Then the files themselves
   diff the way the form does, with no git setup. `--write` rewrites a file in
   the form. The form holds no YAML comments, so `--write` drops them:

   ```bash
   python -m mathspec canonical --write spec.yaml
   ```

   `--check` writes nothing. It exits with status 1 if the file is not in the
   form, and names the rewrite:

   ```text
   spec.yaml is not in the canonical form. Run `python -m mathspec canonical --write spec.yaml` to rewrite it.
   ```

   Check every spec, and fail the job if one of them fails:

   ```bash
   status=0
   for spec in specs/*.yaml; do python -m mathspec canonical --check "$spec" || status=1; done
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
