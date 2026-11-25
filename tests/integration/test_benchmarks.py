from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_import_benchmarks_run_when_disabled() -> None:
    """Test that the real import benchmarks run once without measure, as
    the checks of a pull request run them."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/benchmarks/test_import_benchmark.py",
            "--benchmark-disable",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
