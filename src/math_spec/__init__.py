"""The language: what a YAML file may say, and what it means.

Everything from the bytes on disk to a fully typed, dim-checked core AST —
the file reader, the schema, the two grammars, expansion, resolution, the dim
rules, and the load-time pass that runs them all. The AST this package
produces is the narrow waist of docs/ARCHITECTURE.md: everything downstream
reads it, and nothing downstream is visible from here.

**The directory is the rule, in the direction the engine's is not.** Hard rule
2 says the engine never sees the schema or the AST; this is its mirror —
nothing under ``language/`` may import ``lowering``, ``piecewise``,
``sources``, ``api``, or any of the three consuming subpackages. What a model
*means* cannot depend on what any consumer does with it, which is what makes
``lps.check()`` a pass with no data and no plan, and a second consumer cheap.
``errors.py`` stays outside deliberately: it is the dependency-free leaf both
this package and the engine may import (``ENGINE_MAY_IMPORT``), and moving it
in would put the language's path on the engine's import list.

``tests/test_architecture.py`` reads membership off the path, so a new
front-end module cannot land outside the fence by being spelled differently.
"""
