# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The front door, and the rules a declaration is held to against the others before any expression is read.

:func:`to_spec` reads a model definition into a :class:`~math_spec.model.Spec`.
:func:`reference_errors` holds the rules one declaration is held to against
the others — a name declared once, a frame over declared dimensions, a bound
naming a numeric parameter, a set over one dim of one variable, a curve
through parameters carrying its breakpoints — which lowering runs before it
reads any expression, since resolution assumes every one of them.
:func:`emitted_name_errors` is read off the program instead: what a block's
expansion writes is decided by the block as lowered. The rules that need a
typed expression stay with the expressions in :func:`~math_spec.lowering.lower`:
a macro formal against a dimension, a curve's links, and every dim rule.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import TYPE_CHECKING

from math_spec._yaml import read_model
from math_spec.errors import SchemaError
from math_spec.model import NUMERIC_DTYPES, Spec, side_columns
from math_spec.operators import BUILTIN_NAMES
from math_spec.piecewise import Emitted as EmittedCurve
from math_spec.sos import Emitted as EmittedSet
from math_spec.sos import coefficients

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from math_spec.model import PiecewiseBlock, PiecewiseLink
    from math_spec.program import Program


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
    errors = [
        error
        for name, block in program.sos.items()
        for error in _collisions(schema, f"Sos '{name}'", EmittedSet.of(name, block.sos_type).by_kind)
    ]
    for name, curve in program.piecewise.items():
        written = EmittedCurve.of(name, curve)
        errors.extend(
            f"piecewise '{name}': link '{row.removeprefix(f'{name}_')}' names its row '{row}', which the block "
            f'already writes for itself. Rename the link.'
            for row in written.reused
        )
        errors.extend(_collisions(schema, f"piecewise '{name}'", written.by_kind))
    return errors


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
    """Every declaration a block names by key exists and has the shape the block needs.

    The breakpoint dim, the frame ``dims:`` states, each link's values
    parameter, the relation and columns a walk reads through, and the gate.
    What a link's expression and the where carry is resolution's to say, and
    whether the pieces fit together is decided as the block is lowered
    (:func:`math_spec.piecewise.declaration_of`).
    """
    for name, block in schema.piecewise.items():
        context = f"piecewise '{name}'"
        if block.along not in schema.dimensions:
            yield undeclared_dimension('piecewise', name, block.along)
            continue
        for d in block.dims:
            if d not in schema.dimensions:
                yield undeclared_dimension('piecewise', name, d)
            elif d == block.along:
                yield (
                    f"{context}: dims carries '{block.along}', the breakpoint dim. The frame is what the block "
                    f'builds one curve per, and every curve runs along the breakpoints — drop it from dims:.'
                )
        if len(set(block.dims)) != len(block.dims):
            yield f'{context}: dims repeats a dimension: {block.dims}'
        for key, link in block.links.items():
            yield from _piecewise_link_shape(schema, name, block, key, link)
        if (activity := block.activity) is None:
            continue
        if activity not in schema.variables:
            yield (
                f"{context}: activity '{activity}' is not a declared variable. A gate is a binary variable; "
                f'declare it, or drop activity: for weights that sum to 1.'
            )
        elif schema.variables[activity].domain != 'binary':
            yield f"{context}: activity variable '{activity}' must be binary"
        elif stray := [d for d in schema.variables[activity].dims if d not in block.dims]:
            yield (
                f"{context}: activity '{activity}' carries {stray}, which dims {block.dims} does not. The gate "
                f'switches the curve of one coordinate of dims:, and a gate varying along {stray} would need a '
                f'curve per coordinate of it — add {stray} to dims:, or gate with a variable over dims:.'
            )


def _piecewise_link_shape(
    schema: Spec, name: str, block: PiecewiseBlock, key: str, link: PiecewiseLink
) -> Iterator[str]:
    """One link's values parameter, and the relation its walk names, exist as the link needs them."""
    context = f"piecewise '{name}' link '{key}'"
    if link.values not in schema.parameters:
        yield f"{context}: values references undeclared parameter '{link.values}'"
    elif (dtype := schema.parameters[link.values].dtype) not in NUMERIC_DTYPES:
        yield (
            f"{context}: values parameter '{link.values}' is declared dtype: {dtype}, and a breakpoint is a "
            f'number. Declare it dtype: float or int.'
        )
    elif block.along not in schema.parameters[link.values].dims:
        yield (
            f"{context}: values parameter '{link.values}' must carry dim "
            f"'{block.along}' (has {schema.parameters[link.values].dims})"
        )
    if link.walks:
        yield from _piecewise_walk_shape(schema, context, block, link)


def _piecewise_walk_shape(schema: Spec, context: str, block: PiecewiseBlock, link: PiecewiseLink) -> Iterator[str]:
    """A walk's relation is declared, it consumes the block's own dims, and it produces dims of its own."""
    assert link.by is not None and link.over is not None and link.into is not None
    if link.by not in schema.relations:
        yield (
            f"{context}: by references undeclared relation '{link.by}'. A walked link reads the curve's "
            f'weights through a declared relation — declare it, or drop by, over and into.'
        )
        return
    roles = dict(schema.relations[link.by].pairs)
    sides: list[frozenset[str]] = []
    for side, written in (('over', link.over), ('into', link.into)):
        named = [written] if isinstance(written, str) else list(written)
        if stray := [c for c in named if c not in roles]:
            yield f"{context}: {side} names {stray}, which relation '{link.by}' has no column for (it has {sorted(roles)})"
            return
        if len(set(named)) != len(named):
            yield f'{context}: {side} repeats a column: {named}'
            return
        sides.append(frozenset(roles[c] for c in named))
    consumed, produced = sides
    if shared := sorted(consumed & produced):
        yield (
            f'{context}: over and into both reach {shared}, so the walk consumes and produces one dimension. '
            f'Name different columns on each side.'
        )
    elif missing := sorted(consumed - set(block.dims)):
        yield (
            f"{context}: over reaches {missing}, which the block's dims {block.dims} do not carry. A walk "
            f"consumes one of the curve's own dimensions — name a column over one of {block.dims}, or declare "
            f'it in dims:.'
        )
    elif framed := sorted(produced & set(block.dims)):
        yield (
            f"{context}: into reaches {framed}, which the block's dims {block.dims} already carry. The block "
            f"builds one curve per coordinate of dims:, so {framed} cannot also index this link's rows — drop "
            f'it from dims:, or walk into a dimension of its own.'
        )
    elif block.along in produced:
        yield (
            f"{context}: into reaches '{block.along}', the breakpoint dim. A walk indexes the link's rows, "
            f'and every row runs along the breakpoints.'
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
