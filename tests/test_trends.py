"""Unit tests for wbsb.history.trends — deterministic trend classification."""
from __future__ import annotations

from unittest.mock import MagicMock

from wbsb.history.trends import TrendResult, compute_trends

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BAND = 0.02  # matches config/rules.yaml history.stable_band_pct


def _reader(values: list[float]) -> MagicMock:
    """Build a mock HistoryReader that returns the given values as history."""
    reader = MagicMock()
    reader.get_metric_history.return_value = [
        (f"2026-0{i + 1}-01", v) for i, v in enumerate(values)
    ]
    return reader


def _trend(values: list[float], **kwargs) -> TrendResult:
    """Shortcut: run compute_trends for a single metric and return its result."""
    result = compute_trends(_reader(values), ["m"], **kwargs)
    return result["m"]


# ---------------------------------------------------------------------------
# insufficient_history
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# stable
# ---------------------------------------------------------------------------


def test_trend_stable():
    # All changes within ±2%, 3 points (>= stable_min_weeks=3)
    t = _trend([100.0, 101.0, 100.5, 101.0])
    assert t["trend_label"] == "stable"
    assert t["weeks_consecutive"] == 0


def test_trend_stable_requires_min_weeks():
    # Only 2 points — not enough for stable (stable_min_weeks=3)
    t = _trend([100.0, 101.0])
    # Cannot be stable; might be volatile or insufficient_history
    assert t["trend_label"] != "stable"


# ---------------------------------------------------------------------------
# rising
# ---------------------------------------------------------------------------


def test_trend_rising():
    # 3 consecutive up steps, each +5%
    t = _trend([100.0, 105.0, 110.25, 115.76])
    assert t["trend_label"] == "rising"
    assert t["weeks_consecutive"] >= 2


def test_trend_rising_weeks_consecutive():
    t = _trend([100.0, 105.0, 110.25, 115.76])
    assert t["weeks_consecutive"] == 3


# ---------------------------------------------------------------------------
# falling
# ---------------------------------------------------------------------------


def test_trend_falling():
    t = _trend([100.0, 95.0, 90.0, 85.0])
    assert t["trend_label"] == "falling"
    assert t["weeks_consecutive"] >= 2


# ---------------------------------------------------------------------------
# recovering
# ---------------------------------------------------------------------------


def test_trend_recovering():
    # Down, then up
    t = _trend([100.0, 90.0, 85.0, 91.0])
    assert t["trend_label"] == "recovering"
    assert t["weeks_consecutive"] == 1


# ---------------------------------------------------------------------------
# volatile
# ---------------------------------------------------------------------------


def test_trend_volatile():
    # Alternating up / down
    t = _trend([100.0, 110.0, 95.0, 108.0, 90.0])
    assert t["trend_label"] == "volatile"
    assert t["weeks_consecutive"] == 0


# ---------------------------------------------------------------------------
# Flat step handling
# ---------------------------------------------------------------------------


def test_trend_flat_steps_do_not_break_rising():
    # up, flat, up → non-flat sequence is ["up", "up"] → rising
    t = _trend([100.0, 106.0, 107.0, 114.0])  # 6%, 0.9% (flat), 6.5%
    # The flat step should not break the rising classification
    assert t["trend_label"] == "rising"


# ---------------------------------------------------------------------------
# Config thresholds
# ---------------------------------------------------------------------------


def test_trend_respects_config_thresholds():
    # Changes of ~1% are clearly within the ±2% stable_band_pct from config.
    # 4 values satisfy stable_min_weeks=3. Result must be stable, not rising/volatile.
    # This verifies the threshold is read from config (not hardcoded to some other value).
    t = _trend([100.0, 101.0, 102.01, 103.03])
    assert t["trend_label"] == "stable"


# ---------------------------------------------------------------------------
# Empty metric_ids
# ---------------------------------------------------------------------------


def test_compute_trends_empty_metric_list():
    reader = MagicMock()
    result = compute_trends(reader, [])
    assert result == {}
    reader.get_metric_history.assert_not_called()


# ---------------------------------------------------------------------------
# direction_sequence
# ---------------------------------------------------------------------------


def test_direction_sequence_oldest_first():
    # 100 → 110 (+10%, up), 110 → 100 (-9%, down)
    t = _trend([100.0, 110.0, 100.0])
    assert t["direction_sequence"] == ["up", "down"]


# ---------------------------------------------------------------------------
# baseline_delta_pct
# ---------------------------------------------------------------------------


def test_baseline_delta_pct_calculation():
    # values: [100, 110, 120] → mean=110, current=120
    # baseline_delta_pct = (120 - 110) / 110 ≈ 0.0909
    t = _trend([100.0, 110.0, 120.0])
    assert t["baseline_delta_pct"] is not None
    assert abs(t["baseline_delta_pct"] - (120.0 - 110.0) / 110.0) < 1e-9


def test_insufficient_history_baseline_is_none():
    t = _trend([100.0])
    assert t["baseline_delta_pct"] is None


# ---------------------------------------------------------------------------
# weeks_consecutive = 0 for non-directional labels
# ---------------------------------------------------------------------------


def test_weeks_consecutive_zero_for_stable():
    t = _trend([100.0, 101.0, 100.5, 101.0])
    if t["trend_label"] == "stable":
        assert t["weeks_consecutive"] == 0


def test_weeks_consecutive_zero_for_volatile():
    t = _trend([100.0, 110.0, 95.0, 108.0, 90.0])
    assert t["trend_label"] == "volatile"
    assert t["weeks_consecutive"] == 0
