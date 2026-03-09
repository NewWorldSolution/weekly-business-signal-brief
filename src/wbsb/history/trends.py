"""Deterministic trend classification engine.

Analyses historical metric values (via HistoryReader) and assigns one of six
trend labels. All threshold values are read from config/rules.yaml — never
hardcoded. No LLM dependency. No pipeline wiring.

Label priority (evaluated top-to-bottom, first match wins):
    1. insufficient_history — fewer than 2 prior data points
    2. stable              — all changes within ±stable_band_pct, min stable_min_weeks points
    3. rising              — last min_consecutive non-flat steps are all "up"
    4. falling             — last min_consecutive non-flat steps are all "down"
    5. recovering          — last non-flat step "up", previous non-flat step "down"
    6. volatile            — none of the above

Flat-step handling:
    A "flat" step (change within ±stable_band_pct) is neutral. Rising/falling/
    recovering labels are derived from the sub-sequence of non-flat steps only.
    Example: ["up", "flat", "up"] → rising (2 consecutive non-flat "up" steps).

weeks_consecutive:
    For rising/falling: count of trailing matching steps in the full
    direction_sequence (stops at first direction change).
    For stable, volatile, insufficient_history, recovering: always 0/1/0.
"""
from __future__ import annotations

import logging
from pathlib import Path
from statistics import mean
from typing import TypedDict

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parents[3] / "config" / "rules.yaml"


def _load_history_config() -> dict:
    with _CONFIG_PATH.open() as f:
        cfg = yaml.safe_load(f)
    section = cfg.get("history")
    if section is None:
        raise KeyError(
            "Required 'history:' section missing from config/rules.yaml. "
            "Run I6-1 task to add it."
        )
    for key in ("n_weeks", "min_consecutive", "stable_band_pct", "stable_min_weeks"):
        if key not in section:
            raise KeyError(
                f"Required config key 'history.{key}' missing from config/rules.yaml."
            )
    return section


_HISTORY_CFG: dict = _load_history_config()

# ---------------------------------------------------------------------------
# TrendResult
# ---------------------------------------------------------------------------


class TrendResult(TypedDict):
    metric_id: str
    trend_label: str              # one of the six labels
    weeks_consecutive: int        # 0 for stable / volatile / insufficient_history
    baseline_delta_pct: float | None  # None for insufficient_history
    direction_sequence: list[str]     # [] for insufficient_history


# ---------------------------------------------------------------------------
# Direction helpers
# ---------------------------------------------------------------------------


def _classify_direction(change: float, band: float) -> str:
    """Return 'up', 'down', or 'flat' for a week-over-week fractional change."""
    if change > band:
        return "up"
    if change < -band:
        return "down"
    return "flat"


def _build_direction_sequence(values: list[float], band: float) -> list[str]:
    """Return per-step direction labels, oldest → newest.

    len(result) == len(values) - 1.
    Skips steps where the previous value is 0 (avoids division by zero)
    and emits a warning.
    """
    sequence: list[str] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev == 0.0:
            logger.warning(
                "trends.direction.zero_prev: skipping step %d (prev value is 0)", i
            )
            continue
        change = (values[i] - prev) / prev
        sequence.append(_classify_direction(change, band))
    return sequence


# ---------------------------------------------------------------------------
# Label classifiers
# ---------------------------------------------------------------------------


def _classify(
    direction_sequence: list[str],
    n_points: int,
    cfg: dict,
) -> tuple[str, int]:
    """Return (trend_label, weeks_consecutive) from direction_sequence.

    Args:
        direction_sequence: oldest → newest list of "up"/"down"/"flat".
        n_points: number of historical data points (len(values)).
        cfg: history config dict.

    Returns:
        (label, weeks_consecutive)
    """
    min_consec = cfg["min_consecutive"]
    stable_min = cfg["stable_min_weeks"]

    # 1. insufficient_history
    if n_points < 2:
        return "insufficient_history", 0

    # 2. stable — all steps within band AND enough observations
    if n_points >= stable_min and all(s == "flat" for s in direction_sequence):
        return "stable", 0

    # Non-flat steps only (used for rising / falling / recovering)
    non_flat = [s for s in direction_sequence if s != "flat"]

    # 3. rising — last min_consec non-flat steps are all "up"
    if len(non_flat) >= min_consec and all(s == "up" for s in non_flat[-min_consec:]):
        # weeks_consecutive: count trailing matching steps in full sequence
        consec = _trailing_count(direction_sequence, "up")
        return "rising", consec

    # 4. falling — last min_consec non-flat steps are all "down"
    if len(non_flat) >= min_consec and all(s == "down" for s in non_flat[-min_consec:]):
        consec = _trailing_count(direction_sequence, "down")
        return "falling", consec

    # 5. recovering — last non-flat = "up", previous non-flat = "down"
    if len(non_flat) >= 2 and non_flat[-1] == "up" and non_flat[-2] == "down":
        return "recovering", 1

    # 6. volatile
    return "volatile", 0


def _trailing_count(sequence: list[str], direction: str) -> int:
    """Count trailing steps in `sequence` that match `direction` (ignoring flat)."""
    count = 0
    for step in reversed(sequence):
        if step == direction:
            count += 1
        elif step != "flat":
            break
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_trends(
    history_reader,
    metric_ids: list[str],
    n_weeks: int | None = None,
) -> dict[str, TrendResult]:
    """Compute deterministic trend labels for a list of metric IDs.

    Args:
        history_reader: HistoryReader already scoped to a dataset_key.
        metric_ids: Metric IDs to classify. Empty list returns {}.
        n_weeks: Lookback window. Defaults to config value when None.

    Returns:
        Dict mapping metric_id → TrendResult. Never raises — returns
        insufficient_history for any metric with sparse or missing data.
    """
    if not metric_ids:
        return {}

    cfg = _HISTORY_CFG
    effective_n_weeks = n_weeks if n_weeks is not None else cfg["n_weeks"]
    band = cfg["stable_band_pct"]

    results: dict[str, TrendResult] = {}

    for metric_id in metric_ids:
        try:
            history = history_reader.get_metric_history(
                metric_id, n_weeks=effective_n_weeks
            )
            values = [v for _, v in history]

            if len(values) < 2:
                results[metric_id] = TrendResult(
                    metric_id=metric_id,
                    trend_label="insufficient_history",
                    weeks_consecutive=0,
                    baseline_delta_pct=None,
                    direction_sequence=[],
                )
                continue

            direction_sequence = _build_direction_sequence(values, band)
            label, consec = _classify(direction_sequence, len(values), cfg)

            baseline = mean(values)
            current = values[-1]
            if baseline == 0.0:
                logger.warning(
                    "trends.baseline.zero: metric_id=%r baseline is 0, "
                    "cannot compute baseline_delta_pct",
                    metric_id,
                )
                baseline_delta_pct: float | None = None
            else:
                baseline_delta_pct = (current - baseline) / baseline

            results[metric_id] = TrendResult(
                metric_id=metric_id,
                trend_label=label,
                weeks_consecutive=consec,
                baseline_delta_pct=baseline_delta_pct,
                direction_sequence=direction_sequence,
            )

        except Exception as exc:
            logger.warning(
                "trends.compute.error: metric_id=%r error=%s — returning insufficient_history",
                metric_id,
                exc,
            )
            results[metric_id] = TrendResult(
                metric_id=metric_id,
                trend_label="insufficient_history",
                weeks_consecutive=0,
                baseline_delta_pct=None,
                direction_sequence=[],
            )

    return results
