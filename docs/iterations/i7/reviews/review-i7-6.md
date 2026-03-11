# WBSB Review Prompt — I7-6: Golden Dataset Runner + `wbsb eval` CLI

---

## Reviewer Role & Mandate

You are an **independent code reviewer** for the WBSB project.

Your role is to evaluate a completed task implementation with the same rigour as a senior
engineer reviewing a PR for a production system. You did not write this code. You have no
bias toward approving it. Your job is to protect the codebase.

**Your mandate:**

- Verify the implementation satisfies every acceptance criterion — not approximately, exactly.
- Identify violations of the architecture constraints — even minor ones.
- Flag silent failures, hardcoded values, scope creep, and weak tests.
- Report problems precisely: file path, line number, exact issue, why it matters.
- Be specific. "Looks fine" is not an acceptable assessment.

**What you must NOT do:**

- Do not fix the code. Report problems. Fixing is the implementer's job.
- Do not approve based on tests passing alone — tests can be incomplete.
- Do not overlook an issue because it seems minor. Log it with `severity: minor`.
- Do not invent problems that are not there. Every finding must be backed by evidence.

**Your verdict has three options:**

| Verdict | Meaning |
|---------|---------|
| `PASS` | All acceptance criteria met, no architecture violations, tests adequate. Ready to merge. |
| `CHANGES REQUIRED` | One or more problems found. List every fix needed before re-review. |
| `BLOCKED` | A fundamental design decision is wrong and the approach must be reconsidered. |

---

## Project Context

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for
appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics,
detects signals via a config-driven rules engine, and generates a structured business brief.
An LLM is optionally used for narrative sections only — never for calculations or decisions.

**Core pipeline:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Architecture principles (violations of any = CHANGES REQUIRED minimum):**

| # | Principle |
|---|-----------|
| 1 | **Deterministic first** — runner must produce the same result for the same inputs every time |
| 2 | **Config-driven** — all pass/fail thresholds in `criteria.json`; zero hardcoded thresholds in runner code |
| 3 | **No silent failure** — missing required files must raise `ValueError` with clear messages |
| 4 | **Separation of concerns** — eval and feedback packages must not import from each other |
| 5 | **Domain model is frozen** — `src/wbsb/domain/models.py` must not be modified |

---

## Task Under Review

| Field | Value |
|-------|-------|
| Task ID | I7-6 |
| Title | Golden Dataset Runner + `wbsb eval` CLI |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Claude |
| Reviewed by | Codex |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-6-golden-runner` |
| PR | #TBD |
| Expected test count | 306 before → 312 after (expected +6) |

---

## What This Task Was Supposed to Build

### New/modified files

```
src/wbsb/eval/runner.py             ← create
src/wbsb/eval/golden/               ← create with 6 initial cases
src/wbsb/cli.py                     ← extend (add wbsb eval command)
tests/test_eval_runner.py           ← create
```

### Required runner API

```python
def load_case(name: str) -> dict: ...   # raises ValueError on missing findings/criteria
def run_case(case: dict) -> dict: ...   # returns {name, passed, failures, scores}
def run_all_cases() -> list[dict]: ...  # runs all cases in golden dir
```

### Required 6 golden cases

```
clean_week/
single_dominant_cluster/
independent_signals/
low_volume_guardrail/
zero_signals/
fallback_no_llm/             ← no llm_response.json; uses eval_skipped_reason contract
```

### Required `criteria.json` schema

```json
{
  "schema_version": "1.0",
  "description": "...",
  "expect_eval_scores": true | false,
  "min_grounding": float | null,
  "min_signal_coverage": float | null,
  "max_hallucination_risk": int | null,
  "expected_skipped_reason": null | "llm_fallback"
}
```

### What must NOT have been built

- No hardcoded pass/fail thresholds in `runner.py`.
- No changes to `scorer.py`, `llm_adapter.py`, `pipeline.py`, `domain/models.py`.
- No `min_grounding: 1.0` in initial synthetic `criteria.json` (must be conservative).
- `fallback_no_llm` must not have `llm_response.json`.

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-6-golden-runner
git pull origin feature/i7-6-golden-runner
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 312 passing, 0 failures

ruff check .
# Expected: no issues
```

