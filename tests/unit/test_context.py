from __future__ import annotations

import copy
import pickle
import threading
from collections.abc import Mapping
from typing import Any

import pytest

from minevent import Context

#############################
#     Tests for Context     #
#############################


def test_context_getitem() -> None:
    assert Context({"a": 1})["a"] == 1


def test_context_getitem_missing_key() -> None:
    with pytest.raises(KeyError, match=r"key 'c' not found in the context.*\['a', 'b'\]"):
        Context({"a": 1, "b": 2})["c"]


def test_context_getitem_missing_key_empty_context() -> None:
    with pytest.raises(KeyError, match=r"key 'a' not found in the context.*\[\]"):
        Context()["a"]


def test_context_get() -> None:
    assert Context({"a": 1}).get("a") == 1


def test_context_get_missing_key() -> None:
    assert Context({"a": 1}).get("b") is None


def test_context_get_missing_key_default() -> None:
    assert Context({"a": 1}).get("b", 5) == 5


def test_context_get_falsy_value() -> None:
    assert Context({"a": 0}).get("a", 5) == 0


def test_context_contains_true() -> None:
    assert "a" in Context({"a": 1})


def test_context_contains_false() -> None:
    assert "b" not in Context({"a": 1})


def test_context_len() -> None:
    assert len(Context({"a": 1, "b": 2})) == 2


def test_context_len_empty() -> None:
    assert len(Context()) == 0


def test_context_len_none() -> None:
    assert len(Context(None)) == 0


def test_context_iter_keeps_the_order() -> None:
    assert list(Context({"b": 1, "a": 2, "c": 3})) == ["b", "a", "c"]


def test_context_items() -> None:
    assert list(Context({"a": 1, "b": 2}).items()) == [("a", 1), ("b", 2)]


def test_context_dict() -> None:
    assert dict(Context({"a": 1, "b": 2})) == {"a": 1, "b": 2}


def test_context_is_a_mapping() -> None:
    assert isinstance(Context(), Mapping)


def test_context_kwargs_bridge() -> None:
    def func(a: object, b: object) -> tuple[object, object]:
        return b, a

    assert func(**Context({"a": 5, "b": 2})) == (2, 5)


def test_context_eq_context() -> None:
    assert Context({"a": 1}) == Context({"a": 1})


def test_context_eq_dict() -> None:
    assert Context({"a": 1}) == {"a": 1}


def test_context_ne_different_value() -> None:
    assert Context({"a": 1}) != Context({"a": 2})


def test_context_ne_different_key() -> None:
    assert Context({"a": 1}) != Context({"b": 1})


def test_context_repr() -> None:
    assert repr(Context({"epoch": 3, "loss": 0.5})) == "Context({'epoch': 3, 'loss': 0.5})"


def test_context_repr_empty() -> None:
    assert repr(Context()) == "Context({})"


def test_context_str() -> None:
    assert str(Context({"a": 1})) == "Context({'a': 1})"


def test_context_not_hashable() -> None:
    with pytest.raises(TypeError, match=r"unhashable type"):
        hash(Context({"a": 1}))


@pytest.mark.parametrize("method", ["__setitem__", "__delitem__", "update", "pop", "clear"])
def test_context_has_no_mutating_method(method: str) -> None:
    assert not hasattr(Context({"a": 1}), method)


def test_context_setitem_raises() -> None:
    context: Any = Context({"a": 1})
    with pytest.raises(TypeError, match=r"does not support item assignment"):
        context["a"] = 2


def test_context_has_no_instance_dict() -> None:
    assert not hasattr(Context(), "__dict__")


def test_context_copies_the_input() -> None:
    data = {"a": 1}
    context = Context(data)
    data["b"] = 2
    assert dict(context) == {"a": 1}


def test_context_does_not_mutate_the_input() -> None:
    data = {"a": 1}
    Context(data)
    assert data == {"a": 1}


def test_context_does_not_copy_the_values() -> None:
    value = [1, 2]
    assert Context({"a": value})["a"] is value


def test_context_copy_of_context() -> None:
    context = Context({"a": 1})
    assert Context(context) == context


def test_context_accepts_any_mapping() -> None:
    assert dict(Context(Context({"a": 1}))) == {"a": 1}


@pytest.mark.parametrize("data", [1, "abc", [("a", 1)], 1.5])
def test_context_invalid_data(data: Any) -> None:
    with pytest.raises(TypeError, match=r"data must be a mapping or None, but got"):
        Context(data)


@pytest.mark.parametrize("key", [1, None, (1, 2), b"a"])
def test_context_invalid_key(key: Any) -> None:
    with pytest.raises(TypeError, match=r"the keys of data must be str, but got"):
        Context({key: 1})


@pytest.mark.parametrize("protocol", range(2, pickle.HIGHEST_PROTOCOL + 1))
def test_context_pickle(protocol: int) -> None:
    assert pickle.dumps(Context({"epoch": 3, "losses": [0.5]}), protocol)


def test_context_pickle_empty() -> None:
    assert pickle.dumps(Context())


def test_context_pickle_unpicklable_value() -> None:
    with pytest.raises(TypeError, match=r"cannot pickle"):
        pickle.dumps(Context({"lock": threading.Lock()}))


def test_context_deepcopy() -> None:
    assert copy.deepcopy(Context({"a": [1]})) == Context({"a": [1]})


def test_context_deepcopy_returns_a_context() -> None:
    assert isinstance(copy.deepcopy(Context({"a": 1})), Context)


def test_context_deepcopy_copies_the_values() -> None:
    value = [1, 2]
    assert copy.deepcopy(Context({"a": value}))["a"] is not value


def test_context_copy() -> None:
    assert copy.copy(Context({"a": 1})) == Context({"a": 1})


def test_context_copy_does_not_copy_the_values() -> None:
    value = [1, 2]
    assert copy.copy(Context({"a": value}))["a"] is value
