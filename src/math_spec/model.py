"""The YAML surface's types — every block a file may contain, rooted at :class:`Model`.

A block per declaration kind, and one strict base: an unrecognised key is an
error naming the near miss rather than a shrug, because a dropped ``bounds:``
leaves a variable unbounded and says nothing.

:class:`Model` is the first of the three stages the pipeline names — what a
file *declares*, before ``plan.Program`` (what it lowers to) and an executor
(what a build holds). Nothing here has seen data.
"""

from __future__ import annotations

import math
from importlib import metadata
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from lpspec.errors import did_you_mean, schema_error
from lpspec.language.helpers import BUILTIN_NAMES

if TYPE_CHECKING:
    from collections.abc import Iterable


class _StrictBlock(BaseModel):
    """Base for every schema model: unknown keys are an error, not a shrug.

    Without this, a misspelled optional key is silently dropped and the
    declaration it belonged to falls back to its default — ``boundz:`` leaves
    the variable unbounded, ``wher:`` leaves it unmasked. Both build a model
    the file does not describe, and neither says anything.
    """

    model_config = ConfigDict(extra='forbid')

    #: What this model is called in a YAML file, for the error message.
    _label: ClassVar[str] = ''

    @model_validator(mode='before')
    @classmethod
    def _reject_unknown_keys(cls, data: Any) -> Any:
        # pydantic's own extra='forbid' is the backstop; this runs first only
        # to name the near-miss, which is what a typo actually needs.
        if not isinstance(data, dict):
            return data
        known = set(cls.model_fields)
        unknown = [k for k in data if isinstance(k, str) and k not in known]
        if unknown:
            raise ValueError('\n'.join(cls._unknown_key_error(k, known) for k in unknown))
        return data

    @classmethod
    def _unknown_key_error(cls, key: str, known: set[str]) -> str:
        label = cls._label or cls.__name__
        return f"unknown key '{key}' in {label}. {did_you_mean(key, known, label='Valid keys')}"


def _one_of(value: str, allowed: set[str], field: str) -> str:
    """Check an enumerated string field, in one wording for all of them."""
    if value not in allowed:
        msg = f"{field} must be one of {allowed}, got '{value}'"
        raise ValueError(msg)
    return value


class DimensionBlock(_StrictBlock):
    """A declared dimension with optional dtype, values and coordinates.

    ``coords`` names non-index coordinates carried alongside this dimension's
    labels — a generator's bus, a line's endpoints, a snapshot's month. Each
    maps a coordinate name to the dimension its *values* are labels of, which
    is what makes ``sum(x, over=..., group_by=...)`` checkable: the values are
    verified to be coordinates of that dimension once data is bound, instead of
    being joined blind. Written either as a list, when the coordinate is named
    after its target dimension::

        generator:
          coords: [bus]

    or as a mapping, when it is not — including two coordinates onto one
    dimension::

        line:
          coords: {from: bus, to: bus}
    """

    _label: ClassVar[str] = 'a dimension declaration'

    dtype: str = 'str'
    values: list[Any] | None = None
    coords: dict[str, str] = Field(default_factory=dict)

    @field_validator('coords', mode='before')
    @classmethod
    def _normalise_coords(cls, v: Any) -> Any:
        """``[bus]`` is shorthand for ``{bus: bus}``."""
        if isinstance(v, list):
            bad = [x for x in v if not isinstance(x, str)]
            if bad:
                msg = f'coords list entries must be coordinate names, got {bad!r}'
                raise ValueError(msg)
            return {name: name for name in v}
        return v

    @field_validator('dtype')
    @classmethod
    def _check_dtype(cls, v: str) -> str:
        return _one_of(v, {'float', 'int', 'str', 'datetime'}, 'dtype')


class ParameterBlock(_StrictBlock):
    """A declared parameter with dims and dtype."""

    _label: ClassVar[str] = 'a parameter declaration'

    dims: list[str]
    dtype: str = 'float'

    @property
    def referenced_dims(self) -> list[str]:
        """The dimensions this block names — `dims` here, `foreach` on the rest."""
        return self.dims

    @field_validator('dtype')
    @classmethod
    def _check_dtype(cls, v: str) -> str:
        return _one_of(v, {'float', 'int', 'bool', 'str'}, 'dtype')


