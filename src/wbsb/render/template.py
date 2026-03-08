"""Template-based brief renderer using Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from wbsb.domain.models import Findings, LLMResult
from wbsb.render.context import prepare_render_context

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "template.md.j2"


def _extract_executive_summary(llm_result: LLMResult | None) -> str | None:
    """Return a normalized executive summary when available."""
    if llm_result is None:
        return None
    summary = llm_result.executive_summary.strip()
    return summary or None


def _extract_llm_signal_narratives(llm_result: LLMResult | None) -> dict[str, str]:
    """Return non-empty LLM narrative overrides keyed by rule_id."""
    if llm_result is None:
        return {}
    return {
        rule_id: narrative.strip()
        for rule_id, narrative in llm_result.signal_narratives.narratives.items()
        if narrative.strip()
    }


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
    ctx = prepare_render_context(findings)
    ctx["executive_summary"] = _extract_executive_summary(llm_result)
    ctx["llm_signal_narratives"] = _extract_llm_signal_narratives(llm_result)
    return template.render(**ctx)
