"""LLM rendering helper — orchestrates adapter call and deterministic fallback."""
from __future__ import annotations

import logging

from wbsb.domain.models import Findings, LLMResult, LLMSignalNarratives
from wbsb.render import llm_adapter
from wbsb.render.context import prepare_render_context
from wbsb.render.llm_adapter import LLMClientProtocol
from wbsb.render.template import render_template

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _adapter_to_domain(adapter_result: llm_adapter.AdapterLLMResult) -> LLMResult:
    """Map AdapterLLMResult to the shared domain LLMResult model."""
    return LLMResult(
        executive_summary=adapter_result.executive_summary,
        signal_narratives=LLMSignalNarratives(
            narratives=adapter_result.signal_narratives.narratives
        ),
        model=adapter_result.model,
        prompt_version=adapter_result.prompt_version,
        fallback=adapter_result.fallback,
        fallback_reason=adapter_result.fallback_reason,
        token_usage=adapter_result.token_usage,
        situation=adapter_result.situation,
        key_story=adapter_result.key_story,
        group_narratives=adapter_result.group_narratives,
        watch_signals=adapter_result.watch_signals,
    )


def _build_enriched_brief(findings: Findings, llm_result: LLMResult) -> str:
    """Render the brief with LLM section overlays and per-signal overrides.

    Delegates to render_template() with llm_result so all section fields
    (situation, key_story, group_narratives, signal_narratives, watch_signals)
    are injected into the Jinja2 context.
    """
    return render_template(findings, llm_result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_llm(
    findings: Findings,
    mode: str,
    provider: str,
    client: LLMClientProtocol | None = None,
    trend_context: dict | None = None,
) -> tuple[str, LLMResult | None, str, str]:
    """Render the brief using an LLM overlay with deterministic fallback.

    Always computes the deterministic brief first. Then attempts to enrich
    it with LLM narrative. On any LLM failure the deterministic brief is
    returned and ``llm_result`` is None — the pipeline must not crash.

    Args:
        findings: Pre-computed Findings document.
        mode: LLM mode — "summary" or "full".
        provider: LLM provider name. Only "anthropic" is implemented in I4.
        client: Injectable LLM client for testing; defaults to AnthropicClient.

    Returns:
        A 4-tuple of:
            brief_md: Rendered brief markdown (enriched or deterministic fallback).
            llm_result: Domain LLMResult on success, None on failure.
            rendered_system_prompt: Rendered system prompt (empty string on early failure).
            rendered_user_prompt: Rendered user prompt (empty string on early failure).
    """
    ctx = prepare_render_context(findings)

    # Render prompts for observability — results are passed to the artifact writer
    # regardless of whether the adapter succeeds.
    rendered_system_prompt = ""
    rendered_user_prompt = ""
    try:
        prompt_inputs = llm_adapter.build_prompt_inputs(ctx, trend_context=trend_context)
        rendered_system_prompt = llm_adapter.render_system_prompt(mode)
        rendered_user_prompt = llm_adapter.render_user_prompt(prompt_inputs, mode)
    except Exception as exc:  # noqa: BLE001
        logger.warning("render_llm: failed to render prompts: %s", exc)
        return render_template(findings), None, "", ""

    # Delegate to adapter — returns None on any failure; never raises.
    adapter_result = llm_adapter.generate(
        ctx, mode=mode, provider=provider, client=client, trend_context=trend_context
    )

    if adapter_result is None:
        logger.info("render_llm: adapter returned None, using deterministic fallback")
        return render_template(findings), None, rendered_system_prompt, rendered_user_prompt

    llm_result = _adapter_to_domain(adapter_result)
    brief_md = _build_enriched_brief(findings, llm_result)

    return brief_md, llm_result, rendered_system_prompt, rendered_user_prompt
