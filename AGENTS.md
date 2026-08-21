`uv.lock` is not committed — it is a local resolution of `pyproject.toml`. After changing the dependencies there, run `uv lock` so your environment matches what you declared.

Everything runs in the project environment. Any command (like `pytest`) must be prefixed with `uv run` (e.g. `uv run pytest`).

Code formatting must align with our standards. Run `uv run pre-commit run --all-files` before `git commit`s to ensure this.
