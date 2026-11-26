from __future__ import annotations

import logging
import runpy
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from dev import generate_versions
from dev.generate_versions import fetch_package_versions, main
from feu.version import PackageBounds

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from unittest.mock import MagicMock

PYPROJECT = """
[project]
name = "sample"
dependencies = ["numpy>=2.0,<3.0"]

[project.optional-dependencies]
extra = ["coola>=1.0"]
"""


def fake_fetch(
    packages: Sequence[PackageBounds], include_lower_bound: bool
) -> dict[str, list[str]]:
    r"""Stand in for the functions of ``feu`` that request the versions
    of the packages."""
    suffix = "lower" if include_lower_bound else "latest"
    return {package.name: [f"{package.lower}-{suffix}"] for package in packages}


@pytest.fixture(autouse=True)
def major_fetch() -> Iterator[MagicMock]:
    r"""Patch the request of the major versions, so no test uses the
    network."""
    with patch.object(
        generate_versions, "fetch_latest_major_versions_map", side_effect=fake_fetch
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def minor_fetch() -> Iterator[MagicMock]:
    r"""Patch the request of the minor versions, so no test uses the
    network."""
    with patch.object(
        generate_versions, "fetch_latest_minor_versions_map", side_effect=fake_fetch
    ) as mock:
        yield mock


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    r"""Create a directory with a ``pyproject.toml`` that has a required
    and an optional dependency."""
    tmp_path.joinpath("pyproject.toml").write_text(PYPROJECT)
    return tmp_path


@pytest.fixture
def script_dir(base_dir: Path) -> Iterator[Path]:
    r"""Make the script believe that it is in ``dev/`` of ``base_dir``,
    so ``main`` does not write in the repository."""
    script = base_dir.joinpath("dev", "generate_versions.py")
    with patch.object(generate_versions, "__file__", str(script)):
        yield base_dir


############################################
#     Tests for fetch_package_versions     #
############################################


def test_fetch_package_versions(base_dir: Path) -> None:
    assert fetch_package_versions(base_dir) == {
        "coola": ["1.0-lower"],
        "numpy": ["2.0-lower"],
    }


def test_fetch_package_versions_sorted_by_name(base_dir: Path) -> None:
    # The required dependency, ``numpy``, is read before the optional one.
    assert list(fetch_package_versions(base_dir)) == ["coola", "numpy"]


def test_fetch_package_versions_fetches_the_minor_versions(
    base_dir: Path, minor_fetch: MagicMock
) -> None:
    fetch_package_versions(base_dir)
    minor_fetch.assert_called_once_with(
        [
            PackageBounds(name="numpy", lower="2.0", upper="3.0", section="project.dependencies"),
            PackageBounds(
                name="coola",
                lower="1.0",
                upper=None,
                section="project.optional-dependencies.extra",
            ),
        ],
        include_lower_bound=True,
    )


def test_fetch_package_versions_fetches_no_major_version(
    base_dir: Path, major_fetch: MagicMock
) -> None:
    fetch_package_versions(base_dir)
    major_fetch.assert_called_once_with([], include_lower_bound=True)


def test_fetch_package_versions_merges_the_major_versions(
    base_dir: Path, major_fetch: MagicMock
) -> None:
    major_fetch.side_effect = None
    major_fetch.return_value = {"torch": ["2.0"]}
    assert fetch_package_versions(base_dir) == {
        "coola": ["1.0-lower"],
        "numpy": ["2.0-lower"],
        "torch": ["2.0"],
    }


def test_fetch_package_versions_without_dependency(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text('[project]\nname = "sample"\n')
    assert fetch_package_versions(tmp_path) == {}


def test_fetch_package_versions_without_pyproject(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"pyproject\.toml"):
        fetch_package_versions(tmp_path)


def test_fetch_package_versions_fetch_error(base_dir: Path, minor_fetch: MagicMock) -> None:
    minor_fetch.side_effect = RuntimeError("no network")
    with pytest.raises(RuntimeError, match=r"no network"):
        fetch_package_versions(base_dir)


##########################
#     Tests for main     #
##########################


def test_main_saves_the_versions(script_dir: Path) -> None:
    main()
    path = script_dir.joinpath("dev", "config", "package_versions.json")
    assert path.read_text() == '{"coola": ["1.0-lower"], "numpy": ["2.0-lower"]}\n'


def test_main_replaces_the_file(script_dir: Path) -> None:
    path = script_dir.joinpath("dev", "config", "package_versions.json")
    path.parent.mkdir(parents=True)
    path.write_text('{"old": ["0.1"]}\n')
    main()
    assert path.read_text() == '{"coola": ["1.0-lower"], "numpy": ["2.0-lower"]}\n'


def test_main_keeps_the_file_on_a_fetch_error(script_dir: Path, minor_fetch: MagicMock) -> None:
    path = script_dir.joinpath("dev", "config", "package_versions.json")
    path.parent.mkdir(parents=True)
    path.write_text('{"old": ["0.1"]}\n')
    minor_fetch.side_effect = RuntimeError("no network")
    with pytest.raises(RuntimeError, match=r"no network"):
        main()
    assert path.read_text() == '{"old": ["0.1"]}\n'


@pytest.mark.usefixtures("script_dir")
def test_main_logs_the_versions(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="dev.generate_versions"):
        main()
    assert caplog.messages[0] == "versions={'coola': ['1.0-lower'], 'numpy': ['2.0-lower']}"


def test_script_saves_the_versions_when_run() -> None:
    # The script imports the functions of ``feu`` again, so they are patched where they are defined,
    # and nothing is written in the repository.
    with (
        patch("feu.version.fetch_latest_major_versions_map", return_value={}),
        patch("feu.version.fetch_latest_minor_versions_map", return_value={"coola": ["1.0"]}),
        patch("feu.utils.io.save_json") as save_json,
        patch("logging.basicConfig"),
    ):
        runpy.run_path(generate_versions.__file__, run_name="__main__")
    save_json.assert_called_once_with(
        {"coola": ["1.0"]},
        Path(generate_versions.__file__).parent.joinpath("config", "package_versions.json"),
        exist_ok=True,
    )
