"""Unit tests for wbsb.eval.extractor."""
from __future__ import annotations

from datetime import UTC, date, datetime

from wbsb.domain.models import Findings, MetricResult, Periods, RunMeta, Signal
from wbsb.eval.extractor import (
    build_evidence_allowlist,
    candidate_values,
    extract_numbers_from_text,
    is_grounded,
    normalize_number,
)


def _make_findings() -> Findings:
    return Findings(
        run=RunMeta(
            run_id="run-i7-1",
            generated_at=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
            input_file="input.csv",
            input_sha256="a" * 64,
            config_sha256="b" * 64,
        ),
        periods=Periods(
            current_week_start=date(2026, 3, 9),
            current_week_end=date(2026, 3, 15),
            previous_week_start=date(2026, 3, 2),
            previous_week_end=date(2026, 3, 8),
        ),
        metrics=[
            MetricResult(
                id="net_revenue",
                name="Net Revenue",
                unit="currency",
                current=1503.0,
                previous=1400.0,
                delta_abs=103.0,
                delta_pct=0.07357,
            ),
            MetricResult(
                id="show_rate",
                name="Show Rate",
                unit="ratio",
                current=0.4,
                previous=None,
                delta_abs=None,
                delta_pct=None,
            ),
        ],
        signals=[
            Signal(
                rule_id="A1",
                severity="WARN",
                metric_id="net_revenue",
                label="Revenue Decline",
                category="revenue",
                priority=10,
                condition="delta_pct_lte",
                explanation="test",
                evidence={
                    "current": 1503.0,
                    "previous": 1400.0,
                    "delta_abs": 103.0,
                    "delta_pct": 0.07357,
                    "threshold": -0.15,
                },
            )
        ],
        audit=[],
    )


def test_extract_numbers_basic():
    text = "Revenue 120 vs 33.5 baseline"
    assert extract_numbers_from_text(text) == ["120", "33.5"]


def test_extract_numbers_with_percentages():
    text = "Gross margin moved to 40% from 38.5%"
    assert extract_numbers_from_text(text) == ["40%", "38.5%"]


def test_extract_numbers_negative():
    text = "Declined by -0.92 this week"
    assert extract_numbers_from_text(text) == ["-0.92"]


def test_extract_numbers_comma_separated():
    text = "Now at 1,503 this week"
    assert extract_numbers_from_text(text) == ["1,503"]


def test_extract_numbers_skips_dates():
    text = "Period 2024-03-18 to 2024-03-24"
    assert extract_numbers_from_text(text) == []


def test_normalize_number_percent():
    assert normalize_number("40%") == 40.0


def test_normalize_number_invalid():
    assert normalize_number("abc") is None
    assert normalize_number("$") is None


def test_candidate_values_percent_normalization_on():
    assert candidate_values("40%", True) == [40.0, 0.4]


def test_candidate_values_percent_normalization_off():
    assert candidate_values("40%", False) == [40.0]


def test_build_evidence_allowlist():
    findings = _make_findings()
    allowlist = build_evidence_allowlist(findings)
    assert allowlist == {1503.0, 1400.0, 103.0, 0.07357, 0.4, -0.15}


def test_is_grounded_within_abs_tolerance():
    cfg = {
        "grounding_tolerance_abs": 0.01,
        "grounding_tolerance_rel": 0.01,
    }
    assert is_grounded(0.405, {0.4}, cfg) is True


def test_is_grounded_within_rel_tolerance():
    cfg = {
        "grounding_tolerance_abs": 0.01,
        "grounding_tolerance_rel": 0.01,
    }
    assert is_grounded(1510.0, {1503.0}, cfg) is True


def test_is_grounded_false():
    cfg = {
        "grounding_tolerance_abs": 0.01,
        "grounding_tolerance_rel": 0.01,
    }
    assert is_grounded(999.0, {1503.0}, cfg) is False
    assert is_grounded(0.5, set(), cfg) is False
