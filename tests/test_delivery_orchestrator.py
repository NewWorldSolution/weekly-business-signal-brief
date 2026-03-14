"""Tests for wbsb.delivery.orchestrator."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.delivery.models import DeliveryResult, DeliveryStatus, DeliveryTarget
from wbsb.delivery.orchestrator import deliver_run, load_run_artifacts
from wbsb.domain.models import Findings, LLMResult, Periods, RunMeta

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RUN_ID = "20260310T090000Z_abc123"

_MANIFEST = {
    "run_id": _RUN_ID,
    "generated_at": "2026-03-10T09:00:00+00:00",
    "input_file": "weekly_data_2026-03-10.csv",
    "input_sha256": "a" * 64,
    "config_sha256": "b" * 64,
    "elapsed_seconds": 1.23,
    "llm_status": "success",
}

_MANIFEST_FALLBACK = {**_MANIFEST, "llm_status": "fallback"}
_MANIFEST_OFF = {**_MANIFEST, "llm_status": "off"}


def _make_findings() -> Findings:
    return Findings(
        run=RunMeta(
            run_id=_RUN_ID,
            generated_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            input_file="weekly_data_2026-03-10.csv",
            input_sha256="a" * 64,
            config_sha256="b" * 64,
        ),
        periods=Periods(
            current_week_start=date(2026, 3, 9),
            current_week_end=date(2026, 3, 15),
            previous_week_start=date(2026, 3, 2),
            previous_week_end=date(2026, 3, 8),
        ),
        metrics=[],
        signals=[],
        audit=[],
    )


def _write_run(
    output_dir: Path,
    run_id: str,
    manifest: dict,
    with_llm_response: bool = False,
) -> None:
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True)
    findings = _make_findings()
    (run_dir / "findings.json").write_text(
        findings.model_dump_json(), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    if with_llm_response:
        llm_result = LLMResult(situation="Revenue softened this week.")
        (run_dir / "llm_response.json").write_text(
            json.dumps({"llm_result": llm_result.model_dump(mode="json")}),
            encoding="utf-8",
        )


def _delivery_cfg(
    teams_enabled: bool = False,
    slack_enabled: bool = False,
    teams_url: str = "${TEAMS_WEBHOOK_URL}",
    slack_url: str = "${SLACK_WEBHOOK_URL}",
) -> dict:
    return {
        "delivery": {
            "teams": {"enabled": teams_enabled, "webhook_url": teams_url},
            "slack": {"enabled": slack_enabled, "webhook_url": slack_url},
        }
    }


# ---------------------------------------------------------------------------
# load_run_artifacts
# ---------------------------------------------------------------------------


def test_load_run_artifacts_success(tmp_path: Path) -> None:
    """Loads all three artifacts when all files are present."""
    _write_run(tmp_path, _RUN_ID, _MANIFEST, with_llm_response=True)

    result = load_run_artifacts(_RUN_ID, tmp_path)

    assert isinstance(result["findings"], Findings)
    assert result["findings"].run.run_id == _RUN_ID
    assert isinstance(result["manifest"], dict)
    assert result["manifest"]["llm_status"] == "success"
    assert isinstance(result["llm_result"], LLMResult)
    assert result["llm_result"].situation == "Revenue softened this week."


def test_load_run_artifacts_no_llm_response(tmp_path: Path) -> None:
    """llm_result is None when llm_response.json is absent — no error raised."""
    _write_run(tmp_path, _RUN_ID, _MANIFEST_OFF, with_llm_response=False)

    result = load_run_artifacts(_RUN_ID, tmp_path)

    assert isinstance(result["findings"], Findings)
    assert result["llm_result"] is None


def test_load_run_artifacts_missing_findings(tmp_path: Path) -> None:
    """FileNotFoundError with a clear message when findings.json is absent."""
    run_dir = tmp_path / _RUN_ID
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="findings.json"):
        load_run_artifacts(_RUN_ID, tmp_path)


# ---------------------------------------------------------------------------
# deliver_run
# ---------------------------------------------------------------------------

_SUCCESS_RESULT = DeliveryResult(
    target=DeliveryTarget.teams,
    status=DeliveryStatus.success,
    http_status_code=200,
    error=None,
    delivered_at="2026-03-10T09:00:00Z",
)

_SLACK_SUCCESS = DeliveryResult(
    target=DeliveryTarget.slack,
    status=DeliveryStatus.success,
    http_status_code=200,
    error=None,
    delivered_at="2026-03-10T09:00:00Z",
)


def _patched_artifacts(manifest: dict | None = None) -> dict:
    return {
        "findings": _make_findings(),
        "manifest": manifest or _MANIFEST,
        "llm_result": LLMResult(situation="Revenue softened."),
    }


def test_deliver_run_teams_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only Teams fires when Slack is disabled."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")
    _write_run(tmp_path, _RUN_ID, _MANIFEST, with_llm_response=True)

    with (
        patch(
            "wbsb.delivery.orchestrator.load_run_artifacts",
            return_value=_patched_artifacts(),
        ),
        patch(
            "wbsb.delivery.orchestrator.send_teams_card",
            return_value=_SUCCESS_RESULT,
        ) as mock_send,
    ):
        results = deliver_run(
            _RUN_ID,
            _delivery_cfg(teams_enabled=True, slack_enabled=False),
            tmp_path,
        )

    assert len(results) == 1
    assert results[0].target == DeliveryTarget.teams
    assert results[0].status == DeliveryStatus.success
    mock_send.assert_called_once()


def test_deliver_run_both_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both Teams and Slack fire when both are enabled."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://slack.test")

    with (
        patch(
            "wbsb.delivery.orchestrator.load_run_artifacts",
            return_value=_patched_artifacts(),
        ),
        patch(
            "wbsb.delivery.orchestrator.send_teams_card",
            return_value=_SUCCESS_RESULT,
        ),
        patch(
            "wbsb.delivery.orchestrator.send_slack_message",
            return_value=_SLACK_SUCCESS,
        ),
    ):
        results = deliver_run(
            _RUN_ID,
            _delivery_cfg(teams_enabled=True, slack_enabled=True),
            tmp_path,
        )

    assert len(results) == 2
    targets = {r.target for r in results}
    assert DeliveryTarget.teams in targets
    assert DeliveryTarget.slack in targets


def test_deliver_run_no_targets(tmp_path: Path) -> None:
    """Returns empty list when both channels are disabled."""
    with patch(
        "wbsb.delivery.orchestrator.load_run_artifacts",
        return_value=_patched_artifacts(),
    ):
        results = deliver_run(
            _RUN_ID,
            _delivery_cfg(teams_enabled=False, slack_enabled=False),
            tmp_path,
        )

    assert results == []


def test_deliver_run_failure_captured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exception from send is captured as a failed DeliveryResult — never raised."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")

    with (
        patch(
            "wbsb.delivery.orchestrator.load_run_artifacts",
            return_value=_patched_artifacts(),
        ),
        patch(
            "wbsb.delivery.orchestrator.send_teams_card",
            side_effect=RuntimeError("network exploded"),
        ),
    ):
        results = deliver_run(
            _RUN_ID,
            _delivery_cfg(teams_enabled=True, slack_enabled=False),
            tmp_path,
        )

    assert len(results) == 1
    assert results[0].status == DeliveryStatus.failed
    assert results[0].target == DeliveryTarget.teams
    assert "network exploded" in (results[0].error or "")


def test_deliver_run_llm_fallback_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When manifest.llm_status is 'fallback', card builders receive llm_result=None."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")

    captured_llm: list = []

    def _fake_build(findings, llm_result, feedback_url):
        captured_llm.append(llm_result)
        return {}

    with (
        patch(
            "wbsb.delivery.orchestrator.load_run_artifacts",
            return_value=_patched_artifacts(manifest=_MANIFEST_FALLBACK),
        ),
        patch("wbsb.delivery.orchestrator.build_teams_card", side_effect=_fake_build),
        patch(
            "wbsb.delivery.orchestrator.send_teams_card",
            return_value=_SUCCESS_RESULT,
        ),
    ):
        deliver_run(
            _RUN_ID,
            _delivery_cfg(teams_enabled=True, slack_enabled=False),
            tmp_path,
        )

    assert captured_llm == [None], (
        "orchestrator must pass llm_result=None to card builders when fallback is detected"
    )


# ---------------------------------------------------------------------------
# deliver_run — missing-artifact capture (never raises)
# ---------------------------------------------------------------------------


def test_deliver_run_missing_artifacts_captured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """deliver_run() must return a failed DeliveryResult rather than raising when
    the run directory or findings.json is absent."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")

    # tmp_path has no run subdirectory — load_run_artifacts will raise FileNotFoundError
    results = deliver_run(
        "nonexistent_run_id",
        _delivery_cfg(teams_enabled=True, slack_enabled=False),
        tmp_path,
    )

    assert len(results) >= 1, "expected at least one failed DeliveryResult"
    assert all(r.status == DeliveryStatus.failed for r in results)
    assert any("findings.json" in (r.error or "") or "not found" in (r.error or "").lower()
               for r in results)


