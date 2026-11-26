"""A typed sample: ``ty check`` checks the annotated handlers that a
user writes, and the tests run them.

The handlers that a type checker must report are checked by running
``ty`` on a sample file.
"""

from __future__ import annotations

import asyncio
import functools
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest

from minevent import Context, EventManager

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from minevent import Handler

SAMPLE = """
from functools import partial
from typing import Any

from minevent import Context, EventManager

manager = EventManager()

{code}
"""


def check_types(path: Path, code: str) -> subprocess.CompletedProcess[str]:
    r"""Run ``ty check`` on a sample of the code of a user.

    Args:
        path: The directory where the sample file is written.
        code: The code that registers a handler to ``manager``.

    Returns:
        The completed process of ``ty``.
    """
    sample = path / "sample.py"
    sample.write_text(SAMPLE.format(code=code))
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ty", "check", "--python", sys.prefix, sample.name],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )


class Trainer:
    r"""Implement a handler that is a callable object.

    Args:
        calls: The list that receives the calls of the object.
    """

    def __init__(self, calls: list[object]) -> None:
        self._calls = calls

    def __call__(self, context: Context) -> None:
        r"""Implement a handler that is a callable object."""
        self._calls.append(("call", context["epoch"]))


def save(path: str, context: Context) -> None:
    r"""Implement a handler that needs a bound argument."""
    context.get(path)


def test_typed_handler_shapes_are_registered_and_called() -> None:
    """Test that the shapes of handler that a type checker accepts are
    registered and called."""
    manager = EventManager()
    calls: list[object] = []
    trainer = Trainer(calls)
    contexts: list[Context] = []

    def ignored(_: Context) -> None:
        calls.append("ignored")

    def with_context(context: Context) -> None:
        calls.append(("with_context", context["epoch"]))

    def with_mapping(context: Mapping[str, Any]) -> None:
        calls.append(("with_mapping", context["epoch"]))

    def context_and_default(context: Context, verbose: bool = False) -> None:
        calls.append(("context_and_default", context["epoch"], verbose))

    handlers: list[Handler] = [
        ignored,
        with_context,
        with_mapping,
        context_and_default,
        trainer,
    ]
    for handler in handlers:
        manager.add_event_handler("epoch_end", handler)
    manager.add_event_handler(
        "epoch_end", lambda context, i=2: calls.append(("context_lambda", context["epoch"], i))
    )
    manager.add_event_handler("epoch_end", functools.partial(save, "model.pt"))
    manager.add_event_handler("epoch_end", contexts.append)
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert (calls, contexts) == (
        [
            "ignored",
            ("with_context", 3),
            ("with_mapping", 3),
            ("context_and_default", 3, False),
            ("call", 3),
            ("context_lambda", 3, 2),
        ],
        [Context({"epoch": 3})],
    )


def test_typed_coroutine_handler_is_awaited() -> None:
    """Test that a coroutine handler is a ``Handler`` for the type
    checker and is awaited at run time."""
    manager = EventManager()
    calls: list[int] = []

    async def upload(context: Context) -> None:
        await asyncio.sleep(0)
        calls.append(context["epoch"])

    manager.add_event_handler("epoch_end", upload)
    asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 3}))
    assert calls == [3]


def test_typed_decorated_handler_keeps_its_type() -> None:
    """Test that a function decorated with ``on`` keeps its own type for
    the type checker and at run time."""
    manager = EventManager()

    @manager.on("epoch_end")
    def next_epoch(context: Context) -> int:
        return context["epoch"] + 1

    result: int = next_epoch(Context({"epoch": 3}))
    assert result == 4


def test_typed_handler_accepted_by_the_type_checker_but_rejected_at_registration() -> None:
    """Test that ``print``, which a type checker accepts, is still
    rejected by the registration."""
    manager = EventManager()
    with pytest.raises(
        TypeError, match=r"^handler print must take the context as its only required argument"
    ):
        manager.add_event_handler("epoch_end", print)


