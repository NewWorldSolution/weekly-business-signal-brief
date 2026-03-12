"""Evaluation scorer utilities for Iteration 7."""
from __future__ import annotations

from datetime import UTC, datetime

from wbsb.domain.models import Findings, LLMResult
from wbsb.eval.extractor import (
    build_evidence_allowlist,
    candidate_values,
    extract_numbers_from_text,
    is_grounded,
)
from wbsb.eval.models import EvalScores


def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict:
    """
    Score how well LLM-cited numbers are grounded in findings evidence.

    Returns:
        {
            "grounding": float | None,
            "grounding_reason": str | None,
            "flagged_numbers": list[str],
        }
    """
    parts: list[str] = []
    if llm_result.situation is not None:
        parts.append(llm_result.situation)
    if llm_result.key_story is not None:
        parts.append(llm_result.key_story)
    parts.extend((llm_result.group_narratives or {}).values())

    signal_narratives_raw = llm_result.signal_narratives or {}
    if hasattr(signal_narratives_raw, "narratives"):
        signal_narratives = signal_narratives_raw.narratives or {}
    else:
        signal_narratives = signal_narratives_raw
    parts.extend(signal_narratives.values())

    for entry in llm_result.watch_signals or []:
        observation = entry.get("observation")
        if observation is not None:
            parts.append(observation)

    combined_text = "\n".join(parts)
    tokens = extract_numbers_from_text(combined_text)

    if len(tokens) == 0:
        return {
            "grounding": None,
            "grounding_reason": "no_numbers_cited",
            "flagged_numbers": [],
        }

    allowlist = build_evidence_allowlist(findings)
    pct_normalization = cfg["grounding_pct_normalization"]

    flagged_numbers: list[str] = []
    for raw_token in tokens:
        candidates = candidate_values(raw_token, pct_normalization)
        grounded = any(is_grounded(candidate, allowlist, cfg) for candidate in candidates)
        if not grounded:
            flagged_numbers.append(raw_token)

    grounding = (len(tokens) - len(flagged_numbers)) / len(tokens)
    return {
        "grounding": grounding,
        "grounding_reason": None,
        "flagged_numbers": flagged_numbers,
    }


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

    dominant_cluster_exists = findings.dominant_cluster_exists

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


def build_eval_scores(
    findings: Findings,
    llm_result: LLMResult,
    cfg: dict,
) -> EvalScores:
    """
    Combine grounding, coverage, and hallucination results into a single EvalScores.

    Args:
        findings:   Pydantic Findings from the pipeline.
        llm_result: Pydantic LLMResult from the LLM adapter.
        cfg:        The eval section from config/rules.yaml (a dict).

    Returns:
        EvalScores instance with all fields populated.
    """
    grounding_result = score_grounding(findings, llm_result, cfg)
    coverage_result = score_signal_coverage(findings, llm_result)
    hallucination_result = score_hallucination(findings, llm_result)

    return EvalScores(
        grounding=grounding_result["grounding"],
        grounding_reason=grounding_result["grounding_reason"],
        flagged_numbers=grounding_result["flagged_numbers"],
        signal_coverage=coverage_result["signal_coverage"],
        group_coverage=coverage_result["group_coverage"],
        hallucination_risk=hallucination_result["hallucination_risk"],
        hallucination_violations=hallucination_result["hallucination_violations"],
        model=llm_result.model,
        evaluated_at=datetime.now(UTC).isoformat(),
    )
