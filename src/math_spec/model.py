"""The YAML surface's types — every block a file may contain, rooted at :class:`Model`.

A block per declaration kind, and one strict base: an unrecognised key is an
error naming the near miss rather than a shrug, because a dropped ``bounds:``
leaves a variable unbounded and says nothing.

:class:`Model` is the first of the three stages the pipeline names — what a
file *declares*, before ``plan.Program`` (what it lowers to) and an engine
(what a build holds). Nothing here has seen data.
"""

from __future__ import annotations

import math
from importlib import metadata
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from lpspec.errors import did_you_mean, schema_error
from lpspec.language.operators import BUILTIN_NAMES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class _StrictBlock(BaseModel):
    """Base for every schema model: unknown keys are an error, not a shrug.

    A misspelled optional key would otherwise be dropped and its declaration
    fall back to a default — ``boundz:`` leaves the variable unbounded,
    ``wher:`` leaves it unmasked — building a model the file does not describe.
    """

    model_config = ConfigDict(extra='forbid')

    #: What this model is called in a YAML file, for the error message.
    _label: ClassVar[str] = ''

    @model_validator(mode='before')
    @classmethod
    def _reject_unknown_keys(cls, data: Any) -> Any:
        """Name the near-miss, which is what a typo actually needs.

        pydantic's own ``extra='forbid'`` is the backstop; this runs first
        only for the wording.
        """
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


#: The dtypes a dimension index may declare (SPEC §2). The one home of the
#: vocabulary: both dtype validators read it, and ``tests/test_architecture.py``
#: pins the engine's empty-index dtype table (``relational/frames.py``) to the
#: same set — a test rather than an import, because the fence keeps the engine
#: from reaching the language.
DIMENSION_DTYPES = frozenset({'float', 'int', 'str', 'datetime'})

#: The domains a variable may declare (SPEC §2). Matches the plan's
#: ``VariableType`` vocabulary (``relational/plan.py``), pinned by a test for
#: the same fence reason as the dtype table above.
VARIABLE_DOMAINS = frozenset({'continuous', 'integer', 'binary'})


def _one_of(value: str, allowed: frozenset[str] | set[str], field: str) -> str:
    """Check an enumerated string field, in one wording for all of them."""
    if value not in allowed:
        msg = f"{field} must be one of {allowed}, got '{value}'"
        raise ValueError(msg)
    return value


class LookupBlock(_StrictBlock):
    """A named single-valued map out of a dimension (SPEC §2).

    Two kinds, told apart by which field is set:

    - ``into:`` names the dimension the values are labels of — the *groupable*
      kind, what ``sum(by=)`` lands terms on and ``at(by=)`` reads through,
      checked for containment once data is bound rather than joined blind::

          lookups:
            bus_of: {over: generator, into: bus}
            send:   {over: line, into: bus}

    - ``dtype:`` declares an inline label space — the *selection-only* kind,
      owning its values and targeting nothing, so no axis exists for terms to
      land on. Grouping into one is refused with the promotion rewrite
      (:func:`lpspec.language.resolution.resolve`)::

          lookups:
            period: {over: snapshot, dtype: int}
    """

    _label: ClassVar[str] = 'a lookup declaration'

    over: str
    into: str | None = None
    dtype: str | None = None
    description: str | None = None

    @field_validator('dtype')
    @classmethod
    def _check_dtype(cls, v: str | None) -> str | None:
        return v if v is None else _one_of(v, DIMENSION_DTYPES, 'dtype')

    @model_validator(mode='after')
    def _exactly_one_kind(self) -> LookupBlock:
        if (self.into is None) == (self.dtype is None):
            msg = (
                "a lookup declares exactly one of 'into:' (a groupable map onto that "
                "dimension) or 'dtype:' (its own label space)"
            )
            raise ValueError(msg)
        return self


