"""Tests for wbsb.history.store and wbsb.history.trends."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wbsb.history.store import (
    HistoryReader,
    RunRecord,
    derive_dataset_key,
    register_run,
)
from wbsb.history.trends import TrendResult, compute_trends

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_findings(tmp_path: Path, metrics: list[dict], name: str = "findings.json") -> Path:
    """Write a minimal findings.json and return its path."""
    findings_path = tmp_path / name
    findings_path.write_text(json.dumps({"metrics": metrics}), encoding="utf-8")
    return findings_path


def _make_record(findings_path: Path, **overrides) -> RunRecord:
    """Return a minimal valid RunRecord."""
    base: RunRecord = {
        "run_id": "20260309T000000Z_aabbcc",
        "dataset_key": "weekly_data",
        "input_file": "weekly_data_2026-03-09.csv",
        "week_start": "2026-03-03",
        "week_end": "2026-03-09",
        "signal_count": 2,
        "findings_path": str(findings_path),
        "registered_at": "2026-03-09T10:00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# derive_dataset_key
# ---------------------------------------------------------------------------


def test_derive_dataset_key_strips_date():
    assert derive_dataset_key("weekly_data_2026-03-03.csv") == "weekly_data"


def test_derive_dataset_key_strips_yyyymmdd():
    assert derive_dataset_key("report_20260303.xlsx") == "report"


def test_derive_dataset_key_no_date():
    assert derive_dataset_key("dataset_07_extreme_ad_spend.csv") == "dataset_07_extreme_ad_spend"


def test_derive_dataset_key_handles_full_path():
    result_full = derive_dataset_key("/some/path/to/weekly_data_2026-03-10.csv")
    result_name = derive_dataset_key("weekly_data_2026-03-10.csv")
    assert result_full == result_name == "weekly_data"


def test_derive_dataset_key_dash_date_separator():
    assert derive_dataset_key("weekly-data-2026-03-03.csv") == "weekly-data"


def test_derive_dataset_key_returns_lowercase():
    assert derive_dataset_key("Weekly_Data_2026-03-03.csv") == "weekly_data"


# ---------------------------------------------------------------------------
# register_run
# ---------------------------------------------------------------------------


def test_register_run_creates_index(tmp_path):
    findings_path = _make_findings(tmp_path, [{"id": "net_revenue", "current": 5000.0}])
    record = _make_record(findings_path)
    index_path = tmp_path / "index.json"

    register_run(record, index_path)

    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert len(data) == 1
    assert data[0]["run_id"] == "20260309T000000Z_aabbcc"
    assert data[0]["dataset_key"] == "weekly_data"


def test_register_run_appends_records(tmp_path):
    findings_1 = _make_findings(tmp_path, [], name="findings_1.json")
    findings_2 = _make_findings(tmp_path, [], name="findings_2.json")
    index_path = tmp_path / "index.json"

    record_1 = _make_record(findings_1, run_id="run_aaa", week_start="2026-02-24")
    record_2 = _make_record(findings_2, run_id="run_bbb", week_start="2026-03-03")

    register_run(record_1, index_path)
    register_run(record_2, index_path)

    data = json.loads(index_path.read_text())
    assert len(data) == 2
    assert {entry["run_id"] for entry in data} == {"run_aaa", "run_bbb"}


def test_register_run_rejects_duplicate_run_id(tmp_path):
    findings_path = _make_findings(tmp_path, [])
    index_path = tmp_path / "index.json"
    record = _make_record(findings_path)

    register_run(record, index_path)

    with pytest.raises(ValueError, match="run_id already exists"):
        register_run(record, index_path)


def test_register_run_rejects_missing_findings(tmp_path):
    index_path = tmp_path / "index.json"
    record = _make_record(tmp_path / "nonexistent_findings.json")

    with pytest.raises(FileNotFoundError, match="findings_path does not exist"):
        register_run(record, index_path)


def test_register_run_atomic_write(tmp_path):
    """Verify no temp file is left behind after a successful write."""
    findings_path = _make_findings(tmp_path, [])
    index_path = tmp_path / "index.json"
    register_run(_make_record(findings_path), index_path)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Temp files left behind: {tmp_files}"


# ---------------------------------------------------------------------------
# HistoryReader
# ---------------------------------------------------------------------------


def test_history_reader_empty_when_no_index(tmp_path):
    reader = HistoryReader(tmp_path / "index.json", dataset_key="weekly_data")
    assert reader.get_metric_history("net_revenue") == []


def test_history_reader_dataset_isolation(tmp_path):
    """Runs registered under dataset_a must not appear in queries for dataset_b."""
    findings_a = _make_findings(tmp_path, [{"id": "cac_paid", "current": 100.0}], "fa.json")
    findings_b = _make_findings(tmp_path, [{"id": "cac_paid", "current": 999.0}], "fb.json")
    index_path = tmp_path / "index.json"

    register_run(_make_record(findings_a, run_id="run_a", dataset_key="dataset_a"), index_path)
    register_run(_make_record(findings_b, run_id="run_b", dataset_key="dataset_b"), index_path)

    reader_a = HistoryReader(index_path, dataset_key="dataset_a")
    results = reader_a.get_metric_history("cac_paid")

    assert len(results) == 1
    assert results[0][1] == 100.0  # only dataset_a value


def test_history_reader_returns_chronological_order(tmp_path):
    index_path = tmp_path / "index.json"
    for i, (run_id, week_start, value) in enumerate([
        ("run_1", "2026-02-10", 50.0),
        ("run_2", "2026-02-24", 75.0),
        ("run_3", "2026-03-03", 90.0),
    ]):
        f = _make_findings(tmp_path, [{"id": "net_revenue", "current": value}], f"f{i}.json")
        register_run(_make_record(f, run_id=run_id, week_start=week_start), index_path)

    reader = HistoryReader(index_path, dataset_key="weekly_data")
    results = reader.get_metric_history("net_revenue")

    week_starts = [r[0] for r in results]
    assert week_starts == sorted(week_starts), "Results must be chronological (oldest first)"
    assert [r[1] for r in results] == [50.0, 75.0, 90.0]


def test_history_reader_respects_n_weeks_limit(tmp_path):
    index_path = tmp_path / "index.json"
    for i in range(6):
        week_start = f"2026-0{i + 1}-01"
        metrics = [{"id": "net_revenue", "current": float(i * 100)}]
        f = _make_findings(tmp_path, metrics, f"f{i}.json")
        register_run(
            _make_record(f, run_id=f"run_{i}", week_start=week_start),
            index_path,
        )

    reader = HistoryReader(index_path, dataset_key="weekly_data")
    results = reader.get_metric_history("net_revenue", n_weeks=3)

    # Should return the 3 most-recent weeks (i=3,4,5) in oldest-first order
    assert len(results) == 3
    assert [r[0] for r in results] == ["2026-04-01", "2026-05-01", "2026-06-01"]
    assert [r[1] for r in results] == [300.0, 400.0, 500.0]


def test_history_reader_skips_missing_findings(tmp_path):
    findings_path = _make_findings(tmp_path, [{"id": "net_revenue", "current": 100.0}])
    index_path = tmp_path / "index.json"
    register_run(_make_record(findings_path), index_path)

    # Delete the findings file to simulate a stale index entry
    findings_path.unlink()

    reader = HistoryReader(index_path, dataset_key="weekly_data")
    results = reader.get_metric_history("net_revenue")

    assert results == []  # entry skipped, no exception


def test_history_reader_skips_missing_metric(tmp_path):
    findings_path = _make_findings(tmp_path, [{"id": "other_metric", "current": 42.0}])
    index_path = tmp_path / "index.json"
    register_run(_make_record(findings_path), index_path)

    reader = HistoryReader(index_path, dataset_key="weekly_data")
    results = reader.get_metric_history("net_revenue")

    assert results == []  # metric absent, entry skipped, no exception


def test_history_reader_before_week_start_filter(tmp_path):
    index_path = tmp_path / "index.json"
    for i, (run_id, week_start, value) in enumerate([
        ("run_1", "2026-02-10", 10.0),
        ("run_2", "2026-02-24", 20.0),
        ("run_3", "2026-03-03", 30.0),
    ]):
        f = _make_findings(tmp_path, [{"id": "net_revenue", "current": value}], f"f{i}.json")
        register_run(_make_record(f, run_id=run_id, week_start=week_start), index_path)

    reader = HistoryReader(index_path, dataset_key="weekly_data")
    results = reader.get_metric_history("net_revenue", before_week_start="2026-03-03")

    # Only runs before 2026-03-03 should be returned
    assert all(r[0] < "2026-03-03" for r in results)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# compute_trends — deterministic trend classification (I6-4)
# ---------------------------------------------------------------------------


def _mock_reader(values: list[float]) -> MagicMock:
    """Build a mock HistoryReader returning the given values as history."""
    reader = MagicMock()
    reader.get_metric_history.return_value = [
        (f"2026-0{i + 1}-01", v) for i, v in enumerate(values)
    ]
    return reader


def _trend(values: list[float], **kwargs) -> TrendResult:
    """Run compute_trends for a single metric and return its result."""
    return compute_trends(_mock_reader(values), ["m"], **kwargs)["m"]


def test_trend_insufficient_history_no_points():
    t = _trend([])
    assert t["trend_label"] == "insufficient_history"
    assert t["weeks_consecutive"] == 0
    assert t["baseline_delta_pct"] is None
    assert t["direction_sequence"] == []


def test_trend_insufficient_history_one_point():
    t = _trend([100.0])
    assert t["trend_label"] == "insufficient_history"
    assert t["baseline_delta_pct"] is None


def test_trend_stable():
    t = _trend([100.0, 101.0, 100.5, 101.0])
    assert t["trend_label"] == "stable"
    assert t["weeks_consecutive"] == 0


def test_trend_stable_requires_min_weeks():
    # Only 2 points — not enough for stable (stable_min_weeks=3)
    t = _trend([100.0, 101.0])
    assert t["trend_label"] != "stable"


def test_trend_rising():
    t = _trend([100.0, 105.0, 110.25, 115.76])
    assert t["trend_label"] == "rising"
    assert t["weeks_consecutive"] >= 2


def test_trend_rising_weeks_consecutive():
    t = _trend([100.0, 105.0, 110.25, 115.76])
    assert t["weeks_consecutive"] == 3


def test_trend_falling():
    t = _trend([100.0, 95.0, 90.0, 85.0])
    assert t["trend_label"] == "falling"
    assert t["weeks_consecutive"] >= 2


def test_trend_recovering():
    t = _trend([100.0, 90.0, 85.0, 91.0])
    assert t["trend_label"] == "recovering"
    assert t["weeks_consecutive"] == 1


def test_trend_volatile():
    t = _trend([100.0, 110.0, 95.0, 108.0, 90.0])
    assert t["trend_label"] == "volatile"
    assert t["weeks_consecutive"] == 0


def test_trend_flat_steps_do_not_break_rising():
    # up, flat, up → non-flat sequence is ["up", "up"] → rising
    t = _trend([100.0, 106.0, 107.0, 114.0])
    assert t["trend_label"] == "rising"


def test_trend_respects_config_thresholds():
    # ~1% changes are clearly within the ±2% stable_band_pct from config
    t = _trend([100.0, 101.0, 102.01, 103.03])
    assert t["trend_label"] == "stable"


def test_compute_trends_empty_metric_list():
    reader = MagicMock()
    result = compute_trends(reader, [])
    assert result == {}
    reader.get_metric_history.assert_not_called()


def test_direction_sequence_generation():
    # 100 → 110 (+10%, up), 110 → 100 (-9%, down) — oldest step first
    t = _trend([100.0, 110.0, 100.0])
    assert t["direction_sequence"] == ["up", "down"]


def test_baseline_delta_pct_calculation():
    # mean=110, current=120 → (120-110)/110
    t = _trend([100.0, 110.0, 120.0])
    assert t["baseline_delta_pct"] is not None
    assert abs(t["baseline_delta_pct"] - (120.0 - 110.0) / 110.0) < 1e-9


def test_insufficient_history_baseline_is_none():
    t = _trend([100.0])
    assert t["baseline_delta_pct"] is None


def test_weeks_consecutive_zero_for_stable():
    t = _trend([100.0, 101.0, 100.5, 101.0])
    if t["trend_label"] == "stable":
        assert t["weeks_consecutive"] == 0


def test_weeks_consecutive_zero_for_volatile():
    t = _trend([100.0, 110.0, 95.0, 108.0, 90.0])
    assert t["trend_label"] == "volatile"
    assert t["weeks_consecutive"] == 0


def test_baseline_average_zero():
    # Values averaging to 0 — baseline_delta_pct must be None, no exception
    t = _trend([-50.0, 0.0, 50.0])
    assert t["baseline_delta_pct"] is None
    assert t["trend_label"] in {
        "rising", "falling", "stable", "recovering", "volatile", "insufficient_history"
    }


def test_history_gap_between_weeks():
    # Non-contiguous week timestamps must not break classification
    reader = MagicMock()
    reader.get_metric_history.return_value = [
        ("2026-01-01", 100.0),
        ("2026-01-15", 110.0),
        ("2026-02-01", 120.0),
    ]
    result = compute_trends(reader, ["m"])
    t = result["m"]
    assert t["trend_label"] != "insufficient_history"
    assert t["direction_sequence"] == ["up", "up"]


def test_history_contains_missing_metric():
    # Metric absent from all historical findings → reader returns []
    reader = MagicMock()
    reader.get_metric_history.return_value = []
    result = compute_trends(reader, ["absent_metric"])
    assert result["absent_metric"]["trend_label"] == "insufficient_history"
    assert result["absent_metric"]["baseline_delta_pct"] is None
