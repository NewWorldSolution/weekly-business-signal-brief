# Task Prompt — I7-5: build_eval_scores() + Pipeline Integration

---

## Context

You are implementing **task I7-5** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-2, I7-3, and I7-4 have all been merged into `feature/iteration-7`.
`score_grounding()`, `score_signal_coverage()`, and `score_hallucination()` all exist in
`src/wbsb/eval/scorer.py`. You are adding the integrator and wiring it into the LLM adapter.

**Your task:** Add `build_eval_scores()` to `scorer.py` and wire it into `llm_adapter.py`
after `validate_response()` succeeds. This is the only task that touches existing pipeline code.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Deterministic** — same inputs must always produce the same output (exception: `evaluated_at` timestamp) |
| 2 | **Config-driven** — all tolerance values read from `cfg` dict; zero hardcoded numbers |
| 3 | **No silent failure** — never `except: pass`; scorer errors must be logged and recorded |
| 4 | **Module boundaries** — `wbsb.eval` must not import from `wbsb.feedback` |
| 5 | **Domain model is frozen** — never modify `src/wbsb/domain/models.py` |
| 6 | **Allowed files only** — touch only the four files listed below |
| 7 | **Draft PR first** — open a draft PR before writing any code |
| 8 | **Non-breaking** — scorer failure must never cause pipeline failure or exit code 1 |

---

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch — AFTER I7-2, I7-3, I7-4 are all merged
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-5-pipeline-integration
git push -u origin feature/i7-5-pipeline-integration

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-5-pipeline-integration \
  --title "I7-5: build_eval_scores() + pipeline integration" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 302 tests passing (271 + 13 I7-1 + 5 I7-2 + 6 I7-3 + 7 I7-4), ruff clean
```

---

## What to Build

### Allowed files (exactly these four, no others)

```
src/wbsb/eval/scorer.py          ← extend (add build_eval_scores)
src/wbsb/render/llm_adapter.py   ← extend (wire scorer after validate_response)
tests/test_eval_scorer.py        ← extend (add 1 new test)
tests/test_llm_adapter.py        ← extend (add 3 new tests)
```

---

### Part A — `build_eval_scores()` in `src/wbsb/eval/scorer.py`

Append this function. Do not modify existing scorer functions.

```python
from datetime import datetime, timezone

from wbsb.eval.models import EvalScores


