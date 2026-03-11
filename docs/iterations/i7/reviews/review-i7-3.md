# WBSB Review Prompt — I7-3: Signal Coverage Scorer

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
- Do not invent problems that are not there. Every finding must be backed by evidence
  (file path + line number or command output).

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

**Architecture principles (violations of any of these = CHANGES REQUIRED minimum):**

| # | Principle |
|---|-----------|
| 1 | **Deterministic first** — no randomness, no time-dependent logic in metrics or rules |
| 2 | **Config-driven** — all thresholds in `config/rules.yaml`; zero hardcoded numbers in code |
| 3 | **Auditability** — emit `AuditEvent` after every significant state change |
| 4 | **No silent failure** — never `except: pass`; raise `ValueError` with a clear message |
| 5 | **Separation of concerns** — metrics, rules, and rendering are strictly isolated |
| 6 | **LLM is optional** — `--llm-mode off` must always produce a complete, valid report |
| 7 | **Stable ordering** — signals sorted by `rule_id`; metrics in deterministic order |
| 8 | **Secrets never in code** — API keys from env vars only; never logged |

---

## Task Under Review

| Field | Value |
|-------|-------|
| Task ID | I7-3 |
| Title | Signal Coverage Scorer |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Codex |
| Reviewed by | Claude |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-3-coverage-scorer` |
| PR | #TBD |
| Expected test count | 289 before → 295 after (expected +6) |

---

## What This Task Was Supposed to Build

### Modified files (exactly these, no more)

```
src/wbsb/eval/scorer.py          ← extend (add score_signal_coverage only)
tests/test_eval_scorer.py        ← extend (add 6 new tests)
```

### Public API (required signature)

```python
from wbsb.domain.models import Findings, LLMResult

