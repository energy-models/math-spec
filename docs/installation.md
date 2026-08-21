<!--

-->

# Installation

## Installing a user environment

# Installation

!!! hint

    If it is your first time using Python, we recommend [uv](https://docs.astral.sh/uv/), [pixi](https://pixi.prefix.dev/), or [conda](https://docs.conda.io/projects/conda) as easy-to-use package managers.
    They are available for Windows, macOS, and GNU/Linux.
    It is always helpful to use dedicated environments.

You can install `math-spec` via all common package managers:

=== "uv"

    ``` bash
    uv add math_spec
    ```

=== "pixi"

    ``` bash
    pixi add --pypi math_spec
    ```

=== "conda"

    ``` bash
    conda create -n math-spec "python>=3.12" "pip"
    conda activate math-spec
    pip install math_spec
    ```

=== "pip"

    ``` bash
    pip install math_spec
    ```

`math-spec` is written and tested to be compatible with Python 3.12 and above.
We recommend to use the latest version with active support (see [endoflife.date](https://endoflife.date/python)).

## Installing a development environment

The install instructions are slightly different to create a development environment compared to a user environment:

--8<-- "README.md:docs-install-dev"

For more detailed installation instructions specific to developing the `math-spec` codebase, see our [development documentation][setting-up-a-development-environment].
