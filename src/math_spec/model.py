# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The YAML surface's types — every block a file may contain, rooted at :class:`Spec`.

Nothing here has seen data.
"""

from __future__ import annotations

import math
import re
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self, cast, get_args, override

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from math_spec._expression_parser import NAME, ComparisonOperator
from math_spec.errors import did_you_mean, schema_error
from math_spec.program import (
    DimensionDtype,
    ObjectiveSense,
    ParameterDtype,
    PiecewiseMethod,
    Program,
    SosType,
    VariableAbsence,
    VariableDomain,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import GetJsonSchemaHandler, SerializerFunctionWrapHandler
    from pydantic.config import ExtraValues
    from pydantic_core import CoreSchema


class _StrictBlock(BaseModel):
    """Base for every schema model: unknown keys are an error, not a shrug.

    A misspelled optional key would otherwise be dropped and its declaration
    fall back to a default — ``boundz:`` leaves the variable unbounded,
    ``wher:`` leaves it unmasked — building a model the file does not describe.
    """

    model_config = ConfigDict(extra='forbid')

    #: What this model is called in a YAML file, for the error message.
    _label: ClassVar[str]

    @model_validator(mode='before')
    @classmethod
    def _reject_unknown_keys(cls, data: object) -> object:
        """Name the near-miss, which is what a typo actually needs.

        pydantic's own ``extra='forbid'`` is the backstop; this runs first
        only for the wording.
        """
        if not isinstance(data, dict):
            return data
        known = set(cls.model_fields)
        unknown = [k for k in data if isinstance(k, str) and k not in known]
        if unknown:
            raise ValueError(
                '\n'.join(
                    f"unknown key '{k}' in {cls._label}. {did_you_mean(k, known, label='Valid keys')}" for k in unknown
                )
            )
        return data


#: A block that states rows rather than being one, which :meth:`Spec.expand`
#: writes out on request.
Formulation = Literal['piecewise', 'sos']

#: The shape a method needs a curve to have to be exact on it, which the
#: ``<block>_curvature`` assumption states. ``convex`` and ``concave`` name the
#: side a bounded link binds from; ``either`` is the weaker condition a block
#: with both links pinned states — any single bend will do, and only a *mixed*
#: curve fails it.
Curvature = Literal['convex', 'concave', 'either']

#: The parameter dtypes that stand where a number belongs — a coefficient, a
#: term, a divisor, a bound. A label selects and a flag masks; neither is one.
NUMERIC_DTYPES: frozenset[ParameterDtype] = frozenset({'float', 'int'})

#: Every formulation, in the order :meth:`Spec.expand` writes them out: a curve
#: emits a set, and no set emits a curve.
FORMULATIONS: tuple[Formulation, ...] = ('piecewise', 'sos')


def _also_written_as(
    core_schema: CoreSchema, handler: GetJsonSchemaHandler, shorthand: Mapping[str, object]
) -> dict[str, object]:
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


def side_columns(written: str | list[str] | dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    """``(role, dimension)`` per column of one side of a relation, in written order.

    A bare name or a list names each column after the dimension it is over; a
    mapping names the roles, which is what two columns over one dimension need.
    """
    if written is None:
        return ()
    if isinstance(written, dict):
        return tuple(written.items())
    return tuple((d, d) for d in ((written,) if isinstance(written, str) else written))


class RelationBlock(_StrictBlock):
    """A named relation between dimensions: the columns a row is keyed by, and the columns that key determines.

    Each side is a dimension, a list of them, or a mapping of column name to
    dimension where two columns share one. ``key:`` is the claim the language
    checks at bind: one row per key tuple, so every ``values:`` column is a
    function of it. A relation with no ``values:`` is **bare** — every column is
    in its key, a row is its own identity, and nothing reads it::

        relations:
          gen_bus: {key: generator, values: bus}
          gen_bt: {key: [generator], values: [bus, technology]}
          zone_of: {key: [generator, period], values: zone}
          ends: {key: line, values: {bus0: bus, bus1: bus}}
          connection: {key: [generator, bus]}

    An operator reads the table in the direction the call names
    (``over=``, ``into=``), joining on the other key columns; the
    declaration fixes no direction. The map itself is data, and arrives at bind
    time under the relation's name, one column per role.
    """

    _label: ClassVar[str] = 'a relation declaration'

    key: str | list[str] | dict[str, str]
    values: str | list[str] | dict[str, str] | None = None
    description: str | None = None

    @property
    def pairs(self) -> tuple[tuple[str, str], ...]:
        """``(role, dimension)`` per column, the key's columns first.

        The program calls the same thing :attr:`~math_spec.program.RelationDeclaration.columns`;
        here the table has no field of its own, being what the two sides make.
        """
        return (*side_columns(self.key), *side_columns(self.values))

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(role for role, _ in self.pairs)

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(dim for _, dim in self.pairs)

    @property
    def key_roles(self) -> tuple[str, ...]:
        """The key roles, however ``key:`` was written."""
        return tuple(role for role, _ in side_columns(self.key))

    @property
    def value_roles(self) -> tuple[str, ...]:
        """The roles the key determines; empty for a bare relation."""
        return tuple(role for role, _ in side_columns(self.values))


class DimensionBlock(_StrictBlock):
    """A declared dimension, and the dtype its coordinates must be.

    A dimension is an axis and nothing else: it declares that the axis exists
    and what its coordinates are typed as, never which coordinates there are —
    those are data, and arrive at bind time. The maps its members carry — a
    generator's bus, a snapshot's period — are top-level ``relations:``
    (:class:`RelationBlock`), keyed by their own name.
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

    An omitted bound leaves the variable unbounded on that side, not
    implicitly non-negative.
    """

    _label: ClassVar[str] = 'a bounds block'

    lower: float | str = float('-inf')
    upper: float | str = float('inf')

    @field_validator('lower', 'upper', mode='before')
    @classmethod
    def _a_number_or_a_name(cls, v: object, info: ValidationInfo[object]) -> object:
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

    dims: list[str]
    where: str | None = None
    bounds: BoundsBlock = BoundsBlock()
    domain: VariableDomain = 'continuous'
    absence: VariableAbsence = 'undefined'
    description: str | None = None

    @model_validator(mode='after')
    def _absence_needs_a_mask(self) -> VariableBlock:
        """``absence:`` says what a *missing* coordinate means, so one must be missable."""
        if self.absence != 'undefined' and self.where is None:
            msg = (
                f'absence: {self.absence} needs a `where:` — a variable with no mask exists at every '
                f'coordinate of its dims, so there is no absence for it to describe. Add the mask, '
                f'or drop the key.'
            )
            raise ValueError(msg)
        return self


class GivenVariableBlock(_StrictBlock):
    """A column this file reads and another file introduces.

    The frame and the domain are all this file states. The file that introduces
    the column owns its bounds and its mask.
    """

    _label: ClassVar[str] = 'a given variable declaration'

    dims: list[str]
    domain: VariableDomain = 'continuous'
    description: str | None = None


class GivenConstraintBlock(_StrictBlock):
    """A row family this file reads the dual of and another model builds.

    The frame says how many duals there are and what indexes them, which is
    what ``dual()`` needs. There is no ``expression:``, because nothing here
    builds a row.
    """

    _label: ClassVar[str] = 'a given constraint declaration'

    dims: list[str]
    description: str | None = None


class GivenBlock(_StrictBlock):
    """What this file reads and does not build, by kind. Closed at the two kinds."""

    _label: ClassVar[str] = 'a given block'

    #: Columns another file introduces (:class:`GivenVariableBlock`).
    variables: dict[str, GivenVariableBlock] = {}
    #: Row families another model builds (:class:`GivenConstraintBlock`).
    constraints: dict[str, GivenConstraintBlock] = {}

    def __bool__(self) -> bool:
        """Whether the file reads anything it does not build."""
        return bool(self.variables or self.constraints)


class ConstraintBlock(_StrictBlock):
    """A declared constraint: one rule, over one frame."""

    _label: ClassVar[str] = 'a constraint declaration'

    dims: list[str]
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
    shadow model names inside the template, and every call site expands in
    the syntax tree before resolution reads the expression.
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


def _number_is_an_expression(value: object) -> object:
    """``expression: 0`` is how a file writes a constant — YAML reads it as an int.

    Booleans are left to fail: ``true`` is not arithmetic, and an error naming
    the type reads better than one naming ``'True'``.
    """
    return str(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


#: An expression string, or a number written as one.
Expression = Annotated[str, BeforeValidator(_number_is_an_expression, json_schema_input_type=str | float)]


class ExpressionCase(_StrictBlock):
    """One region of a named expression: the value, and when it is the value.

    Every case says where it applies. The value wherever none of them does is
    the block's ``otherwise:``, which is written outside ``cases:`` because it
    is not a region like these — it is what is left::

        cases:
          opening: { when: "position(snapshot) == 0", expression: p_max }
        otherwise: 0
    """

    _label: ClassVar[str] = 'an expression case'

    when: str
    expression: Expression


class ExpressionBlock(_StrictBlock):
    """A named quantity: one arithmetic expression, referenced by the math or read back after a solve.

    Written in YAML as a bare string, or as a mapping once it carries a
    ``description:`` — and serialised back to whichever form it was written in,
    so a round trip through :meth:`Spec.to_yaml` reproduces the file::

        expressions:
          total_generation: sum(p, over=generator)
          emissions:
            expression: sum(p * rate, over=generator)
            description: CO2 released, the quantity the cap bounds

    A quantity whose value varies by region is written as ``cases:`` over a
    declared ``dims:``, with an ``otherwise:`` for the rest — see the
    language reference.
    """

    _label: ClassVar[str] = 'a named expression'

    expression: Expression | None = None
    #: The frame the cases are read over — required with them, refused without.
    dims: list[str] | None = None
    #: The regions, keyed by the name labelling the row each prints; every ``when`` is proved apart from the others.
    cases: Annotated[dict[str, ExpressionCase], Field(min_length=1)] = {}
    #: The value wherever no case's ``when`` holds, printed as the last row.
    otherwise: Expression | None = None
    description: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _from_string(cls, data: object) -> object:
        return {'expression': data} if isinstance(data, str) else data

    @model_validator(mode='after')
    def _one_form_or_the_other(self) -> Self:
        """One ``expression:``, or ``cases:`` with the ``otherwise:`` and ``dims:`` they need."""
        if bool(self.cases) == (self.expression is not None):
            got = 'both' if self.cases else 'neither'
            msg = (
                f'a named expression is one `expression:` or a set of `cases:`, and this has {got}. '
                f'Cases are for a quantity whose value varies by region; one expression is everything else.'
            )
            raise ValueError(msg)
        if self.cases and self.dims is None:
            msg = (
                '`cases:` needs a `dims:` — it is the frame the cases are read over, and no one '
                "case's body gives it, since a case may be a scalar while the condition selecting it is not."
            )
            raise ValueError(msg)
        if self.dims is not None and not self.cases:
            msg = (
                '`dims:` is only for a named expression with `cases:`. Without them the dims fall '
                'out of the body, and declaring a second answer is a second thing to keep true.'
            )
            raise ValueError(msg)
        if self.cases and self.otherwise is None:
            msg = (
                'a `cases:` block needs an `otherwise:` — the value wherever no `when` holds, and '
                'the row that prints as "otherwise". Without it the quantity would have no value '
                'there, and absence spreads to every constraint that names it.'
            )
            raise ValueError(msg)
        if self.otherwise is not None and not self.cases:
            msg = (
                '`otherwise:` is what is left once the `cases:` have taken their regions, and there '
                'are none here. A value that holds everywhere is a plain `expression:`.'
            )
            raise ValueError(msg)
        return self

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, object]:
        """The published schema admits the bare string the one-line form is written as."""
        return _also_written_as(core_schema, handler, {'type': 'string'})

    @model_serializer
    def _as_written(self) -> str | dict[str, object]:
        if self.cases:
            written: dict[str, object] = {'dims': list(self.dims or [])}
            if self.description is not None:
                written['description'] = self.description
            written['cases'] = {name: case.model_dump() for name, case in self.cases.items()}
            written['otherwise'] = self.otherwise
            return written
        assert self.expression is not None
        if self.description is None:
            return self.expression
        return {'expression': self.expression, 'description': self.description}


class AssumptionBlock(_StrictBlock):
    """What the model assumes of its data: a predicate every coordinate it is checked at has to satisfy.

    Written in YAML as a bare where string, or as a mapping once it carries a
    ``where:`` or a ``description:``, and serialised back to whichever form it
    was written in::

        assumptions:
          efficiency_is_a_fraction: "efficiency > 0 AND efficiency <= 1"
          bounds_do_not_cross:
            holds: "p_min <= p_max"
            where: "p_min"
            description: a unit with no minimum is unconstrained below

    The language decides nothing about the numbers, so the consumer binding
    the data checks it, and refuses the data where it does not hold.
    """

    _label: ClassVar[str] = 'an assumption declaration'

    #: The predicate, in the where grammar. It holds at every coordinate of
    #: its own frame that ``where`` admits.
    holds: str
    #: Which coordinates it is checked at, in the same grammar; absent means every one.
    where: str | None = None
    #: Why the rule is there, in the author's words. The sentence a consumer
    #: refuses with quotes it.
    description: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _from_string(cls, data: object) -> object:
        return {'holds': data} if isinstance(data, str) else data

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, object]:
        """The published schema admits the bare string the one-line form is written as."""
        return _also_written_as(core_schema, handler, {'type': 'string'})

    @model_serializer
    def _as_written(self) -> str | dict[str, object]:
        if self.where is None and self.description is None:
            return self.holds
        written: dict[str, object] = {'holds': self.holds}
        if self.where is not None:
            written['where'] = self.where
        if self.description is not None:
            written['description'] = self.description
        return written


class PiecewiseLink(_StrictBlock):
    """One link of a piecewise block: an expression pinned to a values curve.

    Written in YAML as ``[expression, values]`` or ``[expression, values,
    sign]`` and serialised back to exactly that form, so a round trip through
    :meth:`Spec.to_yaml` reproduces the file.
    """

    _label: ClassVar[str] = 'a piecewise link'

    expression: str
    values: str
    sign: ComparisonOperator = '=='

    @model_validator(mode='before')
    @classmethod
    def _from_list(cls, data: object) -> object:
        if isinstance(data, list):
            if not 2 <= len(data) <= 3:
                msg = f'each link must be [expression, values] or [expression, values, sign], got {data!r}'
                raise ValueError(msg)
            return dict(zip(('expression', 'values', 'sign'), data, strict=False))
        return data

    @classmethod
    @override
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, object]:
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
    """

    _label: ClassVar[str] = 'a piecewise declaration'

    #: The breakpoint dimension.
    over: str
    links: list[PiecewiseLink]
    #: Which of :data:`PIECEWISE_METHODS` restricts the weights.
    method: PiecewiseMethod = 'adjacency'
    #: What the weights sum to — 1 where absent, or a binary that pins the formulation to 0 when it is 0.
    activity: str | None = None
    #: A boolean parameter saying how far each curve runs, for curves of unequal length.
    points: str | None = None
    description: str | None = None

    @property
    def nominated(self) -> str | None:
        """The block's own values parameter ``points:`` names, so the mask is derived from it — or ``None``."""
        return self.points if self.points in {link.values for link in self.links} else None

    @property
    def curve(self) -> tuple[PiecewiseLink, PiecewiseLink]:
        """The two links as ``(x, y)``, the bounded one last.

        Two-link blocks only.
        """
        x, y = self.links
        return (y, x) if x.sign != '==' else (x, y)

    @field_validator('method', mode='wrap')
    @classmethod
    def _check_method(cls, v: object, handler: ValidatorFunctionWrapHandler) -> PiecewiseMethod:
        try:
            return cast('PiecewiseMethod', handler(v))
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

    One set per coordinate of the variable's ``dims`` minus ``along``; the
    members are the variable's *existing* coordinates along ``along``, in that
    dimension's declared order.

    ``type: 1`` admits at most one nonzero member, ``type: 2`` at most two,
    and those two consecutive. A consumer with the concept takes the set as
    one; :meth:`Spec.expand` states it as binaries instead, and the rows it
    writes multiply by the member's own ``bounds``, which is why a member
    needs both.
    """

    _label: ClassVar[str] = 'a sos declaration'

    variable: str
    along: str
    type: SosType
    description: str | None = None

    @field_validator('type', mode='wrap')
    @classmethod
    def _check_type(cls, v: object, handler: ValidatorFunctionWrapHandler) -> SosType:
        orders = ' or '.join(str(t) for t in sorted(SOS_TYPES))
        msg = f'sos type must be {orders}, got {v!r}. A set of any other order is not a construct solvers carry.'
        if type(v) is not int:  # True == 1 == 1.0, and a set of order True is nothing
            raise ValueError(msg)
        try:
            return cast('SosType', handler(v))
        except ValidationError:
            raise ValueError(msg) from None


#: The language surfaces this reader understands. A **language** version, not a
#: package one: it moves when the accepted YAML surface moves, which most
#: releases do not, so deriving it from the package version would be automatic
#: and wrong. `0` is the unstable surface — no compatibility promise, per
#: *breaking changes are free* in CONTRIBUTING.
SUPPORTED_VERSIONS: tuple[int, ...] = (0,)


def _without_absence(value: object) -> object:
    """*value* with every absent entry stripped, recursively — see :meth:`Spec._drop_absence`."""
    if not isinstance(value, dict):
        return value
    kept = {}
    for key, before in value.items():
        after = _without_absence(before)
        if not _is_absent(after) and after != {}:
            kept[key] = after
    return kept


def _is_absent(value: object) -> bool:
    """Whether *value* is a null or an infinite bound."""
    if value is None:
        return True
    return isinstance(value, float) and math.isinf(value)


class Spec(_StrictBlock):
    """The declared math — one YAML file, or one dict, validated. Nothing here has seen data.

    A ``Spec`` that exists has passed the whole language: constructing one by
    any route — ``to_spec``, :meth:`model_validate`, the constructor — runs
    every load-time check, expression pass included, and raises
    :class:`~math_spec.errors.LanguageError` on a model the language refuses.
    Holding one is the proof, so nothing downstream checks it again.

    The API is the twelve declaration sections plus ``version`` and
    ``description``, three ways back out — :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads, :meth:`expand` for the
    same math with its formulations written out — and :attr:`program`, the
    model typed, which every reader after load walks. Everything else on this
    class is pydantic's, not a contract this package keeps.
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: Which language surface this file is written against. Absent means 0, so
    #: the field is additive. **0 means unstable** — the surface may change in
    #: any release — and declaring it is what lets a later reader refuse a file
    #: it cannot read rather than misinterpret it.
    version: int = 0
    #: What the file as a whole is, in the same plain prose a declaration's
    #: ``description:`` takes. The typeset document opens with it.
    description: str | None = None
    dimensions: dict[str, DimensionBlock] = {}
    relations: dict[str, RelationBlock] = {}
    parameters: dict[str, ParameterBlock] = {}
    variables: dict[str, VariableBlock] = {}
    constraints: dict[str, ConstraintBlock] = {}
    objective: ObjectiveBlock | None = None
    expressions: dict[str, ExpressionBlock] = {}
    macros: dict[str, MacroBlock] = {}
    piecewise: dict[str, PiecewiseBlock] = {}
    sos: dict[str, SosBlock] = {}
    assumptions: dict[str, AssumptionBlock] = {}
    #: What this file reads and does not build (:class:`GivenBlock`): columns
    #: under ``variables:``, row families under ``constraints:``. Empty in a
    #: file that stands alone.
    given: GivenBlock = GivenBlock()

    @cached_property
    def program(self) -> Program:
        """This model typed, section for section — what every reader after load walks.

        Computing it *is* the expression pass, so a model the language refuses
        raises here; loading forces it, so every ask on a model in hand is the
        one object. It mirrors the model: a ``piecewise:`` block still in it is
        a curve under ``program.piecewise`` and a ``sos:`` block a set under
        ``program.sos``, and :meth:`expand` is what writes either out as rows,
        so a consumer building rows reads ``spec.expand(...).program`` and
        refuses a block it does not take.
        """
        from math_spec.lowering import lower

        return lower(self)

    @classmethod
    @override
    def model_validate(
        cls,
        obj: object,
        *,
        strict: bool | None = None,
        extra: ExtraValues | None = None,
        from_attributes: bool | None = None,
        context: object = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate a mapping, raising this package's exception tree rather than pydantic's.

        ``__init__`` is not wrapped the same way, because defining one makes
        pydantic run every after-validator twice.
        """
        try:
            return super().model_validate(
                obj,
                strict=strict,
                extra=extra,
                from_attributes=from_attributes,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
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
    def _drop_absence(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Absence is not serialised: a null, an infinite bound, a mapping that stripping emptied, a section declaring nothing.

        An empty list stays, being a value rather than an absence (``dims:
        []`` is a scalar). On the serializer so that ``model_dump``,
        :meth:`to_dict` and :meth:`to_yaml` agree.
        """
        return cast('dict[str, object]', _without_absence(handler(self)))

    def to_dict(self) -> dict[str, object]:
        """The model as plain data. ``to_spec(m.to_dict())`` reproduces it."""
        return self.model_dump()

    def to_yaml(self) -> str:
        """The file a reviewer reads — including for a model that never had one."""
        import yaml

        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    def expand(self, *kinds: Formulation) -> Spec:
        """This model with its formulations written out as plain variables and constraints.

        A formulation states rows rather than being one — ``piecewise:`` states
        a curve, ``sos:`` states which members of a family may be nonzero — and
        expanding one writes those rows under names prefixed with the block's
        own, then drops the block. The math is the same afterwards, and so is
        the data that binds it: neither a set nor a curve emits a parameter,
        and a curve's rows sit on ``where`` predicates over the file's own.

        Args:
            kinds: Which formulations to write out — ``'piecewise'``,
                ``'sos'``, or none of them for every one. They go in
                :data:`FORMULATIONS` order whatever order they are asked in,
                because a ``method: sos2`` curve emits a set and no set emits a
                curve.

        Returns:
            The model those blocks wrote out, or this one where it declares
            none of them. It is a model like any other: :meth:`to_yaml` writes
            it, and the file binds the same data as the one it came from.

        Raises:
            ValueError: *kinds* names something that is not a formulation.
        """
        wanted = _formulations(kinds)
        from math_spec.piecewise import expand_piecewise
        from math_spec.sos import expand_sets

        expanded = expand_piecewise(self) if 'piecewise' in wanted else self
        if 'sos' in wanted and expanded.sos:
            expanded = expand_sets(expanded)
        return expanded

    @model_validator(mode='after')
    def _names_are_names(self) -> Spec:
        """Every declaration is keyed by something an expression could write.

        Read off the model's own mappings rather than a list of sections, so a
        section added later cannot be forgotten here — every mapping a Spec
        carries is keyed by a declaration name. ``given:`` nests its two
        mappings one level down, so they are read off :class:`GivenBlock` the
        same way.
        """
        sections = [*self, *((f'given: {kind}', group) for kind, group in self.given)]
        errors = [
            f'{section}: {name!r} is not a name. A declaration is named the way an expression '
            f'writes it — a letter or an underscore, then letters, digits or underscores — so '
            f'nothing can refer to this one. Rename it.'
            for section, value in sections
            if isinstance(value, dict)
            for name in value
            if not re.fullmatch(NAME, name)
        ]
        if errors:
            raise ValueError('\n'.join(errors))

        return self

    @model_validator(mode='after')
    def _lower(self) -> Spec:
        """Every rule that reads across declarations, then every expression and where string.

        A fault in a curve's link is named against the link the file wrote. The
        rows a curve states are held to the language when :meth:`expand`
        writes them out, since an expansion is a model like any other.
        """
        _ = self.program
        return self


def _formulations(asked: tuple[str, ...]) -> tuple[Formulation, ...]:
    """What *asked* names, in :data:`FORMULATIONS` order — all of them where it names none.

    Raises:
        ValueError: A name that is not a formulation.
    """
    if unknown := [kind for kind in asked if kind not in FORMULATIONS]:
        spelled = ' and '.join(repr(kind) for kind in FORMULATIONS)
        msg = f'{unknown[0]!r} is not a formulation. Expand {spelled}, or pass none of them for every one.'
        raise ValueError(msg)
    return tuple(kind for kind in FORMULATIONS if not asked or kind in asked)
