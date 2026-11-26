from __future__ import annotations

import copy
import pickle
from typing import TYPE_CHECKING, Any

import pytest

from minevent import PeriodicCondition
from minevent.conditions import _to_int

if TYPE_CHECKING:
    from collections.abc import Callable


class Index:
    r"""Implement an integer that is not an ``int``.

    Args:
        value: The value returned by ``__index__``.
    """

    def __init__(self, value: int) -> None:
        self._value = value

    def __index__(self) -> int:
        return self._value


class IntSubclass(int):
    r"""Implement a subclass of ``int``."""


#############################
#     Tests for _to_int     #
#############################


@pytest.mark.parametrize(
    ("value", "minimum", "expected"),
    [
        pytest.param(3, 1, 3, id="int"),
        pytest.param(0, 0, 0, id="zero"),
        pytest.param(1, 1, 1, id="minimum"),
        pytest.param(-2, -3, -2, id="negative"),
        pytest.param(10**30, 0, 1_000_000_000_000_000_000_000_000_000_000, id="huge"),
        pytest.param(Index(3), 1, 3, id="index"),
        pytest.param(IntSubclass(3), 1, 3, id="int-subclass"),
    ],
)
def test_to_int(value: object, minimum: int, expected: int) -> None:
    assert _to_int(value, "freq", minimum) == expected


@pytest.mark.parametrize("value", [Index(3), IntSubclass(3)])
def test_to_int_returns_an_int(value: object) -> None:
    assert type(_to_int(value, "freq", 1)) is int


@pytest.mark.parametrize("value", [True, False, 2.0, 2.9, "3", None])
def test_to_int_incorrect_type(value: object) -> None:
    with pytest.raises(
        TypeError, match=r"^freq must be an integer, got (bool|float|str|NoneType)$"
    ):
        _to_int(value, "freq", 0)


@pytest.mark.parametrize("value", [0, -1, Index(0)])
def test_to_int_below_the_minimum(value: object) -> None:
    with pytest.raises(ValueError, match=r"^start must be greater than or equal to 1, got (0|-1)$"):
        _to_int(value, "start", 1)


def test_to_int_index_raises() -> None:
    class BadIndex:
        def __index__(self) -> int:
            msg = "index failed"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match=r"^index failed$"):
        _to_int(BadIndex(), "freq", 1)


#######################################
#     Tests for PeriodicCondition     #
#######################################


def test_periodic_condition_str() -> None:
    assert str(PeriodicCondition(3)).startswith("PeriodicCondition(freq=3,")


@pytest.mark.parametrize("freq", [1, 2, 3])
def test_periodic_condition_freq(freq: int) -> None:
    assert PeriodicCondition(freq).freq == freq


@pytest.mark.parametrize(
    ("freq", "expected"),
    [
        (1, "TTTTTTTTTT"),
        (2, "TFTFTFTFTF"),
        (3, "TFFTFFTFFT"),
        (4, "TFFFTFFFTF"),
    ],
)
def test_periodic_condition_call_freq(freq: int, expected: str) -> None:
    condition = PeriodicCondition(freq)
    assert "".join("T" if condition() else "F" for _ in range(10)) == expected


##############################################################
#     Tests for PeriodicCondition validation and options     #
##############################################################


@pytest.mark.parametrize("freq", [0, -1, -3])
def test_periodic_condition_incorrect_freq_value(freq: int) -> None:
    with pytest.raises(ValueError, match=r"freq must be greater than or equal to 1"):
        PeriodicCondition(freq)


@pytest.mark.parametrize("freq", [2.9, "3", None, True])
def test_periodic_condition_incorrect_freq_type(freq: Any) -> None:
    with pytest.raises(TypeError, match=r"freq must be an integer"):
        PeriodicCondition(freq)


def test_periodic_condition_freq_with_index() -> None:
    assert PeriodicCondition(Index(3)).freq == 3


def test_periodic_condition_start_with_index() -> None:
    assert PeriodicCondition(3, start=Index(2)).start == 2


def test_periodic_condition_call_with_index() -> None:
    condition = PeriodicCondition(Index(3), start=Index(2))
    assert "".join("T" if condition() else "F" for _ in range(10)) == "FFTFFTFFTF"


def test_periodic_condition_repr_with_index() -> None:
    condition = PeriodicCondition(Index(3), start=Index(2))
    assert repr(condition) == "PeriodicCondition(freq=3, start=2, step=0)"


def test_periodic_condition_start_default() -> None:
    assert PeriodicCondition(3).start == 0


@pytest.mark.parametrize("start", [0, 1, 3, 100])
def test_periodic_condition_start(start: int) -> None:
    assert PeriodicCondition(3, start=start).start == start


@pytest.mark.parametrize("start", [-1, -3])
def test_periodic_condition_incorrect_start_value(start: int) -> None:
    with pytest.raises(ValueError, match=r"start must be greater than or equal to 0, got -"):
        PeriodicCondition(3, start=start)


@pytest.mark.parametrize("start", [2.9, "3", None, True, False])
def test_periodic_condition_incorrect_start_type(start: Any) -> None:
    with pytest.raises(TypeError, match=r"start must be an integer, got "):
        PeriodicCondition(3, start=start)


def test_periodic_condition_start_is_keyword_only() -> None:
    args: list[Any] = [3, 1]
    with pytest.raises(TypeError, match=r"positional argument"):
        PeriodicCondition(*args)


