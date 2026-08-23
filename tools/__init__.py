# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Generators whose source is the language, and whose output is its reference.

Each rewrites a block of documentation from the thing it documents, so the page
cannot drift from the code: the JSON Schema is `Model.model_json_schema()`, the
operator table is every builtin printed through the typesetter, the notation
page is every construct beside the math it renders to, and the homepage is one
model shown as YAML and as the math that YAML means.

**The rule is the same one the language's tests keep**: nothing here may reach a
consumer of the AST. A generator that needs to build, solve, or plan a model is
documenting a *consumer*, not the language, and belongs with that consumer.

`pixi run docs-current` is what holds each page to its source; `tools/pages.py`
is the half of that shared between them, and says which differences count.
"""
