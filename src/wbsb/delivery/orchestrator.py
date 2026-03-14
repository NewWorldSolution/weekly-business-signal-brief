"""Delivery orchestrator: read run artifacts from disk and dispatch to enabled channels."""
from __future__ import annotations

import json
from pathlib import Path

from wbsb.delivery.models import DeliveryResult, DeliveryStatus, DeliveryTarget
from wbsb.delivery.slack import build_slack_blocks, send_slack_message
from wbsb.delivery.teams import build_teams_card, send_teams_card
from wbsb.domain.models import Findings, LLMResult


def load_run_artifacts(run_id: str, output_dir: Path = Path("runs")) -> dict:
    """Load findings.json, manifest.json, and llm_response.json from runs/{run_id}/.

    Returns a dict with keys:
        findings   — Findings instance
        manifest   — raw dict from manifest.json
        llm_result — LLMResult instance, or None when absent

    Raises:
        FileNotFoundError: if findings.json or manifest.json is missing, with a clear message.
    """
    run_dir = output_dir / run_id

    findings_path = run_dir / "findings.json"
    manifest_path = run_dir / "manifest.json"
    llm_response_path = run_dir / "llm_response.json"

    if not findings_path.exists():
        raise FileNotFoundError(
            f"findings.json not found for run {run_id!r} — expected: {findings_path}"
        )
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"manifest.json not found for run {run_id!r} — expected: {manifest_path}"
        )

    findings = Findings.model_validate_json(findings_path.read_text(encoding="utf-8"))
    manifest: dict = json.loads(manifest_path.read_text(encoding="utf-8"))

    llm_result: LLMResult | None = None
    if llm_response_path.exists():
        llm_data = json.loads(llm_response_path.read_text(encoding="utf-8"))
        if "llm_result" in llm_data:
            llm_result = LLMResult.model_validate(llm_data["llm_result"])

    return {"findings": findings, "manifest": manifest, "llm_result": llm_result}


def deliver_run(
    run_id: str,
    delivery_cfg: dict,
    output_dir: Path = Path("runs"),
) -> list[DeliveryResult]:
    """Load artifacts for run_id and dispatch to all enabled delivery targets.

    Returns one DeliveryResult per attempted target.  Never raises — all errors
    (including missing artifacts) are captured as failed DeliveryResult entries.
    """
    # Lazy import: wbsb.delivery.config requires PyYAML; keeping it lazy means
    # importing this module does not require yaml to be installed.
    from wbsb.delivery.config import resolve_webhook_url, slack_enabled, teams_enabled

    try:
        artifacts = load_run_artifacts(run_id, output_dir)
    except Exception as exc:  # noqa: BLE001
        error_msg = f"Failed to load run artifacts: {exc}"
        failed: list[DeliveryResult] = []
        if teams_enabled(delivery_cfg):
            failed.append(
                DeliveryResult(
                    target=DeliveryTarget.teams,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=error_msg,
                    delivered_at=None,
                )
            )
        if slack_enabled(delivery_cfg):
            failed.append(
                DeliveryResult(
                    target=DeliveryTarget.slack,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=error_msg,
                    delivered_at=None,
                )
            )
        if not failed:
            # No targets were enabled; return one sentinel result so the caller
            # knows the load failed rather than getting a silent empty list.
            failed.append(
                DeliveryResult(
                    target=DeliveryTarget.teams,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=error_msg,
                    delivered_at=None,
                )
            )
        return failed

    findings: Findings = artifacts["findings"]
    manifest: dict = artifacts["manifest"]
    llm_result: LLMResult | None = artifacts["llm_result"]

    # Orchestrator-level fallback logic: normalise llm_result to None when the
    # run used no LLM or LLM fell back.  Card builders render the fallback banner
    # when llm_result is None.
    is_fallback = manifest.get("llm_status") in ("off", "fallback") or llm_result is None
    effective_llm: LLMResult | None = None if is_fallback else llm_result

    results: list[DeliveryResult] = []

    if teams_enabled(delivery_cfg):
        try:
            webhook_url = resolve_webhook_url(
                delivery_cfg["delivery"]["teams"]["webhook_url"]
            )
            card = build_teams_card(findings, effective_llm, None)
            results.append(send_teams_card(card, webhook_url))  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            results.append(
                DeliveryResult(
                    target=DeliveryTarget.teams,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=f"Teams delivery error: {exc}",
                    delivered_at=None,
                )
            )

    if slack_enabled(delivery_cfg):
        try:
            webhook_url = resolve_webhook_url(
                delivery_cfg["delivery"]["slack"]["webhook_url"]
            )
            blocks = build_slack_blocks(findings, effective_llm, None)
            results.append(send_slack_message(blocks, webhook_url))  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            results.append(
                DeliveryResult(
                    target=DeliveryTarget.slack,
                    status=DeliveryStatus.failed,
                    http_status_code=None,
                    error=f"Slack delivery error: {exc}",
                    delivered_at=None,
                )
            )

    return results