def test_type_checker_accepts_a_correct_sample(tmp_path: Path) -> None:
    """Test that ``ty`` accepts a correct sample, so the reports of the
    other samples come from their handlers."""
    code = "def handler(context: Context) -> None: ...\n\n\nmanager.add_event_handler('e', handler)"
    result = check_types(tmp_path, code)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            "def handler(a: int, b: int) -> None: ...\n\n\nmanager.add_event_handler('e', handler)",
            id="two-parameters",
        ),
        pytest.param(
            "def handler(*, epoch: int) -> None: ...\n\n\nmanager.add_event_handler('e', handler)",
            id="keyword-only",
        ),
        pytest.param(
            "def handler(context: dict[str, Any]) -> None: ...\n\n\n"
            "manager.add_event_handler('e', handler)",
            id="dict-parameter",
        ),
        pytest.param(
            "def handler(epoch: int) -> None: ...\n\n\nmanager.add_event_handler('e', handler)",
            id="int-parameter",
        ),
        pytest.param(
            "@manager.on('e')\ndef handler(a: int, b: int) -> None: ...",
            id="decorator",
        ),
        pytest.param(
            "def handler() -> None: ...\n\n\nmanager.add_event_handler('e', handler)",
            id="no-parameter",
        ),
        pytest.param(
            "class Model:\n    def train(self, mode: bool = True) -> None: ...\n\n\n"
            "manager.add_event_handler('e', Model().train)",
            id="bound-method-with-default",
        ),
        pytest.param("manager.add_event_handler('e', lambda: None)", id="lambda-no-parameter"),
        pytest.param(
            "manager.add_event_handler('e', print, condition=lambda: True)",
            id="condition-no-parameter",
        ),
    ],
)
def test_type_checker_reports_a_wrong_handler(tmp_path: Path, code: str) -> None:
    """Test that ``ty`` reports a handler that the manager cannot
    call."""
    result = check_types(tmp_path, code)
    assert "error[invalid-argument-type]" in result.stdout, result.stdout + result.stderr


def test_context_subclass_is_reported(tmp_path: Path) -> None:
    """Test that ``ty`` reports a subclass of ``Context``, which is
    final."""
    result = check_types(tmp_path, "class MyContext(Context): ...")
    assert "error[subclass-of-final-class]" in result.stdout, result.stdout + result.stderr


def test_typed_handler_computes_with_the_values() -> None:
    """Test that an annotated handler computes with the values of the
    context without a cast, for the type checker and at run time."""
    manager = EventManager()
    results: list[tuple[int, float, str]] = []

    def handler(context: Context) -> None:
        epoch: int = context["epoch"] + 1
        loss: float = context.get("loss", 0.0) * 2
        name: str = context["name"].upper()
        results.append((epoch, loss, name))

    manager.add_event_handler("epoch_end", handler)
    manager.trigger_event("epoch_end", {"epoch": 3, "loss": 0.5, "name": "train"})
    assert results == [(4, 1.0, "TRAIN")]


def test_typed_handler_reads_optional_values() -> None:
    """Test that an annotated handler reads optional values with ``get``
    without a cast, for the type checker and at run time."""
    manager = EventManager()
    results: list[tuple[int, int | None]] = []

    def handler(context: Context) -> None:
        batch: int = context.get("batch", 0) + 1
        results.append((batch, context.get("lr")))

    manager.add_event_handler("epoch_end", handler)
    manager.trigger_event("epoch_end", {"epoch": 3})
    assert results == [(1, None)]


def test_typed_condition_compares_the_values() -> None:
    """Test that an annotated condition compares a value of the context
    without a cast, for the type checker and at run time."""
    manager = EventManager()
    calls: list[int] = []

    def is_late(context: Context) -> bool:
        return context["epoch"] >= 2

    def record(context: Context) -> None:
        calls.append(context["epoch"])

    manager.add_event_handler("epoch_end", record, condition=is_late)
    manager.trigger_event("epoch_end", {"epoch": 1})
    manager.trigger_event("epoch_end", {"epoch": 2})
    assert calls == [2]
