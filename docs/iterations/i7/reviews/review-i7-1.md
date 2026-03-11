# WBSB Review Prompt — I7-1: Numeric Extraction Utility

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

**Architecture principles (violations of any = CHANGES REQUIRED minimum):**

| # | Principle |
|---|-----------|
| 1 | **Deterministic first** — no randomness, no time-dependent logic in metrics or rules |
| 2 | **Config-driven** — all thresholds in `config/rules.yaml`; zero hardcoded numbers in code |
| 3 | **No silent failure** — never `except: pass`; raise `ValueError` with a clear message |
| 4 | **Separation of concerns** — eval and feedback packages must not import from each other |
| 5 | **Domain model is frozen** — `src/wbsb/domain/models.py` must not be modified |

---

## Task Under Review

| Field | Value |
|-------|-------|
| Task ID | I7-1 |
| Title | Numeric Extraction Utility |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Codex |
| Reviewed by | Claude |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-1-numeric-extractor` |
| PR | #TBD |
| Expected test count | 271 before → 284 after (expected +13) |

---

## What This Task Was Supposed to Build

### New files (exactly these, no more)

```
src/wbsb/eval/extractor.py
tests/test_eval_extractor.py
```

### Public API (required signatures)

```python
from wbsb.domain.models import Findings

def extract_numbers_from_text(text: str) -> list[str]: ...
def normalize_number(raw: str) -> float | None: ...
def build_evidence_allowlist(findings: Findings) -> set[float]: ...
def candidate_values(raw: str, pct_normalization: bool) -> list[float]: ...
def is_grounded(candidate: float, allowlist: set[float], cfg: dict) -> bool: ...
```

### Behaviour rules the implementation must enforce

- **Rule 1:** Extraction regex must handle negatives, comma thousands, decimals, optional `%`.
- **Rule 2:** Date-like tokens (e.g. `2024-03-18`) must be excluded.
- **Rule 3:** Normalization strips `%`, `,`, `$` safely.
- **Rule 4:** Percent normalization rule — if `%` present and `pct_normalization=True`, candidates include both raw value and raw/100.
- **Rule 5:** Allowlist built from findings metrics/signals evidence numeric fields only.
- **Rule 6:** Tolerance source must be `cfg` dict — absolute for `|allowlist_value| < 1.0`, relative for `|allowlist_value| >= 1.0`.
- **Rule 7:** No hardcoded tolerance constants anywhere in implementation.

### What must NOT have been built

- No changes to `src/wbsb/eval/models.py`
- No changes to `src/wbsb/pipeline.py`
- No changes to `src/wbsb/render/llm_adapter.py`
- No changes to `config/rules.yaml`
- No cross-imports between `wbsb.eval` and `wbsb.feedback`
- No `@field_validator` decorators or logic beyond pure functions

---

## Acceptance Criteria to Verify

- [ ] `extract_numbers_from_text` exists in `wbsb.eval.extractor` with correct signature
- [ ] `normalize_number` exists in `wbsb.eval.extractor` with correct signature
- [ ] `build_evidence_allowlist` exists in `wbsb.eval.extractor` with correct signature
- [ ] `candidate_values` exists in `wbsb.eval.extractor` with correct signature
- [ ] `is_grounded` exists in `wbsb.eval.extractor` with correct signature
- [ ] Regex handles negatives, comma thousands, decimals, optional `%`
- [ ] Date-like tokens excluded from extraction
- [ ] `normalize_number` strips `%`, `,`, `$` and returns `None` for invalid input
- [ ] `candidate_values` with `pct_normalization=True` returns `[raw, raw/100]` for `%` tokens
- [ ] `candidate_values` with `pct_normalization=False` returns `[raw]` only
- [ ] `is_grounded` uses absolute tolerance when `|allowlist_value| < 1.0`
- [ ] `is_grounded` uses relative tolerance when `|allowlist_value| >= 1.0`
- [ ] No hardcoded tolerance values in implementation
- [ ] `is_grounded` returns `False` for empty allowlist
- [ ] All 13 required test functions present
- [ ] All 271 existing tests still pass (284 total)
- [ ] Ruff clean
- [ ] Only 2 allowed files in scope diff

---

## Tests Required (from task prompt)

| Test function | What it verifies |
|---------------|-----------------|
| `test_extract_numbers_basic` | integers/decimals extracted |
| `test_extract_numbers_with_percentages` | `%` tokens extracted |
| `test_extract_numbers_negative` | negative values extracted |
| `test_extract_numbers_comma_separated` | comma separated values extracted |
| `test_extract_numbers_skips_dates` | dates excluded |
| `test_normalize_number_percent` | percent normalization parsing |
| `test_normalize_number_invalid` | invalid token returns None |
| `test_candidate_values_percent_normalization_on` | returns both forms |
| `test_candidate_values_percent_normalization_off` | returns raw only |
| `test_build_evidence_allowlist` | expected numeric set built |
| `test_is_grounded_within_abs_tolerance` | abs tolerance success |
| `test_is_grounded_within_rel_tolerance` | rel tolerance success |
| `test_is_grounded_false` | mismatch returns False |

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-1-numeric-extractor
git pull origin feature/i7-1-numeric-extractor
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 284 passing, 0 failures

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
src/wbsb/eval/extractor.py
tests/test_eval_extractor.py
```

