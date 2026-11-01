r"""Contain the main features of the ``minevent`` package."""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "AlwaysCondition",
    "AndCondition",
    "BaseCondition",
    "BaseEventHandler",
    "CallableCondition",
    "EventHandler",
    "EventManager",
    "NotCondition",
    "OnceCondition",
    "OrCondition",
    "PeriodicCondition",
    "Subscription",
    "__version__",
    "as_condition",
]

from minevent.conditions import (
    AfterNCondition,
    AlwaysCondition,
    AndCondition,
    BaseCondition,
    CallableCondition,
    NotCondition,
    OnceCondition,
    OrCondition,
    PeriodicCondition,
    as_condition,
)
from minevent.handlers import (
    BaseEventHandler,
    EventHandler,
)
from minevent.manager import EventManager
from minevent.subscription import Subscription


def __getattr__(name: str) -> object:
    # PEP 562: the version is read from the metadata of the installed package the first time
    # it is used, because ``importlib.metadata`` is slow to import.
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

        try:
            value = version(__name__)
        except PackageNotFoundError:
            # Package is not installed, fallback if needed
            value = "0.0.0"
        globals()["__version__"] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted([*globals(), "__version__"])
