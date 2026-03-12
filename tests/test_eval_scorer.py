"""Tests for wbsb.eval.scorer signal coverage."""
from __future__ import annotations

from datetime import UTC, date, datetime

from wbsb.domain.models import (
    Findings,
    LLMResult,
    LLMSignalNarratives,
    Periods,
    RunMeta,
    Signal,
)
from wbsb.eval.scorer import score_signal_coverage


def _findings(signals: list[Signal]) -> Findings:
    return Findings(
        run=RunMeta(
            run_id="run-i7-3",
            generated_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
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
        metrics=[],
        signals=signals,
        audit=[],
    )


def _signal(rule_id: str, category: str) -> Signal:
    return Signal(
        rule_id=rule_id,
        severity="WARN",
        metric_id="net_revenue",
        label="Signal",
        category=category,
        priority=10,
        condition="delta_pct_lte",
        explanation="test",
        evidence={},
    )


def _llm(
    signal_narratives: dict[str, str],
    group_narratives: dict[str, str] | None = None,
) -> LLMResult:
    return LLMResult(
        executive_summary="",
        signal_narratives=LLMSignalNarratives(narratives=signal_narratives),
        model="claude-haiku-4-5-20251001",
        group_narratives=group_narratives,
    )


def test_coverage_all_signals_covered():
    findings = _findings([_signal("A1", "revenue"), _signal("B1", "acquisition")])
    llm_result = _llm({"A1": "a", "B1": "b"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["signal_coverage"] == 1.0


def test_coverage_partial_signals():
    findings = _findings(
        [
            _signal("A1", "revenue"),
            _signal("B1", "acquisition"),
            _signal("C1", "operations"),
        ]
    )
    llm_result = _llm({"A1": "a", "B1": "b"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["signal_coverage"] == 2 / 3


def test_coverage_no_signals():
    findings = _findings([])
    llm_result = _llm({})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["signal_coverage"] == 1.0


def test_group_coverage_all_categories():
    findings = _findings([_signal("A1", "Financial Health"), _signal("B1", "revenue")])
    llm_result = _llm({}, {"financial_health": "ok", "revenue": "ok"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 1.0


def test_group_coverage_partial():
    findings = _findings([_signal("A1", "Financial Health"), _signal("B1", "revenue")])
    llm_result = _llm({}, {"financial_health": "ok"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 0.5


def test_group_coverage_no_categories():
    findings = _findings([])
    llm_result = _llm({}, {})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 1.0
