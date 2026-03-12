"""Tests for wbsb.eval.runner (I7-6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import wbsb.eval.runner as runner_module
from wbsb.eval.runner import load_case, run_all_cases, run_case

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_case(
    base: Path,
    name: str,
    findings: dict,
    criteria: dict,
    llm_response: dict | None = None,
) -> Path:
    """Write a minimal case directory under base and return the case dir."""
    case_dir = base / name
    case_dir.mkdir(parents=True)
    (case_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    (case_dir / "criteria.json").write_text(json.dumps(criteria), encoding="utf-8")
    if llm_response is not None:
        (case_dir / "llm_response.json").write_text(
            json.dumps(llm_response), encoding="utf-8"
        )
    return case_dir


def _minimal_findings() -> dict:
    return {
        "run": {
            "run_id": "test-run",
            "generated_at": "2026-03-09T12:00:00+00:00",
            "input_file": "test.csv",
            "input_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        },
        "periods": {
            "current_week_start": "2026-03-09",
            "current_week_end": "2026-03-15",
            "previous_week_start": "2026-03-02",
            "previous_week_end": "2026-03-08",
        },
        "metrics": [],
        "signals": [],
        "dominant_cluster_exists": False,
        "audit": [],
    }


def _passing_criteria() -> dict:
    return {
        "schema_version": "1.0",
        "description": "test case",
        "expect_eval_scores": True,
        "min_grounding": 0.80,
        "min_signal_coverage": 1.0,
        "max_hallucination_risk": 0,
        "expected_skipped_reason": None,
    }


def _passing_eval_scores() -> dict:
    return {
        "grounding": 1.0,
        "grounding_reason": None,
        "flagged_numbers": [],
        "signal_coverage": 1.0,
        "group_coverage": 1.0,
        "hallucination_risk": 0,
        "hallucination_violations": [],
        "model": "claude-haiku-4-5-20251001",
        "evaluated_at": "2026-03-09T12:05:00+00:00",
        "schema_version": "1.0",
    }


# ---------------------------------------------------------------------------
# 1. test_load_case_valid
# ---------------------------------------------------------------------------


def test_load_case_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_module, "GOLDEN_DIR", tmp_path)
    _write_case(
        tmp_path,
        "my_case",
        findings=_minimal_findings(),
        criteria=_passing_criteria(),
    )

    result = load_case("my_case")

    assert "name" in result
    assert "findings" in result
    assert "criteria" in result
    assert result["name"] == "my_case"
    assert result["llm_response"] is None  # no llm_response.json written


# ---------------------------------------------------------------------------
# 2. test_load_case_missing_findings
# ---------------------------------------------------------------------------


def test_load_case_missing_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_module, "GOLDEN_DIR", tmp_path)
    case_dir = tmp_path / "bad_case"
    case_dir.mkdir()
    (case_dir / "criteria.json").write_text(
        json.dumps(_passing_criteria()), encoding="utf-8"
    )
    # findings.json intentionally absent

    with pytest.raises(ValueError, match="findings"):
        load_case("bad_case")


# ---------------------------------------------------------------------------
# 3. test_run_case_passes
# ---------------------------------------------------------------------------


def test_run_case_passes() -> None:
    case = {
        "name": "passing_case",
        "findings": _minimal_findings(),
        "llm_response": {"eval_scores": _passing_eval_scores(), "eval_skipped_reason": None},
        "criteria": _passing_criteria(),
    }

    result = run_case(case)

    assert result["passed"] is True
    assert result["failures"] == []


# ---------------------------------------------------------------------------
# 4. test_run_case_fails_grounding
# ---------------------------------------------------------------------------


def test_run_case_fails_grounding() -> None:
    failing_scores = _passing_eval_scores()
    failing_scores["grounding"] = 0.50  # below min_grounding=0.80

    case = {
        "name": "failing_grounding",
        "findings": _minimal_findings(),
        "llm_response": {"eval_scores": failing_scores, "eval_skipped_reason": None},
        "criteria": _passing_criteria(),
    }

    result = run_case(case)

    assert result["passed"] is False
    assert len(result["failures"]) >= 1
    assert any("grounding" in f for f in result["failures"])


# ---------------------------------------------------------------------------
# 5. test_run_case_fallback_no_llm
# ---------------------------------------------------------------------------


def test_run_case_fallback_no_llm() -> None:
    fallback_criteria = {
        "schema_version": "1.0",
        "description": "fallback case",
        "expect_eval_scores": False,
        "min_grounding": None,
        "min_signal_coverage": None,
        "max_hallucination_risk": None,
        "expected_skipped_reason": "llm_fallback",
    }
    case = {
        "name": "fallback_no_llm",
        "findings": _minimal_findings(),
        "llm_response": None,  # no llm_response.json
        "criteria": fallback_criteria,
    }

    result = run_case(case)

    assert result["passed"] is True
    assert result["failures"] == []


# ---------------------------------------------------------------------------
# 6. test_run_all_cases_returns_list
# ---------------------------------------------------------------------------


def test_run_all_cases_returns_list() -> None:
    # Tests against the real golden directory (6 cases must all pass)
    results = run_all_cases()

    assert isinstance(results, list)
    assert len(results) >= 1
    for item in results:
        assert "name" in item
        assert "passed" in item
        assert "failures" in item
        assert "scores" in item
        assert item["passed"] is True, (
            f"Golden case '{item['name']}' failed: {item['failures']}"
        )
