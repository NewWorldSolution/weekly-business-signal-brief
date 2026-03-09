"""LLM adapter boundary module for WBSB.

This module is the sole interface between WBSB and any external LLM API.
It handles prompt construction, API calls, response validation, and fallback.

COMPATIBILITY NOTE (I4-1):
    This module defines a task-local response model (`AdapterLLMResult`) whose
    field names are intentionally aligned with the future shared domain model
    (`wbsb.domain.models.LLMResult`) introduced in Task I4-2.
    Task I4-3 will replace or map this local model to the shared domain model
    with minimal code changes.

Architecture constraints:
    - This module does NOT import from wbsb.domain.models (no cross-task dep).
    - All prompt engineering is contained here (templates in render/prompts/).
    - The generate() function is the sole public API entry point.
    - All LLM failures return None; callers must handle graceful fallback.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Prompt version constants derived from template filenames.
PROMPT_VERSION_SUMMARY = "summary_v1"
PROMPT_VERSION_FULL = "full_v2"

_PROMPT_VERSIONS = {
    "summary": PROMPT_VERSION_SUMMARY,
    "full": PROMPT_VERSION_FULL,
}

_EXECUTIVE_SUMMARY_MAX_CHARS = 800
_EXECUTIVE_SUMMARY_MIN_CHARS = 1
_FULL_PROMPT_TEMPLATE = "user_full_v2.j2"
_FULL_SYSTEM_TEMPLATE = "system_full_v2.j2"
_FORBIDDEN_WATCH_OBSERVATION_TERMS = (
    "recommend",
    "should",
    "need to",
    "consider",
    "review",
    "adjust",
    "increase",
    "decrease",
    "improve",
    "fix",
    "address",
    "prioritize",
)

_CHAIN_DEFINITIONS: list[dict[str, Any]] = [
    {
        "chain_id": "paid_acquisition",
        "title": "Paid Acquisition Chain",
        "metrics": [
            "ad_spend_total",
            "leads_paid",
            "paid_lead_to_client",
            "new_clients_paid",
            "cac_paid",
        ],
    },
    {
        "chain_id": "operations",
        "title": "Operational Chain",
        "metrics": [
            "bookings_total",
            "show_rate",
            "cancel_rate",
            "appointments_completed",
        ],
    },
    {
        "chain_id": "financial",
        "title": "Financial Chain",
        "metrics": [
            "gross_margin",
            "marketing_pct_revenue",
            "contribution_after_marketing",
        ],
    },
]

# ---------------------------------------------------------------------------
# LLM Client Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for any LLM backend client used by this adapter.

    Implementations must be injectable for testing without live API calls.
    """

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        """Call the LLM and return the raw response string.

        Args:
            system_prompt: The static system role/constraint prompt.
            user_prompt: The per-run data payload prompt.
            timeout: Maximum seconds to wait for a response.

        Returns:
            Raw string response from the LLM (expected to be JSON).

        Raises:
            TimeoutError: If the request exceeds the timeout.
            Exception: For any API-level error.
        """
        ...


# ---------------------------------------------------------------------------
# Task-local response model
# Field names intentionally aligned with future wbsb.domain.models.LLMResult.
# ---------------------------------------------------------------------------


class AdapterSignalNarratives(BaseModel):
    """Container for per-signal LLM narratives keyed by rule_id."""

    narratives: dict[str, str] = Field(default_factory=dict)


class AdapterLLMResult(BaseModel):
    """Task-local validated LLM response model.

    Shape is intentionally compatible with the future shared domain model
    (wbsb.domain.models.LLMResult) to be introduced in Task I4-2.
    Task I4-3 will map or replace this with the shared model.
    """

    executive_summary: str = ""
    signal_narratives: AdapterSignalNarratives = Field(
        default_factory=AdapterSignalNarratives
    )
    model: str = ""
    prompt_version: str = ""
    fallback: bool = False
    fallback_reason: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    # Iteration 5 section-based fields — all optional for backward compatibility
    situation: str | None = None
    key_story: str | None = None
    group_narratives: dict[str, str] | None = None
    watch_signals: list[dict[str, str]] | None = None


# ---------------------------------------------------------------------------
# Anthropic client implementation
# ---------------------------------------------------------------------------