class DimensionBlock(_StrictBlock):
    """A declared dimension with optional dtype and values.

    A dimension is an axis and nothing else. The maps its members carry — a
    generator's bus, a snapshot's period — are top-level ``lookups:``
    (:class:`LookupBlock`), keyed by their own name.
    """

    _label: ClassVar[str] = 'a dimension declaration'

    dtype: str = 'str'
    values: list[Any] | None = None
    description: str | None = None

    @field_validator('dtype')
    @classmethod
    def _check_dtype(cls, v: str) -> str:
        return _one_of(v, DIMENSION_DTYPES, 'dtype')

    @classmethod
    def _unknown_key_error(cls, key: str, known: set[str]) -> str:
        if key == 'coords':
            return (
                "'coords:' under a dimension was removed; a coordinate is a top-level lookup. Rewrite\n"
                '  dimensions:\n'
                '    generator: {coords: [bus]}\n'
                'as\n'
                '  lookups:\n'
                '    bus_of: {over: generator, into: bus}\n'
                'and an inline label space {period: {dtype: int}} as {period: {over: <dim>, dtype: int}}.\n'
                'A lookup name joins the flat namespace, so one shadowing a dimension — its target '
                'included — needs a name of its own (bus -> bus_of).'
            )
        return super()._unknown_key_error(key, known)


class ParameterBlock(_StrictBlock):
    """A declared parameter with dims and dtype."""

    _label: ClassVar[str] = 'a parameter declaration'

    dims: list[str]
    dtype: str = 'float'
    description: str | None = None

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

    linopy's defaults (``add_variables(lower=-inf, upper=inf)``): omitting a
    bound leaves the variable unbounded on that side, not implicitly
    non-negative. Non-negativity is a real constraint, so the file says it.
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
    domain: str = 'continuous'
    description: str | None = None

    @property
    def referenced_dims(self) -> list[str]:
        return self.foreach

    @field_validator('domain')
    @classmethod
    def _check_domain(cls, v: str) -> str:
        return _one_of(v, VARIABLE_DOMAINS, 'domain')

    @model_validator(mode='before')
    @classmethod
    def _refuse_flags(cls, data: Any) -> Any:
        """Name the rewrite for a file written against the flag surface.

        Caught here rather than by the closed-schema check, whose near miss
        against the remaining fields would be noise for a key that used to be
        real.
        """
        if not isinstance(data, dict):
            return data
        removed = [k for k in ('binary', 'integer') if k in data]
        if removed:
            k = removed[0]
            msg = f'`{k}:` was removed from variable declarations; write `domain: {k}` instead.'
            raise ValueError(msg)
        return data


