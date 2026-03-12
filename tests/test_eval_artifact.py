"""Tests for eval_scores_data artifact writing via write_artifacts().

Covers all three eval paths:
  - success: eval_scores dict merged into llm_response.json
  - scorer_error: eval_scores=null + eval_skipped_reason="scorer_error"
  - llm_fallback: eval_scores=null + eval_skipped_reason="llm_fallback"
    (written even when llm_result is None)
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from wbsb.domain.models import Findings, LLMResult, LLMSignalNarratives, Periods, RunMeta
from wbsb.export.write import write_artifacts


def _make_findings() -> Findings:
    return Findings(
        run=RunMeta(
            run_id="test-run-eval",
            generated_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
            input_file="input.csv",
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


def _make_llm_result() -> LLMResult:
    return LLMResult(
        executive_summary="Revenue improved.",
        signal_narratives=LLMSignalNarratives(narratives={}),
        model="claude-haiku-4-5-20251001",
    )


def _base_write_kwargs(tmp_path: Path) -> dict:
    return {
        "run_dir": tmp_path,
        "findings": _make_findings(),
        "brief_md": "# brief",
        "elapsed_seconds": 1.0,
        "run_id": "test-run-eval",
        "input_path": Path("input.csv"),
        "input_hash": "a" * 64,
        "config_hash": "b" * 64,
        "llm_mode": "full",
        "llm_provider": "anthropic",
    }


def test_eval_scores_in_llm_response_on_success(tmp_path: Path) -> None:
    """On success, eval_scores dict is merged into llm_response.json alongside llm_result fields."""
    eval_scores_data = {
        "eval_scores": {
            "grounding": 1.0,
            "signal_coverage": 1.0,
            "group_coverage": 1.0,
            "hallucination_risk": 0,
        },
        "eval_skipped_reason": None,
    }
    write_artifacts(
        **_base_write_kwargs(tmp_path),
        llm_result=_make_llm_result(),
        eval_scores_data=eval_scores_data,
    )

    payload = json.loads((tmp_path / "llm_response.json").read_text())
    assert "eval_scores" in payload
    assert payload["eval_scores"]["grounding"] == 1.0
    assert payload["eval_scores"]["signal_coverage"] == 1.0
    assert payload["eval_skipped_reason"] is None
    # Standard llm_result fields must still be present
    assert "llm_result" in payload
    assert "model" in payload


def test_eval_scores_null_on_scorer_error_in_artifact(tmp_path: Path) -> None:
    """On scorer error, eval_scores=null and eval_skipped_reason recorded in llm_response.json."""
    eval_scores_data = {
        "eval_scores": None,
        "eval_skipped_reason": "scorer_error",
        "eval_error": "simulated scorer failure",
    }
    write_artifacts(
        **_base_write_kwargs(tmp_path),
        llm_result=_make_llm_result(),
        eval_scores_data=eval_scores_data,
    )

    payload = json.loads((tmp_path / "llm_response.json").read_text())
    assert payload["eval_scores"] is None
    assert payload["eval_skipped_reason"] == "scorer_error"
    assert payload["eval_error"] == "simulated scorer failure"
    assert "llm_result" in payload


def test_eval_scores_written_on_llm_fallback_artifact(tmp_path: Path) -> None:
    """On LLM fallback (llm_result=None), llm_response.json is still written with eval metadata."""
    eval_scores_data = {
        "eval_scores": None,
        "eval_skipped_reason": "llm_fallback",
    }
    write_artifacts(
        **_base_write_kwargs(tmp_path),
        llm_result=None,
        eval_scores_data=eval_scores_data,
    )

    llm_response_path = tmp_path / "llm_response.json"
    assert llm_response_path.exists(), "llm_response.json must be written even on LLM fallback"
    payload = json.loads(llm_response_path.read_text())
    assert payload["eval_scores"] is None
    assert payload["eval_skipped_reason"] == "llm_fallback"
    # No llm_result fields on pure fallback
    assert "llm_result" not in payload
