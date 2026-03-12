# WBSB Review Prompt — I7-2: Grounding Scorer

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
| Task ID | I7-2 |
| Title | Grounding Scorer |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Codex |
| Reviewed by | Claude |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-2-grounding-scorer` |
| PR | #TBD |
| Expected test count | 284 before → 289 after (expected +5) |

---

## What This Task Was Supposed to Build

### New files (exactly these, no more)

```
src/wbsb/eval/scorer.py          ← create (grounding function only)
tests/test_eval_scorer.py        ← create
```

### Public API (required signature)

```python
from wbsb.domain.models import Findings, LLMResult

def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict:
    """
    Returns:
        {
            "grounding": float | None,
            "grounding_reason": str | None,
            "flagged_numbers": list[str],
        }
    """
```

### Algorithm contract

1. Collect text from: `situation`, `key_story`, all `group_narratives` values, all `signal_narratives` values, all `watch_signals[].observation` values.
2. Call `extract_numbers_from_text()` on the combined text.
3. If zero tokens: return `{"grounding": None, "grounding_reason": "no_numbers_cited", "flagged_numbers": []}`.
4. Build evidence allowlist via `build_evidence_allowlist(findings)`.
5. For each token: get candidates via `candidate_values(token, cfg["grounding_pct_normalization"])`. Check each candidate via `is_grounded(candidate, allowlist, cfg)`.
6. `flagged_numbers` = tokens where no candidate is grounded.
7. `grounding = (total_tokens - len(flagged_numbers)) / total_tokens`.

### What must NOT have been built

- No `score_signal_coverage()` — that is I7-3.
- No `score_hallucination()` — that is I7-4.
- No `build_eval_scores()` — that is I7-5.
- No changes to `extractor.py`, `models.py`, `pipeline.py`, `llm_adapter.py`.
- No hardcoded tolerance values.
- No cross-imports between `wbsb.eval` and `wbsb.feedback`.

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-2-grounding-scorer
git pull origin feature/i7-2-grounding-scorer
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 289 passing, 0 failures

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

### Step 4 — Verify function is importable with correct signature

```bash
python3 -c "
from wbsb.eval.scorer import score_grounding
from wbsb.domain.models import Findings, LLMResult
import inspect

sig = inspect.signature(score_grounding)
params = list(sig.parameters.keys())
assert params == ['findings', 'llm_result', 'cfg'], f'wrong params: {params}'
print('signature: OK')
"
```

Expected: `signature: OK`

### Step 5 — Verify no-numbers case returns correct structure

```bash
pytest -q tests/test_eval_scorer.py -k "grounding_no_numbers_cited or grounding_empty_llm_sections"
# Expected: both tests pass
```

**What to verify manually by reading the code:**
- When `extract_numbers_from_text()` returns `[]`, the function returns `grounding=None` not `grounding=0.0`.
- `grounding_reason` is `"no_numbers_cited"` exactly (not `"no_numbers"`, not `"no_cited_numbers"`).
- `flagged_numbers` is `[]` not `None`.

### Step 6 — Verify text collection from all LLM sections

Read `src/wbsb/eval/scorer.py` and check that ALL of the following sources are included:

```bash
grep -n "situation\|key_story\|group_narratives\|signal_narratives\|watch_signals\|observation" src/wbsb/eval/scorer.py
```

Verify that:
- `llm_result.situation` is included (guarded for None)
- `llm_result.key_story` is included (guarded for None)
- All values from `llm_result.group_narratives` dict are included
- All values from `llm_result.signal_narratives` dict are included
- All `.observation` fields from `llm_result.watch_signals` list are included

If any source is missing: `severity: major` — grounding score will be inflated by unchecked text.

### Step 7 — Verify grounding formula

Read the implementation and confirm:

```bash
grep -n "grounding\|flagged\|len(" src/wbsb/eval/scorer.py
```

Confirm:
- Formula is `(total_tokens - len(flagged)) / total_tokens` — not `len(grounded) / total_tokens` (they are equivalent but verify no off-by-one).
- `flagged_numbers` contains **raw string tokens** (e.g. `"40%"`, `"1,503"`) — not floats.

### Step 8 — Verify pct_normalization is read from cfg

```bash
grep -n "grounding_pct_normalization\|pct_normalization" src/wbsb/eval/scorer.py
```

Expected: at least one match showing `cfg["grounding_pct_normalization"]` or `cfg.get("grounding_pct_normalization", ...)`.

### Step 9 — Hardcoded tolerance check

```bash
# No hardcoded tolerance literals in scorer.py (all tolerance logic is in extractor.py)
grep -n "0\.01\|tolerance" src/wbsb/eval/scorer.py
```

Expected: no matches. The scorer must not duplicate tolerance logic from `extractor.py`.
All tolerance parameters pass through `cfg` into `is_grounded()`.

### Step 10 — Forbidden patterns

```bash
# No silent failure
grep -n "except.*pass\|except:$" src/wbsb/eval/scorer.py tests/test_eval_scorer.py
# Expected: no matches

# No cross-imports
grep -n "from wbsb.feedback\|import wbsb.feedback" src/wbsb/eval/scorer.py
# Expected: no matches

# No new functions beyond score_grounding
grep -n "^def " src/wbsb/eval/scorer.py
# Expected: exactly one function — score_grounding

# domain/models.py not modified
git diff feature/iteration-7 src/wbsb/domain/models.py
# Expected: no output
```

### Step 11 — Verify all 5 test functions exist

```bash
grep -n "^def test_" tests/test_eval_scorer.py
```

Expected — all 5 present:
```
test_grounding_no_numbers_cited
test_grounding_all_grounded
test_grounding_one_flagged
test_grounding_pct_normalization
test_grounding_empty_llm_sections
```

Count must be exactly 5. If any missing: `severity: major`.

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
- [PASS | FAIL] score_grounding importable from wbsb.eval.scorer
- [PASS | FAIL] score_grounding has correct 3-parameter signature (findings, llm_result, cfg)
- [PASS | FAIL] No-numbers case returns grounding=None, grounding_reason="no_numbers_cited"
- [PASS | FAIL] All 5 LLM text sources collected (situation, key_story, group_narratives values, signal_narratives values, watch_signals observations)
- [PASS | FAIL] pct_normalization read from cfg dict (not hardcoded)
- [PASS | FAIL] flagged_numbers contains raw string tokens (not floats)
- [PASS | FAIL] grounding formula correct: (total - flagged) / total
- [PASS | FAIL] No hardcoded tolerance values in scorer.py
- [PASS | FAIL] No other functions beyond score_grounding in scorer.py
- [PASS | FAIL] No cross-imports between wbsb.eval and wbsb.feedback
- [PASS | FAIL] No silent failures
- [PASS | FAIL] domain/models.py not modified
- [PASS | FAIL] All 5 required test functions present
- [PASS | FAIL] 289 tests pass (284 existing + 5 new)
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