class ConstraintBlock(_StrictBlock):
    """A declared constraint: one rule, over one frame."""

    _label: ClassVar[str] = 'a constraint declaration'

    foreach: list[str]
    where: str | None = None
    expression: str
    description: str | None = None

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
    description: str | None = None

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

    Caught here rather than by the closed-schema check, which would offer
    "unknown key 'equations'" and a near miss against ``expression`` — true,
    and useless for a file with three entries in it (#298).
    """
    if not isinstance(data, dict) or 'equations' not in data:
        return data
    entries = data.get('equations')
    n = len(entries) if isinstance(entries, list) else 1
    if n == 1:
        fix = f'Move the single entry up: replace `equations:` with `expression:` on the {kind}.'
    elif kind == 'objective':
        fix = 'A model optimises one: combine the entries into a single expression (a weighted sum is ordinary arithmetic).'
    else:
        fix = (
            f'Split it into {n} {kind}s, one per rule, each with its own name — the entries were '
            f'named by position, so the names were never yours to begin with.'
        )
    msg = f'`equations:` was removed from {kind} declarations; a {kind} holds exactly one rule. {fix}'
    raise ValueError(msg)


class MacroBlock(_StrictBlock):
    """A parameterised expression template, defined in the YAML itself.

    Language, not code: formals (``args`` positional, ``kwargs`` keyword)
    shadow model names inside the template, and every call site expands into
    core AST before either backend sees the expression.
    """

    _label: ClassVar[str] = 'a macro declaration'

    args: list[str] = []
    kwargs: list[str] = []
    template: str
    description: str | None = None

    @model_validator(mode='after')
    def _check_formals(self) -> MacroBlock:
        formals = [*self.args, *self.kwargs]
        if len(set(formals)) != len(formals):
            msg = f'duplicate formal names: {formals}'
            raise ValueError(msg)
        return self


class ExpressionBlock(_StrictBlock):
    """A named quantity: one arithmetic expression, readable after a solve.

    Written in YAML as a bare string, or as a mapping once it carries a
    ``description:`` — and serialised back to whichever form it was written in,
    so a round trip through :meth:`Model.to_yaml` reproduces the file::

        expressions:
          total_generation: sum(p, over=generator)
          emissions:
            expression: sum(p * rate, over=generator)
            description: CO2 released, the quantity the cap bounds

    The description matters more here than anywhere else: a named expression is
    expanded away before the typeset walk, so its whole surface is
    ``result.expression(name)`` after a solve — a name arriving in a summary
    with nothing else to say what it counts.
    """

    _label: ClassVar[str] = 'a named expression'

    expression: str
    description: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _from_string(cls, data: Any) -> Any:
        return {'expression': data} if isinstance(data, str) else data

    @model_serializer
    def _as_written(self) -> str | dict[str, str]:
        if self.description is None:
            return self.expression
        return {'expression': self.expression, 'description': self.description}


class PiecewiseLink(_StrictBlock):
    """One link of a piecewise block: an expression pinned to a values curve.

    Written in YAML as ``[expression, values]`` or ``[expression, values,
    sign]`` and serialised back to exactly that form, so a round trip through
    :meth:`Model.to_yaml` reproduces the file.
    """

    _label: ClassVar[str] = 'a piecewise link'

    expression: str
    values: str
    sign: str = '=='

    @model_validator(mode='before')
    @classmethod
    def _from_list(cls, data: Any) -> Any:
        if isinstance(data, list):
            if not 2 <= len(data) <= 3:
                msg = f'each link must be [expression, values] or [expression, values, sign], got {data!r}'
                raise ValueError(msg)
            return dict(zip(('expression', 'values', 'sign'), data, strict=False))
        return data

    @field_validator('sign')
    @classmethod
    def _check_sign(cls, v: str) -> str:
        if v not in ('==', '<=', '>='):
            msg = f"link sign must be '==', '<=' or '>=', got {v!r}"
            raise ValueError(msg)
        return v

    @model_serializer
    def _as_list(self) -> list[str]:
        return [self.expression, self.values] if self.sign == '==' else [self.expression, self.values, self.sign]


#: How a ``piecewise:`` block restricts its interpolation weights, and what
#: each one emits. The key is ``method:`` because that is
#: ``linopy.Model.add_piecewise_formulation``'s (#695); ``sos2`` is its word
#: too, and means the same thing. ``adjacency`` and ``convex`` are ours,
#: linopy having no name for the first and a different formulation under
#: ``lp`` for the second.
PIECEWISE_METHODS = {
    'adjacency': 'a binary per segment, and a row making the two nonzero weights neighbours',
    'sos2': 'the same weights, restricted by a set the sink branches on (SPEC §4.1)',
    'convex': 'nothing — the weights range over the hull, which is a pure LP',
}


class PiecewiseBlock(_StrictBlock):
    """N expressions jointly pinned to a breakpoint-indexed piecewise curve.

    Mirrors ``linopy.Model.add_piecewise_formulation``. Each link is
    ``[expression, values_parameter]`` or ``[expression, values_parameter,
    sign]``: *expression* is any affine expression string, *values_parameter*
    names a parameter carrying the ``over`` dim, and *sign* bounds the link by
    the curve instead of pinning it (at most one non-``"=="``, and only with
    exactly two links).

    ``over`` names the breakpoint dimension; ``method`` is which of
    :data:`PIECEWISE_METHODS` restricts the weights; ``active`` names a gating
    expression that pins the formulation to 0 when it is 0. Expanded before
    building into plain variables and constraints — see
    ``lpspec.language.piecewise``.
    """

    _label: ClassVar[str] = 'a piecewise declaration'

    over: str
    links: list[PiecewiseLink]
    method: str = 'adjacency'
    active: str | None = None
    description: str | None = None

    @property
    def convex(self) -> bool:
        """Whether this block relaxes to the hull, which needs no binaries.

        The curvature guard and the expansion both ask this rather than
        comparing against the method name, since what they act on is the
        absence of a restriction and not which word was written.
        """
        return self.method == 'convex'

    @field_validator('method')
    @classmethod
    def _check_method(cls, v: str) -> str:
        if v not in PIECEWISE_METHODS:
            options = '\n'.join(f'  {name}: {what}' for name, what in PIECEWISE_METHODS.items())
            msg = f'unknown piecewise method {v!r}. The formulations are:\n{options}'
            raise ValueError(msg)
        return v

    @model_validator(mode='before')
    @classmethod
    def _migrate_convex(cls, data: Any) -> Any:
        """Name the rewrite for a file written against the boolean.

        ``convex:`` was one formulation wearing a flag, so a second one had
        nowhere to go that did not interact with it. Caught here rather than
        by the closed-schema check, which would offer a near miss against
        ``method`` and leave the value to guess at.
        """
        if not isinstance(data, dict) or 'convex' not in data:
            return data
        wanted = 'convex' if data.get('convex') else 'adjacency'
        msg = (
            f'`convex:` was replaced by `method:`, which names the formulation instead of flagging '
            f'one of them: write `method: {wanted}`. The other is `method: sos2`, which restricts '
            f'the same weights with a set the sink branches on.'
        )
        raise ValueError(msg)

    @model_validator(mode='after')
    def _check_convex_shape(self) -> PiecewiseBlock:
        if self.convex and len(self.links) != 2:
            msg = (
                'method: convex requires exactly two links (the hull relaxation '
                'is only well-defined for a single y=f(x) curve).'
            )
            raise ValueError(msg)
        if self.convex and self.active is not None:
            msg = 'active gating is not supported with method: convex.'
            raise ValueError(msg)
        return self

    @field_validator('links')
    @classmethod
    def _check_links(cls, v: list[PiecewiseLink]) -> list[PiecewiseLink]:
        if len(v) < 2:
            msg = 'piecewise needs at least two links ([expression, values, sign?]).'
            raise ValueError(msg)
        non_eq = [link.sign for link in v if link.sign != '==']
        if len(non_eq) > 1:
            msg = "at most one link may carry a non-'==' sign."
            raise ValueError(msg)
        if non_eq and len(v) != 2:
            msg = "a non-'==' sign is only supported with exactly two links."
            raise ValueError(msg)
        return v


class SosBlock(_StrictBlock):
    """A special-ordered set over one dimension of one variable.

    Mirrors ``linopy.Model.add_sos_constraints``, whose decomposition this
    copies: a variable, the dimension the set runs along, the type, and the
    optional big-M a reformulating sink caps its linking rows with. One set
    per coordinate of the variable's ``foreach`` minus ``over``; the members
    are the variable's *existing* coordinates along ``over``, and their order
    is that dimension's declared one — what ``shift`` walks.

    ``type: 1`` admits at most one nonzero member, ``type: 2`` at most two,
    and those two consecutive. Unlike every other block this one declares no
    math a sink can read off ``A``: it is a *set*, carried to the sink that
    has the concept and reformulated for the sink that does not.
    """

    _label: ClassVar[str] = 'a sos declaration'

    variable: str
    over: str
    type: int
    big_m: float | None = None
    description: str | None = None

    @field_validator('type')
    @classmethod
    def _check_type(cls, v: int) -> int:
        if v not in (1, 2):
            msg = f'sos type must be 1 or 2, got {v!r}. A set of any other order is not a construct solvers carry.'
            raise ValueError(msg)
        return v

    @field_validator('big_m')
    @classmethod
    def _check_big_m(cls, v: float | None) -> float | None:
        if v is not None and not (v > 0 and math.isfinite(v)):
            msg = f'big_m must be a positive, finite number, got {v!r} — it caps a linking coefficient.'
            raise ValueError(msg)
        return v


#: The language surfaces this reader understands. A **language** version, not a
#: package one: it moves when the accepted YAML surface moves, which most
#: releases do not, so deriving it from the package version would be automatic
#: and wrong. `0` is the unstable surface — no compatibility promise, per
#: *breaking changes are free* in CONTRIBUTING.
SUPPORTED_VERSIONS: tuple[int, ...] = (0,)


def _without_absence(value: Any) -> Any:
    """Strip what is absent — a null, an infinite bound, or an empty mapping.

    An empty **list** is kept: a list carries *cardinality* here and zero is
    one of its values, ``foreach: []`` being a scalar declaration. Nothing else
    is judged — a value that is there is written, default or not.
    """
    if isinstance(value, dict):
        pruned = {k: _without_absence(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if not _is_absent(v)}
    return value


def _in_our_tree(validate: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run *validate*, raising this package's exception tree.

    Pydantic's ``ValidationError`` carries an ``input_value=`` dump and a link
    to its own docs, neither of which is the type ``docs/api.md`` tells a
    caller to catch. Both of :class:`Model`'s validating doors go through here
    so they cannot answer differently.

    ``__init__`` is deliberately *not* wrapped: defining one makes pydantic
    route validation through it, so every after-validator runs twice — the
    first time with ``context=None``, silently dropping ``known_variables`` and
    refusing every ``extend()`` file. The constructor keeps pydantic's error;
    ``lps.load_model`` is the documented door and comes through here.
    """
    try:
        return validate(*args, **kwargs)
    except ValidationError as exc:
        raise schema_error(exc) from None


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
    *says*, ``plan.Program`` what it lowers to, an engine what a build holds.
    Nothing here has seen data.

    The API is the ten declaration sections plus ``version`` and
    ``description``, and two ways back out: :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads. In goes through
    ``lps.load_model``, which raises
    :class:`~lpspec.errors.LanguageError` on a model the language refuses.

    Everything else on this class is pydantic's, not a contract this package
    keeps — ``model_json_schema()`` describes the shape pydantic validates
    rather than the language, and ``model_construct()`` skips validation
    entirely, so a ``Model`` is valid when it was built the normal way.
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: The last expansion built from this model. Owned entirely — written,
    #: read, keyed — by :func:`~lpspec.language.piecewise.expand_piecewise`,
    #: whose ``_Expansion`` this holds; only the slot lives here.
    _expansion: Any = PrivateAttr(default=None)

    #: Which language surface this file is written against. Absent means 0, so
    #: the field is additive. **0 means unstable** — the surface may change in
    #: any release — and declaring it is what lets a later reader refuse a file
    #: it cannot read rather than misinterpret it.
    version: int = 0
    #: What the file as a whole is, in the same plain prose a declaration's
    #: ``description:`` takes. The typeset document opens with it.
    description: str | None = None
    dimensions: dict[str, DimensionBlock] = {}
    lookups: dict[str, LookupBlock] = {}
    parameters: dict[str, ParameterBlock] = {}
    variables: dict[str, VariableBlock] = {}
    constraints: dict[str, ConstraintBlock] = {}
    objective: ObjectiveBlock | None = None
    expressions: dict[str, ExpressionBlock] = {}
    macros: dict[str, MacroBlock] = {}
    piecewise: dict[str, PiecewiseBlock] = {}
    sos: dict[str, SosBlock] = {}

    def targeted_of(self, dimension: str) -> dict[str, str]:
        """The groupable lookups over *dimension*: name -> the dim they map into."""
        return {n: lk.into for n, lk in self.lookups.items() if lk.over == dimension and lk.into is not None}

    def labels_of(self, dimension: str) -> dict[str, LookupBlock]:
        """The label-space lookups over *dimension* — selection only, never an axis."""
        return {n: lk for n, lk in self.lookups.items() if lk.over == dimension and lk.into is None}

    @model_validator(mode='before')
    @classmethod
    def _refuse_objectives(cls, data: Any) -> Any:
        """Name the rewrite for a file written against the mapping surface.

        Caught here rather than by the closed-schema check: the near miss
        (`objective`) is the right hint for a one-entry file and useless for
        one declaring several.
        """
        if not isinstance(data, dict) or 'objectives' not in data:
            return data
        entries = data.get('objectives')
        n = len(entries) if isinstance(entries, dict) else 1
        if n == 1:
            fix = 'Move the single block up: replace `objectives: {name: {...}}` with `objective: {...}` — the name did nothing.'
        else:
            fix = (
                'A model optimises one. Combine them into a single expression '
                '(a weighted sum is ordinary arithmetic) and declare it as `objective:`.'
            )
        msg = f'`objectives:` was removed; a file declares one `objective:` block. {fix}'
        raise ValueError(msg)

    @classmethod
    # pyrefly: ignore[missing-override-decorator]  — `typing.override` is 3.12+, and this package supports 3.11
    def model_validate(cls, *args: Any, **kwargs: Any) -> Model:
        """Validate a mapping — see :func:`_in_our_tree` for what it raises."""
        return _in_our_tree(super().model_validate, *args, **kwargs)

    @classmethod
    # pyrefly: ignore[missing-override-decorator]  — `typing.override` is 3.12+, and this package supports 3.11
    def model_validate_json(cls, *args: Any, **kwargs: Any) -> Model:
        """The same door, for JSON."""
        return _in_our_tree(super().model_validate_json, *args, **kwargs)

    @field_validator('version')
    @classmethod
    def _check_version(cls, v: int) -> int:
        """Refuse a surface this reader does not know — never interpret it.

        Rejecting is the entire policy: the version gates nothing at runtime,
        keeping two surfaces alive in one codebase being a large permanent cost
        against a hard error that costs one line.

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

        On the *serializer* rather than beside it so ``model_dump``,
        ``model_dump_json``, :meth:`to_dict` and :meth:`to_yaml` give the same
        content; a helper next to them would leave pydantic's own methods
        disagreeing with the file. See :func:`_without_absence` for what stays.
        """
        return _without_absence(handler(self))

    def to_dict(self) -> dict[str, Any]:
        """The model as plain data. ``load_model(m.to_dict())`` reproduces it."""
        return self.model_dump()

    def to_yaml(self) -> str:
        """The file a reviewer reads — including for a model that never had one.

        Hard rule 5 is that the model is the file you review and diff; a model
        a framework emitted as a dict has no such file. Generated rather than
        authored, so length costs a reader nothing and being unambiguous saves
        them knowing this package's defaults at all.
        """
        import yaml

        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @model_validator(mode='after')
    def _validate_references(self) -> Model:
        """Every cross-declaration rule the schema can decide without data.

        Names share one flat namespace, shadowing being how a new declaration
        would silently change what an existing expression means. Every lookup
        joins it — a lookup named after a dimension, its own target included,
        is a collision, so each map carries a name of its own.

        A lookup's target must be a declared dimension other than the one it
        is over — grouping a dim into itself is a no-op that reads as a
        reduction. Bounds look like the expression language but are not it, so
        their error says what they actually accept.
        """
        errors = []

        kinds: list[tuple[str, Iterable[str]]] = [
            ('dimension', self.dimensions),
            ('lookup', self.lookups),
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
                        f"{kind.capitalize()} '{name}' collides with the built-in operator "
                        f"'{name}'. The operator set is closed and its names are reserved; "
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

        for lname, lk in self.lookups.items():
            if lk.over not in self.dimensions:
                errors.append(
                    f"Lookup '{lname}' is over undeclared dimension '{lk.over}'. Declare it under 'dimensions:'."
                )
            if lk.into is not None:
                if lk.into not in self.dimensions:
                    errors.append(
                        f"Lookup '{lname}' targets undeclared dimension '{lk.into}'. "
                        f"Declare it under 'dimensions:' — the target is what the "
                        f'lookup values are checked against.'
                    )
                elif lk.into == lk.over:
                    errors.append(
                        f"Lookup '{lname}' maps '{lk.over}' into itself. A lookup maps into a different dimension."
                    )

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
        an expanded model carrying no ``piecewise:``.

        An expansion *builds* a ``Model``, which validates itself on the way
        out, so the check below runs only when there was nothing to expand;
        and ``expand_piecewise`` memoises on :attr:`_expansion` for the same
        reason, every consumer asking for the expansion next.

        ``known_variables`` arrives as pydantic validation context, for the one
        file deliberately not valid alone: an extension references variables
        already on the model ``lpspec.linopy.extend`` puts it on. It travels
        into expansion too, a link being able to name one.
        """
        from lpspec.language.piecewise import expand_piecewise
        from lpspec.language.validation import validate_expressions

        known = (info.context or {}).get('known_variables', {})
        if expand_piecewise(self, known_variables=known) is self:
            validate_expressions(self, known_variables=known)
        return self
