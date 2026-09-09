# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The seal on what the language hands out — a mapping nothing can write to, which pickles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Iterator


class Sealed[K, V](Mapping[K, V]):
    """A mapping nothing can write to, which pickles.

    What every group a program hands out is held behind, and a node's
    keyword arguments with them: a consumer cannot rewrite what another
    consumer reads, and the whole crosses a process — which is the one thing
    :class:`types.MappingProxyType` cannot do. Equal to any mapping with the
    same items, and hashable over them where they are, so a dataclass may
    hold one as a default.
    """

    __slots__ = ('_items',)

    def __init__(self, items: Mapping[K, V]) -> None:
        self._items = dict(items)

    @override
    def __getitem__(self, key: K) -> V:
        return self._items[key]

    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._items)

    @override
    def __len__(self) -> int:
        return len(self._items)

    @override
    def __hash__(self) -> int:
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._items!r})'

    def __getstate__(self) -> dict[K, V]:
        return self._items

    def __setstate__(self, items: dict[K, V]) -> None:
        self._items = items
