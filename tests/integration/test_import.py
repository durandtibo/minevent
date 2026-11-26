from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"


def run_python(code: str, *options: str) -> subprocess.CompletedProcess[str]:
    r"""Run ``code`` in a fresh isolated interpreter.

    Args:
        code: The code to run.
        *options: More options of the interpreter.

    Returns:
        The completed process. A non-zero exit status raises.
    """
    return subprocess.run(  # noqa: S603
        [sys.executable, "-I", *options, "-c", code], capture_output=True, text=True, check=True
    )


def test_import_minevent_has_no_output() -> None:
    """Test that ``import minevent`` writes nothing."""
    result = run_python("import minevent")
    assert (result.stdout, result.stderr) == ("", "")


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


def test_version_fallback_without_metadata() -> None:
    """Test that ``__version__`` is ``0.0.0`` when the package is not
    installed: without ``site``, only the source is on the path."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "import minevent\n"
        "print(minevent.__version__)"
    )
    assert run_python(code, "-S").stdout.strip() == "0.0.0"