class AnthropicClient:
    """Anthropic SDK-backed LLM client implementing LLMClientProtocol.

    Reads ANTHROPIC_API_KEY from the environment.
    Model can be overridden via constructor argument or WBSB_LLM_MODEL env var.
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, model: str | None = None) -> None:
        self._model = (
            model
            or os.environ.get("WBSB_LLM_MODEL")
            or self.DEFAULT_MODEL
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        """Call the Anthropic messages API and return the raw text response.

        Args:
            system_prompt: System role/constraint prompt.
            user_prompt: Per-run data payload prompt.
            timeout: Request timeout in seconds.

        Returns:
            Raw text string from the model response.

        Raises:
            TimeoutError: On request timeout.
            Exception: On any Anthropic API error.
        """
        import anthropic  # deferred import — not required at module load

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it or use --llm-mode off to skip LLM generation."
            )

        client = anthropic.Anthropic(api_key=api_key, timeout=float(timeout))
        message = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Log the stop reason and content block types for observability.
        logger.debug(
            "Anthropic response received: stop_reason=%s, content_blocks=%s",
            getattr(message, "stop_reason", "unknown"),
            [getattr(b, "type", "unknown") for b in message.content],
        )
        # Concatenate all text-type blocks into a single string.
        # This is safe when the model returns multiple text blocks or when the
        # SDK wraps the response differently across versions.
        response_text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        if not response_text:
            raise ValueError(
                f"Anthropic response contained no text blocks. "
                f"stop_reason={getattr(message, 'stop_reason', 'unknown')!r}, "
                f"content_types={[getattr(b, 'type', 'unknown') for b in message.content]!r}"
            )
        return response_text


# ---------------------------------------------------------------------------
# Prompt input builder
# ---------------------------------------------------------------------------


def build_prompt_inputs(ctx: dict[str, Any]) -> dict[str, Any]:
    """Extract serializable LLM-relevant fields from the deterministic render context.

    This is the boundary between the deterministic pipeline context and the LLM
    prompt layer. No domain objects pass through — only primitive, serializable values.

    Args:
        ctx: Output of prepare_render_context(findings). Not mutated.

    Returns:
        Flat dict of serializable values for rendering user prompt templates.
        Contains keys for both summary and full modes; unused keys are ignored
        by each template.
    """
    findings = ctx["findings"]
    run = findings.run
    periods = findings.periods

    # Top signals (up to 3 WARN) from context
    top_signal_inputs = []
    for sc in ctx.get("signal_contexts", []):
        if sc["signal"].severity == "WARN" and len(top_signal_inputs) < 3:
            ni = sc["narrative_inputs"]
            top_signal_inputs.append({
                "rule_id": ni["rule_id"],
                "label": ni["label"],
                "category": ni["category"],
                "category_display": ni["category_display"],
                "severity": ni["severity"],
                "metric_name": ni["metric_name"],
                "metric_id": ni["metric_id"],
                "direction": ni["direction"],
                "current_value": ni["current_value"],
                "previous_value": ni["previous_value"],
                "delta_pct": ni["delta_pct"],
                "delta_abs": ni["delta_abs"],
                "threshold": ni["threshold"],
                "threshold_pct": ni["threshold_pct"],
                "threshold_abs": ni["threshold_abs"],
            })

    # All signals for full mode
    all_signal_inputs = []
    for sc in ctx.get("signal_contexts", []):
        ni = sc["narrative_inputs"]
        all_signal_inputs.append({
            "rule_id": ni["rule_id"],
            "label": ni["label"],
            "category": ni["category"],
            "category_display": ni["category_display"],
            "severity": ni["severity"],
            "metric_name": ni["metric_name"],
            "metric_id": ni["metric_id"],
            "direction": ni["direction"],
            "current_value": ni["current_value"],
            "previous_value": ni["previous_value"],
            "delta_pct": ni["delta_pct"],
            "delta_abs": ni["delta_abs"],
            "threshold": ni["threshold"],
            "threshold_pct": ni["threshold_pct"],
            "threshold_abs": ni["threshold_abs"],
            "deterministic_narrative": sc["narrative"],
        })

    # Collect all rule_ids for response validation
    rule_ids = [s["rule_id"] for s in all_signal_inputs]
    metric_ids = [m.id for m in findings.metrics]

    grouped_signals = _group_signals_by_category(all_signal_inputs)
    category_health_summary = _build_category_health_summary(grouped_signals)
    dominant_cluster_exists, dominant_cluster_category = _resolve_dominant_cluster(
        grouped_signals
    )
    business_mechanism_chains = _build_business_mechanism_chains(findings.metrics)
    relationship_hints = _build_relationship_hints(
        grouped_signals=grouped_signals,
        chains=business_mechanism_chains,
    )

    return {
        # Period info
        "generated_at": run.generated_at.isoformat(),
        "current_week_start": str(periods.current_week_start),
        "current_week_end": str(periods.current_week_end),
        "previous_week_start": str(periods.previous_week_start),
        "previous_week_end": str(periods.previous_week_end),
        # Signal counts
        "warn_count": ctx["warn_count"],
        "info_count": ctx["info_count"],
        # Category breakdown (WARN only)
        "severity_by_category": dict(ctx.get("severity_by_category", {})),
        # Top 3 WARN signals (for summary mode)
        "top_signals": top_signal_inputs,
        # All signals (for full mode)
        "all_signals": all_signal_inputs,
        # Grouped deterministic evidence for full mode
        "grouped_signals": grouped_signals,
        "category_health_summary": category_health_summary,
        "business_mechanism_chains": business_mechanism_chains,
        "dominant_cluster_exists": dominant_cluster_exists,
        "dominant_cluster_category": dominant_cluster_category,
        "relationship_hints": relationship_hints,
        # Rule IDs for validation
        "rule_ids": rule_ids,
        "metric_ids": metric_ids,
    }


def _group_signals_by_category(all_signal_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group flat signal inputs by category for full-mode prompt rendering."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for signal in all_signal_inputs:
        grouped.setdefault(signal["category"], []).append(signal)

    preferred_order = ("acquisition", "financial_health", "operations", "revenue")
    ordered_categories = [
        category for category in preferred_order if category in grouped
    ] + sorted(category for category in grouped if category not in preferred_order)

    result: list[dict[str, Any]] = []
    for category in ordered_categories:
        signals = grouped[category]
        result.append({
            "category": category,
            "category_display": signals[0]["category_display"] if signals else category,
            "signals": signals,
        })
    return result


def _build_category_health_summary(
    grouped_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build conservative deterministic category summaries with no interpretation."""
    summary: list[dict[str, Any]] = []
    for group in grouped_signals:
        directions = {
            signal["direction"] for signal in group["signals"]
            if signal.get("direction") in {"up", "down"}
        }
        if len(directions) == 1 and directions:
            consistency = "consistent"
            dominant_direction = next(iter(directions))
        else:
            consistency = "mixed"
            dominant_direction = "mixed"

        severity_counts = Counter(signal["severity"] for signal in group["signals"])
        summary.append({
            "category": group["category"],
            "category_display": group["category_display"],
            "signal_count": len(group["signals"]),
            "warn_count": severity_counts.get("WARN", 0),
            "severity_counts": dict(severity_counts),
            "directional_consistency": consistency,
            "dominant_direction": dominant_direction,
        })
    return summary


