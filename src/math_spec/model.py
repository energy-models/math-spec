# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The YAML surface's types — every block a file may contain, rooted at :class:`Spec`.

A block per declaration kind, and one strict base: an unrecognised key is an
error naming the near miss rather than a shrug, because a dropped ``bounds:``
leaves a variable unbounded and says nothing.

Nothing here has seen data.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, Self, get_args, override

from pydantic import (
    BaseModel,
    BeforeValidator,
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
    from collections.abc import Iterable

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
            label = cls._label or cls.__name__
            raise ValueError(
                '\n'.join(
                    f"unknown key '{k}' in {label}. {did_you_mean(k, known, label='Valid keys')}" for k in unknown
                )
            )
        return data


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

#: The order of special ordered set.
SosType = Literal[1, 2]

#: How a ``piecewise:`` block restricts its interpolation weights. Kept in step
#: with :data:`PIECEWISE_METHODS`, which says what each one emits, by
#: ``tests/test_schema.py``.
PiecewiseMethod = Literal['adjacency', 'sos2', 'convex', 'lp']

#: The shape a method needs a curve to have to be exact on it, answered by
#: :func:`~math_spec.piecewise.curvature_required`. ``convex`` and ``concave``
#: name one bend; ``either`` is the hull's weaker condition — any single bend
#: will do, and only a *mixed* curve fails it.
Curvature = Literal['convex', 'concave', 'either']

#: The set form of each vocabulary above, for callers that want membership.
DIMENSION_DTYPES = frozenset(get_args(DimensionDtype))
PARAMETER_DTYPES = frozenset(get_args(ParameterDtype))
#: The parameter dtypes that stand where a number belongs — a coefficient, a
#: term, a divisor, a bound. A label selects and a flag masks; neither is one.
NUMERIC_DTYPES = frozenset({'float', 'int'})
VARIABLE_DOMAINS = frozenset(get_args(VariableDomain))
VARIABLE_ABSENCE = frozenset(get_args(VariableAbsence))
CURVATURES = frozenset(get_args(Curvature))


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

    Exactly one of ``into:`` (a groupable map onto that dimension, what
    ``sum(by=)`` lands terms on) or ``dtype:`` (its own label space, selection
    only)::

        lookups:
          bus_of: {over: generator, into: bus}
          period: {over: snapshot, dtype: int}

    The map itself is data, and arrives at bind time under the lookup's name.
    """

    _label: ClassVar[str] = 'a lookup declaration'

    over: str
    into: str | None = None
    dtype: DimensionDtype | None = None
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
    """A declared dimension, and the dtype its coordinates must be.

    A dimension is an axis and nothing else: it declares that the axis exists
    and what its coordinates are typed as, never which coordinates there are —
    those are data, and arrive at bind time. The maps its members carry — a
    generator's bus, a snapshot's period — are top-level ``lookups:``
    (:class:`LookupBlock`), keyed by their own name.
    """

    _label: ClassVar[str] = 'a dimension declaration'

    dtype: DimensionDtype = 'str'
    description: str | None = None


class ParameterBlock(_StrictBlock):
    """A declared parameter with dims and dtype."""

    _label: ClassVar[str] = 'a parameter declaration'

    dims: list[str]
    dtype: ParameterDtype = 'float'
    description: str | None = None


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

    @model_validator(mode='after')
    def _literals_do_not_cross(self) -> BoundsBlock:
        """Two numbers that leave no value between them are refused; a named bound is data."""
        if isinstance(self.lower, float) and isinstance(self.upper, float) and self.lower > self.upper:
            msg = (
                f'bounds.lower {self.lower} is above bounds.upper {self.upper}, so no value satisfies them. '
                f'Swap them, or drop one.'
            )
            raise ValueError(msg)
        return self


class VariableBlock(_StrictBlock):
    """A declared decision variable."""

    _label: ClassVar[str] = 'a variable declaration'

    foreach: list[str]
    where: str | None = None
    bounds: BoundsBlock = BoundsBlock()
    domain: VariableDomain = 'continuous'
    absence: VariableAbsence = 'undefined'
    description: str | None = None

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


def _number_is_an_expression(value: Any) -> Any:
    """``expression: 0`` is how a file writes a constant — YAML reads it as an int.

    Booleans are left to fail: ``true`` is not arithmetic, and an error naming
    the type reads better than one naming ``'True'``.
    """
    return str(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


#: An expression string, or a number written as one.
Expression = Annotated[str, BeforeValidator(_number_is_an_expression, json_schema_input_type=str | float)]


class ExpressionCase(_StrictBlock):
    """One region of a named expression: the value, and when it is the value.

    ``when`` is absent on the case named ``default`` and only there, so that
    case is written as the bare value — the shorthand ``expressions:`` itself
    takes, for the same reason::

        cases:
          opening: { when: "position(snapshot) == 0", expression: p_max }
          default: 0
    """

    _label: ClassVar[str] = 'an expression case'

    when: str | None = None
    expression: Expression

    @model_validator(mode='before')
    @classmethod
    def _from_value(cls, data: Any) -> Any:
        return data if isinstance(data, dict) else {'expression': data}

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """The published schema admits the bare value a conditionless case is written as."""
        return _also_written_as(core_schema, handler, {'type': ['string', 'number']})

    @model_serializer
    def _as_written(self) -> str | dict[str, Any]:
        if self.when is None:
            return self.expression
        return {'when': self.when, 'expression': self.expression}


class ExpressionBlock(_StrictBlock):
    """A named quantity: one arithmetic expression, readable after a solve.

    Written in YAML as a bare string, or as a mapping once it carries a
    ``description:`` — and serialised back to whichever form it was written in,
    so a round trip through :meth:`Spec.to_yaml` reproduces the file::

        expressions:
          total_generation: sum(p, over=generator)
          emissions:
            expression: sum(p * rate, over=generator)
            description: CO2 released, the quantity the cap bounds

    A quantity whose value varies by **region** is written as ``cases:``
    instead — one case per region over a declared ``foreach:``, no two of them
    claiming one coordinate, and ``default`` last for the rest::

        previous_status:
          foreach: [snapshot, generator]
          cases:
            always_on: { when: "not committable", expression: 1 }
            boundary:  { when: "committable and position(snapshot) == 0", expression: status_initial }
            default:   shift(status, over=snapshot, offset=1)

    So the constraint that needs it names it, rather than being forked into one
    copy per regime.
    """

    _label: ClassVar[str] = 'a named expression'

    expression: Expression | None = None
    #: The frame the cases are read over — required with them and refused
    #: without, since no one case's body gives a cased expression its shape.
    foreach: list[str] | None = None
    #: The regions this quantity is defined by, keyed by the name labelling the
    #: row it prints. Each ``when`` is proved apart from every other, so the
    #: order is the page's rather than the meaning's — bar ``default``, which
    #: carries no ``when`` and is written last because that is where it prints.
    cases: dict[str, ExpressionCase] = {}
    description: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _from_string(cls, data: Any) -> Any:
        return {'expression': data} if isinstance(data, str) else data

    @model_validator(mode='after')
    def _one_form_or_the_other(self) -> Self:
        """One ``expression:`` or two or more ``cases:``, and a ``foreach:`` with those.

        Each near-miss gets its own sentence, being a different mistake: both
        is not knowing which wins, neither is an empty declaration, and a
        ``foreach:`` alone is a second answer to what the body already answers.
        """
        if bool(self.cases) == (self.expression is not None):
            got = 'both' if self.cases else 'neither'
            msg = (
                f'a named expression is one `expression:` or a set of `cases:`, and this has {got}. '
                f'Cases are for a quantity whose value varies by region; one expression is everything else.'
            )
            raise ValueError(msg)
        if self.cases and self.foreach is None:
            msg = (
                '`cases:` needs a `foreach:` — it is the frame the cases are read over, and no one '
                "case's body gives it, since a case may be a scalar while the condition selecting it is not."
            )
            raise ValueError(msg)
        if self.foreach is not None and not self.cases:
            msg = (
                '`foreach:` is only for a named expression with `cases:`. Without them the dims fall '
                'out of the body, and declaring a second answer is a second thing to keep true.'
            )
            raise ValueError(msg)
        return self

    @model_validator(mode='after')
    def _default_is_the_last_case(self) -> Self:
        """A case named ``default`` is written last, and it alone carries no ``when``.

        Whether two cases can overlap is a question about predicates, which
        :mod:`math_spec.exclusivity` answers once the names have resolved. That
        the quantity has a value at *every* coordinate is settled here instead,
        by the block's shape: ``default`` has no condition to fail.
        """
        if not self.cases:
            return self
        labels = list(self.cases)
        if 'default' not in self.cases:
            msg = (
                f'a `cases:` block needs a case named `default` — the value wherever no `when` '
                f'holds, and the row that prints as "otherwise". Without it the quantity would have '
                f'no value there, and absence spreads to every constraint that names it. '
                f'The cases here are `{"`, `".join(labels)}`.'
            )
            raise ValueError(msg)
        if labels[-1] != 'default':
            msg = (
                f'`default` is written last, and here `{labels[-1]}` follows it. It is the row that '
                f'prints as "otherwise", which is the last row of the block, so the file reads in '
                f'the order the page does.'
            )
            raise ValueError(msg)
        if len(labels) == 1:
            msg = (
                'a `cases:` block whose only case is `default` is one value everywhere, '
                'which is what a plain `expression:` already says.'
            )
            raise ValueError(msg)
        if self.cases['default'].when is not None:
            msg = (
                '`default` carries a `when:`, and it is the one case that must not — it is what '
                'covers every coordinate the others leave. Give the region a name of its own if it '
                'is a region like any other.'
            )
            raise ValueError(msg)
        conditionless = [name for name, case in self.cases.items() if case.when is None and name != 'default']
        if conditionless:
            msg = (
                f'`{"`, `".join(conditionless)}` carry no `when:`, and `default` is the only case '
                f'that may omit one — every other case says where it applies, so that no two of '
                f'them can claim one coordinate.'
            )
            raise ValueError(msg)
        return self

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """The published schema admits the bare string the one-line form is written as."""
        return _also_written_as(core_schema, handler, {'type': 'string'})

    @model_serializer
    def _as_written(self) -> str | dict[str, Any]:
        if self.cases:
            written: dict[str, Any] = {'foreach': list(self.foreach or [])}
            if self.description is not None:
                written['description'] = self.description
            written['cases'] = {name: case.model_dump() for name, case in self.cases.items()}
            return written
        assert self.expression is not None
        if self.description is None:
            return self.expression
        return {'expression': self.expression, 'description': self.description}


class PiecewiseLink(_StrictBlock):
    """One link of a piecewise block: an expression pinned to a values curve.

    Written in YAML as ``[expression, values]`` or ``[expression, values,
    sign]`` and serialised back to exactly that form, so a round trip through
    :meth:`Spec.to_yaml` reproduces the file.
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
#: ``linopy.Spec.add_piecewise_formulation``'s (#695); ``sos2`` and ``lp`` are
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
    'sos2': 'the same weights, restricted by a set the solver branches on (the sos rules)',
    'convex': 'nothing — the weights range over the hull, which is a pure LP',
    'lp': 'no weights at all — one row per segment line, plus the two rows holding the domain',
}


