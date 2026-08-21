"""Generators whose source is the language, and whose output is its reference.

Each rewrites a block of documentation from the thing it documents, so the page
cannot drift from the code: the JSON Schema is `Model.model_json_schema()`, the
operator table is every builtin printed through the typesetter, and the notation
page is every construct beside the math it renders to.

**The rule is the same one the language's tests keep**: nothing here may reach a
consumer of the AST. A generator that needs `build`, `solve`, a plan or a lane is
documenting *math_spec*, not the language — `tools/constructs.py` and
`tools/gallery_math.py` are those, and they stay where they are, cataloguing the
gallery and its externally-sourced optima.

`tests/test_architecture.py` reads membership off the path.
"""
