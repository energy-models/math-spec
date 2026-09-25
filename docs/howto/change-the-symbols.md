<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Change the symbols for one render

Print a model with symbols other than the ones its
[`symbols:`](../reference/typeset.md#symbol-tables) block declares, and leave
the file as it is. Use this for one document that needs another convention,
or for a reader whose LaTeX lacks a package the file's table needs.

`symbols=` replaces the file's whole block, and nothing merges the two. So
start from a copy of the file's block and edit it.

## 1. Copy the file's block

`to_dict()` returns the model as plain data, and its `symbols` entry is a dict
of the shape `symbols=` takes. The dict is a copy, so editing it leaves the
spec as it is.

```python
import mathspec as ms

spec = ms.to_spec('model.yaml')
table = spec.to_dict().get('symbols', {})
```

A model with no `symbols:` block has no `symbols` entry, which is what the
`{}` default covers.

## 2. Edit it

Change, add or delete an entry. Use `setdefault` for a notation or a section
the file does not spell yet:

```python
latex = table.setdefault('latex', {})
latex.setdefault('names', {})['cost'] = r'\kappa'  # change or add a name
latex['names'].pop('capacity')  # derive this one instead
latex.setdefault('dimensions', {}).pop('snapshot')  # derive its index and set
```

A name or a dimension you delete prints with its derived symbol, such as
$\mathrm{capacity}_g$.

## 3. Render with it

Pass the edited dict to any of the three functions:

```python
print(ms.to_latex(spec, symbols=table))
```

The table is checked against the model as the file's own block is. An entry
that names nothing is refused with the near miss:

```text
symbols: latex: 'costt' under names: is not declared by the model. Did you mean 'cost'?
```

## 4. Use it from a shell

Write the dict to a file and pass it with `--symbols`:

```python
import yaml

with open('model.symbols.yaml', 'w') as f:
    yaml.safe_dump(table, f, allow_unicode=True)
```

```bash
python -m mathspec latex model.yaml --symbols model.symbols.yaml
```

To derive every symbol and ignore the file's block, pass `symbols={}` or
`--no-symbols`.