class PiecewiseBlock(_StrictBlock):
    """N expressions jointly pinned to a breakpoint-indexed piecewise curve.

    Mirrors ``linopy.Spec.add_piecewise_formulation``. Each link is
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
    def curve(self) -> tuple[PiecewiseLink, PiecewiseLink]:
        """The two links as ``(x, y)``, the bounded one last.

        Only a two-link block has a curve to speak of, and only a bounded link
        can be the wrong way round in ``links:`` — so this is what reads the
        pair anywhere the ``y`` side is the one being stated.
        """
        x, y = self.links
        return (y, x) if x.sign != '==' else (x, y)

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
        if self.method == 'convex' and len(self.links) != 2:
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


#: The orders of special ordered set — nothing else is a construct solvers
#: have.
SOS_TYPES = frozenset(get_args(SosType))


class SosBlock(_StrictBlock):
    """A special-ordered set over one dimension of one variable.

    One set per coordinate of the variable's ``foreach`` minus ``over``; the
    members are the variable's *existing* coordinates along ``over``, in that
    dimension's declared order, and ``big_m`` is the optional cap a consumer
    that reformulates the set puts on its linking rows.

    ``type: 1`` admits at most one nonzero member, ``type: 2`` at most two,
    and those two consecutive. Unlike every other block this one declares no
    math to read off ``A``: it is a *set*, carried to a consumer that has the
    concept and reformulated for one that does not.
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


