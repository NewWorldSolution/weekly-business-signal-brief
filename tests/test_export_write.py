import json
from datetime import UTC, date, datetime
from pathlib import Path

from wbsb.domain.models import Findings, LLMResult, LLMSignalNarratives, Periods, RunMeta
from wbsb.export.write import write_artifacts


def _make_findings() -> Findings:
    return Findings(
        run=RunMeta(
            run_id="test_run",
            generated_at=datetime.now(UTC),
            input_file="input.csv",
            input_sha256="abc123",
            config_sha256="def456",
        ),
        periods=Periods(
            current_week_start=date(2024, 1, 8),
            current_week_end=date(2024, 1, 14),
            previous_week_start=date(2024, 1, 1),
            previous_week_end=date(2024, 1, 7),
        ),
        metrics=[],
        signals=[],
        audit=[],
    )


def test_write_artifacts_without_llm_is_backward_compatible(tmp_path):
    write_artifacts(
        run_dir=tmp_path,
        findings=_make_findings(),
        brief_md="# Test brief\n",
        elapsed_seconds=1.234,
        run_id="test_run",
        input_path=Path("input.csv"),
        input_hash="abc123",
        config_hash="def456",
        signals_warn_count=1,
        signals_info_count=2,
        audit_events_count=3,
        render_mode="off",
        config_version="2026.03",
    )

    findings_path = tmp_path / "findings.json"
    brief_path = tmp_path / "brief.md"
    manifest_path = tmp_path / "manifest.json"
    llm_response_path = tmp_path / "llm_response.json"

    assert findings_path.exists()
    assert brief_path.exists()
    assert manifest_path.exists()
    assert not llm_response_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["artifacts"].keys()) == {"findings.json", "brief.md"}
    assert manifest["render_mode"] == "off"
    assert manifest["config_version"] == "2026.03"
    assert manifest["signals_warn_count"] == 1
    assert manifest["signals_info_count"] == 2
    assert manifest["audit_events_count"] == 3
    assert manifest["llm_status"] == "off"
    assert manifest["llm_mode"] == "off"
    assert manifest["llm_provider"] == ""
    assert manifest["llm_model"] == ""
    assert manifest["llm_prompt_version"] == ""
    assert manifest["llm_fallback_reason"] == ""
    assert manifest["llm_token_usage"] == {}


def test_write_artifacts_with_llm_writes_response_and_manifest_metadata(tmp_path):
    llm_result = LLMResult(
        executive_summary="Summary from model",
        signal_narratives=LLMSignalNarratives(narratives={"A1": "Narrative text"}),
        model="gpt-4.1-mini",
        prompt_version="prompt-v1",
        fallback=False,
        fallback_reason="",
        token_usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
    )

    write_artifacts(
        run_dir=tmp_path,
        findings=_make_findings(),
        brief_md="# LLM brief\n",
        elapsed_seconds=2.5,
        run_id="test_run",
        input_path=Path("input.csv"),
        input_hash="abc123",
        config_hash="def456",
        render_mode="on",
        config_version="2026.03",
        llm_result=llm_result,
        llm_mode="on",
        llm_provider="openai",
        rendered_system_prompt="You are an analyst.",
        rendered_user_prompt="Summarize findings.",
        raw_response="Model response raw text",
    )

    llm_response_path = tmp_path / "llm_response.json"
    manifest_path = tmp_path / "manifest.json"
    assert llm_response_path.exists()

    llm_payload = json.loads(llm_response_path.read_text(encoding="utf-8"))
    assert llm_payload["rendered_system_prompt"] == "You are an analyst."
    assert llm_payload["rendered_user_prompt"] == "Summarize findings."
    assert llm_payload["provider"] == "openai"
    assert llm_payload["model"] == "gpt-4.1-mini"
    assert llm_payload["raw_response"] == "Model response raw text"
    assert isinstance(llm_payload["timestamp"], str)
    assert len(llm_payload["prompt_hash"]) == 64
    assert llm_payload["llm_result"]["prompt_version"] == "prompt-v1"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "llm_response.json" in manifest["artifacts"]
    assert manifest["llm_status"] == "success"
    assert manifest["llm_mode"] == "on"
    assert manifest["llm_provider"] == "openai"
    assert manifest["llm_model"] == "gpt-4.1-mini"
    assert manifest["llm_prompt_version"] == "prompt-v1"
    assert manifest["llm_fallback_reason"] == ""
    assert manifest["llm_token_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