class BoundsBlock(_StrictBlock):
    """Variable bounds — each side is a number or parameter name.

    The defaults are linopy's (``add_variables(lower=-inf, upper=inf)``): a
    declaration that omits a bound means the variable is unbounded on that
    side, not implicitly non-negative. Non-negativity is a real constraint,
    so the file has to say it.
    """

    _label: ClassVar[str] = 'a bounds block'

    lower: float | str = float('-inf')
    upper: float | str = float('inf')


class VariableBlock(_StrictBlock):
    """A declared decision variable."""

    _label: ClassVar[str] = 'a variable declaration'

    foreach: list[str]
    where: str | None = None
    bounds: BoundsBlock = BoundsBlock()
    binary: bool = False
    integer: bool = False

    @property
    def referenced_dims(self) -> list[str]:
        return self.foreach

    @model_validator(mode='after')
    def _check_binary_integer(self) -> VariableBlock:
        if self.binary and self.integer:
            msg = 'A variable cannot be both binary and integer.'
            raise ValueError(msg)
        return self


class ConstraintBlock(_StrictBlock):
    """A declared constraint: one rule, over one frame."""

    _label: ClassVar[str] = 'a constraint declaration'

    foreach: list[str]
    where: str | None = None
    expression: str

    @property
    def referenced_dims(self) -> list[str]:
        return self.foreach

    @model_validator(mode='before')
    @classmethod
    def _migrate_equations(cls, data: Any) -> Any:
        return _refuse_equations(data, 'constraint')


class ObjectiveBlock(_StrictBlock):
    """A declared objective function."""

    _label: ClassVar[str] = 'an objective declaration'

    sense: str = 'minimize'
    expression: str

    @field_validator('sense')
    @classmethod
    def _check_sense(cls, v: str) -> str:
        return _one_of(v, {'minimize', 'maximize'}, 'sense')

    @model_validator(mode='before')
    @classmethod
    def _migrate_equations(cls, data: Any) -> Any:
        return _refuse_equations(data, 'objective')


def _refuse_equations(data: Any, kind: str) -> Any:
    """Name the rewrite for a file written against the old surface.

    ``equations:`` held a *list*, and a list needs names for its entries — which
    it did not have, so they were numbered by position and the block's own name
    resolved to nothing (#298). One rule per block removes the list rather than
    labelling it, so the migration is mechanical in both directions and the
    error can say exactly what to write.

    Caught here rather than by the closed-schema check, which would only offer
    "unknown key 'equations'" and a near miss against `expression` — true, and
    useless for a file with three entries in it.
    """
    if not isinstance(data, dict) or 'equations' not in data:
        return data
    entries = data.get('equations')
    n = len(entries) if isinstance(entries, list) else 1
    if n == 1:
        fix = f'Move the single entry up: replace `equations:` with `expression:` on the {kind}.'
    else:
        fix = (
            f'Split it into {n} {kind}s, one per rule, each with its own name — the entries were '
            f'named by position, so the names were never yours to begin with.'
        )
    msg = f'`equations:` was removed from {kind} declarations; a {kind} holds exactly one rule. {fix}'
    raise ValueError(msg)


class MacroBlock(_StrictBlock):
    """A parameterised expression template, defined in the YAML itself.

    The template is language, not code: formal names (``args`` positional,
    ``kwargs`` keyword) shadow model names inside it, and every call site is
    expanded into core AST before either backend sees the expression.
    """

    _label: ClassVar[str] = 'a macro declaration'

    args: list[str] = []
    kwargs: list[str] = []
    template: str

    @model_validator(mode='after')
    def _check_formals(self) -> MacroBlock:
        formals = [*self.args, *self.kwargs]
        if len(set(formals)) != len(formals):
            msg = f'duplicate formal names: {formals}'
            raise ValueError(msg)
        return self


