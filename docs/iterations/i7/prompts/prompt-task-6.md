# Task Prompt — I7-6: Golden Dataset Runner + `wbsb eval` CLI

---

## Context

You are implementing **task I7-6** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-5 has been merged — `build_eval_scores()` exists and `eval_scores` is
written to `llm_response.json` on every successful LLM run.

**Your task:** Build the golden dataset runner (`src/wbsb/eval/runner.py`), create initial golden
cases, and add the `wbsb eval` CLI command. No pipeline or adapter changes.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Deterministic** — runner must produce the same result for the same inputs every time |
| 2 | **Config-driven** — no hardcoded pass/fail thresholds; all criteria live in `criteria.json` |
| 3 | **No silent failure** — missing required files must raise `ValueError` with clear messages |
| 4 | **Module boundaries** — `wbsb.eval` must not import from `wbsb.feedback` |
| 5 | **Domain model is frozen** — never modify `src/wbsb/domain/models.py` |
| 6 | **Allowed files only** — touch only the files listed below |
| 7 | **Draft PR first** — open a draft PR before writing any code |
| 8 | **Test before commit** — `pytest` and `ruff check .` must both pass before every push |

---

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch — AFTER I7-5 is merged
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-6-golden-runner
git push -u origin feature/i7-6-golden-runner

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-6-golden-runner \
  --title "I7-6: Golden dataset runner + wbsb eval CLI" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 306 tests passing, ruff clean
```

---

## What to Build

### Allowed files

```
src/wbsb/eval/runner.py             ← create
src/wbsb/eval/golden/               ← create directory with initial cases
src/wbsb/cli.py                     ← extend (add wbsb eval command)
tests/test_eval_runner.py           ← create
```

---

### Golden dataset directory structure

```
src/wbsb/eval/golden/
├── README.md
├── clean_week/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
├── single_dominant_cluster/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
├── independent_signals/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
├── low_volume_guardrail/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
├── zero_signals/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
└── fallback_no_llm/
    ├── findings.json
    └── criteria.json              ← no llm_response.json — this is the fallback case
```

**All 6 cases must be present.** `fallback_no_llm` must NOT have `llm_response.json`.

---

### `criteria.json` schema

Every case directory must have a `criteria.json` that matches this schema exactly:

```json
{
  "schema_version": "1.0",
  "description": "human-readable description of what this case tests",
  "expect_eval_scores": true,
  "min_grounding": 0.80,
  "min_signal_coverage": 1.0,
  "max_hallucination_risk": 0,
  "expected_skipped_reason": null
}
```

For `fallback_no_llm`:
```json
{
  "schema_version": "1.0",
  "description": "LLM fallback path — no LLM output, eval must be skipped cleanly",
  "expect_eval_scores": false,
  "min_grounding": null,
  "min_signal_coverage": null,
  "max_hallucination_risk": null,
  "expected_skipped_reason": "llm_fallback"
}
```

**Field rules:**
- `expect_eval_scores`: if `false`, runner checks `eval_skipped_reason` matches `expected_skipped_reason` instead of checking scores.
- `min_grounding`, `min_signal_coverage`, `max_hallucination_risk`: null when `expect_eval_scores=false`.
- Criteria values must be **conservative** — do not set `min_grounding: 1.0` for initial synthetic cases.

---

### `src/wbsb/eval/golden/README.md` — governance rules

Include all of the following:
- Golden cases are created from real production runs after I9 deployment.
- A new case requires: `findings.json` + `llm_response.json` from a real run + manually reviewed `criteria.json`.
- Criteria values must be set conservatively — do not set `min_grounding: 1.0` unless you have verified every cited number.
- Case updates require a PR review — do not edit `criteria.json` in place without review.
- `fallback_no_llm` must always be present and must always pass.
- For MVP: initial cases use synthetic data; replace with real-run data after I9 deployment.

---

### `src/wbsb/eval/runner.py`

```python
from pathlib import Path
import json

GOLDEN_DIR = Path(__file__).parent / "golden"


def load_case(name: str) -> dict:
    """
    Load findings.json, optional llm_response.json, and criteria.json
    for a named case directory under GOLDEN_DIR.

    Raises ValueError if case directory does not exist.
    Raises ValueError if findings.json is missing.
    Raises ValueError if criteria.json is missing.
    Returns dict with keys: name, findings, llm_response (or None), criteria.
    """


def run_case(case: dict) -> dict:
    """
    Evaluate a single loaded case against its criteria.

    Returns:
        {
            "name": str,
            "passed": bool,
            "failures": list[str],   # human-readable failure descriptions
            "scores": dict | None,   # the eval_scores from llm_response, or None
        }
    """


def run_all_cases() -> list[dict]:
    """
    Discover and run all cases in GOLDEN_DIR.
    Returns list of per-case results from run_case().
    Skips files/dirs that are not valid case directories (e.g. README.md).
    """