If either fails, verdict is `CHANGES REQUIRED` immediately.

### Step 3 — Verify scope

```bash
git diff --name-only feature/iteration-7
```

Expected — `runner.py`, `golden/` files, `cli.py`, `test_eval_runner.py`. No other files.

Any change to `scorer.py`, `llm_adapter.py`, `pipeline.py`, or `domain/models.py` = scope violation.

### Step 4 — Verify all 3 runner functions exist and are importable

```bash
python3 -c "
from wbsb.eval.runner import load_case, run_case, run_all_cases
import inspect

for fn in [load_case, run_case, run_all_cases]:
    print(f'{fn.__name__}: {list(inspect.signature(fn).parameters.keys())}')
print('runner imports: OK')
"
```

Expected:
- `load_case` takes `name: str`
- `run_case` takes `case: dict`
- `run_all_cases` takes no required params

### Step 5 — Verify all 6 golden cases present

```bash
ls src/wbsb/eval/golden/
```

Expected directories:
```
clean_week
single_dominant_cluster
independent_signals
low_volume_guardrail
zero_signals
fallback_no_llm
```

Also verify each case has `findings.json` and `criteria.json`:

```bash
for d in src/wbsb/eval/golden/*/; do
    echo "=== $d ==="
    ls "$d"
done
```

`fallback_no_llm` must have `findings.json` and `criteria.json` but NO `llm_response.json`.

### Step 6 — Verify criteria.json schema in each case

```bash
python3 -c "
import json
from pathlib import Path

golden = Path('src/wbsb/eval/golden')
required_keys = {'schema_version', 'description', 'expect_eval_scores',
                 'min_grounding', 'min_signal_coverage',
                 'max_hallucination_risk', 'expected_skipped_reason'}

for case_dir in sorted(golden.iterdir()):
    if not case_dir.is_dir():
        continue
    criteria_path = case_dir / 'criteria.json'
    if not criteria_path.exists():
        print(f'MISSING criteria.json: {case_dir.name}')
        continue
    criteria = json.loads(criteria_path.read_text())
    missing = required_keys - set(criteria.keys())
    if missing:
        print(f'MISSING keys in {case_dir.name}: {missing}')
    else:
        print(f'OK: {case_dir.name}')
"
```

Expected: all cases print `OK`.

Also check `fallback_no_llm/criteria.json` has `expect_eval_scores: false` and
`expected_skipped_reason: \"llm_fallback\"`.

### Step 7 — Verify conservative criteria thresholds

```bash
python3 -c "
import json
from pathlib import Path

golden = Path('src/wbsb/eval/golden')
for case_dir in sorted(golden.iterdir()):
    if not case_dir.is_dir():
        continue
    criteria_path = case_dir / 'criteria.json'
    if not criteria_path.exists():
        continue
    criteria = json.loads(criteria_path.read_text())
    if criteria.get('expect_eval_scores') and criteria.get('min_grounding') == 1.0:
        print(f'WARNING — min_grounding=1.0 is fragile: {case_dir.name}')
    else:
        print(f'OK: {case_dir.name}')
"
```

`min_grounding: 1.0` in a synthetic case = `severity: minor` — will break on any
unrecognized number in the synthetic narrative text.

### Step 8 — Verify load_case raises on missing findings

```bash
python3 -c "
import tempfile, json
from pathlib import Path
from wbsb.eval.runner import load_case

# Patch GOLDEN_DIR temporarily
import wbsb.eval.runner as runner
orig = runner.GOLDEN_DIR

with tempfile.TemporaryDirectory() as tmp:
    case_dir = Path(tmp) / 'test_case'
    case_dir.mkdir()
    # criteria.json only, no findings.json
    (case_dir / 'criteria.json').write_text(json.dumps({'schema_version': '1.0'}))
    runner.GOLDEN_DIR = Path(tmp)
    try:
        load_case('test_case')
        print('FAIL — should have raised ValueError')
    except ValueError as e:
        print(f'OK — raised ValueError: {e}')
    finally:
        runner.GOLDEN_DIR = orig
"
```

Expected: `OK — raised ValueError: ...` with message containing "findings".

### Step 9 — Verify wbsb eval CLI exit codes