class PiecewiseBlock(_StrictBlock):
    """N expressions jointly pinned to a breakpoint-indexed piecewise curve.

    Mirrors ``linopy.Model.add_piecewise_formulation``: each link is a tuple
    ``[expression, values_parameter]`` or ``[expression, values_parameter,
    sign]``, where *expression* is any affine expression string (a bare
    variable name being the simplest), *values_parameter* names a parameter
    carrying the ``over`` dim (the breakpoint coordinates of this link), and
    *sign* bounds the link by the curve instead of pinning it (at most one
    non-``"=="``, and only with exactly two links).

    Expanded (before building) into plain variables and constraints via the
    λ convex-combination method — see ``lpspec.language.piecewise``.
    """

    _label: ClassVar[str] = 'a piecewise declaration'

    over: str  # breakpoint dimension
    links: list[list[str]]
    convex: bool = False  # True: pure-LP convex hull (no binaries)
    active: str | None = None  # gating expression: formulation pinned to 0 when 0

    @model_validator(mode='after')
    def _check_convex_shape(self) -> PiecewiseBlock:
        if self.convex and len(self.links) != 2:
            msg = (
                'convex: true requires exactly two links (the hull relaxation '
                'is only well-defined for a single y=f(x) curve).'
            )
            raise ValueError(msg)
        if self.convex and self.active is not None:
            msg = 'active gating is not supported with convex: true.'
            raise ValueError(msg)
        return self

    @field_validator('links')
    @classmethod
    def _check_links(cls, v: list[list[str]]) -> list[list[str]]:
        if len(v) < 2:
            msg = 'piecewise needs at least two links ([expression, values, sign?]).'
            raise ValueError(msg)
        signs = []
        for link in v:
            if not 2 <= len(link) <= 3:
                msg = f'each link must be [expression, values] or [expression, values, sign], got {link!r}'
                raise ValueError(msg)
            sign = link[2] if len(link) == 3 else '=='
            if sign not in ('==', '<=', '>='):
                msg = f"link sign must be '==', '<=' or '>=', got {sign!r}"
                raise ValueError(msg)
            signs.append(sign)
        non_eq = [s for s in signs if s != '==']
        if len(non_eq) > 1:
            msg = "at most one link may carry a non-'==' sign."
            raise ValueError(msg)
        if non_eq and len(v) != 2:
            msg = "a non-'==' sign is only supported with exactly two links."
            raise ValueError(msg)
        return v


#: The language surfaces this reader understands. A **language** version, not a
#: package one: it moves when the accepted YAML surface moves, which most
#: releases do not. Deriving it from the package version would be automatic and
#: wrong.
#:
#: `0` is the unstable surface — no compatibility promise, per *breaking changes
#: are free* in CONTRIBUTING. What `1` is stays deliberately undecided; the one
#: thing decided is that 0 does not silently become 1 without a changelog entry
#: saying what moved.
SUPPORTED_VERSIONS: tuple[int, ...] = (0,)