Any other file = scope violation = `CHANGES REQUIRED`.

### Step 4 — Verify all 5 functions are importable with correct signatures

```bash
python3 -c "
from wbsb.eval.extractor import (
    extract_numbers_from_text,
    normalize_number,
    build_evidence_allowlist,
    candidate_values,
    is_grounded,
)
import inspect

# Verify signatures
sig = inspect.signature
assert str(sig(extract_numbers_from_text)) == '(text: str) -> list[str]', f'wrong sig: {sig(extract_numbers_from_text)}'
assert str(sig(normalize_number)) == '(raw: str) -> float | None', f'wrong sig: {sig(normalize_number)}'
assert str(sig(candidate_values)) == '(raw: str, pct_normalization: bool) -> list[float]', f'wrong sig: {sig(candidate_values)}'
assert str(sig(is_grounded)) == '(candidate: float, allowlist: set[float], cfg: dict) -> bool', f'wrong sig: {sig(is_grounded)}'

print('signatures: OK')
"
```

Expected: `signatures: OK`

Note: signature strings may vary slightly by Python version. If the assertion fails due to formatting, verify manually that parameter names and types match exactly.

### Step 5 — Verify extraction behaviour

```bash
python3 -c "
from wbsb.eval.extractor import extract_numbers_from_text

# Basic integers and decimals
result = extract_numbers_from_text('Revenue was 1503 and margin 12.5%')
assert '1503' in result or '1,503' in result or '12.5%' in result, f'basic extraction failed: {result}'

# Negative values
result = extract_numbers_from_text('Change was -8.3%')
assert any('-8.3' in r for r in result), f'negative not extracted: {result}'

# Comma thousands
result = extract_numbers_from_text('Total 1,234,567 bookings')
assert any('1,234,567' in r or '1234567' in r for r in result), f'comma thousands failed: {result}'

# Date exclusion
result = extract_numbers_from_text('Date 2024-03-18 shows 42 bookings')
assert '2024-03-18' not in result, f'date not excluded: {result}'
assert not any(r in ('2024', '03', '18') and '-' not in r for r in result if r.replace('-','').isdigit()), \
    'date parts leaked: {result}'
assert any('42' in r for r in result), f'42 not extracted: {result}'

# No numbers
result = extract_numbers_from_text('No numbers here at all')
assert result == [], f'empty case failed: {result}'

print('extraction: OK')
"
```

Expected: `extraction: OK`

### Step 6 — Verify normalization

```bash
python3 -c "
from wbsb.eval.extractor import normalize_number

# Percent
v = normalize_number('12.5%')
assert v == 12.5, f'percent normalization wrong: {v}'

# Comma thousands
v = normalize_number('1,503')
assert v == 1503.0, f'comma stripping wrong: {v}'

# Currency
v = normalize_number('\$1,200')
assert v == 1200.0, f'currency stripping wrong: {v}'

# Negative
v = normalize_number('-8.3%')
assert v == -8.3, f'negative percent wrong: {v}'

# Invalid
v = normalize_number('abc')
assert v is None, f'invalid should return None, got: {v}'

# Invalid: date-like (should not be passed to normalize, but if it is, must not crash)
v = normalize_number('2024-03-18')
# Either returns None or raises — must not silently return a wrong float

print('normalization: OK')
"
```

Expected: `normalization: OK`

### Step 7 — Verify candidate_values