def undeclared_dimension(kind: str, name: str, dimension: str) -> str:
    """The one wording for a declaration naming a dimension the file does not declare."""
    return f"{kind} '{name}' references undeclared dimension '{dimension}'. Declare it under 'dimensions:'."


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
    """*value* with every absent entry stripped, recursively — see :meth:`Spec._drop_absence`."""
    if not isinstance(value, dict):
        return value
    kept = {}
    for key, before in value.items():
        after = _without_absence(before)
        if not _is_absent(after) and after != {}:
            kept[key] = after
    return kept


def _is_absent(value: Any) -> bool:
    """Whether *value* is a null or an infinite bound."""
    if value is None:
        return True
    return isinstance(value, float) and math.isinf(value)


class Spec(_StrictBlock):
    """The declared math — one YAML file, or one dict, validated. Nothing here has seen data.

    The API is the ten declaration sections plus ``version`` and
    ``description``, and two ways back out: :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads. In goes through
    ``to_spec``, which raises
    :class:`~math_spec.errors.LanguageError` on a model the language refuses.

    Everything else on this class is pydantic's, not a contract this package
    keeps — ``model_json_schema()`` describes the shape pydantic validates
    rather than the language (checked in for editors as
    ``schema/math_spec.schema.json``), and ``model_construct()`` skips validation
    entirely, so a ``Spec`` is valid when it was built the normal way.
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: The :class:`_ExpandedSpec` built from this model. Owned entirely — written
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

    @classmethod
    @override
    def model_validate(cls, *args: Any, **kwargs: Any) -> Self:
        """Validate a mapping, raising this package's exception tree rather than pydantic's.

        ``__init__`` is not wrapped the same way, because defining one makes
        pydantic run every after-validator twice.
        """
        try:
            return super().model_validate(*args, **kwargs)
        except ValidationError as exc:
            raise schema_error(exc) from None

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
        """Absence is not serialised: a null, an infinite bound, a mapping that stripping emptied, a section declaring nothing.

        An empty list stays, being a value rather than an absence (``foreach:
        []`` is a scalar). On the serializer so that ``model_dump``,
        :meth:`to_dict` and :meth:`to_yaml` agree.
        """
        return _without_absence(handler(self))

    def to_dict(self) -> dict[str, Any]:
        """The model as plain data. ``to_spec(m.to_dict())`` reproduces it."""
        return self.model_dump()

    def to_yaml(self) -> str:
        """The file a reviewer reads — including for a model that never had one.

        Generated rather than authored, so length costs a reader nothing and
        being unambiguous saves them knowing this package's defaults at all.
        """
        import yaml

        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @model_validator(mode='after')
    def _validate_references(self) -> Spec:
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
                        f'the same name. Names share one flat namespace — rename one of them.'
                    )
                else:
                    seen[name] = kind

        frames = [
            *(('Parameter', name, p.dims) for name, p in self.parameters.items()),
            *(('Variable', name, v.foreach) for name, v in self.variables.items()),
            *(('Constraint', name, c.foreach) for name, c in self.constraints.items()),
            *(('Named expression', name, e.foreach or []) for name, e in self.expressions.items()),
        ]
        for kind, name, dims in frames:
            errors.extend(undeclared_dimension(kind, name, d) for d in dims if d not in self.dimensions)
            errors.extend(
                f"{kind} '{name}' names dimension '{d}' twice. A frame is a product of distinct dimensions."
                for d in _repeated(dims)
            )

        for lname, lk in self.lookups.items():
            if lk.over not in self.dimensions:
                errors.append(undeclared_dimension('Lookup', lname, lk.over))
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

        claimed: dict[str, str] = {}
        for sname, block in self.sos.items():
            context = f"Sos '{sname}'"
            if block.over not in self.dimensions:
                errors.append(undeclared_dimension('Sos', sname, block.over))
            elif block.variable not in self.variables:
                errors.append(
                    f"{context}: '{block.variable}' is not a declared variable.\n"
                    f'  Variables: {sorted(self.variables)}\n'
                    f'A set is over one variable, so a parameter or an expression cannot carry one.'
                )
            elif block.over not in self.variables[block.variable].foreach:
                errors.append(
                    f"{context}: over '{block.over}' is not a dim of variable "
                    f"'{block.variable}' (foreach {self.variables[block.variable].foreach}). The set runs "
                    f"along one of the variable's own dims — one set per coordinate of the rest."
                )
            elif block.variable in claimed:
                errors.append(
                    f"{context}: variable '{block.variable}' already carries the set declared by "
                    f"'{claimed[block.variable]}'. A variable holds one set — declare a second "
                    f'variable, or state the other restriction as a constraint.'
                )
            else:
                claimed[block.variable] = sname

        if errors:
            raise ValueError('\n'.join(errors))

        return self

    @model_validator(mode='after')
    def _validate_expressions(self) -> Spec:
        """Every expression and where string — after expansion, whose emitted declarations are language too.

        The :class:`_ExpandedSpec` expansion builds runs every validator of its own,
        so a file with ``piecewise:`` has its references checked twice and its
        expressions once, there. The checkers import this module, so the
        imports are local.
        """
        from math_spec.piecewise import expand_piecewise
        from math_spec.validation import validate_expressions

        if self.piecewise:
            expand_piecewise(self)
        else:
            validate_expressions(self)
        return self


class _ExpandedSpec(Spec):
    """A model with nothing left to expand — what rows are built from.

    :func:`~math_spec.piecewise.expand_piecewise` produces one, and
    ``variables:`` and ``constraints:`` then hold the whole model. A consumer
    that builds takes this type; one that reads takes :class:`Spec` and
    accepts either.
    """

    @model_validator(mode='after')
    def _nothing_left_to_expand(self) -> _ExpandedSpec:
        if self.piecewise:
            msg = 'an _ExpandedSpec carries no piecewise: — expand_piecewise is what produces one'
            raise ValueError(msg)
        return self
