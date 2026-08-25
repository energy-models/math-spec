# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The YAML surface's types — every block a file may contain, rooted at :class:`Model`.

A block per declaration kind, and one strict base: an unrecognised key is an
error naming the near miss rather than a shrug, because a dropped ``bounds:``
leaves a variable unbounded and says nothing.

Nothing here has seen data.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, get_args, override

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from math_spec.errors import did_you_mean, schema_error
from math_spec.operators import BUILTIN_NAMES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema


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


#: The dtype a dimension index may declare (the declaration rules).
DimensionDtype = Literal['float', 'int', 'str', 'datetime']

#: The dtype a parameter may declare (the declaration rules), and what its bound
#: column must be.
ParameterDtype = Literal['float', 'int', 'bool', 'str']

#: The domain a variable may declare.
VariableDomain = Literal['continuous', 'integer', 'binary']

#: What a masked variable's non-existence *means*.
VariableAbsence = Literal['undefined', 'zero']

#: Which way an objective is optimised (the declaration rules).
ObjectiveSense = Literal['minimize', 'maximize']

#: The relation a link may pin its expression to the curve with.
LinkSign = Literal['==', '<=', '>=']

#: The order of special ordered set a sink carries.
SosType = Literal[1, 2]

#: How a ``piecewise:`` block restricts its interpolation weights. Kept in step
#: with :data:`PIECEWISE_METHODS`, which says what each one emits, by
#: ``tests/test_schema.py``.
PiecewiseMethod = Literal['adjacency', 'sos2', 'convex', 'lp']

# The set form of each vocabulary above, for callers that want membership.

DIMENSION_DTYPES = frozenset(get_args(DimensionDtype))
PARAMETER_DTYPES = frozenset(get_args(ParameterDtype))
#: The parameter dtypes that stand where a number belongs — a coefficient, a
#: term, a divisor, a bound. A label selects and a flag masks; neither is one.
NUMERIC_DTYPES = frozenset({'float', 'int'})
VARIABLE_DOMAINS = frozenset(get_args(VariableDomain))
VARIABLE_ABSENCE = frozenset(get_args(VariableAbsence))


def _also_written_as(
    core_schema: CoreSchema, handler: GetJsonSchemaHandler, shorthand: JsonSchemaValue
) -> JsonSchemaValue:
    """The block's own schema, widened to a *shorthand* its before-validator takes.

    A ``mode='before'`` rewrite is invisible to pydantic, which generates the
    schema from the post-rewrite fields alone, so the shorthand has to be added
    back by hand or an editor red-squiggles the form the file is written in.

    ``handler`` returns the definition itself on most versions and a ``$ref``
    to it on pydantic 2.10; the ref is followed, because an ``anyOf`` branch
    pointing at its own entry is a loop with the mapping form unreachable.
    """
    generated = handler(core_schema)
    if set(generated) == {'$ref'}:
        generated = handler.resolve_ref_schema(generated)
    return {'anyOf': [dict(generated), shorthand]}


class LookupBlock(_StrictBlock):
    """A named single-valued map out of a dimension (the declaration rules).

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
      (:func:`math_spec.resolution._ungroupable`)::

          lookups:
            period: {over: snapshot, dtype: int}

    ``values:`` gives the map in the file — ``{label of over: value}`` — for a
    relation small enough to read, the way a dimension's own ``values:`` does.
    A label it omits is unmapped, which is the partial case a lookup already
    allows. Without it the map is supplied at bind time under the lookup's own
    source key, as a ``(over, label space)`` relation of the rows it has (the
    data-binding rules). One of the two, and never neither.
    """

    _label: ClassVar[str] = 'a lookup declaration'

    over: str
    into: str | None = None
    dtype: DimensionDtype | None = None
    values: dict[Any, Any] | None = None
    description: str | None = None

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

    dtype: DimensionDtype = 'str'
    values: list[Any] | None = None
    description: str | None = None


class ParameterBlock(_StrictBlock):
    """A declared parameter with dims and dtype."""

    _label: ClassVar[str] = 'a parameter declaration'

    dims: list[str]
    dtype: ParameterDtype = 'float'
    description: str | None = None

    @property
    def referenced_dims(self) -> list[str]:
        """The dimensions this block names — `dims` here, `foreach` on the rest."""
        return self.dims


