"""LLM rendering interface stub."""
from __future__ import annotations

from wbsb.domain.models import Findings


def render_llm(findings: Findings, mode: str) -> str:
    """Render the brief using an LLM (stub implementation).

    The LLM receives the pre-computed findings.json and returns ONLY narrative.
    It does NOT compute metrics, detect anomalies, or make recommendations.

    Args:
        findings: Pre-computed Findings document.
        mode: LLM provider mode (e.g., "openai", "anthropic").

    Returns:
        Markdown-formatted brief narrative.
    """
    # Stub: in production, serialize findings and call the LLM API
    raise NotImplementedError(
        f"LLM mode '{mode}' is not yet implemented. "
        "Add provider credentials and implement the API call here. "
        "Use --llm off for template-based rendering."
    )
