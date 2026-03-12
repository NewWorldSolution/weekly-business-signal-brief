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

    payload_categories = {signal.category.lower().replace(" ", "_") for signal in findings.signals}

    group_narratives = llm_result.group_narratives or {}

    if not payload_categories:
        group_coverage = 1.0
    else:
        covered_categories = sum(1 for cat in payload_categories if cat in group_narratives)
        group_coverage = covered_categories / len(payload_categories)

    return {
        "signal_coverage": signal_coverage,
        "group_coverage": group_coverage,
    }