```bash
# Run all golden cases — expect PASS
wbsb eval
echo "Exit code: $?"
# Expected: exit code 0 (all cases pass)
```

If any case fails, report which case and what failure reason.

```bash
# Verify --case flag works
wbsb eval --case fallback_no_llm
echo "Exit code: $?"
# Expected: PASS, exit code 0
```

### Step 10 — Verify no hardcoded thresholds in runner.py

```bash
grep -n "0\.8\|0\.9\|1\.0\|> 0\|< 0\|== 0" src/wbsb/eval/runner.py
```

Any numeric threshold literal in logic (not in comments) = `severity: major`. All pass/fail
logic must read from the `criteria` dict.

### Step 11 — Verify governance README present

```bash
cat src/wbsb/eval/golden/README.md
```

Must contain at minimum:
- Reference to production runs being the source for real cases.
- Instruction that `criteria.json` requires PR review to update.
- Statement that `fallback_no_llm` must always be present.

### Step 12 — Forbidden patterns

```bash
# No silent failure
grep -n "except.*pass\|except:$" src/wbsb/eval/runner.py tests/test_eval_runner.py
# Expected: no matches

# No cross-imports
grep -n "from wbsb.feedback\|import wbsb.feedback" src/wbsb/eval/runner.py
# Expected: no matches

# domain/models.py not modified
git diff feature/iteration-7 src/wbsb/domain/models.py
# Expected: no output
```

### Step 13 — Verify all 6 test functions exist

```bash
grep -n "^def test_" tests/test_eval_runner.py
```

Expected — all 6 present:
```
test_load_case_valid
test_load_case_missing_findings
test_run_case_passes
test_run_case_fails_grounding
test_run_case_fallback_no_llm
test_run_all_cases_returns_list
```

---

## Required Output Format

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List everything implemented correctly. Reference file paths and line numbers.
Must not be empty on a PASS verdict.

---

### 3. Problems Found

```
- severity: critical | major | minor
  file: path/to/file.py:LINE
  exact problem: one or two sentences
  why it matters: one sentence on the consequence
```

If no problems: `None.`

---

### 4. Missing or Weak Tests

```
- test: test_function_name (missing | weak assertion)
  issue: ...
  suggestion: ...
```

If none: `None.`

---

### 5. Scope Violations

```
- file: path/to/unexpected_file
  change: what was changed
  verdict: revert | move to correct task
```

If no violations: `None.`

---

### 6. Acceptance Criteria Check

```
- [PASS | FAIL] load_case importable from wbsb.eval.runner
- [PASS | FAIL] run_case importable from wbsb.eval.runner
- [PASS | FAIL] run_all_cases importable from wbsb.eval.runner
- [PASS | FAIL] load_case raises ValueError when findings.json missing
- [PASS | FAIL] run_case returns {name, passed, failures, scores}
- [PASS | FAIL] run_case passes when eval_scores meets all criteria
- [PASS | FAIL] run_case fails when eval_scores below min_grounding
- [PASS | FAIL] fallback_no_llm case handled correctly (no llm_response.json, expect_eval_scores=false)
- [PASS | FAIL] All 6 required golden case directories present
- [PASS | FAIL] Each case directory has criteria.json with all required keys
- [PASS | FAIL] fallback_no_llm has no llm_response.json
- [PASS | FAIL] No min_grounding: 1.0 in synthetic criteria.json files
- [PASS | FAIL] No hardcoded thresholds in runner.py
- [PASS | FAIL] Governance README present with required content
- [PASS | FAIL] wbsb eval runs all cases with correct exit code 0
- [PASS | FAIL] wbsb eval --case NAME routes to single case correctly
- [PASS | FAIL] No cross-imports between wbsb.eval and wbsb.feedback
- [PASS | FAIL] domain/models.py not modified
- [PASS | FAIL] All 6 test functions present
- [PASS | FAIL] 312 tests pass (306 existing + 6 new)
- [PASS | FAIL] Ruff clean
```

---

### 7. Exact Fixes Required

Numbered list. Each fix must be actionable — file path, line number, what to change.
If verdict is PASS: `None.`

---

### 8. Final Recommendation

```
approve | request changes | block
```

One sentence explaining the recommendation.