```

#### `run_case` logic

When `criteria["expect_eval_scores"]` is `True`:
- Read `eval_scores` from `llm_response.json` (the `eval_scores` key).
- If `eval_scores` is None: failure — `"eval_scores is null; expected scores"`.
- If `eval_scores["grounding"]` is not None and `eval_scores["grounding"] < criteria["min_grounding"]`: failure.
- If `eval_scores["signal_coverage"] < criteria["min_signal_coverage"]`: failure.
- If `eval_scores["hallucination_risk"] > criteria["max_hallucination_risk"]`: failure.

When `criteria["expect_eval_scores"]` is `False`:
- Read `eval_skipped_reason` from `llm_response.json` (or treat as `"llm_fallback"` if no `llm_response.json`).
- If `eval_skipped_reason != criteria["expected_skipped_reason"]`: failure.

`passed = len(failures) == 0`.

---

### `src/wbsb/cli.py` — add `wbsb eval` command

```python
@app.command("eval")
def eval_cmd(case: str = typer.Option(None, "--case", help="Run a single named case.")):
    """Run evaluation against golden dataset cases."""
    from wbsb.eval.runner import run_all_cases, run_case, load_case

    if case:
        results = [run_case(load_case(case))]
    else:
        results = run_all_cases()

    any_failed = False
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        typer.echo(f"[{status}] {result['name']}")
        for failure in result["failures"]:
            typer.echo(f"  - {failure}")
        if not result["passed"]:
            any_failed = True

    if any_failed:
        raise typer.Exit(code=1)
```

---

## What NOT to Do

- Do not modify `src/wbsb/eval/scorer.py` — it is frozen after I7-5.
- Do not modify `src/wbsb/render/llm_adapter.py` or `src/wbsb/pipeline.py`.
- Do not modify `src/wbsb/domain/models.py`.
- Do not hardcode pass/fail thresholds in `runner.py` — all thresholds read from `criteria.json`.
- Do not set `min_grounding: 1.0` in initial synthetic `criteria.json` files.
- Do not add golden cases to `tests/` — they live in `src/wbsb/eval/golden/`.
- Do not use `except: pass` or any silent failure.

---

## Tests Required

Create `tests/test_eval_runner.py` with exactly these 6 test functions.

Use `tmp_path` pytest fixture to create temporary case directories for isolation.

#### `test_load_case_valid`

```python
def test_load_case_valid(tmp_path):
    # Create a case dir with findings.json and criteria.json
    # Call load_case with the case name
    # Assert result has keys: name, findings, criteria
    # Assert result["name"] == case name
```

#### `test_load_case_missing_findings`

```python
def test_load_case_missing_findings(tmp_path):
    # Create a case dir with criteria.json but NO findings.json
    # Call load_case and assert ValueError is raised
    # Assert error message contains "findings"
```

#### `test_run_case_passes`

```python
def test_run_case_passes():
    # Build a case dict where eval_scores meets all criteria thresholds
    # Call run_case(case)
    # Assert result["passed"] == True
    # Assert result["failures"] == []
```

#### `test_run_case_fails_grounding`

```python
def test_run_case_fails_grounding():
    # Build a case dict where grounding < min_grounding in criteria
    # Call run_case(case)
    # Assert result["passed"] == False
    # Assert len(result["failures"]) >= 1
```

#### `test_run_case_fallback_no_llm`

```python
def test_run_case_fallback_no_llm():
    # Build a case with expect_eval_scores=False, expected_skipped_reason="llm_fallback"
    # llm_response has eval_scores=null, eval_skipped_reason="llm_fallback"
    # (or no llm_response.json at all)
    # Assert result["passed"] == True
```

#### `test_run_all_cases_returns_list`

```python
def test_run_all_cases_returns_list():
    # Monkeypatch GOLDEN_DIR or test against real golden dir
    # Call run_all_cases()
    # Assert return is a list
    # Assert len(result) >= 1
    # Assert each item has "name", "passed", "failures", "scores" keys
```

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 312 passing (306 existing + 6 new), 0 failures

ruff check .
# Expected: no issues

# Verify wbsb eval runs
wbsb eval
# Expected: all golden cases print [PASS], exit code 0

git diff --name-only feature/iteration-7
# Expected:
# src/wbsb/cli.py
# src/wbsb/eval/golden/README.md
# src/wbsb/eval/golden/clean_week/criteria.json
# src/wbsb/eval/golden/clean_week/findings.json
# src/wbsb/eval/golden/clean_week/llm_response.json
# ... (all 6 case dirs)
# src/wbsb/eval/runner.py
# tests/test_eval_runner.py
```

---

## Commit and PR

```bash
git add src/wbsb/eval/runner.py src/wbsb/eval/golden/ src/wbsb/cli.py tests/test_eval_runner.py

git commit -m "$(cat <<'EOF'
feat(eval): golden dataset runner + wbsb eval CLI

Adds runner.py with load_case/run_case/run_all_cases, 6 initial golden
cases with criteria.json contracts, governance README, and wbsb eval CLI
command with --case flag and exit code 1 on any failure.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-6-golden-runner
gh pr ready
```

---

## Handoff to I7-9

When this task is merged into `feature/iteration-7`, I7-7 (feedback system) merges next,
followed by I7-8 (architecture review) and I7-9 (final cleanup).

No exports from I7-6 are consumed by other tasks — `wbsb eval` is a standalone CLI command.
