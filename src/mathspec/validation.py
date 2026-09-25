# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The front door, and the rules a declaration is held to against the others before any expression is read.

:func:`to_spec` reads a model definition into a :class:`~mathspec.model.Spec`.
:func:`reference_errors` holds the rules one declaration is held to against
the others — a name declared once, a frame over declared dimensions, a bound
naming a numeric parameter, a set over one dim of one variable, a curve
through parameters carrying its breakpoints — which lowering runs before it
reads any expression, since resolution assumes every one of them.
:func:`emitted_name_errors` is read off the program instead: what a block's
expansion writes is decided by the block as lowered. The rules that need a
typed expression stay with the expressions in :func:`~mathspec.lowering.lower`:
a macro formal against a dimension, a curve's links, and every dim rule.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import TYPE_CHECKING

from mathspec._yaml import read_model
from mathspec.errors import SchemaError
from mathspec.model import NUMERIC_DTYPES, Spec, side_columns
from mathspec.operators import BUILTIN_NAMES
from mathspec.piecewise import Emitted as EmittedCurve
from mathspec.sos import Emitted as EmittedSet
from mathspec.sos import coefficients

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from mathspec.program import Program


def to_spec(model: str | Path | Mapping[str, object] | Spec) -> Spec:
    """Load and validate a model definition — the language's front door.

    Everything decidable without data is decided here: schema shape, every
    rule one declaration is held to against the others, every expression and
    where string, and every macro template.

    Args:
        model: A YAML path — a :class:`~pathlib.Path`, or a ``str`` with no
            newline in it — the YAML text itself as a ``str`` with one, a
            mapping, or a loaded :class:`Spec`.

    Returns:
        The schema *as the file declares it*, ``piecewise:`` intact.

    Raises:
        LanguageError: Anything the language does not accept, a text that is
            not a mapping of sections included.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    if isinstance(model, (list, tuple)):
        msg = 'a model is one file, one dict or one Spec, never a list of them; merge the declarations into one dict.'
        raise SchemaError(msg)
    if isinstance(model, Spec):
        return model
    return Spec.model_validate(model if isinstance(model, Mapping) else read_model(model))


def emitted_name_errors(schema: Spec, program: Program) -> list[str]:
    """Every name a set or curve of *program* would write out that *schema* already declares.

    Read off the program rather than the file, since what a curve writes is
    decided by the curve as lowered — its links, its method, its mask.
    """
    by_block = [
        *((f"Sos '{name}'", EmittedSet.of(name, block.sos_type).by_kind) for name, block in program.sos.items()),
        *((f"piecewise '{name}'", EmittedCurve.of(name, curve).by_kind) for name, curve in program.piecewise.items()),
    ]
    return [error for context, by_kind in by_block for error in _collisions(schema, context, by_kind)]


def reference_errors(schema: Spec) -> list[str]:
    """Every cross-declaration rule *schema* breaks, collected rather than raised on the first."""
    return [
        *_name_collisions(schema),
        *_frame_dimensions(schema),
        *_relation_targets(schema),
        *_bound_names(schema),
        *_sos_shapes(schema),
        *_sos_bounds(schema),
        *_piecewise_references(schema),
    ]


def undeclared_dimension(kind: str, name: str, dimension: str) -> str:
    """The one wording for a declaration naming a dimension the file does not declare."""
    return f"{kind} '{name}' references undeclared dimension '{dimension}'. Declare it under 'dimensions:'."


def _flat_namespace(schema: Spec) -> list[tuple[str, Iterable[str]]]:
    """Each kind of declaration whose names share the one namespace an expression reads, in declaration order."""
    return [
        ('dimension', schema.dimensions),
        ('relation', schema.relations),
        ('parameter', schema.parameters),
        ('variable', schema.variables),
        ('named expression', schema.expressions),
        ('macro', schema.macros),
    ]


def _name_collisions(schema: Spec) -> Iterator[str]:
    """A name is declared once, and never as a built-in operator."""
    seen: dict[str, str] = {}
    for kind, group in _flat_namespace(schema):
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


def _frame_dimensions(schema: Spec) -> Iterator[str]:
    """Every frame is a product of distinct, declared dimensions."""
    frames = [
        *(('Parameter', name, p.dims) for name, p in schema.parameters.items()),
        *(('Variable', name, v.dims) for name, v in schema.variables.items()),
        *(('Constraint', name, c.dims) for name, c in schema.constraints.items()),
        *(('Named expression', name, e.dims or []) for name, e in schema.expressions.items()),
    ]
    for kind, name, dims in frames:
        yield from (undeclared_dimension(kind, name, d) for d in dims if d not in schema.dimensions)
        yield from (
            f"{kind} '{name}' names dimension '{d}' twice. A frame is a product of distinct dimensions."
            for d, count in Counter(dims).items()
            if count > 1
        )


def _relation_targets(schema: Spec) -> Iterator[str]:
    """A relation has at least two columns over declared dimensions, each named once, and a key naming some of them."""
    for lname, lk in schema.relations.items():
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
                for d, count in Counter(dim for _, dim in side_columns(written)).items()
                if count > 1 and not isinstance(written, dict)
            )
        yield from (
            f"Relation '{lname}' names column '{role}' under both 'key:' and 'values:'. A relation names each "
            f'column once — name the value column after what it holds: values: {{<name>: {dict(lk.pairs)[role]}}}.'
            for role in dict.fromkeys(lk.key_roles)
            if role in lk.value_roles
        )
        yield from (
            undeclared_dimension('Relation', lname, d) for d in dict.fromkeys(lk.dims) if d not in schema.dimensions
        )
        yield from (
            f"Relation '{lname}' names column '{role}' after dimension '{role}', but the column is over "
            f"'{dim}'. A column named like a dimension is read as over it — name it after what it holds."
            for role, dim in lk.pairs
            if role in schema.dimensions and role != dim
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


def _bound_names(schema: Spec) -> Iterator[str]:
    """A named bound is a numeric parameter."""
    for vname, vdef in schema.variables.items():
        for side in ('lower', 'upper'):
            val = getattr(vdef.bounds, side)
            if not isinstance(val, str):
                continue
            if val in schema.parameters:
                dtype = schema.parameters[val].dtype
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


def _sos_shapes(schema: Spec) -> Iterator[str]:
    """A set runs along one dim of one declared variable, and a variable carries one set."""
    claimed: dict[str, str] = {}
    for sname, block in schema.sos.items():
        context = f"Sos '{sname}'"
        if block.along not in schema.dimensions:
            yield (undeclared_dimension('Sos', sname, block.along))
        elif block.variable not in schema.variables:
            yield (
                f"{context}: '{block.variable}' is not a declared variable.\n"
                f'  Variables: {sorted(schema.variables)}\n'
                f'A set is over one variable, so a parameter or an expression cannot carry one.'
            )
        elif block.along not in schema.variables[block.variable].dims:
            yield (
                f"{context}: along '{block.along}' is not a dim of variable "
                f"'{block.variable}' (dims {schema.variables[block.variable].dims}). The set runs "
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


def _sos_bounds(schema: Spec) -> Iterator[str]:
    """A set states what the binaries it expands to state: each side of a member carries a coefficient.

    The rewrite holds an unpicked member at zero from both sides, so a side
    the model leaves open leaves the member free of it. Either coefficient
    may be a parameter, because a row multiplies by it rather than reading
    it. Decided here rather than where the rewrite runs, so a set the
    language cannot state twice is refused before any data exists.
    """
    for sname, block in schema.sos.items():
        if (member := schema.variables.get(block.variable)) is None:
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


def _piecewise_references(schema: Spec) -> Iterator[str]:
    """A curve runs along a declared dimension through numeric values parameters carrying it, gated by a binary, masked by a bool."""
    for name, pw in schema.piecewise.items():
        context = f"piecewise '{name}'"
        if pw.over not in schema.dimensions:
            yield undeclared_dimension('piecewise', name, pw.over)
            continue
        for i, link in enumerate(pw.links):
            if link.values not in schema.parameters:
                yield f"{context}: link {i} values references undeclared parameter '{link.values}'"
            elif (dtype := schema.parameters[link.values].dtype) not in NUMERIC_DTYPES:
                yield (
                    f"{context}: link {i} values parameter '{link.values}' is declared dtype: {dtype}, and a "
                    f'breakpoint is a number. Declare it dtype: float or int.'
                )
            elif pw.over not in schema.parameters[link.values].dims:
                yield (
                    f"{context}: link {i} values parameter '{link.values}' must carry dim "
                    f"'{pw.over}' (has {schema.parameters[link.values].dims})"
                )
        if (activity := pw.activity) is not None:
            if activity not in schema.variables:
                yield (
                    f"{context}: activity '{activity}' is not a declared variable. A gate is a binary variable; "
                    f'declare it, or drop activity: for weights that sum to 1.'
                )
            elif schema.variables[activity].domain != 'binary':
                yield f"{context}: activity variable '{activity}' must be binary"
        if (points := pw.points) is None or pw.nominated is not None:
            continue
        if points not in schema.parameters:
            yield f"{context}: points references undeclared parameter '{points}'"
        elif (dtype := schema.parameters[points].dtype) != 'bool':
            yield (
                f"{context}: points parameter '{points}' is {dtype}, and a mask is a bool parameter — one "
                f'saying, per breakpoint, whether the curve reaches it. Declare it dtype: bool.'
            )
        elif pw.over not in schema.parameters[points].dims:
            yield (
                f"{context}: points parameter '{points}' must carry dim '{pw.over}' — "
                f'it says how far each curve runs along it (has {schema.parameters[points].dims})'
            )


def _collisions(schema: Spec, context: str, by_kind: Iterable[tuple[str, Iterable[str]]]) -> Iterator[str]:
    """The refusal for each name *context*'s expansion writes that the file already declares, by kind.

    An emitted variable joins the flat namespace, so any declaration there
    takes its name; a constraint, a set and an assumption each have their own.
    """
    sections = {'named expression': 'expressions', 'sos': 'sos'}
    declared: dict[str, dict[str, str]] = {
        'variable': {name: kind for kind, group in _flat_namespace(schema) for name in group},
        'constraint': dict.fromkeys(schema.constraints, 'constraint'),
        'sos': dict.fromkeys(schema.sos, 'sos'),
        'assumption': dict.fromkeys(schema.assumptions, 'assumption'),
    }
    for kind, names in by_kind:
        yield from (
            f"{context}: its expansion writes {kind} '{one}', which this file already declares under "
            f"'{sections.get(declared[kind][one], declared[kind][one] + 's')}:'. Rename one of them."
            for one in names
            if one in declared[kind]
        )
