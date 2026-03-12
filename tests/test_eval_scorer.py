"""Tests for wbsb.eval.scorer signal coverage."""
from __future__ import annotations

from datetime import UTC, date, datetime

from wbsb.domain.models import (
    Findings,
    LLMResult,
    LLMSignalNarratives,
    MetricResult,
    Periods,
    RunMeta,
    Signal,
)
from wbsb.eval.scorer import score_hallucination, score_signal_coverage


def _findings(
    signals: list[Signal],
    metrics: list[MetricResult] | None = None,
    dominant_cluster_exists: bool = False,
) -> Findings:
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
        metrics=metrics if metrics is not None else [],
        signals=signals,
        dominant_cluster_exists=dominant_cluster_exists,
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
    llm_result = _llm({}, {"Financial Health": "ok", "revenue": "ok"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 1.0


def test_group_coverage_partial():
    findings = _findings([_signal("A1", "Financial Health"), _signal("B1", "revenue")])
    llm_result = _llm({}, {"Financial Health": "ok"})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 0.5


def test_group_coverage_no_categories():
    findings = _findings([])
    llm_result = _llm({}, {})

    scores = score_signal_coverage(findings, llm_result)

    assert scores["group_coverage"] == 1.0


def test_hallucination_clean_output():
    findings = _findings(
        [_signal("A1", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=True,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        key_story="ok",
        signal_narratives=LLMSignalNarratives(narratives={"A1": "text"}),
        group_narratives={"revenue": "group text"},
        watch_signals=[{"metric_or_signal": "A1", "observation": "watch"}],
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 0
    assert result["hallucination_violations"] == []


def test_hallucination_key_story_no_cluster():
    findings = _findings([], dominant_cluster_exists=False)
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        key_story="Some key story text",
        signal_narratives=LLMSignalNarratives(narratives={}),
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 1
    assert result["hallucination_violations"][0]["type"] == "key_story_when_no_cluster"
    assert result["hallucination_violations"][0]["severity"] == "critical"


def test_hallucination_invalid_watch_signal():
    findings = _findings(
        [_signal("A1", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=True,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        signal_narratives=LLMSignalNarratives(narratives={"A1": "text"}),
        group_narratives={"revenue": "group text"},
        watch_signals=[{"metric_or_signal": "nonexistent_id", "observation": "watch"}],
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 1
    v = result["hallucination_violations"][0]
    assert v["type"] == "invalid_watch_signal_id"
    assert v["severity"] == "major"
    assert "nonexistent_id" in v["detail"]


def test_hallucination_invalid_group_category():
    findings = _findings(
        [_signal("A1", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=True,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        signal_narratives=LLMSignalNarratives(narratives={"A1": "text"}),
        group_narratives={"Nonexistent Category": "some text"},
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 1
    v = result["hallucination_violations"][0]
    assert v["type"] == "invalid_group_narrative_category"
    assert v["severity"] == "major"


def test_hallucination_extra_signal_narrative():
    findings = _findings(
        [_signal("A1", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=True,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        signal_narratives=LLMSignalNarratives(narratives={"rule_not_in_findings": "..."}),
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 2
    assert result["hallucination_violations"][0]["type"] == "extra_signal_narrative"
    assert result["hallucination_violations"][0]["severity"] == "minor"


def test_hallucination_missing_signal_narrative():
    findings = _findings(
        [_signal("missing_rule", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=True,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        signal_narratives=LLMSignalNarratives(narratives={}),
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == 1
    v = result["hallucination_violations"][0]
    assert v["type"] == "missing_signal_narrative"
    assert v["severity"] == "minor"
    assert "missing_rule" in v["detail"]


def test_hallucination_multiple_violations():
    findings = _findings(
        [_signal("A1", "Revenue")],
        [MetricResult(id="net_revenue", name="n", unit="u")],
        dominant_cluster_exists=False,
    )
    llm_result = LLMResult(
        executive_summary="",
        model="claude-haiku-4-5-20251001",
        key_story="Some key story text",
        signal_narratives=LLMSignalNarratives(narratives={"extra_rule": "text"}),
    )

    result = score_hallucination(findings, llm_result)

    assert result["hallucination_risk"] == len(result["hallucination_violations"])
    assert result["hallucination_risk"] == 3
    assert {v["type"] for v in result["hallucination_violations"]} == {
        "key_story_when_no_cluster",
        "extra_signal_narrative",
        "missing_signal_narrative",
    }
