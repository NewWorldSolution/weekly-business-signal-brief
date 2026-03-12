"""Golden dataset runner for WBSB evaluation framework (I7-6).

Loads named case directories from src/wbsb/eval/golden/, evaluates
each case's eval_scores against its criteria.json, and reports pass/fail.
"""
from __future__ import annotations

import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"


def load_case(name: str) -> dict:
    """Load findings.json, optional llm_response.json, and criteria.json for a named case.

    Args:
        name: Case directory name under GOLDEN_DIR.

    Returns:
        Dict with keys: name, findings, llm_response (dict or None), criteria.

    Raises:
        ValueError: If case directory, findings.json, or criteria.json is missing.
    """
    case_dir = GOLDEN_DIR / name
    if not case_dir.is_dir():
        raise ValueError(f"Case directory not found: {case_dir}")

    findings_path = case_dir / "findings.json"
    if not findings_path.exists():
        raise ValueError(f"findings.json missing from case '{name}': {findings_path}")

    criteria_path = case_dir / "criteria.json"
    if not criteria_path.exists():
        raise ValueError(f"criteria.json missing from case '{name}': {criteria_path}")

    llm_response_path = case_dir / "llm_response.json"
    llm_response: dict | None = None
    if llm_response_path.exists():
        llm_response = json.loads(llm_response_path.read_text(encoding="utf-8"))

    return {
        "name": name,
        "findings": json.loads(findings_path.read_text(encoding="utf-8")),
        "llm_response": llm_response,
        "criteria": json.loads(criteria_path.read_text(encoding="utf-8")),
    }


def run_case(case: dict) -> dict:
    """Evaluate a single loaded case against its criteria.

    Args:
        case: Dict as returned by load_case().

    Returns:
        {
            "name": str,
            "passed": bool,
            "failures": list[str],   # human-readable failure descriptions
            "scores": dict | None,   # eval_scores from llm_response, or None
        }
    """
    criteria = case["criteria"]
    llm_response = case["llm_response"]
    failures: list[str] = []
    scores: dict | None = None

    if criteria["expect_eval_scores"]:
        if llm_response is None:
            failures.append("eval_scores is null; expected scores (no llm_response.json)")
        else:
            scores = llm_response.get("eval_scores")
            if scores is None:
                failures.append("eval_scores is null; expected scores")
            else:
                grounding = scores.get("grounding")
                min_grounding = criteria.get("min_grounding")
                if grounding is not None and min_grounding is not None:
                    if grounding < min_grounding:
                        failures.append(
                            f"grounding {grounding:.3f} < min_grounding {min_grounding:.3f}"
                        )

                signal_coverage = scores.get("signal_coverage")
                min_signal_coverage = criteria.get("min_signal_coverage")
                if signal_coverage is not None and min_signal_coverage is not None:
                    if signal_coverage < min_signal_coverage:
                        failures.append(
                            f"signal_coverage {signal_coverage:.3f}"
                            f" < min_signal_coverage {min_signal_coverage:.3f}"
                        )

                hallucination_risk = scores.get("hallucination_risk")
                max_hallucination_risk = criteria.get("max_hallucination_risk")
                if hallucination_risk is not None and max_hallucination_risk is not None:
                    if hallucination_risk > max_hallucination_risk:
                        failures.append(
                            f"hallucination_risk {hallucination_risk}"
                            f" > max_hallucination_risk {max_hallucination_risk}"
                        )
    else:
        # expect_eval_scores is False — check skipped reason
        if llm_response is None:
            eval_skipped_reason: str | None = "llm_fallback"
        else:
            eval_skipped_reason = llm_response.get("eval_skipped_reason")

        expected = criteria.get("expected_skipped_reason")
        if eval_skipped_reason != expected:
            failures.append(
                f"eval_skipped_reason {eval_skipped_reason!r} != expected {expected!r}"
            )

    return {
        "name": case["name"],
        "passed": len(failures) == 0,
        "failures": failures,
        "scores": scores,
    }


def run_all_cases() -> list[dict]:
    """Discover and run all cases in GOLDEN_DIR.

    Returns list of per-case results from run_case().
    Skips files/dirs that are not valid case directories (no criteria.json).
    """
    results: list[dict] = []
    for path in sorted(GOLDEN_DIR.iterdir()):
        if not path.is_dir():
            continue
        if not (path / "criteria.json").exists():
            continue
        results.append(run_case(load_case(path.name)))
    return results
