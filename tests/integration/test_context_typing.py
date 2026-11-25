"""A typed sample: ``ty check`` checks the annotated handlers that a
user writes, and the tests run them."""

from __future__ import annotations

from minevent import Context, EventManager


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
