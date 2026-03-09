"""Unit tests for section-based template rendering (Task I5-4)."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime

from wbsb.domain.models import (
    AuditEvent,
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
        run_id="test-i5-4",
        generated_at=datetime(2026, 3, 9, 12, 0, tzinfo=UTC),
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
        category="revenue",
        category_order=1,
        display_order=1,
        current=current,
        previous=previous,
        delta_abs=current - previous,
        delta_pct=(current - previous) / previous if previous else None,
    )


def _make_signal(
    rule_id: str,
    metric_id: str,
    label: str,
    category: str,
    current: float,
    previous: float,
) -> Signal:
    return Signal(
        rule_id=rule_id,
        severity="WARN",
        metric_id=metric_id,
        label=label,
        category=category,
        priority=10,
        condition="delta_pct_lte",
        explanation=f"{metric_id} changed by threshold",
        evidence={
            "current": current,
            "previous": previous,
            "delta_abs": current - previous,
            "delta_pct": (current - previous) / previous if previous else None,
            "threshold": -0.15,
        },
    )


def _make_findings(
    signals: list[Signal],
    audit: list[AuditEvent] | None = None,
) -> Findings:
    metrics = [
        _make_metric(
            id=signal.metric_id,
            name=f"Metric {signal.metric_id}",
            current=signal.evidence["current"],
            previous=signal.evidence["previous"],
        )
        for signal in signals
    ]
    return Findings(
        run=_run_meta(),
        periods=_periods(),
        metrics=metrics,
        signals=signals,
        audit=audit or [],
    )


def _extract_signal_narrative(md: str, rule_id: str) -> str:
    pattern = rf"### .* \(Rule {re.escape(rule_id)}\)\n\n(.*?)\n\n\*\*Evidence:\*\*"
    match = re.search(pattern, md, flags=re.DOTALL)
    assert match is not None
    return match.group(1).strip()


def _base_findings_with_dominant_cluster() -> Findings:
    return _make_findings(
        [
            _make_signal(
                rule_id="B1",
                metric_id="cac_paid",
                label="CAC Rising",
                category="acquisition",
                current=220.0,
                previous=150.0,
            ),
            _make_signal(
                rule_id="C1",
                metric_id="paid_lead_to_client",
                label="Conversion Falling",
                category="acquisition",
                current=0.60,
                previous=0.80,
            ),
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                category="revenue",
                current=8000.0,
                previous=10000.0,
            ),
        ]
    )


def test_situation_section_renders_when_present():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(situation="Performance softened across key categories.")
    rendered = render_template(findings, llm_result=llm)
    assert "## Situation" in rendered
    assert "Performance softened across key categories." in rendered


def test_situation_section_omitted_when_absent():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(situation="   ")
    rendered = render_template(findings, llm_result=llm)
    assert "## Situation" not in rendered


def test_executive_summary_section_removed():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(executive_summary="Legacy summary text.")
    rendered = render_template(findings, llm_result=llm)
    assert "## Executive Summary" not in rendered
    assert "Legacy summary text." not in rendered


def test_key_story_renders_when_present_and_dominant_cluster_exists():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(key_story="Acquisition signals moved together this week.")
    rendered = render_template(findings, llm_result=llm)
    assert "## Key Story This Week" in rendered
    assert "Acquisition signals moved together this week." in rendered


def test_key_story_omitted_when_absent():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(key_story=None)
    rendered = render_template(findings, llm_result=llm)
    assert "## Key Story This Week" not in rendered


def test_key_story_omitted_when_dominant_cluster_does_not_exist():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="B1",
                metric_id="cac_paid",
                label="CAC Rising",
                category="acquisition",
                current=220.0,
                previous=150.0,
            ),
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                category="revenue",
                current=8000.0,
                previous=10000.0,
            ),
        ]
    )
    llm = LLMResult(key_story="This should be hidden.")
    rendered = render_template(findings, llm_result=llm)
    assert "## Key Story This Week" not in rendered
    assert "This should be hidden." not in rendered


def test_group_narrative_renders_only_for_categories_present():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(
        group_narratives={
            "acquisition": "Acquisition movements co-occurred.",
            "financial_health": "This category is absent in findings.",
        }
    )
    rendered = render_template(findings, llm_result=llm)
    assert "Acquisition movements co-occurred." in rendered
    assert "This category is absent in findings." not in rendered


def test_group_narrative_omitted_when_missing():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(group_narratives={"revenue": "Revenue cluster text."})
    rendered = render_template(findings, llm_result=llm)
    assert "Revenue cluster text." in rendered
    assert "Acquisition movements co-occurred." not in rendered


def test_signal_narrative_override_still_works_with_fallback():
    findings = _base_findings_with_dominant_cluster()
    baseline = render_template(findings)
    baseline_a1 = _extract_signal_narrative(baseline, "A1")
    baseline_c1 = _extract_signal_narrative(baseline, "C1")

    llm = LLMResult(
        signal_narratives=LLMSignalNarratives(
            narratives={"A1": "LLM override for revenue rule."}
        )
    )
    rendered = render_template(findings, llm_result=llm)
    assert _extract_signal_narrative(rendered, "A1") == "LLM override for revenue rule."
    assert _extract_signal_narrative(rendered, "C1") == baseline_c1
    assert baseline_a1 != "LLM override for revenue rule."


def test_watch_next_week_renders_when_present():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(
        watch_signals=[
            {"metric_or_signal": "cac_paid", "observation": "Upward movement persisted."},
            {"metric_or_signal": "A1", "observation": "Revenue remained below prior week."},
            {"metric_or_signal": "ignored", "observation": "Should be capped at 2."},
        ]
    )
    rendered = render_template(findings, llm_result=llm)
    assert "## Watch Next Week" in rendered
    assert "- cac_paid — Upward movement persisted." in rendered
    assert "- A1 — Revenue remained below prior week." in rendered
    assert "Should be capped at 2." not in rendered


def test_watch_next_week_omitted_when_absent():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(watch_signals=[])
    rendered = render_template(findings, llm_result=llm)
    assert "## Watch Next Week" not in rendered


def test_deterministic_fallback_valid_when_llm_result_none():
    findings = _base_findings_with_dominant_cluster()
    rendered = render_template(findings, llm_result=None)
    assert "## Weekly Priorities" in rendered
    assert "## Signals (" in rendered
    assert "## Situation" not in rendered
    assert "## Key Story This Week" not in rendered
    assert "## Watch Next Week" not in rendered


def test_metrics_snapshot_and_audit_remain_unchanged():
    findings = _make_findings(
        [
            _make_signal(
                rule_id="A1",
                metric_id="net_revenue",
                label="Revenue Decline",
                category="revenue",
                current=8000.0,
                previous=10000.0,
            )
        ],
        audit=[AuditEvent(event_type="coercion", message="Converted column to numeric.")],
    )
    llm = LLMResult(
        situation="Business softened this week.",
        key_story="Revenue changes were the central movement.",
    )
    rendered = render_template(findings, llm_result=llm)
    assert "## Key Metrics" in rendered
    assert "| Metric | Current | Previous | Δ % |" in rendered
    assert "## Audit" in rendered
    assert "Converted column to numeric." in rendered


def test_no_empty_extra_sections_when_llm_fields_absent():
    findings = _base_findings_with_dominant_cluster()
    llm = LLMResult(
        situation="   ",
        key_story="   ",
        group_narratives={},
        watch_signals=[{"metric_or_signal": " ", "observation": " "}],
    )
    rendered = render_template(findings, llm_result=llm)
    assert "## Situation" not in rendered
    assert "## Key Story This Week" not in rendered
    assert "## Watch Next Week" not in rendered
