from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.delivery.alerts import (
    build_llm_fallback_alert,
    build_no_file_alert,
    build_pipeline_error_alert,
    send_alert,
)
from wbsb.delivery.models import DeliveryStatus

# ---------------------------------------------------------------------------
# Alert payload structure
# ---------------------------------------------------------------------------


def test_pipeline_error_alert_structure() -> None:
    alert = build_pipeline_error_alert("Column 'revenue' missing", run_id="20260312T080000Z_abc123")

    assert alert["type"] == "pipeline_error"
    assert alert["title"] == "⚠️ WBSB Pipeline Error"
    assert "Column 'revenue' missing" in alert["error"]
    assert alert["run_id"] == "20260312T080000Z_abc123"
    assert "Check logs" in alert["instruction"]


def test_pipeline_error_alert_truncates_long_error() -> None:
    long_error = "x" * 300
    alert = build_pipeline_error_alert(long_error, run_id=None)

    assert len(alert["error"]) == 200
    assert alert["run_id"] is None


def test_no_file_alert_structure() -> None:
    alert = build_no_file_alert("data/incoming")

    assert alert["type"] == "no_file"
    assert alert["title"] == "📋 WBSB — No New Data Detected"
    assert "data/incoming" in alert["message"]
    assert "Upload a file" in alert["message"]


def test_llm_fallback_alert_structure() -> None:
    alert = build_llm_fallback_alert(run_id="20260312T080000Z_abc123")

    assert alert["type"] == "llm_fallback"
    assert "AI" in alert["title"] or "Unavailable" in alert["title"]
    assert "fallback" in alert["message"].lower() or "unavailable" in alert["message"].lower()
    assert alert["run_id"] == "20260312T080000Z_abc123"


def test_llm_fallback_alert_run_id_none() -> None:
    alert = build_llm_fallback_alert(run_id=None)

    assert alert["run_id"] is None


# ---------------------------------------------------------------------------
# send_alert dispatch
# ---------------------------------------------------------------------------


def _disabled_cfg() -> dict:
    """Delivery config with both targets disabled."""
    return {
        "delivery": {
            "teams": {"enabled": False, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        },
        "scheduler": {
            "trigger": "manual",
            "cron": "0 8 * * 1",
            "watch_directory": "data/incoming",
            "filename_pattern": "*.csv",
            "llm_mode": "off",
        },
        "alerts": {
            "on_llm_fallback": True,
            "on_pipeline_error": True,
            "on_no_new_file": True,
        },
    }


def test_send_alert_skipped_when_disabled() -> None:
    alert = build_pipeline_error_alert("oops", run_id=None)
    results = send_alert(alert, _disabled_cfg())

    # Both targets are disabled — each should be skipped
    assert len(results) == 2
    for r in results:
        assert r.status == DeliveryStatus.skipped
        assert r.error is None
        assert r.http_status_code is None


def test_send_alert_non_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_alert must not propagate exceptions from the underlying senders."""
    import wbsb.delivery.alerts as alerts_mod

    def _boom(*_args, **_kwargs):  # noqa: ANN001, ANN202
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(alerts_mod, "send_alert", send_alert)  # ensure real function

    # Patch teams_enabled / slack_enabled to return True, and send functions to raise
    import wbsb.delivery.config as cfg_mod
    import wbsb.delivery.slack as slack_mod
    import wbsb.delivery.teams as teams_mod

    monkeypatch.setattr(cfg_mod, "teams_enabled", lambda _cfg: True)
    monkeypatch.setattr(cfg_mod, "slack_enabled", lambda _cfg: True)
    monkeypatch.setattr(cfg_mod, "resolve_webhook_url", lambda _t: "https://example.test/wh")
    monkeypatch.setattr(teams_mod, "send_teams_card", _boom)
    monkeypatch.setattr(slack_mod, "send_slack_message", _boom)

    alert = build_pipeline_error_alert("crash", run_id=None)
    results = send_alert(alert, _disabled_cfg())  # cfg content doesn't matter — patched above

    # Must not raise; both targets captured as failed
    assert len(results) == 2
    for r in results:
        assert r.status == DeliveryStatus.failed
        assert r.error is not None


# ---------------------------------------------------------------------------
# CLI-level visible warning tests
# ---------------------------------------------------------------------------


def test_cli_auto_run_emits_no_file_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Auto-run with no matching file must emit a visible warning to stdout."""
    from typer.testing import CliRunner

    import wbsb.scheduler.auto as auto_mod
    from wbsb.cli import app

    monkeypatch.setattr(auto_mod, "find_latest_input", lambda *_args, **_kw: None)

    result = CliRunner().invoke(
        app, ["run", "--auto", "--watch-dir", str(tmp_path)]
    )

    assert "⚠️" in result.output
    assert "no new data file" in result.output.lower()
    assert result.exit_code == 0


def test_cli_run_emits_pipeline_error_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pipeline exception must emit a visible warning containing the error text."""
    from typer.testing import CliRunner

    import wbsb.pipeline as pipeline_mod
    from wbsb.cli import app

    def _raise(*_args, **_kwargs):  # noqa: ANN001, ANN202
        raise RuntimeError("missing required column: revenue")

    monkeypatch.setattr(pipeline_mod, "execute", _raise)

    fake_input = tmp_path / "data.csv"
    fake_input.write_text("col\n1\n")

    result = CliRunner().invoke(app, ["run", "--input", str(fake_input)])

    assert "⚠️" in result.output
    assert "Pipeline error" in result.output
    assert result.exit_code == 1
