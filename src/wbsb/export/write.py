"""Write run artifacts to disk."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from wbsb.domain.models import Findings, LLMResult, Manifest
from wbsb.observability.logging import get_logger
from wbsb.utils.hash import file_sha256


def _prompt_hash(rendered_system_prompt: str, rendered_user_prompt: str) -> str:
    payload = f"{rendered_system_prompt}\n---\n{rendered_user_prompt}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolve_llm_status(llm_mode: str, llm_result: LLMResult | None) -> str:
    if llm_result is None:
        return "off"
    return "fallback" if llm_result.fallback else "success"


def write_artifacts(
    run_dir: Path,
    findings: Findings,
    brief_md: str,
    elapsed_seconds: float,
    run_id: str,
    input_path: Path,
    input_hash: str,
    config_hash: str,
    signals_warn_count: int = 0,
    signals_info_count: int = 0,
    audit_events_count: int = 0,
    render_mode: str = "off",
    config_version: str = "",
    llm_result: LLMResult | None = None,
    llm_mode: str = "off",
    llm_provider: str = "",
    rendered_system_prompt: str = "",
    rendered_user_prompt: str = "",
    raw_response: str = "",
) -> None:
    """Write all run artifacts to run_dir.

    Artifacts:
        - findings.json
        - brief.md
        - manifest.json

    Args:
        run_dir: Directory for this run's artifacts.
        findings: Computed Findings document.
        brief_md: Rendered brief markdown.
        elapsed_seconds: Pipeline elapsed time.
        run_id: Unique run identifier.
        input_path: Path to input file.
        input_hash: SHA-256 of input file.
        config_hash: SHA-256 of config.
        signals_warn_count: Number of WARN signals fired.
        signals_info_count: Number of INFO signals fired.
        audit_events_count: Number of audit/validation events.
        render_mode: LLM render mode used for this run.
        config_version: Version string from rules.yaml.
        llm_result: Optional typed LLM result.
        llm_mode: LLM operating mode used for this run.
        llm_provider: LLM provider identifier.
        rendered_system_prompt: Rendered system prompt sent to model.
        rendered_user_prompt: Rendered user prompt sent to model.
        raw_response: Optional raw LLM response text.
    """
    findings_path = run_dir / "findings.json"
    brief_path = run_dir / "brief.md"
    llm_response_path = run_dir / "llm_response.json"
    manifest_path = run_dir / "manifest.json"

    try:
        # Write findings.json
        findings_json = findings.model_dump_json(indent=2)
        findings_path.write_text(findings_json, encoding="utf-8")

        # Write brief.md
        brief_path.write_text(brief_md, encoding="utf-8")

        # Compute artifact hashes
        findings_hash = file_sha256(findings_path)
        brief_hash = file_sha256(brief_path)
        artifact_hashes = {
            "findings.json": findings_hash,
            "brief.md": brief_hash,
        }

        if llm_result is not None:
            timestamp = datetime.now(UTC)
            llm_payload = {
                "llm_result": llm_result.model_dump(mode="json"),
                "raw_response": raw_response,
                "rendered_system_prompt": rendered_system_prompt,
                "rendered_user_prompt": rendered_user_prompt,
                "model": llm_result.model,
                "provider": llm_provider,
                "timestamp": timestamp.isoformat(),
                "prompt_hash": _prompt_hash(rendered_system_prompt, rendered_user_prompt),
            }
            llm_response_path.write_text(json.dumps(llm_payload, indent=2), encoding="utf-8")
            artifact_hashes["llm_response.json"] = file_sha256(llm_response_path)

        # Write manifest.json
        manifest = Manifest(
            run_id=run_id,
            generated_at=datetime.now(UTC),
            input_file=input_path.name,
            input_sha256=input_hash,
            config_sha256=config_hash,
            elapsed_seconds=round(elapsed_seconds, 3),
            artifacts=artifact_hashes,
            signals_warn_count=signals_warn_count,
            signals_info_count=signals_info_count,
            audit_events_count=audit_events_count,
            render_mode=render_mode,
            config_version=config_version,
            llm_status=_resolve_llm_status(llm_mode=llm_mode, llm_result=llm_result),
            llm_mode=llm_mode,
            llm_provider=llm_provider,
            llm_model=llm_result.model if llm_result is not None else "",
            llm_prompt_version=llm_result.prompt_version if llm_result is not None else "",
            llm_fallback_reason=llm_result.fallback_reason if llm_result is not None else "",
            llm_token_usage=llm_result.token_usage if llm_result is not None else {},
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    except Exception as exc:
        get_logger().error("write_artifacts.failed", error=str(exc), exc_info=True)
        raise
