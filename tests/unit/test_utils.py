from __future__ import annotations

from tests.unit.utils import Tracer, trace


def add(a: int, b: int = 0) -> int:
    return a + b


###########################
#     Tests for Tracer    #
###########################


def test_tracer_not_called() -> None:
    assert not Tracer(add).called


def test_tracer_call_count_initial() -> None:
    assert Tracer(add).call_count == 0


def test_tracer_call_returns_result() -> None:
    assert Tracer(add)(1, b=2) == 3


def test_tracer_called() -> None:
    tracer = Tracer(add)
    tracer(1)
    assert tracer.called


def test_tracer_call_count() -> None:
    tracer = Tracer(add)
    tracer(1)
    tracer(2)
    assert tracer.call_count == 2


def test_tracer_args() -> None:
    tracer = Tracer(add)
    tracer(1, b=2)
    assert tracer.args == (1,)


def test_tracer_kwargs() -> None:
    tracer = Tracer(add)
    tracer(1, b=2)
    assert tracer.kwargs == {"b": 2}


def test_tracer_wrapped() -> None:
    assert Tracer(add).__wrapped__ is add


def test_tracer_reset() -> None:
    tracer = Tracer(add)
    tracer(1, b=2)
    tracer.reset()
    assert (tracer.called, tracer.call_count, tracer.args, tracer.kwargs) == (False, 0, (), {})


##########################
#     Tests for trace    #
##########################


def test_trace_returns_tracer() -> None:
    assert isinstance(trace(add), Tracer)
