"""Unit tests for template rendering with optional LLM overlays (Task I4-4)."""
from __future__ import annotations

import re
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
from wbsb.render.template import render_template


def _run_meta() -> RunMeta:
    return RunMeta(
        run_id="test-i4-4",
        generated_at=datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
        input_file="test.csv",
        input_sha256="a" * 64,
        config_sha256="b" * 64,
    )


def _periods() -> Periods:
    return Periods(
        current_week_start=date(2026, 3, 2),
        current_week_end=date(2026, 3, 8),
        previous_week_start=date(2026, 2, 23),
        previous_week_end=date(2026, 3, 1),
    )


def _make_metric(id: str, name: str, current: float, previous: float) -> MetricResult:
    return MetricResult(
        id=id,
        name=name,
        unit="currency",
        format_hint="currency",
        current=current,
        previous=previous,
        delta_abs=current - previous,
        delta_pct=(current - previous) / previous if previous else None,
    )


def _make_signal(
    rule_id: str,
    metric_id: str,
    label: str,
    explanation: str,
    current: float,
    previous: float,
) -> Signal:
    return Signal(
        rule_id=rule_id,
        severity="WARN",
        metric_id=metric_id,
        label=label,
        category="revenue",
        priority=10,
        condition="delta_pct_lte",
        explanation=explanation,
        evidence={
            "current": current,
            "previous": previous,
            "delta_abs": current - previous,
            "delta_pct": (current - previous) / previous if previous else None,
            "threshold": -0.15,
        },
    )


def _make_findings(signals: list[Signal]) -> Findings:
    metrics = []
    for signal in signals:
        metrics.append(
            _make_metric(
                id=signal.metric_id,
                name=f"Metric {signal.metric_id}",
                current=signal.evidence["current"],
                previous=signal.evidence["previous"],
            )
        )
    return Findings(
        run=_run_meta(),
        periods=_periods(),
        metrics=metrics,
        signals=signals,
        audit=[],
    )


def _extract_narrative(md: str, rule_id: str) -> str:
    pattern = rf"### .* \(Rule {re.escape(rule_id)}\)\n\n(.*?)\n\n\*\*Evidence:\*\*"
    match = re.search(pattern, md, flags=re.DOTALL)
    assert match is not None
    return match.group(1).strip()


def test_deterministic_rendering_without_llm_result():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            )
        ]
    )
    rendered = render_template(findings)
    assert "## Executive Summary" not in rendered
    assert _extract_narrative(rendered, "A1")


def test_rendering_with_executive_summary():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            )
        ]
    )
    llm_result = LLMResult(executive_summary="This week revenue softened.")
    rendered = render_template(findings, llm_result=llm_result)
    assert "## Executive Summary" in rendered
    assert "This week revenue softened." in rendered
    assert rendered.index("## Executive Summary") < rendered.index("## Weekly Priorities")


def test_rendering_with_signal_narrative_overrides():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            )
        ]
    )
    baseline = render_template(findings)
    baseline_narrative = _extract_narrative(baseline, "A1")

    llm_result = LLMResult(
        signal_narratives=LLMSignalNarratives(
            narratives={"A1": "LLM A1 narrative replacement."}
        )
    )
    rendered = render_template(findings, llm_result=llm_result)
    assert _extract_narrative(rendered, "A1") == "LLM A1 narrative replacement."
    assert "LLM A1 narrative replacement." in rendered
    assert baseline_narrative != "LLM A1 narrative replacement."


def test_partial_signal_narrative_overrides_only_replace_matching_rules():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            ),
            _make_signal(
                rule_id="B1",
                metric_id="new_mrr",
                label="MRR Decline",
                explanation="deterministic B1 explanation",
                current=2000.0,
                previous=3000.0,
            ),
        ]
    )
    baseline = render_template(findings)
    baseline_b1 = _extract_narrative(baseline, "B1")

    llm_result = LLMResult(
        signal_narratives=LLMSignalNarratives(
            narratives={"A1": "LLM override for A1 only."}
        )
    )
    rendered = render_template(findings, llm_result=llm_result)
    assert _extract_narrative(rendered, "A1") == "LLM override for A1 only."
    assert _extract_narrative(rendered, "B1") == baseline_b1


def test_llm_result_none_fallback_matches_deterministic_render():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            )
        ]
    )
    rendered_default = render_template(findings)
    rendered_none = render_template(findings, llm_result=None)
    assert rendered_none == rendered_default


def test_executive_summary_section_absent_when_summary_missing():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                explanation="deterministic A1 explanation",
                current=8000.0,
                previous=10000.0,
            )
        ]
    )
    llm_result = LLMResult(executive_summary="   ")
    rendered = render_template(findings, llm_result=llm_result)
    assert "## Executive Summary" not in rendered