def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Returns:
        {
            "signal_coverage": float,   # [0.0, 1.0]
            "group_coverage": float,    # [0.0, 1.0]
        }
    """
```

### Algorithm contract

**Signal coverage:**
- `total_signals = len(findings.signals)` — includes both WARN and INFO signals.
- If `total_signals == 0`: `signal_coverage = 1.0`.
- Else: `signals_with_narrative = count of signal.rule_id values that appear in llm_result.signal_narratives`.
- `signal_coverage = signals_with_narrative / total_signals`.

**Group coverage:**
- `payload_categories = {signal.category.lower().replace(" ", "_") for signal in findings.signals}`.
- If `payload_categories` is empty: `group_coverage = 1.0`.
- Else: `covered = count of categories present as keys in llm_result.group_narratives`.
- `group_coverage = covered / len(payload_categories)`.

### What must NOT have been built

- No modifications to `score_grounding()` — it is frozen after I7-2.
- No `score_hallucination()` — that is I7-4.
- No `build_eval_scores()` — that is I7-5.
- No changes to `extractor.py`, `models.py`, `pipeline.py`, `llm_adapter.py`.
- No hardcoded threshold values anywhere.
- No cross-imports between `wbsb.eval` and `wbsb.feedback`.

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-3-coverage-scorer
git pull origin feature/i7-3-coverage-scorer
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 295 passing, 0 failures

ruff check .
# Expected: no issues
```

If either fails, verdict is `CHANGES REQUIRED` immediately. Report exact output.

### Step 3 — Verify scope

```bash
git diff --name-only feature/iteration-7
```

Expected output (exactly these 2 files, no others):
```
src/wbsb/eval/scorer.py
tests/test_eval_scorer.py
```

Any other file = scope violation = `CHANGES REQUIRED`.

### Step 4 — Verify score_grounding is untouched

```bash
git diff feature/iteration-7 src/wbsb/eval/scorer.py | grep "^-def \|^+def "
```

Expected: only `score_signal_coverage` appears as an addition (`+def`). If `score_grounding`
appears as modified (`-def` followed by `+def`): `severity: major` — pre-existing function
was altered.

Also verify the signature of `score_grounding` is unchanged:

```bash
grep -n "^def score_grounding" src/wbsb/eval/scorer.py
```

Expected: still exactly `def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict:`.

### Step 5 — Verify function is importable with correct signature

```bash
python3 -c "
from wbsb.eval.scorer import score_signal_coverage
import inspect

params = list(inspect.signature(score_signal_coverage).parameters.keys())
assert params == ['findings', 'llm_result'], f'wrong params: {params}'
print('signature: OK')
"
```

Expected: `signature: OK`

### Step 6 — Verify zero-signal edge cases

```bash
pytest -q tests/test_eval_scorer.py -k "coverage_no_signals or group_coverage_no_categories"
# Expected: both tests pass
```

**What to verify manually by reading the code:**
- When `findings.signals == []`: `signal_coverage = 1.0` (not `0.0`, not division error).
- When `findings.signals == []`: `group_coverage = 1.0` (same reason — no categories).
- Division never occurs with denominator zero.

```bash
grep -n "total_signals\|payload_categories\|== 0\|not \|if len" src/wbsb/eval/scorer.py
```

Verify the guard is present for both zero-total-signals and zero-payload-categories paths.

### Step 7 — Verify category normalization

```bash
grep -n "lower.*replace\|replace.*lower\|category" src/wbsb/eval/scorer.py
```

Expected: category keys normalized as `signal.category.lower().replace(" ", "_")` before
comparing against `group_narratives` keys.

If normalization is absent or uses a different pattern: `severity: major` — categories with
spaces (e.g. "Financial Health") will never match.

### Step 8 — Verify no config parameter in signature

```bash
grep -n "^def score_signal_coverage" src/wbsb/eval/scorer.py
```

Expected: exactly `def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict:`.

If `cfg: dict` is a parameter: `severity: minor` — coverage scorer needs no config; extra param
creates confusion for I7-5 callers.

### Step 9 — Verify only 2 functions in scorer.py

```bash
grep -n "^def " src/wbsb/eval/scorer.py
```

Expected: exactly 2 functions — `score_grounding` and `score_signal_coverage`.
Any additional function = scope creep = `severity: major`.

### Step 10 — Forbidden patterns

```bash
# No silent failure
grep -n "except.*pass\|except:$" src/wbsb/eval/scorer.py tests/test_eval_scorer.py
# Expected: no matches

# No cross-imports
grep -n "from wbsb.feedback\|import wbsb.feedback" src/wbsb/eval/scorer.py
# Expected: no matches

# domain/models.py not modified
git diff feature/iteration-7 src/wbsb/domain/models.py
# Expected: no output

# No hardcoded numbers used as thresholds
grep -n "= 1\.0\|= 0\.0\|/ 2\|/ 3\|> 0\." src/wbsb/eval/scorer.py
# Check each match — 1.0 and 0.0 are acceptable as defaults for empty cases, not as thresholds
```

### Step 11 — Verify all 6 test functions exist

```bash
grep -n "^def test_" tests/test_eval_scorer.py
```

Expected — all 6 new tests present (in addition to the 5 from I7-2):
```
test_coverage_all_signals_covered
test_coverage_partial_signals
test_coverage_no_signals
test_group_coverage_all_categories
test_group_coverage_partial
test_group_coverage_no_categories
```

Total test count in file should be 11 (5 from I7-2 + 6 new). If any of the 5 I7-2 tests are
missing: `severity: critical` — pre-existing tests were deleted.

---

## Required Output Format

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List everything implemented correctly. Reference file paths and line numbers where relevant.
This section must not be empty on a PASS verdict.

---

### 3. Problems Found

For each problem:

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
- [PASS | FAIL] score_signal_coverage importable from wbsb.eval.scorer
- [PASS | FAIL] score_signal_coverage has correct 2-parameter signature (findings, llm_result)
- [PASS | FAIL] score_grounding signature unchanged after this task
- [PASS | FAIL] signal_coverage=1.0 when findings.signals is empty
- [PASS | FAIL] group_coverage=1.0 when no payload categories
- [PASS | FAIL] signal_coverage correct ratio when some signals have narratives
- [PASS | FAIL] group_coverage correct ratio when some categories covered
- [PASS | FAIL] Category normalization applied: .lower().replace(" ", "_")
- [PASS | FAIL] No division by zero possible
- [PASS | FAIL] No hardcoded threshold values
- [PASS | FAIL] Only 2 functions in scorer.py (score_grounding + score_signal_coverage)
- [PASS | FAIL] No cross-imports between wbsb.eval and wbsb.feedback
- [PASS | FAIL] No silent failures
- [PASS | FAIL] domain/models.py not modified
- [PASS | FAIL] All 6 new test functions present
- [PASS | FAIL] All 5 I7-2 tests still present (not deleted)
- [PASS | FAIL] 295 tests pass (289 existing + 6 new)
- [PASS | FAIL] Ruff clean
- [PASS | FAIL] Only 2 allowed files in scope diff
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