def _without_absence(value: Any) -> Any:
    """Strip what is absent — a null, an infinite bound, or a mapping declaring nothing.

    An empty **list** is kept, because in this schema a list carries
    *cardinality* and zero is one of its values: ``foreach: []`` is a scalar
    declaration and ``dims: []`` is a scalar parameter, both of them required
    fields that mean something. An empty **mapping** carries declarations, and
    none of them is nothing.

    Nothing else is judged. A value that is there is written, whether or not it
    equals a default.
    """
    if isinstance(value, dict):
        pruned = {k: _without_absence(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if not _is_absent(v)}
    return value


def _is_absent(value: Any) -> bool:
    """Whether a serialised value says *nothing is here*.

    ``inf`` is included because an infinite bound is not a bound — it is the
    unbounded side, which is what omitting the bound already means. Stripping
    it is what makes JSON lossless as well: JSON has no infinity, so anything
    that reached ``model_dump_json`` as ``inf`` came back as ``null`` and read
    as absent anyway. Removing it here means the two agree instead of one being
    quietly wrong.
    """
    if value is None or value == {}:
        return True
    return isinstance(value, float) and math.isinf(value)


class Model(_StrictBlock):
    """The declared math — one YAML file, or one dict, validated.

    First of the three stages the pipeline names: ``Model`` is what a file
    *says*, ``plan.Program`` is what it lowers to, and an executor is what a
    build holds. Nothing here has seen data.

    **The API is the declarations, and two ways back out.** The eight
    declaration sections plus ``version``; :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads. In goes through
    ``lps.load_model``, which takes a path, a dict or a ``Model``.

    **Everything else on this class is pydantic's** and not a contract this
    package keeps — the inherited surface is twenty-seven public names, a dozen
    of them deprecated v1 aliases. Two are worth knowing about:

    * ``model_json_schema()`` gives a Draft 2020-12 document for free, which is
      most of a machine-readable YAML surface. It describes the *shape*
      pydantic validates, not the language, so it accepts a constraint naming
      an undeclared parameter.
    * ``model_construct()`` **skips validation entirely**, so the guarantee is
      that a model built the normal way is valid, not that a ``Model`` is.
      Overriding it to raise would trade a documented escape hatch for a
      surprise.

    The three that *build* one are overridden, so a wrong model raises this
    package's :class:`~lpspec.errors.LanguageError` wherever it is built rather
    than pydantic's ``ValidationError`` here and ours everywhere else (#527).
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: Which language surface this file is written against. Absent means 0, so
    #: the field is additive — every file that predates it stays valid.
    #:
    #: **0 means unstable**, which is the promise actually being made: the
    #: surface may change in any release. Saying so in the file is more honest
    #: than silence, and it is what lets a *later* reader refuse a file it
    #: cannot read rather than misinterpret it.
    version: int = 0
    dimensions: dict[str, DimensionBlock] = {}
    parameters: dict[str, ParameterBlock] = {}
    variables: dict[str, VariableBlock] = {}
    constraints: dict[str, ConstraintBlock] = {}
    objectives: dict[str, ObjectiveBlock] = {}
    expressions: dict[str, str] = {}
    macros: dict[str, MacroBlock] = {}
    piecewise: dict[str, PiecewiseBlock] = {}

    # `typing.override` is 3.12+ and this package supports 3.11, so the
    # decorator the rule asks for cannot be imported.
    @classmethod
    # pyrefly: ignore[missing-override-decorator]
    def model_validate(cls, *args: Any, **kwargs: Any) -> Model:
        """Validate, raising this package's exception tree.

        Pydantic reports every failure as a ``ValidationError`` carrying an
        ``input_value=`` dump and a link to its own docs — neither of which
        means anything to someone who wrote a YAML file, and neither of which
        is the type ``docs/api.md`` tells a caller to catch.

        ``__init__`` is deliberately *not* wrapped the same way. Defining one
        makes pydantic route validation through it, so every after-validator
        runs twice — the first time with ``context=None``, which silently
        drops ``known_variables`` and refuses every ``extend()`` file. The
        constructor keeps pydantic's own error; ``lps.load_model`` is the door
        this package documents, and it goes through here.
        """
        try:
            return super().model_validate(*args, **kwargs)
        except ValidationError as exc:
            raise schema_error(exc) from None

    # `typing.override` is 3.12+ and this package supports 3.11, so the
    # decorator the rule asks for cannot be imported.
    @classmethod
    # pyrefly: ignore[missing-override-decorator]
    def model_validate_json(cls, *args: Any, **kwargs: Any) -> Model:
        """As :meth:`__init__`, for the door that takes JSON."""
        try:
            return super().model_validate_json(*args, **kwargs)
        except ValidationError as exc:
            raise schema_error(exc) from None

    @field_validator('version')
    @classmethod
    def _check_version(cls, v: int) -> int:
        """Refuse a surface this reader does not know — never interpret it.

        A file from the future must not be read by an older reader; that is the
        whole reason the field exists. Rejecting is the entire policy: the
        version gates *nothing* at runtime, because keeping two surfaces alive
        in one codebase is a large permanent cost against a hard error that
        costs one line.

        The installed version comes from the distribution's metadata rather
        than ``lpspec.__version__``: a language module may not reach forward to
        the package that consumes its AST.
        """
        if v in SUPPORTED_VERSIONS:
            return v
        try:
            installed = metadata.version('lpspec')
        except metadata.PackageNotFoundError:  # pragma: no cover — a tree with no dist-info
            installed = 'unknown'
        supported = ', '.join(str(s) for s in SUPPORTED_VERSIONS)
        msg = (
            f'model declares version {v}, and lpspec {installed} understands [{supported}]. '
            f'Upgrade lpspec, or write the version this file actually targets.'
        )
        raise ValueError(msg)

    @model_serializer(mode='wrap')
    def _drop_absence(self, handler: Any) -> dict[str, Any]:
        """Absence is not serialised — a null, or a mapping declaring nothing.

        On the *serializer* rather than beside it so there is one answer:
        ``model_dump``, ``model_dump_json``, :meth:`to_dict` and
        :meth:`to_yaml` all give the same content. A helper next to them would
        have left pydantic's own methods disagreeing with the file, and which a
        consumer got would depend on which name they reached for.

        **Every value is kept, default or not.** Omitting *defaults* reads
        better and needs a list of which ones are consequential; that list is a
        second copy of the schema and it drifted on its first day, keeping
        ``version`` and ``sense`` while dropping ``dtype``. An empty **list**
        stays, because a list carries cardinality here and zero is one of its
        values — ``foreach: []`` is a scalar declaration.
        """
        return _without_absence(handler(self))

    def to_dict(self) -> dict[str, Any]:
        """The model as plain data. ``load_model(m.to_dict())`` reproduces it."""
        return self.model_dump()

    def to_yaml(self) -> str:
        """The file a reviewer reads — including for a model that never had one.

        Hard rule 5 is that the model is the file you review and diff. A model
        a framework emitted as a dict has no such file; this gives it one. The
        output is generated for review rather than authored, so length costs a
        reader nothing and being unambiguous saves them having to know this
        package's defaults at all.
        """
        import yaml

        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @model_validator(mode='after')
    def _validate_references(self) -> Model:
        errors = []

        # One flat namespace: shadowing would let a new declaration silently
        # change what an existing expression means. See resolution.py.
        kinds: list[tuple[str, Iterable[str]]] = [
            ('dimension', self.dimensions),
            ('parameter', self.parameters),
            ('variable', self.variables),
            ('named expression', self.expressions),
            ('macro', self.macros),
        ]
        seen: dict[str, str] = {}
        for kind, group in kinds:
            for name in group:
                if name in BUILTIN_NAMES:
                    errors.append(
                        f"{kind.capitalize()} '{name}' collides with the built-in helper "
                        f"'{name}'. The helper set is closed and its names are reserved; "
                        f'rename the {kind}.'
                    )
                if name in seen:
                    errors.append(
                        f"{kind.capitalize()} '{name}' collides with the {seen[name]} of "
                        f'the same name. Names share one flat namespace — rename one of '
                        f'them, so that every name in an expression or where string has '
                        f'exactly one meaning.'
                    )
                else:
                    seen[name] = kind

        errors.extend(
            f"{kind} '{name}' references undeclared dimension '{d}'. Declare it under 'dimensions:'."
            for kind, group in (
                ('Parameter', self.parameters),
                ('Variable', self.variables),
                ('Constraint', self.constraints),
            )
            for name, item in group.items()
            for d in item.referenced_dims
            if d not in self.dimensions
        )

        # A coordinate's target must be a declared dimension, and must not be
        # the dimension carrying it: grouping a dim into itself is a no-op that
        # would read as a reduction.
        for dname, ddef in self.dimensions.items():
            for cname, target in ddef.coords.items():
                if target not in self.dimensions:
                    errors.append(
                        f"Dimension '{dname}' coordinate '{cname}' targets undeclared "
                        f"dimension '{target}'. Declare it under 'dimensions:' — the "
                        f'target is what the coordinate values are checked against.'
                    )
                elif target == dname:
                    errors.append(
                        f"Dimension '{dname}' coordinate '{cname}' targets '{dname}' "
                        f'itself. A coordinate must map into a different dimension.'
                    )
                if cname in self.dimensions and cname != target:
                    errors.append(
                        f"Dimension '{dname}' coordinate '{cname}' shadows the dimension "
                        f"of the same name while targeting '{target}'. Rename the "
                        f'coordinate so a reader cannot mistake one for the other.'
                    )

        # Bounds look like the expression language but are not it, so the
        # error says what they actually accept.
        for vname, vdef in self.variables.items():
            for side in ('lower', 'upper'):
                val = getattr(vdef.bounds, side)
                if isinstance(val, str) and val not in self.parameters:
                    looks_like_expression = not val.isidentifier()
                    detail = (
                        f'bounds accept a parameter name or a number, not an expression '
                        f'(got {val!r}). Precompute it as a parameter'
                        if looks_like_expression
                        else f"'{val}' is not a declared parameter"
                    )
                    errors.append(f"Variable '{vname}' bounds.{side}: {detail}.")

        if errors:
            raise ValueError('\n'.join(errors))

        return self

    @model_validator(mode='after')
    def _validate_expressions(self, info: ValidationInfo) -> Model:
        """Every expression and where string, checked here rather than beside.

        The checkers are a layer above this one, so the imports are local and
        declared in ``DELIBERATE_LAZY_IMPORTS``. Expansion runs first — a
        formulation emits declarations that are language too — and terminates,
        since an expanded model carries no ``piecewise:``.

        An expansion *builds* a ``Model``, which validates itself on the way
        out, so the check below runs only when there was nothing to expand.
        Calling it either way validated a piecewise model twice.

        ``known_variables`` arrives as pydantic validation context, for the file
        deliberately not valid alone: an extension references variables already
        on the model ``lpspec.linopy.extend`` puts it on. It travels into
        expansion too, since a link may name one of those variables.
        """
        from lpspec.language.piecewise import expand_piecewise
        from lpspec.language.validation import validate_expressions

        known = (info.context or {}).get('known_variables', {})
        if expand_piecewise(self, known_variables=known) is self:
            validate_expressions(self, known_variables=known)
        return self