def test_periodic_condition_call_sequence() -> None:
    condition = PeriodicCondition(3)
    assert [condition() for _ in range(7)] == [
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


@pytest.mark.parametrize(
    ("freq", "start", "expected"),
    [
        (3, 0, "TFFTFFTFFT"),
        (3, 2, "FFTFFTFFTF"),
        (3, 3, "FFFTFFTFFT"),
        (3, 5, "FFFFFTFFTF"),
        (2, 7, "FFFFFFFTFT"),
        (1, 0, "TTTTTTTTTT"),
        (1, 1, "FTTTTTTTTT"),
        (4, 20, "FFFFFFFFFF"),
    ],
)
def test_periodic_condition_call_start(freq: int, start: int, expected: str) -> None:
    condition = PeriodicCondition(freq, start=start)
    assert "".join("T" if condition() else "F" for _ in range(10)) == expected


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (0, "TTTTTTTT"),
        (1, "FTTTTTTT"),
        (2, "FFTTTTTT"),
        (7, "FFFFFFFT"),
        (8, "FFFFFFFF"),
    ],
)
def test_periodic_condition_freq_one_warm_up(start: int, expected: str) -> None:
    condition = PeriodicCondition(freq=1, start=start)
    assert "".join("T" if condition() else "F" for _ in range(8)) == expected


def test_periodic_condition_reset() -> None:
    condition = PeriodicCondition(3)
    condition()
    condition()
    condition.reset()
    assert condition()


def test_periodic_condition_reset_start() -> None:
    condition = PeriodicCondition(3, start=1)
    condition()
    condition()
    condition.reset()
    assert [condition() for _ in range(2)] == [False, True]


def test_periodic_condition_reset_restores_initial_state() -> None:
    condition = PeriodicCondition(3, start=2)
    condition()
    condition()
    condition.reset()
    assert repr(condition) == "PeriodicCondition(freq=3, start=2, step=0)"


def test_periodic_condition_reset_before_first_call() -> None:
    condition = PeriodicCondition(1, start=1)
    condition.reset()
    assert [condition() for _ in range(2)] == [False, True]


def test_periodic_condition_call_counts_the_call() -> None:
    condition = PeriodicCondition(3)
    condition()
    condition()
    assert repr(condition) == "PeriodicCondition(freq=3, start=0, step=2)"


def test_periodic_condition_call_releases_the_lock() -> None:
    condition = PeriodicCondition(3)
    condition()
    assert not condition._lock.locked()


def test_periodic_condition_reset_releases_the_lock() -> None:
    condition = PeriodicCondition(3)
    condition.reset()
    assert not condition._lock.locked()


def test_periodic_condition_repr() -> None:
    assert repr(PeriodicCondition(3, start=2)) == "PeriodicCondition(freq=3, start=2, step=0)"


def test_periodic_condition_repr_large_values() -> None:
    assert repr(PeriodicCondition(1000, start=2000)) == (
        "PeriodicCondition(freq=1000, start=2000, step=0)"
    )


def test_periodic_condition_repr_large_step() -> None:
    condition = PeriodicCondition(3)
    condition.__setstate__({"_step": 1_000_000, "_freq": 3, "_start": 0})
    assert repr(condition) == "PeriodicCondition(freq=3, start=0, step=1000000)"


def always_true() -> bool:
    r"""Implement a condition that is ``True``."""
    return True


def always_false() -> bool:
    r"""Implement a condition that is ``False``."""
    return False


###################################################
#     Tests for the copy of PeriodicCondition     #
###################################################


def test_periodic_condition_getstate() -> None:
    condition = PeriodicCondition(3, start=2)
    condition()
    assert condition.__getstate__() == {"_step": 1, "_freq": 3, "_start": 2}


def test_periodic_condition_getstate_does_not_remove_the_lock() -> None:
    condition = PeriodicCondition(3)
    condition.__getstate__()
    assert hasattr(condition, "_lock")


def test_periodic_condition_setstate() -> None:
    condition = PeriodicCondition(3)
    condition.__setstate__({"_step": 2, "_freq": 5, "_start": 1})
    assert repr(condition) == "PeriodicCondition(freq=5, start=1, step=2)"


def test_periodic_condition_setstate_creates_a_new_lock() -> None:
    condition = PeriodicCondition(3)
    lock = condition._lock
    condition.__setstate__({"_step": 2, "_freq": 5, "_start": 1})
    assert condition._lock is not lock


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_periodic_condition_pickle(protocol: int) -> None:
    condition = PeriodicCondition(3, start=2)
    condition()
    clone = pickle.loads(pickle.dumps(condition, protocol))  # noqa: S301
    assert repr(clone) == "PeriodicCondition(freq=3, start=2, step=1)"


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_periodic_condition_copy_starts_at_the_same_step(copier: Callable[[Any], Any]) -> None:
    condition = PeriodicCondition(3)
    condition()
    assert repr(copier(condition)) == "PeriodicCondition(freq=3, start=0, step=1)"


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_periodic_condition_copy_has_an_independent_counter(
    copier: Callable[[Any], Any],
) -> None:
    condition = PeriodicCondition(3)
    clone = copier(condition)
    clone()
    assert repr(condition) == "PeriodicCondition(freq=3, start=0, step=0)"


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_periodic_condition_copy_has_an_independent_lock(copier: Callable[[Any], Any]) -> None:
    condition = PeriodicCondition(3)
    assert copier(condition)._lock is not condition._lock