class BoundsBlock(_StrictBlock):
    """Variable bounds — each side is a number or parameter name.

    linopy's defaults (``add_variables(lower=-inf, upper=inf)``): omitting a
    bound leaves the variable unbounded on that side, not implicitly
    non-negative. Non-negativity is a real constraint, so the file says it.
    """

    _label: ClassVar[str] = 'a bounds block'

    lower: float | str = float('-inf')
    upper: float | str = float('inf')

    @field_validator('lower', 'upper', mode='before')
    @classmethod
    def _a_number_or_a_name(cls, v: Any, info: ValidationInfo) -> Any:
        if isinstance(v, bool):
            msg = f'bounds.{info.field_name} is a boolean, and a bound is a number or a parameter name.'
            raise ValueError(msg)
        if isinstance(v, float) and math.isnan(v):
            msg = f'bounds.{info.field_name} is nan, which no value compares to. Write a number, or omit the bound.'
            raise ValueError(msg)
        return v


class VariableBlock(_StrictBlock):
    """A declared decision variable."""

    _label: ClassVar[str] = 'a variable declaration'

    foreach: list[str]
    where: str | None = None
    bounds: BoundsBlock = BoundsBlock()
    domain: VariableDomain = 'continuous'
    absence: VariableAbsence = 'undefined'
    description: str | None = None

    @property
    def referenced_dims(self) -> list[str]:
        return self.foreach

    @model_validator(mode='after')
    def _absence_needs_a_mask(self) -> VariableBlock:
        """``absence:`` says what a *missing* coordinate means, so one must be missable.

        A variable's only source of absence is its own ``where:`` — ``foreach``
        is a product of declared dimensions and has every coordinate. Without a
        mask the key selects between two readings of a case that cannot arise,
        which is a setting the reader has to interpret and nothing can reach.
        """
        if self.absence != 'undefined' and self.where is None:
            msg = (
                f'absence: {self.absence} needs a `where:` — a variable with no mask exists at every '
                f'coordinate of its foreach, so there is no absence for it to describe. Add the mask, '
                f'or drop the key.'
            )
            raise ValueError(msg)
        return self


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


class ObjectiveBlock(_StrictBlock):
    """A declared objective function."""

    _label: ClassVar[str] = 'an objective declaration'

    sense: ObjectiveSense = 'minimize'
    expression: str
    description: str | None = None


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

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """The published schema admits the bare string the one-line form is written as."""
        return _also_written_as(core_schema, handler, {'type': 'string'})

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
    sign: LinkSign = '=='

    @model_validator(mode='before')
    @classmethod
    def _from_list(cls, data: Any) -> Any:
        if isinstance(data, list):
            if not 2 <= len(data) <= 3:
                msg = f'each link must be [expression, values] or [expression, values, sign], got {data!r}'
                raise ValueError(msg)
            return dict(zip(('expression', 'values', 'sign'), data, strict=False))
        return data

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """The published schema admits the ``[expression, values, sign?]`` form every link is written as."""
        list_form = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 3}
        return _also_written_as(core_schema, handler, list_form)

    @model_serializer
    def _as_list(self) -> list[str]:
        return [self.expression, self.values] if self.sign == '==' else [self.expression, self.values, self.sign]


