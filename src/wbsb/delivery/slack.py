from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wbsb.delivery.models import DeliveryResult, DeliveryStatus, DeliveryTarget
from wbsb.domain.models import Findings, LLMResult, Signal

_FALLBACK_BANNER = "⚠️ AI analysis unavailable this week — showing deterministic report"
_FEEDBACK_ACTIONS = (
    ("✅ Looks right", "expected"),
    ("⚠️ Unexpected", "unexpected"),
    ("❌ Something's wrong", "incorrect"),
)


def build_slack_blocks(
    findings: Findings,
    llm_result: LLMResult | None,
    feedback_webhook_url: str | None,
) -> list[dict]:
    """
    Build a deterministic Slack Block Kit message for delivery.

    The feedback webhook URL is used only to decide whether feedback actions
    should be rendered for this message.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Weekly Business Signal Brief"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"{findings.periods.current_week_start.isoformat()} to "
                        f"{findings.periods.current_week_end.isoformat()} | "
                        f"Run {findings.run.run_id}"
                    ),
                }
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": _situation_text(llm_result)},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": _signals_summary(findings.signals)},
        },
        {"type": "divider"},
    ]

    if feedback_webhook_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": text},
                        "value": json.dumps(
                            {"label": label, "run_id": findings.run.run_id},
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    }
                    for text, label in _FEEDBACK_ACTIONS
                ],
            }
        )

    return blocks


def send_slack_message(blocks: list[dict], webhook_url: str) -> DeliveryResult:
    """
    Send a Slack webhook message and return a DeliveryResult.

    This function never raises.
    """
    request = Request(
        webhook_url,
        data=json.dumps({"blocks": blocks}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            status_code = response.getcode()
            if 200 <= status_code < 300:
                return DeliveryResult(
                    target=DeliveryTarget.slack,
                    status=DeliveryStatus.success,
                    http_status_code=status_code,
                    error=None,
                    delivered_at=datetime.now(timezone.utc).isoformat(),  # noqa: UP017
                )

            return DeliveryResult(
                target=DeliveryTarget.slack,
                status=DeliveryStatus.failed,
                http_status_code=status_code,
                error=f"Slack webhook returned HTTP {status_code}",
                delivered_at=None,
            )
    except HTTPError as exc:
        return DeliveryResult(
            target=DeliveryTarget.slack,
            status=DeliveryStatus.failed,
            http_status_code=exc.code,
            error=f"Slack webhook returned HTTP {exc.code}",
            delivered_at=None,
        )
    except TimeoutError:
        return DeliveryResult(
            target=DeliveryTarget.slack,
            status=DeliveryStatus.failed,
            http_status_code=None,
            error="Slack webhook request timed out",
            delivered_at=None,
        )
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            error = "Slack webhook request timed out"
        else:
            error = "Slack webhook request failed"
        return DeliveryResult(
            target=DeliveryTarget.slack,
            status=DeliveryStatus.failed,
            http_status_code=None,
            error=error,
            delivered_at=None,
        )
    except Exception:
        return DeliveryResult(
            target=DeliveryTarget.slack,
            status=DeliveryStatus.failed,
            http_status_code=None,
            error="Slack webhook request failed",
            delivered_at=None,
        )


def _situation_text(llm_result: LLMResult | None) -> str:
    if llm_result is None or llm_result.fallback or not llm_result.situation:
        return _FALLBACK_BANNER
    return llm_result.situation


def _signals_summary(signals: list[Signal]) -> str:
    warn_signals = sorted(
        (signal for signal in signals if signal.severity == "WARN"),
        key=lambda signal: signal.rule_id,
    )
    warn_count = len(warn_signals)
    if warn_count == 0:
        return "No warnings this week."

    top_lines = [f"• {signal.label or signal.rule_id}" for signal in warn_signals[:3]]
    if warn_count > 3:
        top_lines.append(f"+ {warn_count - 3} more")

    return f"{warn_count} warning(s)\n" + "\n".join(top_lines)