def _resolve_dominant_cluster(
    grouped_signals: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    """Compute deterministic dominant WARN cluster fact for prompt header."""
    warn_counts = [
        (
            group["category"],
            sum(1 for signal in group["signals"] if signal["severity"] == "WARN"),
        )
        for group in grouped_signals
    ]
    if not warn_counts:
        return False, None

    dominant_category, dominant_warn_count = max(warn_counts, key=lambda item: item[1])
    if dominant_warn_count >= 2:
        return True, dominant_category
    return False, None


def _direction_from_metric(metric: Any) -> str:
    """Return simple direction indicator for a metric movement."""
    delta_pct = getattr(metric, "delta_pct", None)
    delta_abs = getattr(metric, "delta_abs", None)
    if delta_pct is not None:
        if delta_pct > 0:
            return "up"
        if delta_pct < 0:
            return "down"
        return "flat"
    if delta_abs is not None:
        if delta_abs > 0:
            return "up"
        if delta_abs < 0:
            return "down"
    return "flat"


def _build_business_mechanism_chains(metrics: list[Any]) -> list[dict[str, Any]]:
    """Build deterministic chain views using existing MetricResult values only."""
    metric_by_id = {m.id: m for m in metrics}
    chains: list[dict[str, Any]] = []
    for chain_def in _CHAIN_DEFINITIONS:
        elements = []
        for metric_id in chain_def["metrics"]:
            metric = metric_by_id.get(metric_id)
            if metric is None:
                continue
            elements.append({
                "metric_id": metric.id,
                "metric_name": metric.name,
                "format_hint": metric.format_hint,
                "current_value": metric.current,
                "previous_value": metric.previous,
                "delta_abs": metric.delta_abs,
                "delta_pct": metric.delta_pct,
                "direction": _direction_from_metric(metric),
            })
        chains.append({
            "chain_id": chain_def["chain_id"],
            "title": chain_def["title"],
            "elements": elements,
            "missing_metric_ids": [
                metric_id
                for metric_id in chain_def["metrics"]
                if metric_id not in metric_by_id
            ],
        })
    return chains


def _build_relationship_hints(
    grouped_signals: list[dict[str, Any]],
    chains: list[dict[str, Any]],
) -> list[str]:
    """Generate up to five strictly descriptive deterministic relationship hints."""
    hints: list[str] = []

    for group in grouped_signals:
        warn_signals = [s for s in group["signals"] if s["severity"] == "WARN"]
        if len(warn_signals) >= 2:
            rule_ids = ", ".join(signal["rule_id"] for signal in warn_signals[:3])
            hints.append(
                f"{group['category_display']} WARN signals co-occurred ({rule_ids})."
            )

    for chain in chains:
        elements = chain["elements"]
        for left, right in zip(elements, elements[1:]):
            if left["direction"] != right["direction"]:
                hints.append(
                    f"{left['metric_name']} and {right['metric_name']} diverged "
                    f"({left['metric_id']}, {right['metric_id']})."
                )
                break

    return hints[:5]


# ---------------------------------------------------------------------------
# Prompt rendering helpers
# ---------------------------------------------------------------------------


def _get_jinja_env() -> Environment:
    """Return a Jinja2 environment pointing at the prompts directory."""
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_system_prompt(mode: str) -> str:
    """Render the system prompt Jinja2 template for the given mode.

    Args:
        mode: LLM mode — "summary" or "full".

    Returns:
        Rendered system prompt string.

    Raises:
        ValueError: If mode is unrecognized.
    """
    if mode not in ("summary", "full"):
        raise ValueError(f"Unknown llm mode: {mode!r}. Expected 'summary' or 'full'.")
    env = _get_jinja_env()
    if mode == "full":
        template = env.get_template(_FULL_SYSTEM_TEMPLATE)
    else:
        template = env.get_template("system_summary_v1.j2")
    return template.render()


def render_user_prompt(prompt_inputs: dict[str, Any], mode: str) -> str:
    """Render the user prompt Jinja2 template from built prompt inputs.

    Args:
        prompt_inputs: Output of build_prompt_inputs().
        mode: LLM mode — "summary" or "full".

    Returns:
        Rendered user prompt string (structured data payload for the LLM).

    Raises:
        ValueError: If mode is unrecognized.
    """
    if mode not in ("summary", "full"):
        raise ValueError(f"Unknown llm mode: {mode!r}. Expected 'summary' or 'full'.")
    env = _get_jinja_env()
    if mode == "full":
        template = env.get_template(_FULL_PROMPT_TEMPLATE)
    else:
        template = env.get_template("user_summary_v1.j2")
    return template.render(**prompt_inputs)


# ---------------------------------------------------------------------------
# Response sanitisation
# ---------------------------------------------------------------------------


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from an LLM response string.

    Models sometimes wrap JSON output in ```json ... ``` fences.
    This function removes them so the JSON parser receives a clean string.

    Examples::

        '```json\\n{"k": "v"}\\n```'  →  '{"k": "v"}'
        '{"k": "v"}'                  →  '{"k": "v"}'   (no-op)
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        # parts[0] is empty (before the opening fence),
        # parts[1] is the fenced content, parts[2+] are after the closing fence.
        if len(parts) >= 2:
            inner = parts[1]
            # Remove optional language tag (e.g. "json\n" or "json ")
            if inner.startswith("json"):
                inner = inner[4:]
            stripped = inner.strip()
    return stripped


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def validate_response(
    raw: str,
    mode: str,
    expected_rule_ids: list[str],
    expected_metric_ids: list[str] | None = None,
    dominant_cluster_exists: bool = True,
) -> AdapterLLMResult | None:
    """Parse and validate the raw LLM response string.

    Validation steps:
    1. Parse as JSON.
    2. Validate against AdapterLLMResult schema via Pydantic.
    3. Check executive_summary is non-empty and within length bounds.
    4. For "full" mode: strip unknown rule_ids from signal_narratives.

    Args:
        raw: Raw string response from the LLM.
        mode: LLM mode — "summary" or "full".
        expected_rule_ids: Rule IDs from prompt input.
        expected_metric_ids: Metric IDs from prompt input.
        dominant_cluster_exists: Deterministic dominant cluster fact from prompt input.

    Returns:
        Validated AdapterLLMResult or None if validation fails.
    """
    # Step 0: sanitise — strip markdown code fences if the model added them.
    raw = _strip_markdown_fences(raw)
    expected_metric_ids = expected_metric_ids or []

    # Step 1: parse JSON
    try:
        data = json.loads(raw)
    except JSONDecodeError as exc:
        logger.warning("LLM response is not valid JSON: %s", exc)
        return None

    # Normalise: if signal_narratives is a flat dict (not nested), wrap it
    if isinstance(data.get("signal_narratives"), dict):
        sn = data["signal_narratives"]
        # If the dict doesn't have "narratives" key, assume it IS the narratives dict
        if "narratives" not in sn:
            data["signal_narratives"] = {"narratives": sn}

    # Step 2: Pydantic validation
    try:
        result = AdapterLLMResult.model_validate(data)
    except ValidationError as exc:
        logger.warning("LLM response failed schema validation: %s", exc)
        return None

    # Step 3: executive_summary length / presence check.
    # For I5 responses, situation replaces executive_summary — allow empty summary
    # only when situation is present and non-empty.
    if not result.executive_summary.strip():
        if not (result.situation and result.situation.strip()):
            logger.warning(
                "LLM executive_summary is empty and situation field is absent."
            )
            return None
    if len(result.executive_summary) > _EXECUTIVE_SUMMARY_MAX_CHARS:
        logger.warning(
            "LLM executive_summary too long (%d chars, max %d).",
            len(result.executive_summary),
            _EXECUTIVE_SUMMARY_MAX_CHARS,
        )
        return None

    # Step 3b: key_story must be null/empty when no dominant cluster exists.
    if not dominant_cluster_exists and result.key_story and result.key_story.strip():
        logger.warning(
            "LLM key_story provided despite dominant_cluster_exists=False; field rejected."
        )
        result = result.model_copy(update={"key_story": None})

    # Step 3c: validate watch_signals structure and grounding if present.
    if result.watch_signals is not None:
        if len(result.watch_signals) > 2:
            logger.warning(
                "LLM watch_signals has %d entries (>2); field rejected.",
                len(result.watch_signals),
            )
            result = result.model_copy(update={"watch_signals": None})

    if result.watch_signals is not None:
        allowed_refs = set(expected_rule_ids) | set(expected_metric_ids)
        for i, entry in enumerate(result.watch_signals):
            if "metric_or_signal" not in entry or "observation" not in entry:
                logger.warning(
                    "LLM watch_signals entry %d missing required keys; field rejected.", i
                )
                result = result.model_copy(update={"watch_signals": None})
                break
            ref = str(entry["metric_or_signal"])
            observation = str(entry["observation"])
            if ref not in allowed_refs:
                logger.warning(
                    "LLM watch_signals entry %d references unknown id %r; field rejected.",
                    i,
                    ref,
                )
                result = result.model_copy(update={"watch_signals": None})
                break
            lowered_observation = observation.lower()
            if any(
                term in lowered_observation
                for term in _FORBIDDEN_WATCH_OBSERVATION_TERMS
            ):
                logger.warning(
                    "LLM watch_signals entry %d contains forbidden advisory language; "
                    "field rejected.",
                    i,
                )
                result = result.model_copy(update={"watch_signals": None})
                break

    # Step 4: for full mode, strip unknown rule_ids
    if mode == "full" and result.signal_narratives.narratives:
        valid_ids = set(expected_rule_ids)
        cleaned = {
            k: v
            for k, v in result.signal_narratives.narratives.items()
            if k in valid_ids
        }
        unknown = set(result.signal_narratives.narratives) - valid_ids
        if unknown:
            logger.warning(
                "LLM returned unknown rule_ids (stripped): %s", sorted(unknown)
            )
        result = result.model_copy(
            update={"signal_narratives": AdapterSignalNarratives(narratives=cleaned)}
        )

    # Soft check: warn if any narrative contains raw snake_case metric IDs
    _soft_check_snake_case(result)

    return result


def _soft_check_snake_case(result: AdapterLLMResult) -> None:
    """Log a warning (not a hard fail) if narratives contain raw snake_case metric IDs."""
    import re

    snake_pattern = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b")
    candidates = [result.executive_summary] + list(
        result.signal_narratives.narratives.values()
    )
    for text in candidates:
        matches = snake_pattern.findall(text)
        if matches:
            logger.warning(
                "LLM output may contain raw metric IDs (soft check): %s", matches
            )
            break


# ---------------------------------------------------------------------------
# Fallback logging
# ---------------------------------------------------------------------------


def _log_fallback(reason: str, detail: str) -> None:
    logger.warning("LLM fallback triggered. Reason: %s — %s", reason, detail)


# ---------------------------------------------------------------------------
# Public generate() API
# ---------------------------------------------------------------------------


def generate(
    ctx: dict[str, Any],
    mode: str,
    provider: str,
    client: LLMClientProtocol | None = None,
) -> AdapterLLMResult | None:
    """Generate an LLM narrative overlay from the deterministic render context.

    This is the sole public API for LLM generation. It:
    1. Builds serializable prompt inputs from ctx.
    2. Renders system + user prompts via Jinja2 templates.
    3. Calls the LLM via the injected (or default Anthropic) client.
    4. Validates the response.
    5. Returns AdapterLLMResult on success, None on any failure.

    No exceptions escape for expected LLM failure modes (timeout, API error,
    JSON/schema errors). All failures are logged and return None.

    Args:
        ctx: Output of prepare_render_context(findings). Not mutated.
        mode: LLM mode — "summary" or "full".
        provider: Backend provider name (currently only "anthropic" is implemented).
        client: Injectable LLM client. Defaults to AnthropicClient if None.

    Returns:
        AdapterLLMResult on success, None on any failure (triggers fallback).
    """
    if provider != "anthropic":
        _log_fallback(
            "unsupported_provider",
            f"Provider '{provider}' is not yet implemented. Use 'anthropic'.",
        )
        return None

    resolved_client: LLMClientProtocol
    if client is not None:
        resolved_client = client
    else:
        try:
            resolved_client = AnthropicClient()
        except Exception as exc:  # noqa: BLE001
            _log_fallback("client_init_error", str(exc))
            return None

    try:
        prompt_inputs = build_prompt_inputs(ctx)
        system_prompt = render_system_prompt(mode)
        user_prompt = render_user_prompt(prompt_inputs, mode)
        raw = resolved_client.complete(system_prompt, user_prompt, timeout=30)
    except TimeoutError as exc:
        _log_fallback("timeout", str(exc))
        return None
    except ValueError as exc:
        # Raised by AnthropicClient when API key is missing
        _log_fallback("config_error", str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        _log_fallback("api_error", str(exc))
        return None

    result = validate_response(
        raw,
        mode,
        expected_rule_ids=prompt_inputs["rule_ids"],
        expected_metric_ids=prompt_inputs["metric_ids"],
        dominant_cluster_exists=prompt_inputs["dominant_cluster_exists"],
    )
    if result is None:
        return None

    # Attach metadata
    prompt_version = _PROMPT_VERSIONS.get(mode, "")
    model_name = (
        resolved_client.model  # type: ignore[attr-defined]
        if hasattr(resolved_client, "model")
        else ""
    )
    return result.model_copy(
        update={"prompt_version": prompt_version, "model": model_name}
    )
