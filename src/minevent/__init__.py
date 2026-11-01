r"""Contain the main features of the ``minevent`` package."""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "AlwaysCondition",
    "AndCondition",
    "BaseCondition",
    "BaseEventHandler",
    "CallableCondition",
    "ConditionalEventHandler",
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

from importlib.metadata import PackageNotFoundError, version

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
    ConditionalEventHandler,
    EventHandler,
)
from minevent.manager import EventManager
from minevent.subscription import Subscription

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    # Package is not installed, fallback if needed
    __version__ = "0.0.0"
