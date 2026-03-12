"""Evaluation scorer utilities for Iteration 7."""
from __future__ import annotations

from wbsb.domain.models import Findings, LLMResult


def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Score how many signals and categories are covered by LLM narratives.

    Returns:
        {
            "signal_coverage": float,   # [0.0, 1.0]
            "group_coverage": float,    # [0.0, 1.0]
        }
    """
    total_signals = len(findings.signals)

    signal_narratives_raw = llm_result.signal_narratives or {}
    if hasattr(signal_narratives_raw, "narratives"):
        signal_narratives = signal_narratives_raw.narratives or {}
    else:
        signal_narratives = signal_narratives_raw

    if total_signals == 0:
        signal_coverage = 1.0
    else:
        payload_rule_ids = {signal.rule_id for signal in findings.signals}
        signals_with_narrative = sum(
            1 for rule_id in payload_rule_ids if rule_id in signal_narratives
        )
        signal_coverage = signals_with_narrative / total_signals

    payload_categories = {
        signal.category.lower().replace(" ", "_") for signal in findings.signals
    }

    group_narratives = llm_result.group_narratives or {}

    if not payload_categories:
        group_coverage = 1.0
    else:
        normalized_group_keys = {k.lower().replace(" ", "_") for k in group_narratives}
        covered_categories = sum(1 for cat in payload_categories if cat in normalized_group_keys)
        group_coverage = covered_categories / len(payload_categories)

    return {
        "signal_coverage": signal_coverage,
        "group_coverage": group_coverage,
    }


def score_hallucination(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Detect structural hallucinations in LLM output by comparing it to findings.

    Returns:
        {
            "hallucination_risk": int,
            "hallucination_violations": list[dict],  # each: {type, severity, detail}
        }
    """
    violations: list[dict] = []

    payload_rule_ids = {signal.rule_id for signal in findings.signals}
    payload_metric_ids = {metric.id for metric in findings.metrics}
    payload_valid_ids = payload_rule_ids | payload_metric_ids
    payload_category_keys = {
        signal.category.lower().replace(" ", "_") for signal in findings.signals
    }

    dominant_cluster_exists = getattr(findings, "dominant_cluster_exists", True)

    signal_narratives_raw = llm_result.signal_narratives or {}
    if hasattr(signal_narratives_raw, "narratives"):
        signal_narratives = signal_narratives_raw.narratives or {}
    else:
        signal_narratives = signal_narratives_raw

    # 1) key_story_when_no_cluster
    if llm_result.key_story is not None and dominant_cluster_exists is False:
        violations.append(
            {
                "type": "key_story_when_no_cluster",
                "severity": "critical",
                "detail": "key_story is present but dominant_cluster_exists is False",
            }
        )

    # 2) invalid_watch_signal_id
    for entry in llm_result.watch_signals or []:
        metric_or_signal = entry.get("metric_or_signal")
        if metric_or_signal not in payload_valid_ids:
            violations.append(
                {
                    "type": "invalid_watch_signal_id",
                    "severity": "major",
                    "detail": f"metric_or_signal '{metric_or_signal}' not in payload",
                }
            )

    # 3) invalid_group_narrative_category
    for key in llm_result.group_narratives or {}:
        normalized = key.lower().replace(" ", "_")
        if normalized not in payload_category_keys:
            violations.append(
                {
                    "type": "invalid_group_narrative_category",
                    "severity": "major",
                    "detail": f"group_narratives key '{key}' not in payload categories",
                }
            )

    # 4) extra_signal_narrative
    for rule_id in signal_narratives:
        if rule_id not in payload_rule_ids:
            violations.append(
                {
                    "type": "extra_signal_narrative",
                    "severity": "minor",
                    "detail": f"signal_narratives key '{rule_id}' not in payload",
                }
            )

    # 5) missing_signal_narrative
    for rule_id in sorted(payload_rule_ids):
        if rule_id not in signal_narratives:
            violations.append(
                {
                    "type": "missing_signal_narrative",
                    "severity": "minor",
                    "detail": f"signal '{rule_id}' has no narrative",
                }
            )

    return {
        "hallucination_risk": len(violations),
        "hallucination_violations": violations,
    }
