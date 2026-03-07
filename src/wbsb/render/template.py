"""Template-based brief renderer using Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from wbsb.domain.models import Findings
from wbsb.render.context import prepare_render_context

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "template.md.j2"


def render_template(findings: Findings) -> str:
    """Render brief.md from findings using Jinja2 template.

    Args:
        findings: Pre-computed Findings document.

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
    return template.render(**ctx)
