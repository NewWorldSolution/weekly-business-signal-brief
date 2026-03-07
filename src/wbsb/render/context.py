"""Deterministic render context preparation layer.

Sits between Findings and any render path (Jinja, LLM, etc.).
Exposes prepare_render_context(findings) as the single public entry point.
"""
from __future__ import annotations

from typing import Any

from wbsb.domain.models import Findings, MetricResult, Signal

CATEGORY_LABELS: dict[str, str] = {
    "acquisition": "Acquisition",
    "operations": "Operations",
    "revenue": "Revenue",
    "financial_health": "Financial Health",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_metric_by_id(findings: Findings) -> dict[str, MetricResult]:
    return {m.id: m for m in findings.metrics}


def _hybrid_is_abs_mode(signal: Signal) -> bool:
    """Return True if the hybrid signal fired in absolute (low-volume) mode.

    The rules engine embeds 'low-volume mode' in the explanation when the
    absolute branch fires. This is an internal audit read, not display use.
    """
    return "low-volume mode" in signal.explanation


def _resolve_threshold_hint(signal: Signal, metric: MetricResult | None) -> str:
    """Return the correct format_hint to use when displaying the threshold value.

    delta_pct rules carry a fractional percentage threshold (e.g. -0.15).
    They must always render as percent, regardless of the metric's own unit.

    absolute rules carry a value in the metric's own unit (e.g. 0.50 for
    gross_margin, which is already a ratio rendered as percent).
    """
    condition = signal.condition
    metric_hint = metric.format_hint if metric else "decimal"

    if condition in ("delta_pct_lte", "delta_pct_gte"):
        return "percent"
    if condition in ("absolute_lt", "absolute_gt"):
        return metric_hint
    if condition == "hybrid_delta_pct_lte":
        # Hybrid pct mode → percent; hybrid abs mode → metric's own hint
        return metric_hint if _hybrid_is_abs_mode(signal) else "percent"
    return "decimal"


def _build_narrative(signal: Signal, metric: MetricResult | None) -> str:
    """Build a business-readable narrative string for the signal.

    Uses the metric display name (never raw metric_id), is concise, and
    avoids formatting logic that belongs in Jinja.
    """
    name = metric.name if metric else signal.metric_id.replace("_", " ").title()
    condition = signal.condition
    evidence = signal.evidence
    delta_pct = evidence.get("delta_pct")
    delta_abs = evidence.get("delta_abs")

    if condition == "delta_pct_lte":
        if delta_pct is not None:
            pct_abs = abs(delta_pct * 100)
            direction = "declined" if delta_pct < 0 else "changed"
            return f"{name} {direction} {pct_abs:.1f}% week-over-week."
        return f"{name} fell below its week-over-week threshold."

    if condition == "delta_pct_gte":
        if delta_pct is not None:
            pct_abs = abs(delta_pct * 100)
            direction = "rose" if delta_pct > 0 else "changed"
            return f"{name} {direction} {pct_abs:.1f}% week-over-week."
        return f"{name} exceeded its week-over-week threshold."

    if condition == "absolute_lt":
        return f"{name} fell below its minimum threshold."

    if condition == "absolute_gt":
        return f"{name} exceeded its maximum threshold."

    if condition == "hybrid_delta_pct_lte":
        if _hybrid_is_abs_mode(signal):
            if delta_abs is not None:
                return f"{name} dropped by {abs(delta_abs):.0f} (low-volume week)."
            return f"{name} fell below its absolute threshold."
        if delta_pct is not None:
            pct_abs = abs(delta_pct * 100)
            return f"{name} declined {pct_abs:.1f}% week-over-week."
        return f"{name} fell below its week-over-week threshold."

    return f"{name} triggered rule {signal.rule_id}."


def _infer_direction(signal: Signal) -> str:
    condition = signal.condition
    if condition in ("delta_pct_lte", "absolute_lt", "hybrid_delta_pct_lte"):
        return "down"
    if condition in ("delta_pct_gte", "absolute_gt"):
        return "up"
    return "unknown"


def _build_narrative_inputs(
    signal: Signal, metric: MetricResult | None
) -> dict[str, Any]:
    """Build raw structured values for Iteration 4 LLM consumption.

    All values are raw (unformatted). No prose, no formatted strings.
    Field names are stable across runs.
    """
    evidence = signal.evidence
    return {
        "metric_name": metric.name if metric else None,
        "metric_id": signal.metric_id,
        "condition": signal.condition,
        "direction": _infer_direction(signal),
        "current_value": evidence.get("current"),
        "previous_value": evidence.get("previous"),
        "delta_pct": evidence.get("delta_pct"),
        "delta_abs": evidence.get("delta_abs"),
        "threshold": evidence.get("threshold"),
        "threshold_pct": evidence.get("threshold_pct"),
        "threshold_abs": evidence.get("threshold_abs"),
        "category": signal.category,
        "category_display": CATEGORY_LABELS.get(signal.category, signal.category),
        "severity": signal.severity,
        "priority": signal.priority,
        "label": signal.label,
        "rule_id": signal.rule_id,
    }


def _build_signal_context(
    signal: Signal, metric_by_id: dict[str, MetricResult]
) -> dict[str, Any]:
    metric = metric_by_id.get(signal.metric_id)
    format_hint = metric.format_hint if metric else "decimal"
    threshold_hint = _resolve_threshold_hint(signal, metric)
    narrative = _build_narrative(signal, metric)
    narrative_inputs = _build_narrative_inputs(signal, metric)
    return {
        "signal": signal,
        "category": signal.category,
        "metric": metric,
        "format_hint": format_hint,
        "threshold_hint": threshold_hint,
        "narrative": narrative,
        "narrative_inputs": narrative_inputs,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prepare_render_context(findings: Findings) -> dict[str, Any]:
    """Prepare a deterministic render context from a Findings document.

    Pure function: same Findings → same context dict.
    """
    metric_by_id = _build_metric_by_id(findings)

    warn_signals = [s for s in findings.signals if s.severity == "WARN"]
    info_signals = [s for s in findings.signals if s.severity == "INFO"]
    top_warn = warn_signals[0] if warn_signals else None

    affected_categories = sorted({s.category for s in findings.signals if s.category})

    signal_contexts = [
        _build_signal_context(s, metric_by_id) for s in findings.signals
    ]

    return {
        "findings": findings,
        "warn_count": len(warn_signals),
        "info_count": len(info_signals),
        "top_warn": top_warn,
        "affected_categories": affected_categories,
        "category_labels": CATEGORY_LABELS,
        "metric_by_id": metric_by_id,
        "signal_contexts": signal_contexts,
    }
