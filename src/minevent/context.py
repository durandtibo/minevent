r"""Implement the read-only context passed to the event handlers.

A ``Context`` holds the payload of one trigger. It is an immutable
mapping from ``str`` to values: a handler reads the values it needs and
decides what to do when a value is missing.
"""

from __future__ import annotations

__all__ = ["Context"]

import reprlib
from collections.abc import Iterator, Mapping
from typing import Any, final

# The list of the keys in the message of a missing key: at most 20 of them.
_KEYS_REPR = reprlib.Repr()
_KEYS_REPR.maxlist = 20


@final
class Context(Mapping[str, Any]):
    r"""Implement a read-only mapping of the payload of a trigger.

    The data is copied at construction into a private dict, whose keys
    are checked, and a context has no method that changes it (no ``__setitem__``,
    ``update`` or ``pop``), so neither the code that built the context
    nor a handler can change what the next handler sees. The values
    themselves are not copied: a mutable value stays mutable. A context
    can be copied, deep-copied and pickled (with the protocol 2 or
    higher, like the default one) if its values can.

    The values are typed ``Any``: a type checker lets a handler use a
    value without a cast, and it does not check how the value is used.

    ``context[key]`` reads a required value and raises a ``KeyError``
    if it is missing. Its message lists at most 20 of the keys and
    shortens the long ones. ``context.get(key, default)`` reads an
    optional value. ``get`` and ``key in context`` do not build the
    message of that error, so they cost the same for a present key and a
    missing one, whatever the number of keys. ``len``, iteration, ``keys``,
    ``items``, ``values`` and ``==`` behave like those of any
    ``collections.abc.Mapping``, so ``dict(context)`` is a valid
    ``**kwargs``. A context is equal to a mapping that has the same
    items, and it is not hashable. The class is final: a type checker
    reports a subclass.

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
        if data is not None and type(data) is not dict and not isinstance(data, Mapping):
            msg = f"data must be a mapping or None, but got {type(data).__qualname__}"
            raise TypeError(msg)
        copy = {} if data is None else dict(data)
        # The copy is checked, not ``data``, which can differ between two iterations.
        for key in copy:
            if not isinstance(key, str):
                msg = f"the keys of data must be str, but got {reprlib.repr(key)}"
                raise TypeError(msg)
        self._data = copy

    def __getitem__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError:
            keys = _KEYS_REPR.repr(list(self._data))
            msg = f"key {reprlib.repr(key)} not found in the context; available keys: {keys}"
            raise KeyError(msg) from None

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self._data!r})"

    def get(self, key: object, default: object = None) -> Any:
        r"""Get an optional value.

        Unlike ``context[key]``, a missing key costs the same as a
        present one: no error message is built.

        Args:
            key: The key to read. A key that is not a ``str`` is never
                present.
            default: The value returned if ``key`` is missing. Default
                is ``None``.

        Returns:
            The value of ``key``, or ``default`` if it is missing.

        Raises:
            TypeError: if ``key`` is not hashable.

        Example:
            ```pycon
            >>> from minevent import Context
            >>> context = Context({"epoch": 3})
            >>> context.get("epoch")
            3
            >>> context.get("lr", 0.1)
            0.1

            ```
        """
        if not isinstance(key, str):
            hash(key)  # An unhashable key is an error, as it is for a dict.
            return default
        # ``Mapping.get`` calls ``__getitem__``, which builds a message for a missing key.
        return self._data.get(key, default)
