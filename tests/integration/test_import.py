from __future__ import annotations

import subprocess
import sys

import pytest

LAZY_MODULES = ["logging", "inspect", "asyncio", "importlib.metadata", "typing"]


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    r"""Run ``code`` in a fresh isolated interpreter.

    Args:
        code: The code to run.

    Returns:
        The completed process. A non-zero exit status raises.
    """
    return subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )


@pytest.mark.parametrize("module", LAZY_MODULES)
def test_import_minevent_does_not_import_module(module: str) -> None:
    """Test that ``import minevent`` leaves the heavy modules to the
    code that needs them."""
    result = run_python(f"import sys, minevent; print({module!r} in sys.modules)")
    assert result.stdout.strip() == "False"


def test_import_minevent_has_no_output() -> None:
    """Test that ``import minevent`` writes nothing."""
    result = run_python("import minevent")
    assert (result.stdout, result.stderr) == ("", "")


def test_handler_with_context_works_after_a_cheap_import() -> None:
    """Test that registering a handler imports ``inspect`` when it is
    used and still passes the context to a handler that needs it."""
    code = (
        "import sys\n"
        "from minevent import EventManager\n"
        "assert 'inspect' not in sys.modules\n"
        "manager = EventManager()\n"
        "manager.add_event_handler('e', lambda context: print(context['epoch']))\n"
        "manager.trigger_event('e', {'epoch': 3, 'loss': 0.5})\n"
    )
    assert run_python(code).stdout.strip() == "3"


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="the annotations are evaluated at definition before Python 3.14",
)
def test_handler_with_unresolved_annotation_is_registered_and_called() -> None:
    """Test that a handler annotated with a name imported under
    ``TYPE_CHECKING`` only is registered and called."""
    code = (
        "from typing import TYPE_CHECKING\n"
        "from minevent import EventManager\n"
        "if TYPE_CHECKING:\n"
        "    from decimal import Decimal\n"
        "def handler(context: Decimal) -> Decimal:\n"
        "    print(context['epoch'])\n"
        "manager = EventManager()\n"
        "manager.add_event_handler('e', handler)\n"
        "manager.trigger_event('e', {'epoch': 3})\n"
    )
    assert run_python(code).stdout.strip() == "3"


def test_trigger_event_does_not_import_logging() -> None:
    """Test that registering and triggering handlers never imports
    ``logging``."""
    code = (
        "import sys\n"
        "from minevent import EventManager\n"
        "manager = EventManager()\n"
        "subscription = manager.add_event_handler('e', lambda: None)\n"
        "manager.trigger_event('e')\n"
        "subscription.remove()\n"
        "manager.clear_event('e')\n"
        "print('logging' in sys.modules)\n"
    )
    assert run_python(code).stdout.strip() == "False"