def build_eval_scores(
    findings: Findings,
    llm_result: LLMResult,
    cfg: dict,
) -> EvalScores:
    """
    Combine grounding, coverage, and hallucination results into a single EvalScores.

    Args:
        findings:   Pydantic Findings from the pipeline.
        llm_result: Pydantic LLMResult from the LLM adapter.
        cfg:        The eval section from config/rules.yaml (a dict).

    Returns:
        EvalScores instance with all fields populated.
    """
    grounding_result = score_grounding(findings, llm_result, cfg)
    coverage_result = score_signal_coverage(findings, llm_result)
    hallucination_result = score_hallucination(findings, llm_result)

    return EvalScores(
        grounding=grounding_result["grounding"],
        grounding_reason=grounding_result["grounding_reason"],
        flagged_numbers=grounding_result["flagged_numbers"],
        signal_coverage=coverage_result["signal_coverage"],
        group_coverage=coverage_result["group_coverage"],
        hallucination_risk=hallucination_result["hallucination_risk"],
        hallucination_violations=hallucination_result["hallucination_violations"],
        model=llm_result.model,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
```

---

### Part B — Wire scorer in `src/wbsb/render/llm_adapter.py`

Read the existing file before modifying. Find where `validate_response()` is called and
`llm_result` is finalized. After that point, add scorer wiring.

**How to get `eval_cfg`:**

Load the eval section from `config/rules.yaml`:

```python
import yaml
from pathlib import Path

eval_cfg = yaml.safe_load(Path("config/rules.yaml").read_text()).get("eval", {})
```

**Three paths — implement all three:**

#### Path 1 — LLM fallback (no `llm_result`)

When `llm_result` is `None` (i.e. LLM call failed and template fallback was used):

```python
# Do not call scorer
eval_scores_data = {
    "eval_scores": None,
    "eval_skipped_reason": "llm_fallback",
}
```

#### Path 2 — Scorer succeeds

After `validate_response()` succeeds and `llm_result` is a valid object:

```python
try:
    eval_scores = build_eval_scores(findings, llm_result, eval_cfg)
    eval_scores_data = {
        "eval_scores": eval_scores.model_dump(),
        "eval_skipped_reason": None,
    }
except Exception as exc:
    # Path 3 — scorer error
    log.error("eval.scorer.error", error=str(exc))
    eval_scores_data = {
        "eval_scores": None,
        "eval_skipped_reason": "scorer_error",
        "eval_error": str(exc),
    }
```

**The `eval_scores_data` dict must be included in the data written to `llm_response.json`.**

Read the existing write logic for `llm_response.json` in `llm_adapter.py` and merge
`eval_scores_data` into the artifact. Do not replace existing artifact fields.

**Non-breaking rule:** on scorer error (Path 3), report generation must continue.
The pipeline must not return exit code 1 due to a scorer failure.

---

## What NOT to Do

- Do not add scorer wiring to `src/wbsb/pipeline.py` — wiring belongs only in `llm_adapter.py`.
- Do not modify `score_grounding()`, `score_signal_coverage()`, or `score_hallucination()`.
- Do not modify `src/wbsb/eval/models.py` or `src/wbsb/domain/models.py`.
- Do not modify `config/rules.yaml`.
- Do not modify `src/wbsb/eval/extractor.py`.
- Do not raise on scorer error — log and record, then continue.
- Do not use `except: pass` — catch `Exception`, log the error, record `eval_error`.

---

## Tests Required

### In `tests/test_eval_scorer.py` — add 1 test

#### `test_build_eval_scores_returns_eval_scores_model`

```python
def test_build_eval_scores_returns_eval_scores_model():
    # Build minimal real Findings and LLMResult objects
    # Call build_eval_scores(findings, llm_result, cfg)
    # Assert return type is EvalScores
    # Assert result.model is set from llm_result.model
    # Assert result.evaluated_at is a non-empty string
    # Assert result.schema_version == "1.0"
```

### In `tests/test_llm_adapter.py` — add 3 tests

Use monkeypatch to stub `build_eval_scores` where needed.

#### `test_eval_scores_written_to_artifact_on_success`

```python
def test_eval_scores_written_to_artifact_on_success():
    # Run adapter with real or stubbed LLM result
    # Read llm_response.json artifact
    # Assert "eval_scores" key is present and not None
    # Assert eval_scores has keys: grounding, signal_coverage, group_coverage,
    #   hallucination_risk, hallucination_violations, model, evaluated_at
```

#### `test_eval_scores_null_on_scorer_error`

```python
def test_eval_scores_null_on_scorer_error():
    # Monkeypatch build_eval_scores to raise RuntimeError
    # Run the adapter path that calls scorer
    # Assert report generation completed (no exception propagated)
    # Assert artifact has eval_scores=null, eval_skipped_reason="scorer_error"
    # Assert eval_error key is present in artifact
```

#### `test_eval_scores_null_on_llm_fallback`

```python
def test_eval_scores_null_on_llm_fallback():
    # Simulate path where llm_result is None (LLM fallback mode)
    # Assert artifact has eval_scores=null, eval_skipped_reason="llm_fallback"
    # Assert build_eval_scores was NOT called
```

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 306 passing (302 existing + 4 new), 0 failures

ruff check .
# Expected: no issues

git diff --name-only feature/iteration-7
# Expected exactly:
# src/wbsb/eval/scorer.py
# src/wbsb/render/llm_adapter.py
# tests/test_eval_scorer.py
# tests/test_llm_adapter.py
```

---

## Commit and PR

```bash
git add src/wbsb/eval/scorer.py src/wbsb/render/llm_adapter.py \
        tests/test_eval_scorer.py tests/test_llm_adapter.py

git commit -m "$(cat <<'EOF'
feat(eval): add build_eval_scores() and wire scorer into llm_adapter

Adds build_eval_scores() integrator that combines grounding, coverage,
and hallucination scorers into a single EvalScores instance. Wires scorer
into llm_adapter after validate_response(); scorer error produces
eval_skipped_reason=scorer_error without breaking report generation;
LLM fallback produces eval_skipped_reason=llm_fallback.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-5-pipeline-integration
gh pr ready
```

---

## Handoff to I7-6

When this task is merged, I7-6 will implement the golden dataset runner and `wbsb eval` CLI.
I7-6's branch must be created from `feature/iteration-7` **after** this PR is merged.

Exports consumed by I7-6:
```python
# eval_scores written to llm_response.json artifact — I7-6 reads this for golden cases
# wbsb.eval.scorer: build_eval_scores(findings, llm_result, cfg) -> EvalScores
```
