"""Deterministic rules engine - evaluates config-driven rules against metrics."""
from __future__ import annotations

from typing import Any

from wbsb.domain.models import RunConfig, Signal


def evaluate_rules(
    current_metrics: dict[str, float | None],
    previous_metrics: dict[str, float | None],
    deltas: dict[str, tuple[float | None, float | None]],
    raw_config: dict[str, Any],
    run_config: RunConfig,
    reliability: str,
) -> list[Signal]:
    """Evaluate all rules and return fired signals.

    Args:
        current_metrics: Metric values for current week.
        previous_metrics: Metric values for previous week.
        deltas: Map of metric_id -> (delta_abs, delta_pct).
        raw_config: Raw YAML config dict.
        run_config: Parsed run config.
        reliability: "ok" or "low" based on previous net_revenue.

    Returns:
        List of fired Signal objects, sorted by rule_id.
    """
    rules = raw_config.get("rules", [])
    fired: list[Signal] = []

    curr_net_rev = current_metrics.get("net_revenue") or 0.0
    prev_net_rev = previous_metrics.get("net_revenue") or 0.0
    prev_leads_paid = previous_metrics.get("leads_paid") or 0.0
    prev_new_clients_paid = previous_metrics.get("new_clients_paid") or 0.0
    prev_bookings_total = previous_metrics.get("bookings_total") or 0.0
    volume_threshold = run_config.volume_threshold
    min_prev_net_revenue = run_config.min_prev_net_revenue

    for rule in rules:
        rule_id = rule["id"]
        metric_id = rule["metric_id"]
        severity = rule["severity"]
        condition = rule["condition"]

        # Guard checks
        if rule.get("requires_min_prev_net_revenue") and prev_net_rev < min_prev_net_revenue:
            continue
        if "requires_prev_leads_paid_gte" in rule:
            if prev_leads_paid < rule["requires_prev_leads_paid_gte"]:
                continue
        if "requires_prev_new_clients_paid_gte" in rule:
            if prev_new_clients_paid < rule["requires_prev_new_clients_paid_gte"]:
                continue
        if "requires_prev_bookings_total_gte" in rule:
            if prev_bookings_total < rule["requires_prev_bookings_total_gte"]:
                continue
        if rule.get("requires_current_net_revenue_gt") is not None:
            if curr_net_rev <= rule["requires_current_net_revenue_gt"]:
                continue

        delta_abs, delta_pct = deltas.get(metric_id, (None, None))
        current_val = current_metrics.get(metric_id)
        previous_val = previous_metrics.get(metric_id)

        fired_flag = False
        explanation = ""
        evidence: dict[str, Any] = {
            "current": current_val,
            "previous": previous_val,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
        }

        if condition == "delta_pct_lte":
            threshold = rule["threshold"]
            evidence["threshold"] = threshold
            if delta_pct is not None and delta_pct <= threshold:
                fired_flag = True
                explanation = (
                    f"{metric_id} changed {delta_pct:.1%} (threshold: ≤{threshold:.1%})"
                )
        elif condition == "delta_pct_gte":
            threshold = rule["threshold"]
            evidence["threshold"] = threshold
            if delta_pct is not None and delta_pct >= threshold:
                fired_flag = True
                explanation = (
                    f"{metric_id} changed {delta_pct:.1%} (threshold: ≥{threshold:.1%})"
                )
        elif condition == "absolute_lt":
            threshold = rule["threshold"]
            evidence["threshold"] = threshold
            if current_val is not None and current_val < threshold:
                fired_flag = True
                explanation = (
                    f"{metric_id} is {current_val:.4f} (threshold: <{threshold})"
                )
        elif condition == "absolute_gt":
            threshold = rule["threshold"]
            evidence["threshold"] = threshold
            if current_val is not None and current_val > threshold:
                fired_flag = True
                explanation = (
                    f"{metric_id} is {current_val:.4f} (threshold: >{threshold})"
                )
        elif condition == "hybrid_delta_pct_lte":
            threshold_pct = rule["threshold_pct"]
            threshold_abs = rule["threshold_abs"]
            evidence["threshold_pct"] = threshold_pct
            evidence["threshold_abs"] = threshold_abs
            volume_metric_id = rule.get("volume_metric", metric_id)
            prev_raw = previous_metrics.get(volume_metric_id) or 0.0
            if prev_raw < volume_threshold:
                # Use absolute threshold
                if delta_abs is not None and delta_abs <= threshold_abs:
                    fired_flag = True
                    explanation = (
                        f"{metric_id} dropped by {delta_abs:.0f} "
                        f"(absolute threshold: ≤{threshold_abs}, low-volume mode)"
                    )
            else:
                if delta_pct is not None and delta_pct <= threshold_pct:
                    fired_flag = True
                    explanation = (
                        f"{metric_id} changed {delta_pct:.1%} "
                        f"(threshold: ≤{threshold_pct:.1%})"
                    )

        if fired_flag:
            guardrails = []
            if reliability == "low":
                guardrails.append("reliability=low: previous net_revenue below minimum threshold")
            fired.append(
                Signal(
                    rule_id=rule_id,
                    severity=severity,
                    metric_id=metric_id,
                    label=rule.get("label", ""),
                    category=rule.get("category", ""),
                    priority=rule.get("priority", 0),
                    explanation=explanation,
                    evidence=evidence,
                    guardrails=guardrails,
                    reliability=reliability,
                )
            )

    return sorted(fired, key=lambda s: (0 if s.severity == "WARN" else 1, -s.priority, s.rule_id))
