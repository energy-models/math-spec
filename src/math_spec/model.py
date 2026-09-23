# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The YAML surface's types — every block a file may contain, rooted at :class:`Spec`.

Nothing here has seen data.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self, cast, get_args, override

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from math_spec._expression_parser import NAME, ComparisonOperator
from math_spec.errors import did_you_mean, schema_error
from math_spec.operators import BUILTIN_NAMES
from math_spec.sos import Emitted, coefficients

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from pydantic import GetJsonSchemaHandler, SerializerFunctionWrapHandler
    from pydantic.config import ExtraValues
    from pydantic_core import CoreSchema

    from math_spec.resolution import Resolved


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


#: The dtype a dimension index may declare (the declaration rules), and what
#: its labels are. ``datetime`` is a dimension's alone — labels on a timeline
#: order and compare, where a *value* of that type is a moment nothing
#: computes with.
DimensionDtype = Literal['float', 'int', 'str', 'datetime']

#: The dtype a parameter may declare (the declaration rules), and what its bound
#: column must be. ``bool`` is a parameter's alone — a value column may be a
#: flag a mask reads, where a label set of two members is a dimension nothing
#: indexes by.
ParameterDtype = Literal['float', 'int', 'bool', 'str']

#: What a *name* a where comparison tests may be — a parameter's dtype or a
#: dimension's, since a relation's is its target's. The union rather than either
#: half, because a mask names all three kinds and reads the dtype the same way.
DeclaredDtype = ParameterDtype | DimensionDtype

#: The domain a variable may declare.
VariableDomain = Literal['continuous', 'integer', 'binary']

#: What a masked variable's non-existence *means* where it does not exist.
#: ``undefined`` is the absence rules' default — a term carrying it takes its
#: row. ``zero`` says the quantity *is* zero there, so the term contributes
#: nothing and the row stands.
VariableAbsence = Literal['undefined', 'zero']

#: Which way an objective is optimised (the declaration rules).
ObjectiveSense = Literal['minimize', 'maximize']

#: The order of special ordered set.
SosType = Literal[1, 2]

#: How a ``piecewise:`` block restricts its interpolation weights. Kept in step
#: with :data:`PIECEWISE_METHODS`, which says what each one emits, by
#: ``tests/test_schema.py``.
PiecewiseMethod = Literal['adjacency', 'sos2', 'convex', 'lp']

#: A block that states rows rather than being one, which :meth:`Spec.expand`
#: writes out on request.
Formulation = Literal['piecewise', 'sos']

#: The shape a method needs a curve to have to be exact on it, which the
#: ``<block>_curvature`` assumption states. ``convex`` and ``concave`` name the
#: side a bounded link binds from; ``either`` is the weaker condition a block
#: with both links pinned states — any single bend will do, and only a *mixed*
#: curve fails it.
Curvature = Literal['convex', 'concave', 'either']

#: The set form of each vocabulary above, for callers that want membership.
DIMENSION_DTYPES = frozenset(get_args(DimensionDtype))
PARAMETER_DTYPES = frozenset(get_args(ParameterDtype))
#: The parameter dtypes that stand where a number belongs — a coefficient, a
#: term, a divisor, a bound. A label selects and a flag masks; neither is one.
NUMERIC_DTYPES: frozenset[ParameterDtype] = frozenset({'float', 'int'})
VARIABLE_DOMAINS = frozenset(get_args(VariableDomain))
VARIABLE_ABSENCE = frozenset(get_args(VariableAbsence))
CURVATURES = frozenset(get_args(Curvature))

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


def _side(written: str | list[str] | dict[str, str] | None) -> tuple[tuple[str, str], ...]:
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
        return (*_side(self.key), *_side(self.values))

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(role for role, _ in self.pairs)

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(dim for _, dim in self.pairs)

    @property
    def key_roles(self) -> tuple[str, ...]:
        """The key roles, however ``key:`` was written."""
        return tuple(role for role, _ in _side(self.key))

    @property
    def value_roles(self) -> tuple[str, ...]:
        """The roles the key determines; empty for a bare relation."""
        return tuple(role for role, _ in _side(self.values))


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


