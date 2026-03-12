# WBSB Review Prompt — I7-4: Hallucination Detector

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
| Task ID | I7-4 |
| Title | Hallucination Detector |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Codex |
| Reviewed by | Claude |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-4-hallucination-scorer` |
| PR | #TBD |
| Expected test count | 295 before → 302 after (expected +7) |

---

## What This Task Was Supposed to Build

### Modified files (exactly these, no more)

```
src/wbsb/eval/scorer.py          ← extend (add score_hallucination only)
tests/test_eval_scorer.py        ← extend (add 7 new tests)
```

### Public API (required signature)

```python
from wbsb.domain.models import Findings, LLMResult

def score_hallucination(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Returns:
        {
            "hallucination_risk": int,
            "hallucination_violations": list[dict],   # each: {type, severity, detail}
        }
    """
```

### Violation contract (all 5 checks, in order)

| # | type | severity | trigger |
|---|------|----------|---------|
| 1 | `key_story_when_no_cluster` | `critical` | `llm_result.key_story is not None` AND `findings.dominant_cluster_exists is False` |
| 2 | `invalid_watch_signal_id` | `major` | `entry.metric_or_signal` not in `payload_rule_ids ∪ payload_metric_ids` |
| 3 | `invalid_group_narrative_category` | `major` | `key.lower().replace(" ", "_")` not in `payload_category_keys` |
| 4 | `extra_signal_narrative` | `minor` | `rule_id` in `signal_narratives` not in `payload_rule_ids` |
| 5 | `missing_signal_narrative` | `minor` | `rule_id` in `payload_rule_ids` not in `signal_narratives` |

`hallucination_risk = len(hallucination_violations)`.

### What must NOT have been built

- No modifications to `score_grounding()` or `score_signal_coverage()` — both frozen.
- No `build_eval_scores()` — that is I7-5.
- No changes to `extractor.py`, `models.py`, `pipeline.py`, `llm_adapter.py`.
- No cross-imports between `wbsb.eval` and `wbsb.feedback`.

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-4-hallucination-scorer
git pull origin feature/i7-4-hallucination-scorer
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 302 passing, 0 failures

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

### Step 4 — Verify pre-existing functions are untouched

```bash
git diff feature/iteration-7 src/wbsb/eval/scorer.py | grep "^-def \|^+def "
```

Expected: only `score_hallucination` appears as addition (`+def`). If `score_grounding` or
`score_signal_coverage` appear as modified: `severity: major`.

```bash
grep -n "^def " src/wbsb/eval/scorer.py
```

Expected: exactly 3 functions — `score_grounding`, `score_signal_coverage`, `score_hallucination`.

### Step 5 — Verify function is importable with correct signature

```bash
python3 -c "
from wbsb.eval.scorer import score_hallucination
import inspect

params = list(inspect.signature(score_hallucination).parameters.keys())
assert params == ['findings', 'llm_result'], f'wrong params: {params}'
print('signature: OK')
"
```

Expected: `signature: OK`

### Step 6 — Verify all 5 violation types are implemented

```bash
grep -n "key_story_when_no_cluster\|invalid_watch_signal_id\|invalid_group_narrative_category\|extra_signal_narrative\|missing_signal_narrative" src/wbsb/eval/scorer.py
```

Expected: all 5 type strings present. If any missing: `severity: major` — that violation class
is silently skipped.

### Step 7 — Verify severity strings are correct

```bash
grep -n '"critical"\|"major"\|"minor"' src/wbsb/eval/scorer.py
```

Verify assignment by checking which violation gets which severity:

| Violation type | Required severity |
|---|---|
| `key_story_when_no_cluster` | `"critical"` |
| `invalid_watch_signal_id` | `"major"` |
| `invalid_group_narrative_category` | `"major"` |
| `extra_signal_narrative` | `"minor"` |
| `missing_signal_narrative` | `"minor"` |

Any severity mismatch = `severity: major` finding.

### Step 8 — Verify payload_valid_ids merges rule_ids AND metric_ids

```bash
grep -n "payload_rule_ids\|payload_metric_ids\|payload_valid_ids\|metrics\|rule_id" src/wbsb/eval/scorer.py
```

Verify:
- `payload_rule_ids` is built from `{signal.rule_id for signal in findings.signals}`.
- `payload_metric_ids` is built from `findings.metrics` — the exact access pattern depends on
  whether `Findings.metrics` is a `dict` (use `.keys()`) or a `list` (use a set comprehension
  over the appropriate id attribute). Either approach is acceptable; verify it does not crash.
- Check 2 (`invalid_watch_signal_id`) compares against the **union** of both sets.

If check 2 only compares against `payload_rule_ids` without metric IDs: `severity: major` —
watch signal entries referencing a metric name (e.g. `"net_revenue"`) would be incorrectly flagged.

### Step 9 — Verify category normalization in check 3

```bash
grep -n "lower.*replace\|replace.*lower\|group_narratives" src/wbsb/eval/scorer.py
```

Expected: normalization `key.lower().replace(" ", "_")` applied to `group_narratives` keys
before comparing against `payload_category_keys`.

If the group_narratives key is compared without normalization: `severity: major`.

### Step 10 — Verify determinism in check 5

```bash
grep -n "sorted\|payload_rule_ids" src/wbsb/eval/scorer.py
```

Check 5 (missing_signal_narrative) iterates `payload_rule_ids` — a set. Iteration order of
a set is not deterministic across Python runs. Verify that iteration is wrapped in `sorted()`.

If not sorted: `severity: minor` — violation list order may vary between runs.

### Step 11 — Verify hallucination_risk equals violation count

```bash
grep -n "hallucination_risk\|len(violations" src/wbsb/eval/scorer.py
```

Expected: `hallucination_risk = len(violations)` — not a separate counter that could diverge.

### Step 12 — Verify violation dict structure

```bash
grep -n '"type"\|"severity"\|"detail"' src/wbsb/eval/scorer.py
```

Every `violations.append(...)` call must produce a dict with exactly 3 keys: `type`, `severity`,
`detail`. No extra keys. No missing keys.

### Step 13 — Forbidden patterns

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
```

### Step 14 — Verify all 7 test functions exist

```bash
grep -n "^def test_" tests/test_eval_scorer.py
```

Expected — all 7 new tests present (in addition to 11 from I7-2 + I7-3):
```
test_hallucination_clean_output
test_hallucination_key_story_no_cluster
test_hallucination_invalid_watch_signal
test_hallucination_invalid_group_category
test_hallucination_extra_signal_narrative
test_hallucination_missing_signal_narrative
test_hallucination_multiple_violations
```

Total test count in file should be 18 (5 from I7-2 + 6 from I7-3 + 7 new). If any prior tests
are missing: `severity: critical` — pre-existing tests were deleted.

Also verify `test_hallucination_multiple_violations` asserts:
- `hallucination_risk == len(hallucination_violations)` — the invariant must be explicitly tested.

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
- [PASS | FAIL] score_hallucination importable from wbsb.eval.scorer
- [PASS | FAIL] score_hallucination has correct 2-parameter signature (findings, llm_result)
- [PASS | FAIL] score_grounding and score_signal_coverage signatures unchanged
- [PASS | FAIL] All 5 violation types implemented
- [PASS | FAIL] Severity strings correct for all 5 types (critical/major/major/minor/minor)
- [PASS | FAIL] Check 2 compares against rule_ids UNION metric_ids (not just rule_ids)
- [PASS | FAIL] Category normalization applied in check 3 (.lower().replace(" ", "_"))
- [PASS | FAIL] Check 5 iterates with sorted() for determinism
- [PASS | FAIL] hallucination_risk == len(hallucination_violations)
- [PASS | FAIL] Each violation dict has exactly {type, severity, detail} keys
- [PASS | FAIL] Only 3 functions in scorer.py (grounding + coverage + hallucination)
- [PASS | FAIL] No cross-imports between wbsb.eval and wbsb.feedback
- [PASS | FAIL] No silent failures
- [PASS | FAIL] domain/models.py not modified
- [PASS | FAIL] All 7 new test functions present
- [PASS | FAIL] All 11 prior tests (I7-2 + I7-3) still present and unmodified
- [PASS | FAIL] test_hallucination_multiple_violations asserts risk == len(violations)
- [PASS | FAIL] 302 tests pass (295 existing + 7 new)
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