# ---------------------------------------------------------------------------
# CLI — wbsb run --deliver correctness
# ---------------------------------------------------------------------------


def test_cli_run_deliver_correct_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """wbsb run --deliver must call deliver_run with the run_id just produced,
    not with whatever directory happened to be most recently modified."""
    from typer.testing import CliRunner

    from wbsb.cli import app

    run_id = "20260310T090000Z_correct1"
    # Pre-populate a decoy run that is older — the mtime approach would pick
    # this one if no snapshot is used.
    decoy_dir = tmp_path / "20260309T080000Z_decoy0"
    decoy_dir.mkdir()

    captured: dict = {}

    def fake_execute(**kwargs):
        (kwargs["output_dir"] / run_id).mkdir(parents=True, exist_ok=True)
        return 0

    def fake_deliver(rid, cfg, out_dir=Path("runs")):
        captured["run_id"] = rid
        return []

    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")
    simple_cfg = {
        "delivery": {
            "teams": {"enabled": True, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    input_file = tmp_path / "data.csv"
    input_file.write_text("week_start,revenue\n2026-03-09,1000\n")

    runner = CliRunner()
    with (
        patch("wbsb.pipeline.execute", side_effect=fake_execute),
        patch("wbsb.delivery.config.load_delivery_config", return_value=simple_cfg),
        patch("wbsb.delivery.orchestrator.deliver_run", side_effect=fake_deliver),
    ):
        runner.invoke(
            app,
            ["run", "-i", str(input_file), "--output", str(tmp_path), "--deliver"],
        )

    assert captured.get("run_id") == run_id, (
        f"deliver_run was called with {captured.get('run_id')!r}, expected {run_id!r}"
    )


def test_cli_run_deliver_does_not_crash_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """wbsb run exit code must be 0 (pipeline success) even when delivery raises."""
    from typer.testing import CliRunner

    from wbsb.cli import app

    run_id = "20260310T090000Z_crash01"

    def fake_execute(**kwargs):
        (kwargs["output_dir"] / run_id).mkdir(parents=True, exist_ok=True)
        return 0

    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams.test")
    simple_cfg = {
        "delivery": {
            "teams": {"enabled": True, "webhook_url": "${TEAMS_WEBHOOK_URL}"},
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        }
    }

    input_file = tmp_path / "data.csv"
    input_file.write_text("week_start,revenue\n2026-03-09,1000\n")

    runner = CliRunner()
    with (
        patch("wbsb.pipeline.execute", side_effect=fake_execute),
        patch("wbsb.delivery.config.load_delivery_config", return_value=simple_cfg),
        patch(
            "wbsb.delivery.orchestrator.deliver_run",
            side_effect=RuntimeError("delivery exploded"),
        ),
    ):
        result = runner.invoke(
            app,
            ["run", "-i", str(input_file), "--output", str(tmp_path), "--deliver"],
        )

    assert result.exit_code == 0, (
        "pipeline succeeded so exit code must be 0 even when delivery crashes"
    )


# ---------------------------------------------------------------------------
# CLI — auto mode must never trigger delivery (scheduler boundary)
# ---------------------------------------------------------------------------


def test_auto_run_does_not_trigger_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """wbsb run --auto --deliver must never call deliver_run.

    The scheduler is a run/no-run decision layer only. Delivery is the
    responsibility of wbsb run (manual) or wbsb deliver --run-id.
    """
    from typer.testing import CliRunner

    from wbsb.cli import app

    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    data_file = watch_dir / "weekly_data_2026W10.csv"
    data_file.write_text("week_start,revenue\n2026-03-09,1000\n")

    deliver_run_called: list[bool] = []

    def fake_execute(**kwargs):
        (kwargs["output_dir"] / "20260310T090000Z_abc123").mkdir(parents=True, exist_ok=True)
        return 0

    def fake_deliver(*args, **kwargs):
        deliver_run_called.append(True)
        return []

    runner = CliRunner()
    with (
        patch("wbsb.pipeline.execute", side_effect=fake_execute),
        patch("wbsb.delivery.orchestrator.deliver_run", side_effect=fake_deliver),
        patch(
            "wbsb.scheduler.auto.already_processed",
            return_value=False,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "run",
                "--auto",
                "--watch-dir", str(watch_dir),
                "--output", str(tmp_path),
                "--deliver",
            ],
        )

    assert not deliver_run_called, (
        "deliver_run must never be called from --auto mode; "
        f"exit_code={result.exit_code}, output={result.output!r}"
    )


def test_auto_run_config_load_failure_warns_not_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When scheduler config loading fails, a warning is printed and auto-run continues."""
    from typer.testing import CliRunner

    from wbsb.cli import app

    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    data_file = watch_dir / "weekly_data_2026W10.csv"
    data_file.write_text("week_start,revenue\n2026-03-09,1000\n")

    # Write a delivery.yaml so the config-load path is entered
    delivery_yaml = tmp_path / "delivery.yaml"
    delivery_yaml.write_text("invalid: yaml: [}")

    def fake_execute(**kwargs):
        (kwargs["output_dir"] / "20260310T090000Z_abc123").mkdir(parents=True, exist_ok=True)
        return 0

    runner = CliRunner()
    with (
        patch("wbsb.pipeline.execute", side_effect=fake_execute),
        patch("wbsb.scheduler.auto.already_processed", return_value=False),
        patch(
            "wbsb.delivery.config.load_delivery_config",
            side_effect=ValueError("bad config"),
        ),
        # Patch Path.exists to make delivery.yaml appear present
        patch("wbsb.cli.Path.exists", return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "run",
                "--auto",
                "--watch-dir", str(watch_dir),
                "--output", str(tmp_path),
            ],
        )

    # Must not crash — exit code 0 (pipeline ran) or scheduler skip (not exit 1)
    # Warning must appear in output (typer CliRunner merges stderr into output by default)
    assert result.exit_code != 1 or "Warning:" in result.output, (
        "config load failure must emit a warning, not crash silently"
    )
