"""Helpers for loading delivery configuration and resolving webhook env vars."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Z0-9_]+)\}$")
_REQUIRED_KEYS = (
    ("delivery",),
    ("delivery", "teams"),
    ("delivery", "teams", "enabled"),
    ("delivery", "teams", "webhook_url"),
    ("delivery", "slack"),
    ("delivery", "slack", "enabled"),
    ("delivery", "slack", "webhook_url"),
    ("scheduler",),
    ("scheduler", "trigger"),
    ("scheduler", "cron"),
    ("scheduler", "watch_directory"),
    ("scheduler", "filename_pattern"),
    ("scheduler", "llm_mode"),
    ("alerts",),
    ("alerts", "on_llm_fallback"),
    ("alerts", "on_pipeline_error"),
    ("alerts", "on_no_new_file"),
)


def load_delivery_config(path: Path = Path("config/delivery.yaml")) -> dict:
    """Load delivery.yaml and raise ValueError when required keys are missing."""
    with path.open() as f:
        cfg = yaml.safe_load(f) or {}

    if not isinstance(cfg, dict):
        raise ValueError("delivery config must be a mapping")

    for key_path in _REQUIRED_KEYS:
        _require_key(cfg, key_path)

    return cfg


def resolve_webhook_url(template: str) -> str | None:
    """
    Resolve a ${ENV_VAR} placeholder from os.environ.

    Returns None when the template is not a valid placeholder or the env var is unset.
    """
    match = _PLACEHOLDER_RE.fullmatch(template)
    if match is None:
        return None
    return os.environ.get(match.group(1))


def teams_enabled(cfg: dict) -> bool:
    """True only when Teams delivery is enabled and the webhook env var resolves."""
    teams_cfg = cfg["delivery"]["teams"]
    return bool(teams_cfg["enabled"] and resolve_webhook_url(teams_cfg["webhook_url"]))


def slack_enabled(cfg: dict) -> bool:
    """True only when Slack delivery is enabled and the webhook env var resolves."""
    slack_cfg = cfg["delivery"]["slack"]
    return bool(slack_cfg["enabled"] and resolve_webhook_url(slack_cfg["webhook_url"]))


def _require_key(cfg: dict[str, Any], key_path: tuple[str, ...]) -> None:
    current: Any = cfg
    for key in key_path:
        if not isinstance(current, dict) or key not in current:
            dotted = ".".join(key_path)
            raise ValueError(f"Missing required config key: {dotted}")
        current = current[key]
