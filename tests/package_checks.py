from __future__ import annotations

import asyncio
import functools
import logging
import subprocess
import sys

import minevent
from minevent import Context, EventManager

logger = logging.getLogger(__name__)


def check_event_manager() -> None:
    logger.info("Checking event manager...")

    event_manager = EventManager()
    calls: list[str] = []
    event_manager.add_event_handler(
        event="my_event", handler=functools.partial(calls.append, "Hello!")
    )
    event_manager.trigger_event("my_event")
    assert calls == ["Hello!"]
    assert "my_event" in event_manager


def check_once() -> None:
    logger.info("Checking once...")

    calls: list[int] = []
    event_manager = EventManager()
    event_manager.add_event_handler("my_event", functools.partial(calls.append, 1), once=True)
    event_manager.trigger_event("my_event")
    event_manager.trigger_event("my_event")
    assert calls == [1]
    assert "my_event" not in event_manager


def check_payload() -> None:
    logger.info("Checking payload...")

    received: list[dict[str, object]] = []

    def handler(context: Context) -> None:
        received.append(dict(context))

    event_manager = EventManager()
    event_manager.add_event_handler("my_event", handler)
    event_manager.trigger_event("my_event", {"epoch": 3, "event": "batch_end"})
    assert received == [{"epoch": 3, "event": "batch_end"}]


def check_subscription() -> None:
    logger.info("Checking subscription...")

    calls: list[int] = []
    event_manager = EventManager()
    subscription = event_manager.add_event_handler("my_event", functools.partial(calls.append, 1))
    assert subscription.active
    assert subscription.remove()
    event_manager.trigger_event("my_event")
    assert calls == []
    assert not subscription.active


def check_async_trigger() -> None:
    logger.info("Checking atrigger_event...")

    calls: list[object] = []

    async def handler(context: Context) -> None:
        calls.append(context["value"])

    event_manager = EventManager()
    event_manager.add_event_handler("my_event", handler)
    asyncio.run(event_manager.atrigger_event("my_event", {"value": 7}))
    assert calls == [7]


def check_no_third_party_import() -> None:
    logger.info("Checking that minevent imports no third-party package...")
    # Only the modules loaded by the import are checked: the interpreter can load third-party
    # modules at startup (for example the sitecustomize module of some distributions).
    code = (
        "import sys\n"
        "before = set(sys.modules)\n"
        "import minevent\n"
        "names = {name.split('.')[0] for name in set(sys.modules) - before}\n"
        "third_party = {n for n in names - set(sys.stdlib_module_names) if not n.startswith('_')}\n"
        "third_party -= {'minevent'}\n"
        "assert not third_party, f'third-party modules imported: {sorted(third_party)}'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


def check_lazy_imports() -> None:
    logger.info("Checking that minevent does not import logging, inspect, asyncio...")
    modules = ["logging", "inspect", "asyncio", "importlib.metadata"]
    code = f"import sys, minevent; assert not set({modules!r}) & set(sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


def check_exports() -> None:
    logger.info("Checking exports...")
    for name in minevent.__all__:
        assert hasattr(minevent, name), f"missing export: {name}"


def check_version() -> None:
    logger.info("Checking version...")
    assert minevent.__version__ != "0.0.0"


def main() -> None:
    check_no_third_party_import()
    check_lazy_imports()
    check_exports()
    check_version()
    check_event_manager()
    check_once()
    check_payload()
    check_subscription()
    check_async_trigger()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
