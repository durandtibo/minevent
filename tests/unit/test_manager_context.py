from __future__ import annotations

import functools
from types import MappingProxyType
from typing import Any

import pytest

from minevent import (
    Context,
    EventManager,
)
from minevent.manager import _as_context
from tests.unit.handlers import (
    copy_context,
    hello_handler,
    payload_handler,
    read_epoch,
)

###########################################
#     Tests for trigger_event payload     #
###########################################


def test_event_manager_trigger_event_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert payload_handler.args == ({"epoch": 3, "loss": 0.5},)


def test_event_manager_trigger_event_payload_all_handlers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.add_event_handler("my_event", functools.partial(payload_handler))
    manager.trigger_event("my_event", {"epoch": 3})
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_without_payload() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event")
    assert payload_handler.args == ({},)


def test_event_manager_trigger_event_payload_is_a_context() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert isinstance(payload_handler.args[0], Context)


def test_event_manager_trigger_event_payload_ignored_by_handler_without_parameter() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert hello_handler.call_count == 1


def test_event_manager_trigger_event_handler_without_parameter_called_without_argument() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    manager.trigger_event("my_event", {"epoch": 3})
    assert (hello_handler.args, hello_handler.kwargs) == ((), {})


def test_event_manager_trigger_event_handlers_read_different_keys() -> None:
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("my_event", lambda context: calls.append(context["epoch"]))
    manager.add_event_handler("my_event", lambda context: calls.append(context["loss"]))
    manager.trigger_event("my_event", {"epoch": 3, "loss": 0.5})
    assert calls == [3, 0.5]


def test_event_manager_trigger_event_handler_missing_key_raises_key_error() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", read_epoch)
    with pytest.raises(KeyError, match=r"key 'epoch' not found in the context") as exc_info:
        manager.trigger_event("my_event", {"loss": 0.5})
    assert exc_info.value.__notes__ == ["raised by read_epoch while handling the event 'my_event'"]


def test_event_manager_trigger_event_handler_missing_key_with_default() -> None:
    manager = EventManager()
    calls: list[object] = []
    manager.add_event_handler("my_event", lambda context: calls.append(context.get("epoch", -1)))
    manager.trigger_event("my_event", {"loss": 0.5})
    assert calls == [-1]


def test_event_manager_trigger_event_all_handlers_share_one_context() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    manager.add_event_handler("my_event", contexts.append)
    manager.trigger_event("my_event", {"epoch": 3})
    assert contexts[0] is contexts[1]


def test_event_manager_trigger_event_new_context_for_each_trigger() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    manager.trigger_event("my_event", {"epoch": 1})
    manager.trigger_event("my_event", {"epoch": 2})
    assert contexts == [{"epoch": 1}, {"epoch": 2}]


def test_event_manager_trigger_event_context_is_read_only() -> None:
    manager = EventManager()

    def handler(context: Any) -> None:
        context["epoch"] = 0

    manager.add_event_handler("my_event", handler)
    with pytest.raises(TypeError, match=r"does not support item assignment"):
        manager.trigger_event("my_event", {"epoch": 3})


def test_event_manager_trigger_event_payload_with_event_and_self_keys() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"event": "batch_end", "self": 1})
    assert payload_handler.args == ({"event": "batch_end", "self": 1},)


def test_event_manager_trigger_event_once_payload_with_self_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler, once=True)
    manager.trigger_event("my_event", {"self": 1})
    assert payload_handler.args == ({"self": 1},)


####################################################
#     Tests for the context given to a trigger     #
####################################################


def test_event_manager_trigger_event_context_object_is_passed_as_is() -> None:
    manager = EventManager()
    contexts: list[Context] = []
    manager.add_event_handler("my_event", contexts.append)
    context = Context({"epoch": 3})
    manager.trigger_event("my_event", context)
    assert contexts[0] is context


@pytest.mark.parametrize("data", [{"epoch": 3, "loss": 0.5}, Context({"epoch": 3, "loss": 0.5})])
def test_event_manager_trigger_event_dict_and_context_give_the_same_data(data: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", data)
    assert payload_handler.args == ({"epoch": 3, "loss": 0.5},)


def test_event_manager_trigger_event_context_can_be_reused() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    context = Context({"epoch": 3})
    manager.trigger_event("my_event", context)
    manager.trigger_event("my_event", context)
    assert payload_handler.call_count == 2


def test_event_manager_trigger_event_dict_is_not_modified_by_a_handler() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", copy_context)
    data = {"epoch": 3}
    manager.trigger_event("my_event", data)
    assert data == {"epoch": 3}


def test_event_manager_trigger_event_keys_need_not_be_identifiers() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", {"train/loss": 0.5, "event": "x"})
    assert payload_handler.args == ({"train/loss": 0.5, "event": "x"},)


def test_event_manager_trigger_event_context_none() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", payload_handler)
    manager.trigger_event("my_event", None)
    assert payload_handler.args == ({},)


@pytest.mark.parametrize("context", [1, "abc", [("a", 1)]])
def test_event_manager_trigger_event_invalid_context(context: Any) -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    with pytest.raises(TypeError, match=r"context must be a mapping or None, but got"):
        manager.trigger_event("my_event", context)
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_invalid_key() -> None:
    manager = EventManager()
    manager.add_event_handler("my_event", hello_handler)
    context: Any = {1: "a"}
    with pytest.raises(TypeError, match=r"the keys of data must be str, but got 1"):
        manager.trigger_event("my_event", context)
    assert hello_handler.call_count == 0


def test_event_manager_trigger_event_keyword_payload_is_rejected() -> None:
    manager = EventManager()
    payload: Any = {"epoch": 3}
    with pytest.raises(TypeError, match=r"got an unexpected keyword argument 'epoch'"):
        manager.trigger_event("my_event", **payload)


#################################
#     Tests for _as_context     #
#################################


def test_as_context_dict() -> None:
    assert _as_context({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_as_context_dict_is_a_context() -> None:
    assert isinstance(_as_context({"a": 1}), Context)


def test_as_context_dict_is_copied() -> None:
    data: dict[str, object] = {"a": 1}
    context = _as_context(data)
    data["b"] = 2
    assert dict(context) == {"a": 1}


def test_as_context_dict_is_not_modified() -> None:
    data: dict[str, object] = {"a": 1}
    _as_context(data)
    assert data == {"a": 1}


def test_as_context_empty_dict() -> None:
    assert _as_context({}) == {}


def test_as_context_none() -> None:
    assert _as_context(None) == {}


def test_as_context_none_is_shared() -> None:
    assert _as_context(None) is _as_context(None)


def test_as_context_context_is_reused() -> None:
    context = Context({"a": 1})
    assert _as_context(context) is context


def test_as_context_other_mapping() -> None:
    assert _as_context(MappingProxyType({"a": 1})) == {"a": 1}


@pytest.mark.parametrize("context", [1, "abc", [("a", 1)], 1.5])
def test_as_context_invalid_type(context: Any) -> None:
    with pytest.raises(TypeError, match=r"context must be a mapping or None, but got"):
        _as_context(context)


def test_as_context_invalid_type_names_the_type() -> None:
    with pytest.raises(TypeError, match=r"but got list"):
        _as_context([])


@pytest.mark.parametrize("key", [1, None, b"a"])
def test_as_context_invalid_key(key: Any) -> None:
    with pytest.raises(TypeError, match=r"the keys of data must be str, but got"):
        _as_context({key: 1})
