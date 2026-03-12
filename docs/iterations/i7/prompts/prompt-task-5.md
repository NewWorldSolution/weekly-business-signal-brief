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

### Scope correction (2026-03-12)

The original 4-file scope was insufficient. The original requirement "eval_scores_data must
be included in the data written to llm_response.json" cannot be satisfied without touching
the artifact writing layer. `llm_adapter.py` does NOT write `llm_response.json` — that logic
lives in `export/write.py`, orchestrated by `pipeline.py` via `render/llm.py`.

`domain/models.py` remains **frozen** — do not add `eval_scores_data` to `LLMResult`.
Instead, thread `eval_scores_data` as an explicit dict through the call chain.

### Allowed files (expanded — nine files total)

```
src/wbsb/eval/scorer.py          ← extend (add build_eval_scores)
src/wbsb/render/llm_adapter.py   ← extend (wire scorer after validate_response)
src/wbsb/render/llm.py           ← extend (add llm_eval_out out-param to render_llm)
src/wbsb/export/write.py         ← extend (add eval_scores_data param; write on fallback)
src/wbsb/pipeline.py             ← extend (thread eval_scores_data to write_artifacts)
tests/test_eval_scorer.py        ← extend (add 1 new test)
tests/test_llm_adapter.py        ← extend (add 3 new tests)
tests/test_eval_artifact.py      ← new file (3 tests for artifact writing)
tests/test_llm_integration.py    ← update 1 test (fallback now writes llm_response.json)
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

**`generate()` must continue to return `None` on failure** — changing the return type breaks
`test_llm_integration.py`. Instead, attach `eval_scores_data` to `AdapterLLMResult.eval_scores_data`
on success/scorer-error paths (already done), and expose `build_llm_fallback_eval_data()` as a
public helper for callers that handle the `None` return.

**Part B2 — Thread `eval_scores_data` to `llm_response.json` via `render_llm.py` and `write.py`**

See Part C and Part D below for how `eval_scores_data` reaches the artifact.

**Non-breaking rule:** on scorer error (Path 3), report generation must continue.
The pipeline must not return exit code 1 due to a scorer failure.

---

### Part C — Thread `eval_scores_data` through `src/wbsb/render/llm.py`

Add an optional `llm_eval_out: dict | None = None` parameter to `render_llm()`. The return
signature (4-tuple) must NOT change — that would break existing callers.

```python
def render_llm(
    findings, mode, provider, client=None, trend_context=None,
    llm_eval_out: dict | None = None,  # NEW — out-param, caller reads after return
) -> tuple[str, LLMResult | None, str, str]:
    ...
    adapter_result = llm_adapter.generate(...)

    if adapter_result is None:
        if llm_eval_out is not None:
            llm_eval_out["eval_scores_data"] = llm_adapter.build_llm_fallback_eval_data()
        return render_template(findings), None, rendered_system_prompt, rendered_user_prompt

    if llm_eval_out is not None:
        llm_eval_out["eval_scores_data"] = adapter_result.eval_scores_data
    ...
```

---

### Part D — Add `eval_scores_data` to `src/wbsb/export/write.py`

Add `eval_scores_data: dict | None = None` to `write_artifacts()`. Merge into `llm_payload`
when present. Write `llm_response.json` even when `llm_result is None` if `eval_scores_data`
is provided (covers the LLM fallback path).

```python
def write_artifacts(..., eval_scores_data: dict | None = None) -> None:
    ...
    if llm_result is not None or eval_scores_data is not None:
        timestamp = datetime.now(UTC)
        llm_payload: dict = {}
        if llm_result is not None:
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
        if eval_scores_data is not None:
            llm_payload.update(eval_scores_data)
        llm_response_path.write_text(json.dumps(llm_payload, indent=2), encoding="utf-8")
        artifact_hashes["llm_response.json"] = file_sha256(llm_response_path)
```

---

### Part E — Thread `eval_scores_data` in `src/wbsb/pipeline.py`

Create `llm_eval_out: dict = {}` before the `if llm_mode == "off":` branch. Pass it to
`render_llm()`. Forward `llm_eval_out.get("eval_scores_data")` to `write_artifacts()`.

```python
llm_eval_out: dict = {}
if llm_mode == "off":
    ...
else:
    ...
    brief_md, llm_result, rendered_system_prompt, rendered_user_prompt = render_llm(
        ..., llm_eval_out=llm_eval_out
    )
    ...

write_artifacts(
    ...,
    eval_scores_data=llm_eval_out.get("eval_scores_data"),  # NEW
)
```

---

## What NOT to Do

- Do not change the return signature of `render_llm()` — existing tests rely on 4-tuple unpacking.
- Do not add `eval_scores_data` to `LLMResult` in `domain/models.py` — domain model is frozen.
- Do not add scorer wiring directly to `pipeline.py` — scorer wiring belongs in `llm_adapter.py`.
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
    # Assert generate() returns None (unchanged contract)
    # Assert build_eval_scores was NOT called
    # Assert build_llm_fallback_eval_data() returns correct structure
```

### In `tests/test_eval_artifact.py` — add 3 tests (NEW FILE)

These test the artifact writing end-to-end via `write_artifacts()` directly:

#### `test_eval_scores_in_llm_response_on_success`
- Call `write_artifacts()` with real `llm_result` and `eval_scores_data` containing grounding score
- Assert `llm_response.json` exists and contains `eval_scores` with grounding key
- Assert `eval_skipped_reason` is `null`

#### `test_eval_scores_null_on_scorer_error_in_artifact`
- Call `write_artifacts()` with `llm_result` and `eval_scores_data={"eval_scores": null, "eval_skipped_reason": "scorer_error"}`
- Assert `llm_response.json` has `eval_scores=null`, `eval_skipped_reason="scorer_error"`

#### `test_eval_scores_written_on_llm_fallback_artifact`
- Call `write_artifacts()` with `llm_result=None` and `eval_scores_data={"eval_scores": null, "eval_skipped_reason": "llm_fallback"}`
- Assert `llm_response.json` IS written (even without llm_result)
- Assert it contains `eval_scores=null`, `eval_skipped_reason="llm_fallback"`

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
PYTHONPATH=src pytest --tb=short -q
# Expected: 318 passing (315 existing + 3 new), 0 failures

ruff check .
# Expected: no issues

git diff --name-only origin/feature/iteration-7
# Expected exactly (8 files):
# src/wbsb/eval/scorer.py
# src/wbsb/render/llm_adapter.py
# src/wbsb/render/llm.py
# src/wbsb/export/write.py
# src/wbsb/pipeline.py
# tests/test_eval_scorer.py
# tests/test_llm_adapter.py
# tests/test_eval_artifact.py
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
