"""Teams Adaptive Card builder and sender."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from urllib import error, request

from wbsb.delivery.models import DeliveryResult, DeliveryStatus, DeliveryTarget
from wbsb.domain.models import Findings, LLMResult

try:
    import requests  # type: ignore[import-not-found]
except ModuleNotFoundError:
    class _RequestsShim:
        class Timeout(Exception):
            """Raised on webhook timeout."""

        @staticmethod
        def post(url: str, json: dict, timeout: int) -> SimpleNamespace:
            data = bytes(__import__("json").dumps(json), encoding="utf-8")
            req = request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=timeout) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    return SimpleNamespace(status_code=response.status, text=body)
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                return SimpleNamespace(status_code=exc.code, text=body)
            except TimeoutError as exc:
                raise _RequestsShim.Timeout(str(exc)) from exc

    requests = _RequestsShim()


_FALLBACK_BANNER = "⚠️ AI analysis unavailable this week — showing deterministic report"
_NO_WARNINGS_TEXT = "No warnings this week. All metrics within thresholds."
_FEEDBACK_BUTTONS = (
    ("✅ Looks right", "expected"),
    ("⚠️ Unexpected", "unexpected"),
    ("❌ Something's wrong", "incorrect"),
)


def build_teams_card(
    findings: Findings,
    llm_result: LLMResult | None,
    feedback_webhook_url: str | None,
) -> dict:
    """Build an Adaptive Card payload for Teams delivery."""
    period = (
        f"{findings.periods.current_week_start.isoformat()} "
        f"– {findings.periods.current_week_end.isoformat()}"
    )
    warn_signals = sorted(
        (signal for signal in findings.signals if signal.severity == "WARN"),
        key=lambda signal: signal.rule_id,
    )
    situation = _resolve_situation(llm_result)

    body: list[dict] = [
        {
            "type": "TextBlock",
            "text": f"Weekly Business Signal Brief — {period}",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": (
                f"Run {findings.run.run_id} | "
                f"{findings.periods.current_week_start.isoformat()} to "
                f"{findings.periods.current_week_end.isoformat()} | "
                f"{len(warn_signals)} warnings"
            ),
            "isSubtle": True,
            "spacing": "Small",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": situation,
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    if warn_signals:
        for signal in warn_signals:
            body.append(
                {
                    "type": "TextBlock",
                    "text": f"⚠️ {signal.rule_id} — {signal.label}",
                    "weight": "Bolder",
                    "wrap": True,
                    "spacing": "Medium",
                }
            )
            body.append(
                {
                    "type": "TextBlock",
                    "text": signal.explanation,
                    "wrap": True,
                    "spacing": "Small",
                }
            )
    else:
        body.append(
            {
                "type": "TextBlock",
                "text": _NO_WARNINGS_TEXT,
                "wrap": True,
                "spacing": "Medium",
            }
        )

    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }

    if feedback_webhook_url is not None:
        card["attachments"][0]["content"]["actions"] = [
            {
                "type": "Action.Submit",
                "title": title,
                "data": {"run_id": findings.run.run_id, "label": label},
            }
            for title, label in _FEEDBACK_BUTTONS
        ]

    return card


def send_teams_card(card: dict, webhook_url: str) -> DeliveryResult:
    """POST an Adaptive Card payload to Teams without raising errors."""
    try:
        response = requests.post(webhook_url, json=card, timeout=10)
    except requests.Timeout:
        return DeliveryResult(
            target=DeliveryTarget.teams,
            status=DeliveryStatus.failed,
            http_status_code=None,
            error="Teams webhook request timed out",
            delivered_at=None,
        )
    except Exception as exc:
        return DeliveryResult(
            target=DeliveryTarget.teams,
            status=DeliveryStatus.failed,
            http_status_code=None,
            error=f"Teams webhook request failed: {exc}",
            delivered_at=None,
        )

    if 200 <= response.status_code < 300:
        return DeliveryResult(
            target=DeliveryTarget.teams,
            status=DeliveryStatus.success,
            http_status_code=response.status_code,
            error=None,
            delivered_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )

    return DeliveryResult(
        target=DeliveryTarget.teams,
        status=DeliveryStatus.failed,
        http_status_code=response.status_code,
        error=f"Teams webhook returned HTTP {response.status_code}",
        delivered_at=None,
    )


def _resolve_situation(llm_result: LLMResult | None) -> str:
    if llm_result is None or llm_result.situation is None:
        return _FALLBACK_BANNER

    situation = llm_result.situation.strip()
    if not situation:
        return _FALLBACK_BANNER
    return situation
