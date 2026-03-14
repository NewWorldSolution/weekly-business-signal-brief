"""Alert payload builders and dispatcher for failure / degraded states."""
from __future__ import annotations

from wbsb.delivery.models import DeliveryResult, DeliveryStatus, DeliveryTarget

_ERROR_MAX_LEN = 200


def build_pipeline_error_alert(error: str, run_id: str | None) -> dict:
    """Build a minimal, platform-agnostic alert payload for pipeline errors."""
    return {
        "type": "pipeline_error",
        "title": "⚠️ WBSB Pipeline Error",
        "error": error[:_ERROR_MAX_LEN],
        "run_id": run_id,
        "instruction": "Check logs for full audit trail.",
    }


def build_llm_fallback_alert(run_id: str | None) -> dict:
    """Build alert payload for the LLM fallback condition."""
    return {
        "type": "llm_fallback",
        "title": "⚠️ WBSB — AI Analysis Unavailable",
        "message": (
            "AI narrative generation failed or was unavailable this week. "
            "The report was delivered with a deterministic fallback."
        ),
        "run_id": run_id,
    }


def build_no_file_alert(watch_directory: str) -> dict:
    """Build alert payload for the no-new-file condition."""
    return {
        "type": "no_file",
        "title": "📋 WBSB — No New Data Detected",
        "message": (
            f"No new weekly data file found in {watch_directory}. "
            "Upload a file to trigger the report."
        ),
    }


def send_alert(alert: dict, delivery_cfg: dict) -> list[DeliveryResult]:
    """Dispatch alert to all enabled delivery targets.

    Returns one DeliveryResult per target (success, failed, or skipped).
    Never raises.
    """
    from wbsb.delivery.config import resolve_webhook_url, slack_enabled, teams_enabled
    from wbsb.delivery.slack import send_slack_message
    from wbsb.delivery.teams import send_teams_card

    results: list[DeliveryResult] = []

    if teams_enabled(delivery_cfg):
        try:
            webhook_url = resolve_webhook_url(
                delivery_cfg["delivery"]["teams"]["webhook_url"]
            )
            card = _build_alert_teams_card(alert)
            results.append(send_teams_card(card, webhook_url))  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            results.append(
                DeliveryResult(
                    target=DeliveryTarget.teams,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=f"Teams alert delivery error: {exc}",
                    delivered_at=None,
                )
            )
    else:
        results.append(
            DeliveryResult(
                target=DeliveryTarget.teams,
                status=DeliveryStatus.skipped,
                http_status_code=None,
                error=None,
                delivered_at=None,
            )
        )

    if slack_enabled(delivery_cfg):
        try:
            webhook_url = resolve_webhook_url(
                delivery_cfg["delivery"]["slack"]["webhook_url"]
            )
            blocks = _build_alert_slack_blocks(alert)
            results.append(send_slack_message(blocks, webhook_url))  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            results.append(
                DeliveryResult(
                    target=DeliveryTarget.slack,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=f"Slack alert delivery error: {exc}",
                    delivered_at=None,
                )
            )
    else:
        results.append(
            DeliveryResult(
                target=DeliveryTarget.slack,
                status=DeliveryStatus.skipped,
                http_status_code=None,
                error=None,
                delivered_at=None,
            )
        )

    return results


def _build_alert_teams_card(alert: dict) -> dict:
    """Build a minimal Adaptive Card from a platform-agnostic alert dict."""
    body: list[dict] = [
        {
            "type": "TextBlock",
            "text": alert["title"],
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        }
    ]
    if alert.get("error"):
        body.append({"type": "TextBlock", "text": alert["error"], "wrap": True})
    if alert.get("run_id"):
        body.append(
            {"type": "TextBlock", "text": f"Run ID: {alert['run_id']}", "wrap": True}
        )
    if alert.get("instruction"):
        body.append(
            {
                "type": "TextBlock",
                "text": alert["instruction"],
                "isSubtle": True,
                "wrap": True,
            }
        )
    if alert.get("message"):
        body.append({"type": "TextBlock", "text": alert["message"], "wrap": True})

    return {
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


def _build_alert_slack_blocks(alert: dict) -> list[dict]:
    """Build minimal Slack Block Kit blocks from a platform-agnostic alert dict."""
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": alert["title"]},
        }
    ]

    text_parts: list[str] = []
    if alert.get("error"):
        text_parts.append(alert["error"])
    if alert.get("run_id"):
        text_parts.append(f"Run ID: {alert['run_id']}")
    if alert.get("instruction"):
        text_parts.append(alert["instruction"])
    if alert.get("message"):
        text_parts.append(alert["message"])

    if text_parts:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(text_parts)},
            }
        )

    return blocks
