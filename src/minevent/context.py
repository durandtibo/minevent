r"""Implement the read-only context passed to the event handlers.

A ``Context`` holds the payload of one trigger. It is an immutable
mapping from ``str`` to values: a handler reads the values it needs and
decides what to do when a value is missing.
"""

from __future__ import annotations

__all__ = ["Context"]

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class Context(Mapping[str, "Any"]):
    r"""Implement a read-only mapping of the payload of a trigger.

    The data is copied at construction into a private dict, and a
    context has no method that changes it (no ``__setitem__``,
    ``update`` or ``pop``), so neither the code that built the context
    nor a handler can change what the next handler sees. The values
    themselves are not copied: a mutable value stays mutable. A context
    can be copied, deep-copied and pickled (with the protocol 2 or
    higher, like the default one) if its values can.

    The values are typed ``Any``: a type checker lets a handler use a
    value without a cast, and it does not check how the value is used.

    ``context[key]`` reads a required value and raises a ``KeyError``
    if it is missing. ``context.get(key, default)`` reads an optional
    value. ``key in context``, ``len``, iteration, ``keys``, ``items``,
    ``values`` and ``==`` are inherited from
    ``collections.abc.Mapping``, so ``dict(context)`` is a valid
    ``**kwargs``.

    Args:
        data: The mapping to copy, or ``None`` for an empty context.
            Default is ``None``.

    Raises:
        TypeError: if ``data`` is neither ``None`` nor a mapping, or
            if a key of ``data`` is not a ``str``.

    Example:
        ```pycon
        >>> from minevent import Context
        >>> context = Context({"epoch": 3, "loss": 0.5})
        >>> context["epoch"]
        3
        >>> context.get("lr", 0.1)
        0.1
        >>> "loss" in context
        True
        >>> len(context)
        2
        >>> context
        Context({'epoch': 3, 'loss': 0.5})
        >>> import copy
        >>> copy.deepcopy(context)
        Context({'epoch': 3, 'loss': 0.5})

        ```
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, object] | None = None) -> None:
        if data is None:
            data = {}
        elif type(data) is not dict and not isinstance(data, Mapping):
            msg = f"data must be a mapping or None, but got {type(data).__qualname__}"
            raise TypeError(msg)
        for key in data:
            if not isinstance(key, str):
                msg = f"the keys of data must be str, but got {key!r}"
                raise TypeError(msg)
        self._data = dict(data)

    def __getitem__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError:
            msg = f"key {key!r} not found in the context; available keys: {list(self._data)!r}"
            raise KeyError(msg) from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self._data!r})"
