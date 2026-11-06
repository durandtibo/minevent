from __future__ import annotations

from unittest.mock import Mock

import pytest

from tests.unit.utils import Tracer, raised, reset_traced, trace


def add(a: int, b: int = 0) -> int:
    return a + b


############################
#     Tests for Tracer     #
############################


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
    assert not tracer.called
    assert tracer.call_count == 0
    assert tracer.args == ()
    assert tracer.kwargs == {}


###########################
#     Tests for trace     #
###########################


def test_trace_returns_tracer() -> None:
    assert isinstance(trace(add), Tracer)


def test_trace_registers_tracer_for_reset() -> None:
    tracer = trace(add)
    tracer(1)
    reset_traced()
    assert tracer.call_count == 0


def test_reset_traced_does_not_reset_unregistered_tracer() -> None:
    tracer = Tracer(add)
    tracer(1)
    reset_traced()
    assert tracer.call_count == 1


############################
#     Tests for raised     #
############################


def raise_value_error(message: str = "boom") -> None:
    raise ValueError(message)


def test_raised_returns_exception() -> None:
    assert isinstance(raised(raise_value_error), ValueError)


def test_raised_passes_arguments() -> None:
    assert str(raised(raise_value_error, message="custom")) == "custom"


def test_raised_returns_base_exception() -> None:
    assert isinstance(raised(Mock(side_effect=KeyboardInterrupt("stop"))), KeyboardInterrupt)


def test_raised_fails_when_no_exception() -> None:
    with pytest.raises(BaseException, match=r"DID NOT RAISE"):
        raised(add, 1)
