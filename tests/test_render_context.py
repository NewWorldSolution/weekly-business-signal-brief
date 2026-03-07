"""Unit tests for the render context preparation layer (Task 2)."""
from __future__ import annotations

from datetime import UTC, date, datetime

from wbsb.domain.models import (
    AuditEvent,
    Findings,
    MetricResult,
    Periods,
    RunMeta,
    Signal,
)
from wbsb.render.context import (
    CATEGORY_LABELS,
    _build_narrative,
    _build_narrative_inputs,
    _resolve_threshold_hint,
    prepare_render_context,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_NARRATIVE_INPUT_KEYS = {
    "metric_name",
    "metric_id",
    "condition",
    "direction",
    "current_value",
    "previous_value",
    "delta_pct",
    "delta_abs",
    "threshold",
    "threshold_pct",
    "threshold_abs",
    "category",
    "category_display",
    "severity",
    "priority",
    "label",
    "rule_id",
}

REQUIRED_SIGNAL_CONTEXT_KEYS = {
    "signal",
    "category",
    "metric",
    "format_hint",
    "threshold_hint",
    "narrative",
    "narrative_inputs",
}

REQUIRED_CONTEXT_KEYS = {
    "findings",
    "warn_count",
    "info_count",
    "top_warn",
    "affected_categories",
    "category_labels",
    "metric_by_id",
    "signal_contexts",
}


def _run_meta() -> RunMeta:
    return RunMeta(
        run_id="test-run-001",
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
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


def make_metric(
    id: str = "net_revenue",
    name: str = "Net Revenue",
    format_hint: str = "currency",
    current: float = 8000.0,
    previous: float = 10000.0,
) -> MetricResult:
    return MetricResult(
        id=id,
        name=name,
        unit="currency",
        format_hint=format_hint,
        current=current,
        previous=previous,
        delta_abs=current - previous,
        delta_pct=(current - previous) / previous if previous else None,
    )


def make_signal(
    rule_id: str = "A1",
    metric_id: str = "net_revenue",
    condition: str = "delta_pct_lte",
    evidence: dict | None = None,
    explanation: str = "net_revenue changed -20.0% (threshold: ≤-15.0%)",
    category: str = "revenue",
    label: str = "Revenue Decline",
    severity: str = "WARN",
    priority: int = 10,
) -> Signal:
    if evidence is None:
        evidence = {
            "current": 8000.0,
            "previous": 10000.0,
            "delta_abs": -2000.0,
            "delta_pct": -0.20,
            "threshold": -0.15,
        }
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id=metric_id,
        label=label,
        category=category,
        priority=priority,
        condition=condition,
        explanation=explanation,
        evidence=evidence,
    )


def make_findings(
    signals: list[Signal] | None = None,
    metrics: list[MetricResult] | None = None,
    audit: list[AuditEvent] | None = None,
) -> Findings:
    return Findings(
        run=_run_meta(),
        periods=_periods(),
        metrics=metrics if metrics is not None else [make_metric()],
        signals=signals if signals is not None else [],
        audit=audit if audit is not None else [],
    )


# ---------------------------------------------------------------------------
# Threshold hint resolution
# ---------------------------------------------------------------------------


class TestResolveThresholdHint:
    def test_delta_pct_lte_returns_percent(self):
        signal = make_signal(condition="delta_pct_lte")
        metric = make_metric(format_hint="currency")  # metric unit is irrelevant
        assert _resolve_threshold_hint(signal, metric) == "percent"

    def test_delta_pct_gte_returns_percent(self):
        signal = make_signal(
            rule_id="B1",
            metric_id="cac_paid",
            condition="delta_pct_gte",
            evidence={
                "current": 250.0,
                "previous": 200.0,
                "delta_abs": 50.0,
                "delta_pct": 0.25,
                "threshold": 0.20,
            },
            label="CAC Rising",
        )
        metric = make_metric(id="cac_paid", name="CAC (Paid)", format_hint="currency")
        # Even though cac_paid is currency, threshold for delta_pct_gte must be percent
        assert _resolve_threshold_hint(signal, metric) == "percent"

    def test_absolute_lt_returns_metric_hint(self):
        signal = make_signal(
            rule_id="H1",
            metric_id="gross_margin",
            condition="absolute_lt",
            evidence={
                "current": 0.45,
                "previous": 0.55,
                "delta_abs": -0.10,
                "delta_pct": -0.18,
                "threshold": 0.50,
            },
            label="Gross Margin Below Threshold",
        )
        metric = make_metric(id="gross_margin", name="Gross Margin", format_hint="percent")
        assert _resolve_threshold_hint(signal, metric) == "percent"

    def test_absolute_gt_returns_metric_hint(self):
        signal = make_signal(
            rule_id="H2",
            metric_id="marketing_pct_revenue",
            condition="absolute_gt",
            evidence={
                "current": 0.45,
                "previous": 0.35,
                "delta_abs": 0.10,
                "delta_pct": 0.28,
                "threshold": 0.40,
            },
            label="Marketing Spend Overweight",
        )
        metric = make_metric(
            id="marketing_pct_revenue",
            name="Marketing % of Revenue",
            format_hint="percent",
        )
        assert _resolve_threshold_hint(signal, metric) == "percent"

    def test_fallback_when_metric_missing_delta_pct(self):
        signal = make_signal(condition="delta_pct_lte")
        assert _resolve_threshold_hint(signal, None) == "percent"

    def test_fallback_when_metric_missing_absolute(self):
        signal = make_signal(
            condition="absolute_lt",
            evidence={
                "current": 0.45,
                "previous": 0.55,
                "delta_abs": -0.10,
                "delta_pct": -0.18,
                "threshold": 0.50,
            },
        )
        assert _resolve_threshold_hint(signal, None) == "decimal"

    def test_hybrid_pct_mode_returns_percent(self):
        """High-volume hybrid: pct mode fired — threshold display should be percent."""
        signal = make_signal(
            rule_id="F1",
            metric_id="bookings_total",
            condition="hybrid_delta_pct_lte",
            evidence={
                "current": 40.0,
                "previous": 51.0,
                "delta_abs": -11.0,
                "delta_pct": -0.2157,
                "threshold_pct": -0.20,
                "threshold_abs": -3,
            },
            # No "low-volume mode" in explanation → pct mode
            explanation="bookings_total changed -21.6% (threshold: ≤-20.0%)",
            label="Bookings Volume Falling",
        )
        metric = make_metric(
            id="bookings_total", name="Total Bookings", format_hint="integer"
        )
        assert _resolve_threshold_hint(signal, metric) == "percent"

    def test_hybrid_abs_mode_returns_metric_hint(self):
        """Low-volume hybrid: abs mode fired — threshold display uses metric's hint."""
        signal = make_signal(
            rule_id="F1",
            metric_id="bookings_total",
            condition="hybrid_delta_pct_lte",
            evidence={
                "current": 1.0,
                "previous": 4.0,
                "delta_abs": -3.0,
                "delta_pct": -0.75,
                "threshold_pct": -0.20,
                "threshold_abs": -3,
            },
            explanation="bookings_total dropped by -3 (absolute threshold: ≤-3, low-volume mode)",
            label="Bookings Volume Falling",
        )
        metric = make_metric(
            id="bookings_total", name="Total Bookings", format_hint="integer"
        )
        assert _resolve_threshold_hint(signal, metric) == "integer"


# ---------------------------------------------------------------------------
# Narrative construction
# ---------------------------------------------------------------------------


class TestBuildNarrative:
    def test_delta_pct_lte_uses_display_name(self):
        signal = make_signal(condition="delta_pct_lte")
        metric = make_metric(name="Net Revenue")
        narrative = _build_narrative(signal, metric)
        assert "Net Revenue" in narrative
        assert "net_revenue" not in narrative

    def test_delta_pct_gte_uses_display_name(self):
        signal = make_signal(
            condition="delta_pct_gte",
            evidence={
                "current": 250.0,
                "previous": 200.0,
                "delta_abs": 50.0,
                "delta_pct": 0.25,
                "threshold": 0.20,
            },
        )
        metric = make_metric(name="CAC (Paid)", format_hint="currency")
        narrative = _build_narrative(signal, metric)
        assert "CAC (Paid)" in narrative
        assert "net_revenue" not in narrative

    def test_absolute_lt_uses_display_name(self):
        signal = make_signal(
            condition="absolute_lt",
            evidence={
                "current": 0.45,
                "previous": 0.55,
                "delta_abs": -0.10,
                "delta_pct": -0.18,
                "threshold": 0.50,
            },
        )
        metric = make_metric(name="Gross Margin", format_hint="percent")
        narrative = _build_narrative(signal, metric)
        assert "Gross Margin" in narrative
        assert "net_revenue" not in narrative

    def test_absolute_gt_uses_display_name(self):
        signal = make_signal(
            condition="absolute_gt",
            evidence={
                "current": 0.45,
                "previous": 0.35,
                "delta_abs": 0.10,
                "delta_pct": 0.28,
                "threshold": 0.40,
            },
        )
        metric = make_metric(name="Marketing % of Revenue", format_hint="percent")
        narrative = _build_narrative(signal, metric)
        assert "Marketing % of Revenue" in narrative

    def test_no_snake_case_in_narrative_with_metric(self):
        signal = make_signal(condition="delta_pct_lte")
        metric = make_metric(id="net_revenue", name="Net Revenue")
        narrative = _build_narrative(signal, metric)
        assert "_" not in narrative

    def test_delta_pct_lte_declining_wording(self):
        signal = make_signal(
            condition="delta_pct_lte",
            evidence={
                "current": 8000.0,
                "previous": 10000.0,
                "delta_abs": -2000.0,
                "delta_pct": -0.20,
                "threshold": -0.15,
            },
        )
        metric = make_metric(name="Net Revenue")
        narrative = _build_narrative(signal, metric)
        assert "20.0%" in narrative
        assert "declined" in narrative

    def test_hybrid_abs_mode_narrative(self):
        signal = make_signal(
            condition="hybrid_delta_pct_lte",
            evidence={
                "current": 1.0,
                "previous": 4.0,
                "delta_abs": -3.0,
                "delta_pct": -0.75,
                "threshold_pct": -0.20,
                "threshold_abs": -3,
            },
            explanation="bookings_total dropped by -3 (absolute threshold: ≤-3, low-volume mode)",
        )
        metric = make_metric(id="bookings_total", name="Total Bookings", format_hint="integer")
        narrative = _build_narrative(signal, metric)
        assert "Total Bookings" in narrative
        assert "bookings_total" not in narrative
        assert "low-volume" in narrative.lower()

    def test_hybrid_pct_mode_narrative(self):
        signal = make_signal(
            condition="hybrid_delta_pct_lte",
            evidence={
                "current": 40.0,
                "previous": 51.0,
                "delta_abs": -11.0,
                "delta_pct": -0.2157,
                "threshold_pct": -0.20,
                "threshold_abs": -3,
            },
            explanation="bookings_total changed -21.6% (threshold: ≤-20.0%)",
        )
        metric = make_metric(id="bookings_total", name="Total Bookings", format_hint="integer")
        narrative = _build_narrative(signal, metric)
        assert "Total Bookings" in narrative
        assert "%" in narrative
        assert "bookings_total" not in narrative

    def test_narrative_without_metric_does_not_expose_raw_id(self):
        """When metric is None, narrative should still not expose snake_case IDs directly."""
        signal = make_signal(condition="absolute_lt")
        narrative = _build_narrative(signal, None)
        # Falls back to title-cased version — not ideal but not a snake_case leak
        assert "net_revenue" not in narrative


# ---------------------------------------------------------------------------
# Narrative inputs
# ---------------------------------------------------------------------------


class TestBuildNarrativeInputs:
    def test_contains_required_keys(self):
        signal = make_signal()
        metric = make_metric()
        inputs = _build_narrative_inputs(signal, metric)
        assert REQUIRED_NARRATIVE_INPUT_KEYS.issubset(inputs.keys())

    def test_values_are_raw_not_formatted(self):
        signal = make_signal(
            evidence={
                "current": 8000.0,
                "previous": 10000.0,
                "delta_abs": -2000.0,
                "delta_pct": -0.20,
                "threshold": -0.15,
            }
        )
        metric = make_metric()
        inputs = _build_narrative_inputs(signal, metric)
        assert inputs["current_value"] == 8000.0
        assert inputs["previous_value"] == 10000.0
        assert inputs["delta_pct"] == -0.20
        assert inputs["threshold"] == -0.15
        # Values must be numeric, not strings
        assert isinstance(inputs["current_value"], float)
        assert isinstance(inputs["delta_pct"], float)

    def test_metric_name_present_when_metric_available(self):
        signal = make_signal()
        metric = make_metric(name="Net Revenue")
        inputs = _build_narrative_inputs(signal, metric)
        assert inputs["metric_name"] == "Net Revenue"

    def test_metric_name_none_when_metric_missing(self):
        signal = make_signal()
        inputs = _build_narrative_inputs(signal, None)
        assert inputs["metric_name"] is None

    def test_threshold_keys_for_hybrid(self):
        signal = make_signal(
            condition="hybrid_delta_pct_lte",
            evidence={
                "current": 40.0,
                "previous": 51.0,
                "delta_abs": -11.0,
                "delta_pct": -0.2157,
                "threshold_pct": -0.20,
                "threshold_abs": -3,
            },
            explanation="bookings_total changed -21.6% (threshold: ≤-20.0%)",
        )
        metric = make_metric(id="bookings_total", name="Total Bookings", format_hint="integer")
        inputs = _build_narrative_inputs(signal, metric)
        assert inputs["threshold"] is None  # not in evidence for hybrid
        assert inputs["threshold_pct"] == -0.20
        assert inputs["threshold_abs"] == -3

    def test_category_display_uses_category_labels(self):
        signal = make_signal(category="financial_health")
        metric = make_metric()
        inputs = _build_narrative_inputs(signal, metric)
        assert inputs["category"] == "financial_health"
        assert inputs["category_display"] == "Financial Health"


# ---------------------------------------------------------------------------
# prepare_render_context
# ---------------------------------------------------------------------------


class TestPrepareRenderContext:
    def test_returns_required_top_level_keys(self):
        findings = make_findings()
        ctx = prepare_render_context(findings)
        assert REQUIRED_CONTEXT_KEYS.issubset(ctx.keys())

    def test_warn_count_and_info_count(self):
        warn = make_signal(rule_id="A1", severity="WARN")
        info = make_signal(rule_id="A2", severity="INFO")
        findings = make_findings(signals=[warn, info])
        ctx = prepare_render_context(findings)
        assert ctx["warn_count"] == 1
        assert ctx["info_count"] == 1

    def test_top_warn_is_first_warn_signal(self):
        warn1 = make_signal(rule_id="A1", severity="WARN", label="First")
        warn2 = make_signal(rule_id="A2", severity="WARN", label="Second")
        findings = make_findings(signals=[warn1, warn2])
        ctx = prepare_render_context(findings)
        assert ctx["top_warn"].rule_id == "A1"

    def test_top_warn_none_when_no_warn(self):
        info = make_signal(rule_id="Z1", severity="INFO")
        findings = make_findings(signals=[info])
        ctx = prepare_render_context(findings)
        assert ctx["top_warn"] is None

    def test_metric_by_id_built_correctly(self):
        m1 = make_metric(id="net_revenue", name="Net Revenue")
        m2 = make_metric(id="gross_margin", name="Gross Margin", format_hint="percent")
        findings = make_findings(metrics=[m1, m2])
        ctx = prepare_render_context(findings)
        assert ctx["metric_by_id"]["net_revenue"].name == "Net Revenue"
        assert ctx["metric_by_id"]["gross_margin"].name == "Gross Margin"

    def test_signal_contexts_contain_required_keys(self):
        signal = make_signal()
        findings = make_findings(signals=[signal])
        ctx = prepare_render_context(findings)
        assert len(ctx["signal_contexts"]) == 1
        sc = ctx["signal_contexts"][0]
        assert REQUIRED_SIGNAL_CONTEXT_KEYS.issubset(sc.keys())

    def test_signal_contexts_length_matches_signals(self):
        signals = [
            make_signal(rule_id="A1", label="First"),
            make_signal(rule_id="A2", label="Second"),
        ]
        findings = make_findings(signals=signals)
        ctx = prepare_render_context(findings)
        assert len(ctx["signal_contexts"]) == 2

    def test_category_labels_in_context(self):
        findings = make_findings()
        ctx = prepare_render_context(findings)
        assert ctx["category_labels"] == CATEGORY_LABELS

    def test_is_pure_same_findings_same_context(self):
        findings = make_findings(signals=[make_signal()])
        ctx1 = prepare_render_context(findings)
        ctx2 = prepare_render_context(findings)
        assert ctx1["warn_count"] == ctx2["warn_count"]
        assert ctx1["signal_contexts"][0]["narrative"] == ctx2["signal_contexts"][0]["narrative"]


# ---------------------------------------------------------------------------
# Threshold formatting correctness (the bug fix)
# ---------------------------------------------------------------------------


class TestThresholdFormattingFix:
    """Verify the threshold bug (delta_pct threshold rendered with metric hint) is fixed."""

    def test_a1_threshold_hint_is_percent_not_currency(self):
        """A1: net_revenue delta_pct_lte rule — threshold must render as percent."""
        signal = make_signal(
            rule_id="A1",
            metric_id="net_revenue",
            condition="delta_pct_lte",
            evidence={
                "current": 8500.0,
                "previous": 10000.0,
                "delta_abs": -1500.0,
                "delta_pct": -0.15,
                "threshold": -0.15,
            },
        )
        metric = make_metric(id="net_revenue", name="Net Revenue", format_hint="currency")
        hint = _resolve_threshold_hint(signal, metric)
        # threshold=-0.15, hint='currency' → would render as 0 (BUG)
        # threshold=-0.15, hint='percent'  → renders as -15.0%  (CORRECT)
        assert hint == "percent"

    def test_b1_threshold_hint_is_percent_not_currency(self):
        """B1: cac_paid delta_pct_gte rule — threshold must render as percent."""
        signal = make_signal(
            rule_id="B1",
            metric_id="cac_paid",
            condition="delta_pct_gte",
            evidence={
                "current": 250.0,
                "previous": 200.0,
                "delta_abs": 50.0,
                "delta_pct": 0.25,
                "threshold": 0.20,
            },
            label="CAC Rising",
        )
        metric = make_metric(id="cac_paid", name="CAC (Paid)", format_hint="currency")
        hint = _resolve_threshold_hint(signal, metric)
        # threshold=0.20, hint='currency' → would render as 0 (BUG)
        # threshold=0.20, hint='percent'  → renders as 20.0% (CORRECT)
        assert hint == "percent"

    def test_h1_threshold_hint_is_percent_matches_metric(self):
        """H1: gross_margin absolute_lt rule — threshold uses metric's percent hint."""
        signal = make_signal(
            rule_id="H1",
            metric_id="gross_margin",
            condition="absolute_lt",
            evidence={
                "current": 0.45,
                "previous": 0.55,
                "delta_abs": -0.10,
                "delta_pct": -0.18,
                "threshold": 0.50,
            },
            label="Gross Margin Below Threshold",
        )
        metric = make_metric(id="gross_margin", name="Gross Margin", format_hint="percent")
        hint = _resolve_threshold_hint(signal, metric)
        # threshold=0.50, hint='percent' → renders as 50.0% (correct for gross margin)
        assert hint == "percent"


# ---------------------------------------------------------------------------
# top_signals
# ---------------------------------------------------------------------------


class TestTopSignals:
    def test_top_signals_capped_at_three(self):
        signals = [
            make_signal(rule_id=f"W{i}", label=f"Signal {i}", severity="WARN")
            for i in range(5)
        ]
        findings = make_findings(signals=signals)
        ctx = prepare_render_context(findings)
        assert len(ctx["top_signals"]) == 3

    def test_top_signals_warn_only(self):
        warn1 = make_signal(rule_id="A1", severity="WARN", label="Warn One")
        warn2 = make_signal(rule_id="A2", severity="WARN", label="Warn Two")
        info = make_signal(rule_id="Z1", severity="INFO", label="Info One")
        # Signals list: two WARNs then one INFO
        findings = make_findings(signals=[warn1, warn2, info])
        ctx = prepare_render_context(findings)
        assert all(s.severity == "WARN" for s in ctx["top_signals"])

    def test_top_signals_empty_when_no_warn(self):
        info = make_signal(rule_id="Z1", severity="INFO")
        findings = make_findings(signals=[info])
        ctx = prepare_render_context(findings)
        assert ctx["top_signals"] == []

    def test_top_signals_preserves_engine_order(self):
        """top_signals must reflect the order signals appear in findings.signals."""
        w1 = make_signal(rule_id="A1", severity="WARN", label="First")
        w2 = make_signal(rule_id="B1", severity="WARN", label="Second")
        w3 = make_signal(rule_id="C1", severity="WARN", label="Third")
        w4 = make_signal(rule_id="D1", severity="WARN", label="Fourth")
        findings = make_findings(signals=[w1, w2, w3, w4])
        ctx = prepare_render_context(findings)
        rule_ids = [s.rule_id for s in ctx["top_signals"]]
        assert rule_ids == ["A1", "B1", "C1"]

    def test_top_signals_fewer_than_three(self):
        w1 = make_signal(rule_id="A1", severity="WARN")
        findings = make_findings(signals=[w1])
        ctx = prepare_render_context(findings)
        assert len(ctx["top_signals"]) == 1
        assert ctx["top_signals"][0].rule_id == "A1"


# ---------------------------------------------------------------------------
# severity_by_category
# ---------------------------------------------------------------------------


class TestSeverityByCategory:
    def test_severity_by_category_counts_warn_only(self):
        warn = make_signal(rule_id="A1", severity="WARN", category="revenue")
        info = make_signal(rule_id="Z1", severity="INFO", category="revenue")
        findings = make_findings(signals=[warn, info])
        ctx = prepare_render_context(findings)
        # INFO must not be counted
        assert ctx["severity_by_category"] == {"Revenue": 1}

    def test_severity_by_category_empty_when_no_warn(self):
        info = make_signal(rule_id="Z1", severity="INFO", category="revenue")
        findings = make_findings(signals=[info])
        ctx = prepare_render_context(findings)
        assert ctx["severity_by_category"] == {}

    def test_severity_by_category_counts_correctly(self):
        signals = [
            make_signal(rule_id="A1", severity="WARN", category="revenue"),
            make_signal(rule_id="H1", severity="WARN", category="financial_health"),
            make_signal(rule_id="H2", severity="WARN", category="financial_health"),
            make_signal(rule_id="B1", severity="WARN", category="acquisition"),
        ]
        findings = make_findings(signals=signals)
        ctx = prepare_render_context(findings)
        sbc = ctx["severity_by_category"]
        assert sbc["Revenue"] == 1
        assert sbc["Financial Health"] == 2
        assert sbc["Acquisition"] == 1

    def test_severity_by_category_uses_display_labels(self):
        """Category keys must be human-readable display labels, not raw IDs."""
        signals = [
            make_signal(rule_id="A1", severity="WARN", category="revenue"),
            make_signal(rule_id="H1", severity="WARN", category="financial_health"),
            make_signal(rule_id="F1", severity="WARN", category="operations"),
        ]
        findings = make_findings(signals=signals)
        ctx = prepare_render_context(findings)
        sbc = ctx["severity_by_category"]
        assert "revenue" not in sbc
        assert "financial_health" not in sbc
        assert "operations" not in sbc
        assert "Revenue" in sbc
        assert "Financial Health" in sbc
        assert "Operations" in sbc

    def test_severity_by_category_order_is_deterministic(self):
        """Order must match first appearance of category in WARN signal sequence."""
        signals = [
            make_signal(rule_id="A1", severity="WARN", category="revenue"),
            make_signal(rule_id="H1", severity="WARN", category="financial_health"),
            make_signal(rule_id="H2", severity="WARN", category="financial_health"),
            make_signal(rule_id="B1", severity="WARN", category="acquisition"),
            make_signal(rule_id="F1", severity="WARN", category="operations"),
        ]
        findings = make_findings(signals=signals)
        ctx = prepare_render_context(findings)
        keys = list(ctx["severity_by_category"].keys())
        assert keys == ["Revenue", "Financial Health", "Acquisition", "Operations"]


# ---------------------------------------------------------------------------
# Template surface: narrative not explanation
# ---------------------------------------------------------------------------


class TestTemplateSurface:
    """Verify the signal_context narrative is used, not signal.explanation."""

    def test_signal_context_narrative_differs_from_explanation(self):
        """narrative is human-readable; explanation is the technical audit string."""
        signal = make_signal(
            condition="delta_pct_lte",
            explanation="net_revenue changed -20.0% (threshold: ≤-15.0%)",
        )
        metric = make_metric(name="Net Revenue")
        findings = make_findings(signals=[signal], metrics=[metric])
        ctx = prepare_render_context(findings)
        sc = ctx["signal_contexts"][0]
        # narrative should not equal the raw technical explanation
        assert sc["narrative"] != signal.explanation
        # narrative should use the human-readable metric name
        assert "Net Revenue" in sc["narrative"]

    def test_signal_context_exposes_signal_for_template_access(self):
        """Template still needs sc.signal for rule_id, label, evidence, etc."""
        signal = make_signal()
        findings = make_findings(signals=[signal])
        ctx = prepare_render_context(findings)
        sc = ctx["signal_contexts"][0]
        assert sc["signal"] is signal
