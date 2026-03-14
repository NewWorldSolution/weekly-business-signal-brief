"""Tests for wbsb.delivery.teams."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.delivery.models import DeliveryStatus, DeliveryTarget
from wbsb.delivery.teams import build_teams_card, requests, send_teams_card
from wbsb.domain.models import Findings, LLMResult, Periods, RunMeta, Signal


def _make_findings(signals: list[Signal]) -> Findings:
    return Findings(
        run=RunMeta(
            run_id="20260310T090000Z_abc123",
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
        signals=signals,
        audit=[],
    )


def _signal(rule_id: str, severity: str, label: str, explanation: str) -> Signal:
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id="net_revenue",
        label=label,
        category="revenue",
        explanation=explanation,
        evidence={},
    )


def _card_texts(card: dict) -> list[str]:
    return [item["text"] for item in card["attachments"][0]["content"]["body"]]


def test_build_card_with_llm() -> None:
    findings = _make_findings([_signal("A1", "WARN", "Revenue Decline", "Revenue fell 18%.")])
    llm_result = LLMResult(situation="Performance softened across revenue this week.")

    card = build_teams_card(findings, llm_result, "https://feedback.test")

    assert card["attachments"][0]["content"]["version"] == "1.4"
    assert "Weekly Business Signal Brief — 2026-03-09 – 2026-03-15" in _card_texts(card)
    assert "Performance softened across revenue this week." in _card_texts(card)


def test_build_card_llm_fallback() -> None:
    findings = _make_findings([])

    card = build_teams_card(findings, None, "https://feedback.test")

    assert "⚠️ AI analysis unavailable this week — showing deterministic report" in _card_texts(
        card
    )


def test_build_card_warn_signals() -> None:
    findings = _make_findings(
        [
            _signal("B1", "WARN", "CAC Rising", "CAC rose 22%."),
            _signal("A1", "WARN", "Revenue Decline", "Revenue fell 18%."),
            _signal("H1", "INFO", "Gross Margin Low", "Margin is near threshold."),
        ]
    )

    card = build_teams_card(findings, None, "https://feedback.test")
    texts = _card_texts(card)

    assert "⚠️ A1 — Revenue Decline" in texts
    assert "⚠️ B1 — CAC Rising" in texts
    assert texts.index("⚠️ A1 — Revenue Decline") < texts.index("⚠️ B1 — CAC Rising")
    assert "⚠️ H1 — Gross Margin Low" not in texts


def test_build_card_no_signals() -> None:
    findings = _make_findings([])

    card = build_teams_card(findings, None, "https://feedback.test")

    assert "No warnings this week. All metrics within thresholds." in _card_texts(card)


def test_build_card_no_feedback_url() -> None:
    findings = _make_findings([])

    card = build_teams_card(findings, None, None)

    assert "actions" not in card["attachments"][0]["content"]


def test_build_card_feedback_buttons() -> None:
    findings = _make_findings([])

    card = build_teams_card(findings, None, "https://feedback.test")
    actions = card["attachments"][0]["content"]["actions"]

    assert len(actions) == 3
    assert [action["title"] for action in actions] == [
        "✅ Looks right",
        "⚠️ Unexpected",
        "❌ Something's wrong",
    ]
    assert [action["data"]["label"] for action in actions] == [
        "expected",
        "unexpected",
        "incorrect",
    ]
    assert all(action["data"]["run_id"] == findings.run.run_id for action in actions)


def test_send_card_success() -> None:
    card = {"hello": "world"}

    with patch.object(requests, "post", return_value=type("Resp", (), {"status_code": 200})()):
        result = send_teams_card(card, "https://teams.test")

    assert result.target == DeliveryTarget.teams
    assert result.status == DeliveryStatus.success
    assert result.http_status_code == 200
    assert result.error is None
    assert result.delivered_at is not None


def test_send_card_failure() -> None:
    card = {"hello": "world"}

    with patch.object(requests, "post", return_value=type("Resp", (), {"status_code": 500})()):
        result = send_teams_card(card, "https://teams.test")

    assert result.target == DeliveryTarget.teams
    assert result.status == DeliveryStatus.failed
    assert result.http_status_code == 500
    assert result.delivered_at is None


def test_send_card_timeout() -> None:
    card = {"hello": "world"}

    with patch.object(requests, "post", side_effect=requests.Timeout("simulated timeout")):
        result = send_teams_card(card, "https://teams.test")

    assert result.target == DeliveryTarget.teams
    assert result.status == DeliveryStatus.failed
    assert result.http_status_code is None
    assert "timed out" in result.error.lower()
    assert result.delivered_at is None
