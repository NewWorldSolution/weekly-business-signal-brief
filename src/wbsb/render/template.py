"""Template-based brief renderer using Jinja2."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from wbsb.domain.models import Findings, LLMResult
from wbsb.render.context import prepare_render_context

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "template.md.j2"


def _extract_situation(llm_result: LLMResult | None) -> str | None:
    """Return a normalized situation field when available."""
    if llm_result is None:
        return None
    situation = getattr(llm_result, "situation", None)
    if not isinstance(situation, str):
        return None
    normalized = situation.strip()
    return normalized or None


def _extract_key_story(llm_result: LLMResult | None) -> str | None:
    """Return a normalized key_story field when available."""
    if llm_result is None:
        return None
    key_story = getattr(llm_result, "key_story", None)
    if not isinstance(key_story, str):
        return None
    normalized = key_story.strip()
    return normalized or None


def _extract_llm_signal_narratives(llm_result: LLMResult | None) -> dict[str, str]:
    """Return non-empty LLM narrative overrides keyed by rule_id."""
    if llm_result is None:
        return {}

    signal_narratives = getattr(llm_result, "signal_narratives", None)
    if signal_narratives is None:
        return {}
    narratives = getattr(signal_narratives, "narratives", None)
    if not isinstance(narratives, dict):
        return {}

    return {
        rule_id: narrative.strip()
        for rule_id, narrative in narratives.items()
        if isinstance(narrative, str) and narrative.strip()
    }


def _extract_group_narratives(llm_result: LLMResult | None) -> dict[str, str]:
    """Return non-empty LLM category narratives keyed by internal category key.

    Normalizes LLM-returned keys to internal snake_case format so that
    display-name keys (e.g. "Financial Health") match internal keys
    (e.g. "financial_health") used by signal.category in findings.
    """
    if llm_result is None:
        return {}
    group_narratives = getattr(llm_result, "group_narratives", None)
    if not isinstance(group_narratives, dict):
        return {}
    return {
        category.lower().replace(" ", "_"): narrative.strip()
        for category, narrative in group_narratives.items()
        if isinstance(narrative, str) and narrative.strip()
    }


def _extract_watch_signals(llm_result: LLMResult | None) -> list[dict[str, str]]:
    """Return up to two normalized watch signal entries."""
    if llm_result is None:
        return []
    watch_signals = getattr(llm_result, "watch_signals", None)
    if not isinstance(watch_signals, list):
        return []
    normalized: list[dict[str, str]] = []
    for entry in watch_signals:
        if not isinstance(entry, dict):
            continue
        metric_or_signal = entry.get("metric_or_signal")
        observation = entry.get("observation")
        if not isinstance(metric_or_signal, str) or not isinstance(observation, str):
            continue
        metric_or_signal = metric_or_signal.strip()
        observation = observation.strip()
        if not metric_or_signal or not observation:
            continue
        normalized.append({
            "metric_or_signal": metric_or_signal,
            "observation": observation,
        })
    return normalized[:2]


def _compute_dominant_cluster_exists(findings: Findings) -> bool:
    """Compute deterministic dominant cluster flag from WARN signal counts."""
    cluster_sizes = Counter(
        signal.category for signal in findings.signals if signal.severity == "WARN"
    )
    return max(cluster_sizes.values(), default=0) >= 2


def render_template(findings: Findings, llm_result: LLMResult | None = None) -> str:
    """Render brief.md from findings using Jinja2 template.

    Args:
        findings: Pre-computed Findings document.
        llm_result: Optional LLM output used for executive summary and
            per-signal narrative overrides.

    Returns:
        Markdown string for brief.md.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(_TEMPLATE_NAME)
    ctx: dict[str, Any] = prepare_render_context(findings)
    ctx["situation"] = _extract_situation(llm_result)
    ctx["key_story"] = _extract_key_story(llm_result)
    ctx["group_narratives"] = _extract_group_narratives(llm_result)
    ctx["llm_signal_narratives"] = _extract_llm_signal_narratives(llm_result)
    ctx["watch_signals"] = _extract_watch_signals(llm_result)
    ctx["dominant_cluster_exists"] = _compute_dominant_cluster_exists(findings)
    return template.render(**ctx)
