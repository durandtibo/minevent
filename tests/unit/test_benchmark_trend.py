from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from dev.benchmark_trend import get_label, load_runs, main, make_table, sparkline

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def write_run(path: Path, date: datetime, medians: dict[str, float]) -> None:
    r"""Write a pytest-benchmark result file."""
    benchmarks = [{"name": name, "stats": {"median": median}} for name, median in medians.items()]
    path.write_text(json.dumps({"datetime": date.isoformat(), "benchmarks": benchmarks}))


###############################
#     Tests for get_label     #
###############################


def test_get_label() -> None:
    assert get_label({"name": "test_trigger_event_benchmark"}) == "trigger_event"


def test_get_label_without_prefix_and_suffix() -> None:
    assert get_label({"name": "trigger_event"}) == "trigger_event"


###############################
#     Tests for sparkline     #
###############################


def test_sparkline_increasing() -> None:
    assert sparkline([1.0, 2.0, 3.0]) == "▁▅█"


def test_sparkline_constant() -> None:
    assert sparkline([2.0, 2.0]) == "▁▁"


###############################
#     Tests for load_runs     #
###############################


def test_load_runs_sorted_by_date(tmp_path: Path) -> None:
    now = datetime.now(tz=UTC)
    write_run(tmp_path / "b.json", now, {"test_b_benchmark": 2.0})
    write_run(tmp_path / "a.json", now - timedelta(days=1), {"test_a_benchmark": 1.0})
    assert [times for _, times in load_runs(tmp_path, days=10)] == [{"a": 1.0}, {"b": 2.0}]


def test_load_runs_skips_old_results_and_keeps_the_file(tmp_path: Path) -> None:
    write_run(tmp_path / "old.json", datetime.now(tz=UTC) - timedelta(days=100), {"x": 1.0})
    assert load_runs(tmp_path, days=90) == []
    assert (tmp_path / "old.json").exists()


def test_load_runs_prune_deletes_old_results(tmp_path: Path) -> None:
    write_run(tmp_path / "old.json", datetime.now(tz=UTC) - timedelta(days=100), {"x": 1.0})
    load_runs(tmp_path, days=90, prune=True)
    assert not (tmp_path / "old.json").exists()


def test_load_runs_naive_date_is_utc(tmp_path: Path) -> None:
    write_run(tmp_path / "a.json", datetime.now(tz=UTC).replace(tzinfo=None), {"x": 1.0})
    assert len(load_runs(tmp_path, days=1)) == 1


################################
#     Tests for make_table     #
################################


def test_make_table() -> None:
    date = datetime(2026, 1, 1, tzinfo=UTC)
    table = make_table([(date, {"a": 1e-6}), (date, {"a": 2e-6})])
    assert table.splitlines()[2] == ("| a | 2.0 | 1.0 | +100.0% | 1.5 | 1.0 | 2.0 | 2 | `▁█` |")


#########################
#     Tests for main     #
#########################


def test_main_prints_the_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_run(tmp_path / "a.json", datetime.now(tz=UTC), {"test_a_benchmark": 1e-6})
    monkeypatch.setattr("sys.argv", ["benchmark_trend.py", str(tmp_path), "--days", "10"])
    main()
    assert capsys.readouterr().out.startswith("## Benchmarks over the last 10 days (1 runs)")


def test_main_without_results_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["benchmark_trend.py", str(tmp_path)])
    with caplog.at_level(logging.INFO):
        main()
    assert "No results." in caplog.text