#: How a ``piecewise:`` block restricts its interpolation weights, and what
#: each one emits. The key is ``method:`` because that is
#: ``linopy.Model.add_piecewise_formulation``'s (#695); ``sos2`` and ``lp`` are
#: its words too, and mean the same things. ``adjacency`` and ``convex`` are
#: ours, linopy having no name for the first and reaching the second only as a
#: fallback.
#:
#: ``lp`` is the one that emits no weights: it states the curve as its segment
#: lines directly, which is exact for a convex or concave curve bounded on the
#: matching side, and needs the domain rows because a line does not stop at a
#: breakpoint.
PIECEWISE_METHODS = {
    'adjacency': 'a binary per segment, and a row making the two nonzero weights neighbours',
    'sos2': 'the same weights, restricted by a set the sink branches on (the sos rules)',
    'convex': 'nothing — the weights range over the hull, which is a pure LP',
    'lp': 'no weights at all — one row per segment line, plus the two rows holding the domain',
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
    :data:`PIECEWISE_METHODS` restricts the weights; ``activity`` names what the weights sum
    to — 1 where the block is unconditional, and a binary where a curve applies
    only when something runs, which pins the formulation to 0 when it is 0; ``points`` names a
    boolean parameter saying how far each curve runs, for a model whose curves
    are not all the same length. Expanded before building into plain variables
    and constraints — see ``math_spec.piecewise``.
    """

    _label: ClassVar[str] = 'a piecewise declaration'

    over: str
    links: list[PiecewiseLink]
    method: PiecewiseMethod = 'adjacency'
    activity: str | None = None
    points: str | None = None
    description: str | None = None

    @property
    def convex(self) -> bool:
        """Whether this block relaxes to the hull, which needs no binaries.

        The curvature guard and the expansion both ask this rather than
        comparing against the method name, since what they act on is the
        absence of a restriction and not which word was written.
        """
        return self.method == 'convex'

    @property
    def curve(self) -> tuple[PiecewiseLink, PiecewiseLink]:
        """The two links as ``(x, y)``, the bounded one last.

        Only a two-link block has a curve to speak of, and only a bounded link
        can be the wrong way round in ``links:`` — so this is what reads the
        pair anywhere the ``y`` side is the one being stated.
        """
        x, y = self.links
        return (y, x) if x.sign != '==' else (x, y)

    @property
    def curvature_required(self) -> str | None:
        """The curvature this block's method is only exact for, if any.

        ``'either'`` is the hull's condition — it cuts corners on a *mixed*
        curve and nothing else. ``lp`` states one side of the curve and its
        sign says which, so the opposite bend is silently wrong rather than
        merely loose.
        """
        if self.method == 'convex':
            return 'either'
        if self.method != 'lp':
            return None
        return 'convex' if self.curve[1].sign == '>=' else 'concave'

    @field_validator('method', mode='wrap')
    @classmethod
    def _check_method(cls, v: Any, handler: ValidatorFunctionWrapHandler) -> PiecewiseMethod:
        try:
            return handler(v)
        except ValidationError:
            options = '\n'.join(f'  {name}: {what}' for name, what in PIECEWISE_METHODS.items())
            msg = f'unknown piecewise method {v!r}. The formulations are:\n{options}'
            raise ValueError(msg) from None

    @model_validator(mode='after')
    def _check_method_shape(self) -> PiecewiseBlock:
        if self.convex and len(self.links) != 2:
            msg = (
                'method: convex requires exactly two links (the hull relaxation '
                'is only well-defined for a single y=f(x) curve).'
            )
            raise ValueError(msg)
        if self.method == 'lp' and sum(link.sign != '==' for link in self.links) != 1:
            msg = (
                "method: lp needs exactly one link bounded by the curve — a '<=' or '>=' third "
                'element on it. With every link pinned the segment lines have nothing to bound.'
            )
            raise ValueError(msg)
        if self.activity is not None and self.method in ('convex', 'lp'):
            msg = f'activity is not supported with method: {self.method}.'
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


#: The orders of special ordered set a sink carries — nothing else is a
#: construct solvers have.
SOS_TYPES = frozenset(get_args(SosType))


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
    type: SosType
    big_m: float | None = None
    description: str | None = None

    @field_validator('type', mode='before')
    @classmethod
    def _check_type(cls, v: Any) -> Any:
        if type(v) is not int or v not in SOS_TYPES:
            orders = ' or '.join(str(t) for t in sorted(SOS_TYPES))
            msg = f'sos type must be {orders}, got {v!r}. A set of any other order is not a construct solvers carry.'
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


def _repeated(items: Iterable[Any]) -> list[Any]:
    """Each value that appears more than once, once, in first-repeat order — for labels that may be unhashable."""
    seen: list[Any] = []
    repeats: list[Any] = []
    for item in items:
        if item in seen and item not in repeats:
            repeats.append(item)
        seen.append(item)
    return repeats


def _without_absence(value: Any) -> Any:
    """Strip what is absent — a null, an infinite bound, or a mapping left empty by stripping.

    A mapping that was *declared* empty stays: ``values: {}`` is a map the
    file states with nothing in it, which is not a map supplied later. An
    empty **list** is kept for the same reason — a list carries *cardinality*
    and zero is one of its values, ``foreach: []`` being a scalar declaration.
    Nothing else is judged — a value that is there is written, default or not.
    """
    if isinstance(value, dict):
        pruned = {k: _without_absence(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if not _is_absent(v) and (v != {} or value[k] == {})}
    return value


def _in_our_tree(validate: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run *validate*, raising this package's exception tree.

    Pydantic's ``ValidationError`` carries an ``input_value=`` dump and a link
    to its own docs, neither of which is the type ``docs/reference/api.md`` tells a
    caller to catch. Both of :class:`Model`'s validating doors go through here
    so they cannot answer differently.

    ``__init__`` is deliberately *not* wrapped: defining one makes pydantic
    route validation through it, so every after-validator runs twice, and this
    model's validate every expression in the file. The constructor keeps
    pydantic's error; ``load_model`` is the documented door and comes
    through here.
    """
    try:
        return validate(*args, **kwargs)
    except ValidationError as exc:
        raise schema_error(exc) from None


def _is_absent(value: Any) -> bool:
    """Whether a serialised value says *nothing is here* — a null, or an infinite bound.

    ``inf`` is included because an infinite bound is not a bound — it is the
    unbounded side, which is what omitting the bound already means. Stripping
    it is what makes JSON lossless as well: JSON has no infinity, so anything
    that reached ``model_dump_json`` as ``inf`` came back as ``null`` and read
    as absent anyway. Removing it here means the two agree instead of one being
    quietly wrong.
    """
    if value is None:
        return True
    return isinstance(value, float) and math.isinf(value)


class Model(_StrictBlock):
    """The declared math — one YAML file, or one dict, validated. Nothing here has seen data.

    The API is the ten declaration sections plus ``version`` and
    ``description``, and two ways back out: :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads. In goes through
    ``load_model``, which raises
    :class:`~math_spec.errors.LanguageError` on a model the language refuses.

    Everything else on this class is pydantic's, not a contract this package
    keeps — ``model_json_schema()`` describes the shape pydantic validates
    rather than the language (checked in for editors as
    ``schema/math_spec.schema.json``), and ``model_construct()`` skips validation
    entirely, so a ``Model`` is valid when it was built the normal way.
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: The :class:`Buildable` built from this model. Owned entirely — written
    #: and read — by :func:`~math_spec.piecewise.expand_piecewise`; only
    #: the slot lives here.
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

    def _declared_lookup_errors(self, name: str, lookup: LookupBlock) -> list[str]:
        """What a lookup's inline ``values:`` can be wrong about, without data.

        Law 2: both sides are in the file, so containment is decided here
        rather than at bind time — which is the whole reason declaring the map
        beats supplying it. Only checked against a target that declares its own
        labels; against one bound at run time the check stays where it was.
        """
        if lookup.values is None:
            return []
        errors = []
        over = self.dimensions.get(lookup.over)
        if over is not None and over.values is not None:
            strangers = [k for k in lookup.values if k not in over.values]
            if strangers:
                errors.append(
                    f"Lookup '{name}' declares values for {strangers!r}, which are not "
                    f"labels of '{lookup.over}' ({over.values!r}). A lookup maps the labels "
                    f'its dimension has.'
                )
        target = self.dimensions.get(lookup.into) if lookup.into is not None else None
        if target is not None and target.values is not None:
            strangers = sorted({repr(v) for v in lookup.values.values() if v is not None and v not in target.values})
            if strangers:
                errors.append(
                    f"Lookup '{name}' maps to {', '.join(strangers)}, which are not labels of "
                    f"'{lookup.into}' ({target.values!r}). Every value must be a declared "
                    f"'{lookup.into}' label — otherwise sum(by={name}) drops those terms."
                )
        return errors

    @classmethod
    @override
    def model_validate(cls, *args: Any, **kwargs: Any) -> Self:
        """Validate a mapping — see :func:`_in_our_tree` for what it raises."""
        return _in_our_tree(super().model_validate, *args, **kwargs)

    @classmethod
    @override
    def model_validate_json(cls, *args: Any, **kwargs: Any) -> Self:
        """The same door, for JSON."""
        return _in_our_tree(super().model_validate_json, *args, **kwargs)

    @field_validator('version')
    @classmethod
    def _check_version(cls, v: int) -> int:
        """Refuse a surface this reader does not know — never interpret it."""
        if v in SUPPORTED_VERSIONS:
            return v
        from math_spec import __version__ as installed

        supported = ', '.join(str(s) for s in SUPPORTED_VERSIONS)
        msg = (
            f'model declares version {v}, and math_spec {installed} understands [{supported}]. '
            f'Upgrade math_spec, or write the version this file actually targets.'
        )
        raise ValueError(msg)

    @model_serializer(mode='wrap')
    def _drop_absence(self, handler: Any) -> dict[str, Any]:
        """Absence is not serialised — a null, an infinite bound, or a section declaring nothing.

        On the *serializer* rather than beside it so ``model_dump``,
        ``model_dump_json``, :meth:`to_dict` and :meth:`to_yaml` give the same
        content; a helper next to them would leave pydantic's own methods
        disagreeing with the file. See :func:`_without_absence` for what stays.
        """
        written = _without_absence(handler(self))
        return {k: v for k, v in written.items() if v != {}}

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

        for kind, group in (
            ('Parameter', self.parameters),
            ('Variable', self.variables),
            ('Constraint', self.constraints),
        ):
            for name, item in group.items():
                errors.extend(
                    f"{kind} '{name}' references undeclared dimension '{d}'. Declare it under 'dimensions:'."
                    for d in item.referenced_dims
                    if d not in self.dimensions
                )
                errors.extend(
                    f"{kind} '{name}' names dimension '{d}' twice. A frame is a product of distinct dimensions."
                    for d in _repeated(item.referenced_dims)
                )
        for dname, ddef in self.dimensions.items():
            errors.extend(
                f"Dimension '{dname}' declares label {label!r} twice. A label is one coordinate; drop the repeat."
                for label in _repeated(ddef.values or [])
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
            errors.extend(self._declared_lookup_errors(lname, lk))

        for vname, vdef in self.variables.items():
            for side in ('lower', 'upper'):
                val = getattr(vdef.bounds, side)
                if not isinstance(val, str):
                    continue
                if val in self.parameters:
                    dtype = self.parameters[val].dtype
                    if dtype not in NUMERIC_DTYPES:
                        errors.append(
                            f"Variable '{vname}' bounds.{side}: '{val}' is a {dtype} parameter, and a bound "
                            f'is a number. Declare it dtype: float or int, or bound the variable by another.'
                        )
                    continue
                detail = (
                    f"'{val}' is not a declared parameter"
                    if val.isidentifier()
                    else f'bounds accept a parameter name or a number, not an expression (got {val!r}). '
                    f'Precompute it as a parameter'
                )
                errors.append(f"Variable '{vname}' bounds.{side}: {detail}.")

        if errors:
            raise ValueError('\n'.join(errors))

        return self

    @model_validator(mode='after')
    def _validate_expressions(self) -> Model:
        """Every expression and where string, checked here rather than beside.

        The checkers import this module, so the imports are local. Expansion
        runs first — a
        formulation emits declarations that are language too — and the
        :class:`Buildable` it builds validates itself on the way out, so a file
        with curves is checked there rather than checked twice here.
        """
        from math_spec.piecewise import expand_piecewise
        from math_spec.validation import validate_expressions

        if self.piecewise:
            expand_piecewise(self)
        else:
            validate_expressions(self)
        return self


class Buildable(Model):
    """A model with nothing left to expand — what rows are built from.

    A :class:`Model` is the file as written, and a file may carry a
    ``piecewise:`` block whose variables and constraints do not exist until
    :func:`~math_spec.piecewise.expand_piecewise` emits them. This is the
    model after that pass, and it guarantees the one thing a builder needs:
    ``variables:`` and ``constraints:`` hold the whole model, so the rows built
    from it are the rows the file asked for.

    Taking one is how a consumer says it *builds* rather than *reads*, and
    passing a :class:`Model` where one is wanted is a type error rather than a
    model quietly missing declarations. Whatever reads the file as written
    takes a :class:`Model` and accepts either.

    The guarantee is about *declarations*, and deliberately says nothing about
    the expression strings inside them: ``macros:`` and ``expressions:`` are
    substituted per read, because an expression is needed only when someone
    reads it where the set of declarations is needed before anything can be.
    """

    @model_validator(mode='after')
    def _nothing_left_to_expand(self) -> Buildable:
        if self.piecewise:
            msg = 'a Buildable carries no piecewise: — expand_piecewise is what produces one'
            raise ValueError(msg)
        return self
