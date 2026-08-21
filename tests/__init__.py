"""Tests whose claim is a claim about the language.

**The criterion is the door the claim is decided at**, not the subject it is
about: a test belongs here if `load_model` alone can raise the verdict. A dim
rule, a grammar refusal, a duplicate YAML key and a macro expansion are all
settled before a plan exists, so they are asserted through the language's own
front door and nothing else is imported.

The test cuts the other way and that is what keeps it honest. *"`check` catches
a dim error with no sources bound"* is a claim about the **runner** — it says
the CI verb reaches the rule, not that the rule exists — so it lives in
`tests/test_api.py` beside `check`'s other behaviour. Two tests still span both
halves deliberately (`test_resolution.py`'s literal right-hand side and
`test_schema.py`'s omitted bound, which checks the default survives into the
plan); splitting those is a decision about each claim rather than a move, so
they stay where they are.

`tests/test_architecture.py` reads membership off the path, as it does for the
four fences in `src/`: nothing here may import a consumer of the AST.
"""
