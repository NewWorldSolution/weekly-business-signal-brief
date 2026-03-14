"""Tests for wbsb.delivery.config."""
from __future__ import annotations

from pathlib import Path

import pytest

from wbsb.delivery.config import (
    load_delivery_config,
    resolve_webhook_url,
    slack_enabled,
    teams_enabled,
)


def _write_config(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_load_delivery_config_valid(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "delivery.yaml",
        """
delivery:
  teams:
    enabled: false
    webhook_url: "${TEAMS_WEBHOOK_URL}"
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
scheduler:
  trigger: "manual"
  cron: "0 8 * * 1"
  watch_directory: "data/incoming"
  filename_pattern: "weekly_data_*.csv"
  llm_mode: "off"
alerts:
  on_llm_fallback: true
  on_pipeline_error: true
  on_no_new_file: true
""".strip(),
    )

    cfg = load_delivery_config(config_path)

    assert cfg["delivery"]["teams"]["webhook_url"] == "${TEAMS_WEBHOOK_URL}"
    assert cfg["scheduler"]["filename_pattern"] == "weekly_data_*.csv"
    assert cfg["alerts"]["on_pipeline_error"] is True


def test_load_delivery_config_missing_required_key(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "delivery.yaml",
        """
delivery:
  teams:
    enabled: true
    webhook_url: "${TEAMS_WEBHOOK_URL}"
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"
scheduler:
  trigger: "manual"
  cron: "0 8 * * 1"
  filename_pattern: "weekly_data_*.csv"
  llm_mode: "off"
alerts:
  on_llm_fallback: true
  on_pipeline_error: true
  on_no_new_file: true
""".strip(),
    )

    with pytest.raises(ValueError, match="scheduler.watch_directory"):
        load_delivery_config(config_path)


def test_resolve_webhook_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.test/teams")

    resolved = resolve_webhook_url("${TEAMS_WEBHOOK_URL}")

    assert resolved == "https://example.test/teams"


def test_resolve_webhook_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)

    resolved = resolve_webhook_url("${TEAMS_WEBHOOK_URL}")

    assert resolved is None


def test_teams_enabled_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.test/teams")
    cfg = {
        "delivery": {
            "teams": {"enabled": True, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    assert teams_enabled(cfg) is True


def test_teams_enabled_flag_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.test/teams")
    cfg = {
        "delivery": {
            "teams": {"enabled": False, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    assert teams_enabled(cfg) is False


def test_teams_enabled_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)
    cfg = {
        "delivery": {
            "teams": {"enabled": True, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    assert teams_enabled(cfg) is False


def test_slack_enabled_same_logic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.test/slack")
    cfg = {
        "delivery": {
            "teams": {"enabled": False, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": True, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    assert slack_enabled(cfg) is True

    cfg["delivery"]["slack"]["enabled"] = False
    assert slack_enabled(cfg) is False

    cfg["delivery"]["slack"]["enabled"] = True
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert slack_enabled(cfg) is False
