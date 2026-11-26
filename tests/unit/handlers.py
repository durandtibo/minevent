r"""Implement the handlers and the conditions shared by several test
modules."""

from __future__ import annotations

import logging
import runpy
import sys
from typing import TYPE_CHECKING, Any

import pytest

from tests.unit.utils import trace

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Generator, Iterator
    from pathlib import Path
    from typing import NoReturn

    from minevent import Context


logger = logging.getLogger(__name__)


def fail(_: Context) -> None:
    r"""Implements a handler that raises a ``ValueError``."""
    msg = "boom"
    raise ValueError(msg)


def read_epoch(context: Context) -> object:
    r"""Implement a handler that reads the required key ``epoch``."""
    return context["epoch"]


def has_payload(context: Context) -> bool:
    r"""Implement a condition that is ``True`` if the context is not
    empty."""
    return bool(context)


def copy_context(context: Context) -> dict[str, object]:
    r"""Implement a handler that returns a copy of the context."""
    return dict(context)


class BadReprCallable:
    r"""Implement a handler whose ``repr`` raises."""

    def __repr__(self) -> str:
        msg = "repr failed"
        raise RuntimeError(msg)

    def __call__(self, _: Context) -> None:
        r"""Implement a handler."""


class BadReprCondition:
    r"""Implement a condition whose ``repr`` raises."""

    def __repr__(self) -> str:
        msg = "repr failed"
        raise RuntimeError(msg)

    def __call__(self, _: Context) -> bool:
        return True


class UnnameableCallable:
    r"""Implement a handler that raises a ``ValueError``, and whose
    ``__qualname__`` cannot be read, like some proxies."""

    def __getattr__(self, name: str) -> object:
        if name == "__qualname__":
            msg = "attribute failed"
            raise RuntimeError(msg)
        raise AttributeError(name)

    def __call__(self, _: Context) -> NoReturn:
        r"""Implement a handler or a condition that raises."""
        msg = "boom"
        raise ValueError(msg)


class UnreadableClass:
    r"""Implement an object whose ``__class__`` cannot be read, like a
    proxy of an object that is not available."""

    @property
    def __class__(self) -> type:
        msg = "class failed"
        raise RuntimeError(msg)


@trace
def hello_handler(_: Context) -> None:
    r"""Implements a simple handler that prints hello."""
    logger.info("Hello!")


@trace
def payload_handler(context: Context) -> None:
    r"""Implements a handler that receives the context."""
    logger.info("Payload: %s", context)


def noop_handler(_: Context) -> None:
    r"""Implement a handler that does nothing."""


class CustomCondition:
    r"""Implements a condition that is true for odd calls."""

    def __init__(self) -> None:
        self._count = 0

    def __call__(self, _: Context) -> bool:
        self._count += 1
        return self._count % 2 == 1


class CallableRecorder:
    r"""Implements a callable object that records the payload."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> None:
        self._calls.append(dict(context))


async def async_condition(_: Context) -> bool:
    r"""Implement an async condition that is ``False``."""
    return False


class AsyncConditionObject:
    r"""Implement a condition with an async ``__call__``."""

    async def __call__(self, _: Context) -> bool:
        r"""Return ``False``."""
        return False


class AsyncConditionMethod:
    r"""Implement an object with an async condition method."""

    async def check(self, _: Context) -> bool:
        r"""Return ``False``."""
        return False


def condition_returning_a_coroutine(context: Context) -> object:
    r"""Implement a synchronous condition that returns a coroutine."""
    return async_condition(context)


class AwaitableResult:
    r"""Implement an awaitable that is not a coroutine."""

    def __await__(self) -> Generator[None, None, bool]:
        yield
        return False


def condition_returning_an_awaitable(_: Context) -> object:
    r"""Implement a synchronous condition that returns an awaitable that
    is not a coroutine."""
    return AwaitableResult()


def named_handler(first_name: str, last_name: str) -> None:
    r"""Implements a handler with two named arguments."""
    logger.info("Hello. I am %s %s", first_name, last_name)


def generator_handler(_: Context) -> Iterator[None]:
    r"""Implement a generator handler."""
    yield


class GeneratorObject:
    r"""Implement a callable object whose ``__call__`` yields."""

    def __call__(self, _: Context) -> Iterator[None]:
        r"""Yield once."""
        yield


class AsyncGeneratorObject:
    r"""Implement a callable object whose ``__call__`` is an async
    generator."""

    async def __call__(self, _: Context) -> AsyncIterator[None]:
        r"""Yield once."""
        yield


class ModelStandIn:
    r"""Stand in for a model, with the signature of
    ``torch.nn.Module.train``."""

    def __init__(self) -> None:
        self.mode: object = False

    def train(self, mode: bool = True) -> None:
        r"""Set the training mode."""
        self.mode = mode

    def generate(self, _: Context) -> Iterator[None]:
        r"""Implement a generator method."""
        yield


# The module has no ``from __future__ import annotations``, so Python 3.14+ evaluates the
# annotations when ``inspect.signature`` reads them.
UNRESOLVED_ANNOTATIONS = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal


def unresolved_return(context) -> Decimal: ...


def unresolved_parameter(context: Decimal) -> None: ...
"""


requires_lazy_annotations = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="the annotations are evaluated at definition before Python 3.14",
)


def unresolved_function(path: Path, name: str) -> Callable[..., Any]:
    r"""Define a function whose annotations cannot be resolved."""
    module = path / "unresolved.py"
    module.write_text(UNRESOLVED_ANNOTATIONS)
    return runpy.run_path(str(module))[name]