def undeclared_dimension(kind: str, name: str, dimension: str) -> str:
    """The one wording for a declaration naming a dimension the file does not declare."""
    return f"{kind} '{name}' references undeclared dimension '{dimension}'. Declare it under 'dimensions:'."


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
    every load-time check, expansion and expression pass included, and raises
    :class:`~math_spec.errors.LanguageError` on a model the language refuses.
    Holding one is the proof, so nothing downstream checks it again.

    The API is the eleven declaration sections plus ``version`` and
    ``description``, three ways back out — :meth:`to_dict` for the model as
    data, :meth:`to_yaml` for the file a reviewer reads, :meth:`expand` for the
    same math with its formulations written out — and :attr:`resolved`, the
    typed trees every reader in this package walks. Everything else on this
    class is pydantic's, not a contract this package keeps.
    """

    _label: ClassVar[str] = 'the top level of the file'

    #: What :meth:`expand` returned for each set of formulations asked for, so
    #: a second ask is the same object rather than a second expansion. A model
    #: that expands to itself is not stored: two of them compare by their
    #: private state, which a model holding itself cannot answer.
    _expansions: dict[tuple[Formulation, ...], Spec] = PrivateAttr(default_factory=dict)
    #: Each ``piecewise:`` block of the model this one expanded, as written,
    #: which is what a program keeps of a curve. Empty on a model that is not
    #: an expansion. Written by :func:`~math_spec.piecewise.expand_piecewise`.
    _expanded_piecewise: dict[str, PiecewiseBlock] = PrivateAttr(default_factory=dict)

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

    def relations_of(self, dimension: str) -> dict[str, RelationBlock]:
        """The relations with a column over *dimension*, by name."""
        return {n: lk for n, lk in self.relations.items() if dimension in lk.dims}

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
        if (found := self._expansions.get(wanted)) is not None:
            return found
        from math_spec.piecewise import expand_piecewise
        from math_spec.sos import expand_sets

        if wanted == ('piecewise',):
            expanded = expand_piecewise(self)
        else:
            expanded = self.expand('piecewise') if 'piecewise' in wanted else self
            if expanded.sos:
                expanded = expand_sets(expanded)
        if expanded is not self:
            self._expansions[wanted] = expanded
        return expanded

    @cached_property
    def resolved(self) -> Resolved:
        """Every expression and where string this model declares, typed once — what every reader after validation walks.

        Computing it *is* the expression pass, so a model the language refuses
        raises here; loading forces it, so a spec in hand already holds it. It
        holds what *this* model declares: the rows a formulation states are on
        :meth:`expand`'s result instead.
        """
        from math_spec.validation import validate_expressions

        return validate_expressions(self)

    @model_validator(mode='after')
    def _names_are_names(self) -> Spec:
        """Every declaration is keyed by something an expression could write.

        Read off the model's own mappings rather than a list of sections, so a
        section added later cannot be forgotten here — every mapping a Spec
        carries is keyed by a declaration name.
        """
        errors = [
            f'{section}: {name!r} is not a name. A declaration is named the way an expression '
            f'writes it — a letter or an underscore, then letters, digits or underscores — so '
            f'nothing can refer to this one. Rename it.'
            for section, value in self
            if isinstance(value, dict)
            for name in value
            if not re.fullmatch(NAME, name)
        ]
        if errors:
            raise ValueError('\n'.join(errors))

        return self

    @model_validator(mode='after')
    def _validate_references(self) -> Spec:
        """Every cross-declaration rule the schema can decide without data, collected rather than raised on the first."""
        errors = [
            *self._name_collisions(),
            *self._frame_dimensions(),
            *self._relation_targets(),
            *self._bound_names(),
            *self._sos_shapes(),
            *self._sos_bounds(),
            *self._sos_emitted_names(),
            *self._piecewise_references(),
            *self._piecewise_emitted_names(),
        ]
        if errors:
            raise ValueError('\n'.join(errors))
        return self

    def _name_collisions(self) -> Iterator[str]:
        """A name is declared once, and never as a built-in operator."""
        kinds: list[tuple[str, Iterable[str]]] = [
            ('dimension', self.dimensions),
            ('relation', self.relations),
            ('parameter', self.parameters),
            ('variable', self.variables),
            ('named expression', self.expressions),
            ('macro', self.macros),
        ]
        seen: dict[str, str] = {}
        for kind, group in kinds:
            for name in group:
                if name in BUILTIN_NAMES:
                    yield (
                        f"{kind.capitalize()} '{name}' collides with the built-in operator "
                        f"'{name}'. The operator set is closed and its names are reserved; "
                        f'rename the {kind}.'
                    )
                if name in seen:
                    yield (
                        f"{kind.capitalize()} '{name}' collides with the {seen[name]} of "
                        f'the same name. Names share one flat namespace — rename one of them.'
                    )
                else:
                    seen[name] = kind

    def _frame_dimensions(self) -> Iterator[str]:
        """Every frame is a product of distinct, declared dimensions."""
        frames = [
            *(('Parameter', name, p.dims) for name, p in self.parameters.items()),
            *(('Variable', name, v.dims) for name, v in self.variables.items()),
            *(('Constraint', name, c.dims) for name, c in self.constraints.items()),
            *(('Named expression', name, e.dims or []) for name, e in self.expressions.items()),
        ]
        for kind, name, dims in frames:
            yield from (undeclared_dimension(kind, name, d) for d in dims if d not in self.dimensions)
            yield from (
                f"{kind} '{name}' names dimension '{d}' twice. A frame is a product of distinct dimensions."
                for d, count in Counter(dims).items()
                if count > 1
            )

    def _relation_targets(self) -> Iterator[str]:
        """A relation has at least two columns over declared dimensions, each named once, and a key naming some of them."""
        for lname, lk in self.relations.items():
            if len(lk.pairs) < 2:
                yield (
                    f"Relation '{lname}' has {len(lk.pairs)} column(s). A relation relates dimensions, so 'key:' and "
                    f"'values:' name at least two between them — a label on one dimension is a parameter over it."
                )
            if not lk.key_roles:
                yield (
                    f"Relation '{lname}' names no key column. A relation is keyed by the columns a row is identified "
                    f"by — name them under 'key:', and leave the columns they determine to 'values:'."
                )
            for side, written in (('key', lk.key), ('values', lk.values)):
                yield from (
                    f"Relation '{lname}' names dimension '{d}' twice under '{side}:'. Give the two columns roles: "
                    f'{side}: {{{d}0: {d}, {d}1: {d}}}.'
                    for d, count in Counter(dim for _, dim in _side(written)).items()
                    if count > 1 and not isinstance(written, dict)
                )
            yield from (
                f"Relation '{lname}' names column '{role}' under both 'key:' and 'values:'. A relation names each "
                f'column once — name the value column after what it holds: values: {{<name>: {dict(lk.pairs)[role]}}}.'
                for role in dict.fromkeys(lk.key_roles)
                if role in lk.value_roles
            )
            yield from (
                undeclared_dimension('Relation', lname, d) for d in dict.fromkeys(lk.dims) if d not in self.dimensions
            )
            yield from (
                f"Relation '{lname}' names column '{role}' after dimension '{role}', but the column is over "
                f"'{dim}'. A column named like a dimension is read as over it — name it after what it holds."
                for role, dim in lk.pairs
                if role in self.dimensions and role != dim
            )
            if lk.value_roles:
                yield from (
                    f"Relation '{lname}' has two key columns over '{d}' "
                    f'({[k for k in lk.key_roles if dict(lk.pairs)[k] == d]}). A key that determines a value is read '
                    f'its dimensions, and no frame carries a dimension twice — key the table by one column over '
                    f'each, or leave one of them a value column.'
                    for d, count in Counter(dict(lk.pairs)[k] for k in lk.key_roles).items()
                    if count > 1
                )

    def _bound_names(self) -> Iterator[str]:
        """A named bound is a numeric parameter."""
        for vname, vdef in self.variables.items():
            for side in ('lower', 'upper'):
                val = getattr(vdef.bounds, side)
                if not isinstance(val, str):
                    continue
                if val in self.parameters:
                    dtype = self.parameters[val].dtype
                    if dtype not in NUMERIC_DTYPES:
                        yield (
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
                yield (f"Variable '{vname}' bounds.{side}: {detail}.")

    def _sos_shapes(self) -> Iterator[str]:
        """A set runs along one dim of one declared variable, and a variable carries one set."""
        claimed: dict[str, str] = {}
        for sname, block in self.sos.items():
            context = f"Sos '{sname}'"
            if block.along not in self.dimensions:
                yield (undeclared_dimension('Sos', sname, block.along))
            elif block.variable not in self.variables:
                yield (
                    f"{context}: '{block.variable}' is not a declared variable.\n"
                    f'  Variables: {sorted(self.variables)}\n'
                    f'A set is over one variable, so a parameter or an expression cannot carry one.'
                )
            elif block.along not in self.variables[block.variable].dims:
                yield (
                    f"{context}: along '{block.along}' is not a dim of variable "
                    f"'{block.variable}' (dims {self.variables[block.variable].dims}). The set runs "
                    f"along one of the variable's own dims — one set per coordinate of the rest."
                )
            elif block.variable in claimed:
                yield (
                    f"{context}: variable '{block.variable}' already carries the set declared by "
                    f"'{claimed[block.variable]}'. A variable holds one set — declare a second "
                    f'variable, or state the other restriction as a constraint.'
                )
            else:
                claimed[block.variable] = sname

    def _sos_bounds(self) -> Iterator[str]:
        """A set states what the binaries it expands to state: each side of a member carries a coefficient.

        The rewrite holds an unpicked member at zero from both sides, so a side
        the model leaves open leaves the member free of it. Either coefficient
        may be a parameter, because a row multiplies by it rather than reading
        it. Decided here rather than where the rewrite runs, so a set the
        language cannot state twice is refused before any data exists.
        """
        for sname, block in self.sos.items():
            if (member := self.variables.get(block.variable)) is None:
                continue
            context = f"Sos '{sname}'"
            below, above = coefficients(member.domain, member.bounds.lower, member.bounds.upper)
            if below is None:
                yield (
                    f"{context}: variable '{block.variable}' has no lower bound, and the set expands to rows "
                    f'that hold an unpicked member at zero from below as well as above. Declare bounds.lower, '
                    f'as a number or a parameter.'
                )
            if above is None:
                yield (
                    f"{context}: variable '{block.variable}' has no upper bound, and the set expands to rows "
                    f'that hold an unpicked member at zero from above as well as below. Declare bounds.upper, '
                    f'as a number or a parameter.'
                )

    def _sos_emitted_names(self) -> Iterator[str]:
        """No name a set's expansion writes is one the file already declares."""
        for sname, block in self.sos.items():
            yield from self._collisions(f"Sos '{sname}'", Emitted.of(sname, block.type).by_kind)

    def _piecewise_references(self) -> Iterator[str]:
        """A curve runs along a declared dimension through numeric values parameters carrying it, gated by a binary, masked by a bool."""
        for name, pw in self.piecewise.items():
            context = f"piecewise '{name}'"
            if pw.over not in self.dimensions:
                yield undeclared_dimension('piecewise', name, pw.over)
                continue
            for i, link in enumerate(pw.links):
                if link.values not in self.parameters:
                    yield f"{context}: link {i} values references undeclared parameter '{link.values}'"
                elif (dtype := self.parameters[link.values].dtype) not in NUMERIC_DTYPES:
                    yield (
                        f"{context}: link {i} values parameter '{link.values}' is declared dtype: {dtype}, and a "
                        f'breakpoint is a number. Declare it dtype: float or int.'
                    )
                elif pw.over not in self.parameters[link.values].dims:
                    yield (
                        f"{context}: link {i} values parameter '{link.values}' must carry dim "
                        f"'{pw.over}' (has {self.parameters[link.values].dims})"
                    )
            if (activity := pw.activity) is not None:
                if activity not in self.variables:
                    yield (
                        f"{context}: activity '{activity}' is not a declared variable. A gate is a binary variable; "
                        f'declare it, or drop activity: for weights that sum to 1.'
                    )
                elif self.variables[activity].domain != 'binary':
                    yield f"{context}: activity variable '{activity}' must be binary"
            if (points := pw.points) is None or pw.nominated is not None:
                continue
            if points not in self.parameters:
                yield f"{context}: points references undeclared parameter '{points}'"
            elif (dtype := self.parameters[points].dtype) != 'bool':
                yield (
                    f"{context}: points parameter '{points}' is {dtype}, and a mask is a bool parameter — one "
                    f'saying, per breakpoint, whether the curve reaches it. Declare it dtype: bool.'
                )
            elif pw.over not in self.parameters[points].dims:
                yield (
                    f"{context}: points parameter '{points}' must carry dim '{pw.over}' — "
                    f'it says how far each curve runs along it (has {self.parameters[points].dims})'
                )

    def _piecewise_emitted_names(self) -> Iterator[str]:
        """No name a curve's expansion writes is one the file already declares."""
        from math_spec.piecewise import Emitted as EmittedCurve

        for name, pw in self.piecewise.items():
            yield from self._collisions(f"piecewise '{name}'", EmittedCurve.of(name, pw).by_kind)

    def _collisions(self, context: str, by_kind: Iterable[tuple[str, Iterable[str]]]) -> Iterator[str]:
        """The refusal for each name *context*'s expansion writes that the file already declares, by kind."""
        declared: dict[str, Iterable[str]] = {
            'variable': self.variables,
            'constraint': self.constraints,
            'sos': self.sos,
            'assumption': self.assumptions,
        }
        for kind, names in by_kind:
            yield from (
                f"{context}: its expansion writes {kind} '{one}', which this file already declares. Rename one of them."
                for one in names
                if one in declared[kind]
            )

    @model_validator(mode='after')
    def _validate_expressions(self) -> Spec:
        """Every expression and where string — this file's own, and every one a curve emits.

        This file's own first, so a fault in a link is named against the link
        the file wrote, and the expansion reads the typed links rather than the
        text again. A curve's expansion is a model in its own right, so
        validating it is what holds the declarations it writes to the language.
        """
        _ = self.resolved
        self.expand('piecewise')
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