```bash
python3 -c "
from wbsb.eval.extractor import candidate_values

# Percent with normalization ON: both raw and raw/100
result = candidate_values('40%', True)
assert 40.0 in result, f'raw not in candidates: {result}'
assert 0.4 in result, f'0.4 not in candidates: {result}'
assert len(result) == 2, f'expected 2 candidates, got {len(result)}: {result}'

# Percent with normalization OFF: raw only
result = candidate_values('40%', False)
assert 40.0 in result, f'raw not in candidates: {result}'
assert 0.4 not in result, f'0.4 should not be in candidates: {result}'
assert len(result) == 1, f'expected 1 candidate, got {len(result)}: {result}'

# Non-percent: always raw only, regardless of flag
result_on = candidate_values('1503', True)
result_off = candidate_values('1503', False)
assert result_on == result_off == [1503.0], f'non-pct candidates wrong: {result_on}, {result_off}'

print('candidate_values: OK')
"
```

Expected: `candidate_values: OK`

### Step 8 — Verify is_grounded with abs and rel tolerances

```bash
python3 -c "
from wbsb.eval.extractor import is_grounded

cfg = {
    'grounding_tolerance_abs': 0.01,
    'grounding_tolerance_rel': 0.01,
}

# Absolute tolerance (|allowlist_value| < 1.0): 0.40 ± 0.01 → 0.405 should match
assert is_grounded(0.405, {0.40}, cfg) == True, 'abs tolerance failed'
assert is_grounded(0.42, {0.40}, cfg) == False, 'abs tolerance over-matched'

# Relative tolerance (|allowlist_value| >= 1.0): 1503 ± 1% → 1510 should match
assert is_grounded(1510.0, {1503.0}, cfg) == True, 'rel tolerance failed'
assert is_grounded(1600.0, {1503.0}, cfg) == False, 'rel tolerance over-matched'

# Boundary: |value| == 1.0 must use relative
assert isinstance(is_grounded(1.005, {1.0}, cfg), bool), 'boundary case crashed'

# Empty allowlist: always False
assert is_grounded(1.0, set(), cfg) == False, 'empty allowlist should return False'

print('is_grounded: OK')
"
```

Expected: `is_grounded: OK`

### Step 9 — Hardcoded tolerance checks

```bash
# Config keys must be referenced (not hardcoded values)
grep -n "grounding_tolerance_abs\|grounding_tolerance_rel\|pct_normalization" src/wbsb/eval/extractor.py
# Expected: at least one match showing cfg["grounding_tolerance_abs"] or cfg.get(...)

# No hardcoded 0.01 literal used as a tolerance (comment appearances are acceptable)
grep -n "= 0\.01\|== 0\.01\| 0\.01 " src/wbsb/eval/extractor.py
# Expected: no matches in logic paths (only in comments if present)
```

If `0.01` appears in a logic expression (not a comment): `severity: major` — hardcoded tolerance violates Rule 7 and Principle 2.

### Step 10 — Silent failure checks

```bash
grep -n "except.*pass\|except:$" src/wbsb/eval/extractor.py tests/test_eval_extractor.py
# Expected: no matches

# No cross-imports
grep -n "from wbsb.feedback\|import wbsb.feedback" src/wbsb/eval/extractor.py
# Expected: no matches

# domain/models.py not modified
git diff feature/iteration-7 src/wbsb/domain/models.py
# Expected: no output
```

### Step 11 — Verify all 13 test functions exist

```bash
grep -n "^def test_" tests/test_eval_extractor.py
```

Expected: all 13 test functions from the required list present. Count must be >= 13.

---

## Required Output Format

Structure your review exactly as follows.

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
- [PASS | FAIL] extract_numbers_from_text importable from wbsb.eval.extractor
- [PASS | FAIL] normalize_number importable from wbsb.eval.extractor
- [PASS | FAIL] build_evidence_allowlist importable from wbsb.eval.extractor
- [PASS | FAIL] candidate_values importable from wbsb.eval.extractor
- [PASS | FAIL] is_grounded importable from wbsb.eval.extractor
- [PASS | FAIL] Regex handles negatives, comma thousands, decimals, optional %
- [PASS | FAIL] Date-like tokens excluded from extraction
- [PASS | FAIL] normalize_number returns None for invalid input
- [PASS | FAIL] candidate_values pct_normalization=True returns [raw, raw/100]
- [PASS | FAIL] candidate_values pct_normalization=False returns [raw] only
- [PASS | FAIL] is_grounded uses absolute tolerance for |value| < 1.0
- [PASS | FAIL] is_grounded uses relative tolerance for |value| >= 1.0
- [PASS | FAIL] No hardcoded tolerance values in implementation
- [PASS | FAIL] is_grounded returns False for empty allowlist
- [PASS | FAIL] All 13 required test functions present
- [PASS | FAIL] 284 tests pass (271 existing + 13 new)
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
