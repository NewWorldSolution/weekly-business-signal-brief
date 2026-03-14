from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.delivery.models import DeliveryStatus, DeliveryTarget
from wbsb.delivery.slack import (
    build_slack_blocks,
    send_slack_message,
)
from wbsb.domain.models import Findings, LLMResult, Periods, RunMeta, Signal


def _findings(
    *,
    signals: list[Signal] | None = None,
    run_id: str = "20260312T120000Z_3a1b2c",
) -> Findings:
    return Findings(
        run=RunMeta(
            run_id=run_id,
            generated_at=datetime(2026, 3, 12, 12, 0, 0),
            input_file="data/incoming/weekly_data.csv",
            input_sha256="a" * 64,
            config_sha256="b" * 64,
        ),
        periods=Periods(
            current_week_start=date(2026, 3, 2),
            current_week_end=date(2026, 3, 8),
            previous_week_start=date(2026, 2, 23),
            previous_week_end=date(2026, 3, 1),
        ),
        metrics=[],
        signals=signals or [],
        dominant_cluster_exists=False,
        audit=[],
    )


def _signal(rule_id: str, label: str, severity: str = "WARN") -> Signal:
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id="orders",
        label=label,
        explanation=f"{label} explanation",
        evidence={},
    )


def _llm_result(
    *,
    situation: str = "Revenue softened while order volume held steady.",
) -> LLMResult:
    return LLMResult(situation=situation)


def test_build_blocks_with_llm() -> None:
    findings = _findings(signals=[_signal("warn_b", "Margin pressure")])

    blocks = build_slack_blocks(findings, _llm_result(), "https://example.test/feedback")

    assert [block["type"] for block in blocks] == [
        "header",
        "context",
        "divider",
        "section",
        "section",
        "divider",
        "actions",
    ]
    assert blocks[0]["text"]["text"] == "Weekly Business Signal Brief"
    assert blocks[1]["elements"][0]["text"] == (
        "2026-03-02 to 2026-03-08 | Run 20260312T120000Z_3a1b2c"
    )
    assert blocks[3]["text"]["text"] == "Revenue softened while order volume held steady."


def test_build_blocks_llm_fallback() -> None:
    findings = _findings()

    blocks = build_slack_blocks(findings, None, "https://example.test/feedback")

    assert blocks[3]["text"]["text"] == (
        "⚠️ AI analysis unavailable this week — showing deterministic report"
    )


def test_build_blocks_warn_signals() -> None:
    findings = _findings(
        signals=[
            _signal("warn_c", "C"),
            _signal("warn_a", "A"),
            _signal("info_a", "Ignore me", severity="INFO"),
            _signal("warn_d", "D"),
            _signal("warn_b", "B"),
        ]
    )

    blocks = build_slack_blocks(findings, _llm_result(), "https://example.test/feedback")

    assert blocks[4]["text"]["text"] == "4 warning(s)\n• A\n• B\n• C\n+ 1 more"


def test_build_blocks_no_signals() -> None:
    findings = _findings()

    blocks = build_slack_blocks(findings, _llm_result(), "https://example.test/feedback")

    assert blocks[4]["text"]["text"] == "No warnings this week."


def test_build_blocks_no_feedback_url() -> None:
    findings = _findings()

    blocks = build_slack_blocks(findings, _llm_result(), None)

    assert [block["type"] for block in blocks] == [
        "header",
        "context",
        "divider",
        "section",
        "section",
        "divider",
    ]


def test_build_blocks_feedback_actions() -> None:
    findings = _findings()

    blocks = build_slack_blocks(findings, _llm_result(), "https://example.test/feedback")

    action_block = blocks[-1]
    assert action_block["type"] == "actions"
    assert [element["text"]["text"] for element in action_block["elements"]] == [
        "✅ Looks right",
        "⚠️ Unexpected",
        "❌ Something's wrong",
    ]
    assert json.loads(action_block["elements"][0]["value"]) == {
        "label": "expected",
        "run_id": "20260312T120000Z_3a1b2c",
    }
    assert json.loads(action_block["elements"][1]["value"])["label"] == "unexpected"
    assert json.loads(action_block["elements"][2]["value"])["label"] == "incorrect"


class _SuccessResponse:
    def __init__(self, status_code: int) -> None:
        self._status_code = status_code

    def __enter__(self) -> _SuccessResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def getcode(self) -> int:
        return self._status_code


def test_send_message_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout: int):
        captured["timeout"] = timeout
        captured["body"] = request.data.decode("utf-8")
        captured["content_type"] = request.headers["Content-type"]
        return _SuccessResponse(200)

    monkeypatch.setattr("wbsb.delivery.slack.urlopen", _fake_urlopen)

    result = send_slack_message([{"type": "divider"}], "https://example.test/slack")

    assert result.target == DeliveryTarget.slack
    assert result.status == DeliveryStatus.success
    assert result.http_status_code == 200
    assert result.error is None
    assert result.delivered_at is not None
    assert captured["timeout"] == 10
    assert json.loads(captured["body"]) == {"blocks": [{"type": "divider"}]}
    assert captured["content_type"] == "application/json"


def test_send_message_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_urlopen(request, timeout: int):
        raise HTTPError(
            request.full_url,
            500,
            "server error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("wbsb.delivery.slack.urlopen", _fake_urlopen)

    result = send_slack_message([{"type": "divider"}], "https://example.test/slack")

    assert result.target == DeliveryTarget.slack
    assert result.status == DeliveryStatus.failed
    assert result.http_status_code == 500
    assert result.delivered_at is None
    assert result.error == "Slack webhook returned HTTP 500"


def test_send_message_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_urlopen(request, timeout: int):
        raise TimeoutError("timed out")

    monkeypatch.setattr("wbsb.delivery.slack.urlopen", _fake_urlopen)

    result = send_slack_message([{"type": "divider"}], "https://example.test/slack")

    assert result.target == DeliveryTarget.slack
    assert result.status == DeliveryStatus.failed
    assert result.http_status_code is None
    assert result.delivered_at is None
    assert result.error == "Slack webhook request timed out"
