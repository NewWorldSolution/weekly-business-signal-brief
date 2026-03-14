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
