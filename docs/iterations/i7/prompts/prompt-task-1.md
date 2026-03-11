# WBSB Task Prompt — I7-1: Numeric Extraction Utility

---

## Project Context

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics, detects signals via a config-driven rules engine, and generates a structured business brief. An LLM is optionally used for narrative sections only — never for calculations.

**Core architecture:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Non-negotiable principles:**
- Analytics are deterministic. LLM is explanation only, never analytics.
- All thresholds live in `config/rules.yaml`. Zero hardcoded numbers in code.
- Every module has a strict boundary. Metrics, rules, and rendering never mix.
- No silent failures. Raise clearly or emit an `AuditEvent`.
- LLM is optional. Every mode produces a complete, valid report without it.

---

## Repository State

- **Iteration integration branch:** `feature/iteration-7`
- **Feature branch for this task:** `feature/i7-1-numeric-extractor`
- **Tests passing:** 271
- **Ruff:** clean
- **Last completed task:** I7-0 — eval and feedback domain models + eval config section
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I7-1 |
| Title | Numeric Extraction Utility |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Owner | Codex |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-1-numeric-extractor` |
| Depends on | I7-0 |
| Blocks | I7-2 |
| PR scope | One PR into `feature/iteration-7`. Do not combine tasks. Do not PR to `main`. |

---

## Task Goal

Build the pure utility module that all grounding scoring logic depends on. This module extracts numeric tokens from LLM text, normalises them, builds a numeric evidence allowlist from deterministic findings, and performs tolerance-based matching against that allowlist.

This task is library-only. No pipeline wiring, no LLM adapter changes, no scoring logic. Everything built here is a pure function: same input always produces same output, no I/O.

---

## Why Codex

The task is fully specified with exact function signatures, regex pattern, tolerance rules, and expected input/output examples. No architectural judgment is required. Codex is well-suited to bounded algorithmic utility modules with precise edge-case handling.

---

## Files to Read Before Starting

Read these files in order before touching anything:

```
docs/iterations/i7/tasks.md                ← source of truth for I7-1 rules and tolerance policy
src/wbsb/eval/models.py                    ← schemas frozen in I7-0; do not modify
config/rules.yaml                          ← eval: section added in I7-0; read tolerance keys from here
src/wbsb/domain/models.py                  ← Findings / MetricResult / Signal field names
tests/test_history.py                      ← existing pure-function test style reference
```

---

## Existing Code This Task Builds On

### Already exists and must NOT be reimplemented:

```python
# src/wbsb/eval/models.py  (from I7-0 — do not touch)
class EvalScores(BaseModel): ...
class HallucinationViolation(BaseModel): ...

# src/wbsb/domain/models.py  (frozen — do not touch)
class Findings(BaseModel):
    signals: list[Signal]
    metrics: list[MetricResult]

class MetricResult(BaseModel):
    current_value: float | None
    previous_value: float | None
    delta_abs: float | None
    delta_pct: float | None

class Signal(BaseModel):
    current_value: float | None
    previous_value: float | None
    delta_abs: float | None
    delta_pct: float | None
    threshold: float | None
```

### Contracts established by I7-0 that this task must respect:

```
config/rules.yaml["eval"]["grounding_tolerance_abs"]    → float  (e.g. 0.01)
config/rules.yaml["eval"]["grounding_tolerance_rel"]    → float  (e.g. 0.01)
config/rules.yaml["eval"]["grounding_pct_normalization"] → bool  (e.g. True)
```

These are the only tolerance values the implementation may use. They must come from `cfg` — never hardcoded.

---

## What to Build

### New files

```
src/wbsb/eval/extractor.py         ← all five public functions
tests/test_eval_extractor.py       ← 13 unit tests
```

### Public API

```python
# src/wbsb/eval/extractor.py
from __future__ import annotations
from wbsb.domain.models import Findings


def extract_numbers_from_text(text: str) -> list[str]:
    """
    Extract all numeric tokens from text.

    Returns raw string representations, e.g. ["12.0%", "1,503", "-0.92"].
    Regex: r'-?\d[\d,]*(?:\.\d+)?%?'
    Excludes date-like tokens (YYYY-MM-DD pattern) and run-id fragments.

    Args:
        text: any string, including empty string

    Returns:
        List of raw matched string tokens. Empty list if no matches.
    """


def normalize_number(raw: str) -> float | None:
    """
    Parse a raw token to float. Returns None if unparseable.

    Strips: %, ,, $, whitespace before parsing.
    Does NOT divide by 100 — that is candidate_values' responsibility.

    Args:
        raw: a raw token string e.g. "40%", "1,503", "$120"

    Returns:
        float or None
    """


def candidate_values(raw: str, pct_normalization: bool) -> list[float]:
    """
    Return candidate floats for grounding comparison.

    If token ended with '%' and pct_normalization=True:
        return [normalized_value, normalized_value / 100]
    Else:
        return [normalized_value]
    If normalize_number returns None: return []

    Args:
        raw: raw token string
        pct_normalization: from config eval.grounding_pct_normalization

    Returns:
        List of candidate floats (0, 1, or 2 elements)
    """


def build_evidence_allowlist(findings: Findings) -> set[float]:
    """
    Build the set of all numeric evidence values from findings.

    Sources:
        - findings.metrics: current_value, previous_value, delta_abs, delta_pct
        - findings.signals: current_value, previous_value, delta_abs, delta_pct, threshold

    Include only non-None numeric values. Skip None fields silently.

    Args:
        findings: Findings domain object

    Returns:
        Set of floats. Empty set if findings has no numeric evidence.
    """


def is_grounded(candidate: float, allowlist: set[float], cfg: dict) -> bool:
    """
    Check whether a candidate number is within tolerance of any allowlist value.

    Tolerance rules (from cfg):
        if abs(allowlist_value) < 1.0:
            use grounding_tolerance_abs (absolute)
        else:
            use grounding_tolerance_rel * abs(allowlist_value) (relative)

    A candidate is grounded if it matches ANY value in the allowlist.
    Empty allowlist always returns False.

    Args:
        candidate: the float to test
        allowlist: set of evidence values from findings
        cfg: dict from config/rules.yaml["eval"]

    Returns:
        True if grounded, False otherwise
    """
```

### Input/output examples

```python
# extract_numbers_from_text
extract_numbers_from_text("Revenue 12.0% vs 1,503 baseline")
# → ["12.0%", "1,503"]

extract_numbers_from_text("Period 2024-03-18 to 2024-03-24")
# → []   (dates excluded)

extract_numbers_from_text("Declined by -0.92")
# → ["-0.92"]

extract_numbers_from_text("No numbers here")
# → []

# normalize_number
normalize_number("40%")     # → 40.0
normalize_number("1,503")   # → 1503.0
normalize_number("$120")    # → 120.0
normalize_number("-0.92")   # → -0.92
normalize_number("abc")     # → None

# candidate_values
candidate_values("40%", True)   # → [40.0, 0.4]
candidate_values("40%", False)  # → [40.0]
candidate_values("1503", True)  # → [1503.0]
candidate_values("abc", True)   # → []

# is_grounded — abs tolerance (allowlist_value < 1.0)
is_grounded(0.405, {0.40}, {"grounding_tolerance_abs": 0.01, "grounding_tolerance_rel": 0.01})
# → True  (|0.405 - 0.40| = 0.005 ≤ 0.01)

# is_grounded — rel tolerance (allowlist_value >= 1.0)
is_grounded(1510.0, {1503.0}, {"grounding_tolerance_abs": 0.01, "grounding_tolerance_rel": 0.01})
# → True  (|1510 - 1503| = 7 ≤ 0.01 * 1503 = 15.03)

# is_grounded — no match
is_grounded(999.0, {1503.0}, {"grounding_tolerance_abs": 0.01, "grounding_tolerance_rel": 0.01})
# → False

# is_grounded — empty allowlist
is_grounded(0.5, set(), {"grounding_tolerance_abs": 0.01, "grounding_tolerance_rel": 0.01})
# → False
```

### Behaviour rules

- **Regex:** `r'-?\d[\d,]*(?:\.\d+)?%?'` — handles negatives, commas, decimals, optional `%`. Note: `+` prefix is not matched; a token like `+12.0%` will be extracted as `12.0%`.
- **Date exclusion:** After extraction, filter out any token where the surrounding text matches a date pattern (`YYYY-MM-DD`). Simplest approach: before running the number regex, remove date-like substrings (`\d{4}-\d{2}-\d{2}`) from the input.
- **Pure functions only:** No I/O, no global state, no mutation of inputs.
- **No hardcoded tolerances:** Values `0.01`, `0.001`, etc. must never appear as literals in logic. Always read from `cfg`.
- **Tolerance boundary:** `abs(allowlist_value) < 1.0` uses abs tolerance; `>= 1.0` uses rel tolerance. The boundary is on the **allowlist value**, not the candidate.
- **No `except: pass`:** If a token cannot be parsed, `normalize_number` returns `None`. Never swallow errors silently.

### Config keys consumed

```yaml
# config/rules.yaml — keys this task reads (added in I7-0)
eval:
  grounding_tolerance_abs: float     # absolute tolerance
  grounding_tolerance_rel: float     # relative tolerance (as fraction, not %)
  grounding_pct_normalization: bool  # whether "40%" also tests 0.40
```

---

## Architecture Constraints

These apply to every task without exception.

1. **Deterministic first** — no randomness, no time-dependent logic in metrics or rules.
2. **Config-driven** — all thresholds in `config/rules.yaml`. Zero hardcoded numbers.
3. **Auditability** — emit `AuditEvent` after every significant state change.
4. **No silent failure** — never use `except: pass`. Raise `ValueError` with a clear message.
5. **Separation of concerns** — metrics, rules, and rendering are strictly isolated. Do not mix them.
6. **LLM is optional** — `--llm-mode off` must always produce a complete, valid report.
7. **Stable ordering** — signals sorted by `rule_id`. Metrics in a stable, deterministic order.
8. **Secrets never in code** — API keys and tokens from environment variables only. Never logged.

---

## Allowed Files

```
src/wbsb/eval/extractor.py         ← new: all five public functions
tests/test_eval_extractor.py       ← new: 13 unit tests
```

---

## Files NOT to Touch

```
src/wbsb/eval/models.py            ← frozen after I7-0
src/wbsb/eval/scorer.py            ← created in I7-2 (does not exist yet)
src/wbsb/domain/models.py          ← frozen; eval types are separate from domain types
src/wbsb/pipeline.py               ← touched only in I7-5
src/wbsb/render/llm_adapter.py     ← touched only in I7-5
config/rules.yaml                  ← config added in I7-0; do not change it here
```

If any of these files seem like they need to change to complete this task, **stop and raise it** rather than modifying them.

---

## Acceptance Criteria

- [ ] `extract_numbers_from_text()` returns list of raw string tokens matching the regex
- [ ] Date-like tokens (`YYYY-MM-DD`) are excluded from extraction results
- [ ] `normalize_number()` strips `%`, `,`, `$` and returns `float` or `None`
- [ ] `candidate_values()` returns two values for `%` tokens when `pct_normalization=True`, one otherwise
- [ ] `candidate_values()` returns empty list when `normalize_number` returns `None`
- [ ] `build_evidence_allowlist()` collects all non-None numeric fields from `metrics` and `signals`
- [ ] `is_grounded()` uses absolute tolerance when `|allowlist_value| < 1.0`
- [ ] `is_grounded()` uses relative tolerance when `|allowlist_value| >= 1.0`
- [ ] `is_grounded()` returns `False` for empty allowlist
- [ ] No hardcoded tolerance values in `extractor.py` — verified by grep
- [ ] All 271 existing tests still pass — `pytest` exit code 0
- [ ] All 13 new tests pass
- [ ] Ruff clean — `ruff check .` exit code 0
- [ ] Only allowed files modified

---

## Tests Required

**Test file:** `tests/test_eval_extractor.py`

| Test function | What it verifies |
|---|---|
| `test_extract_numbers_basic` | integers and decimals extracted from plain sentence |
| `test_extract_numbers_with_percentages` | tokens ending in `%` extracted |
| `test_extract_numbers_negative` | negative numbers (e.g. `-0.92`) extracted |
| `test_extract_numbers_comma_separated` | `"1,503"` → `["1,503"]` |
| `test_extract_numbers_skips_dates` | `"2024-03-18"` not in result |
| `test_normalize_number_percent` | `"40%"` → `40.0` (not 0.40) |
| `test_normalize_number_invalid` | `"abc"` → `None` |
| `test_candidate_values_percent_normalization_on` | `"40%", True` → `[40.0, 0.4]` |
| `test_candidate_values_percent_normalization_off` | `"40%", False` → `[40.0]` |
| `test_build_evidence_allowlist` | correct set from findings fixture with known values |
| `test_is_grounded_within_abs_tolerance` | value within ±abs_tol of a small allowlist entry → True |
| `test_is_grounded_within_rel_tolerance` | value within rel_tol% of a large allowlist entry → True |
| `test_is_grounded_false` | value far from all allowlist entries → False |

Each test must assert concrete values — not only list lengths or truthiness.

---

## Edge Cases to Handle Explicitly

| Edge case | Expected behaviour |
|-----------|-------------------|
| Empty string input | `extract_numbers_from_text("")` → `[]` |
| No numbers in text | `extract_numbers_from_text("hello world")` → `[]` |
| Date token `2024-03-18` | not extracted |
| Run ID fragment like `3485e2` | hex-only, no digits-comma pattern — not matched by regex |
| `%` token, normalization off | `candidate_values` returns only raw value |
| Empty allowlist | `is_grounded` returns `False` |
| All findings fields are `None` | `build_evidence_allowlist` returns empty set |
| Token is `"$"` only | `normalize_number` returns `None` |

---

## What NOT to Do

- Do not hardcode tolerance values (`0.01`, `0.001`) anywhere in logic — always read from `cfg`
- Do not build grounding score calculation here — that belongs in I7-2 (`scorer.py`)
- Do not modify `src/wbsb/eval/models.py` — it was frozen in I7-0
- Do not modify `config/rules.yaml` — the `eval:` section already exists from I7-0
- Do not use `except: pass` or any silent error swallowing
- Do not import from `wbsb.feedback` — these packages are independent
- Do not refactor code outside the allowed files

---

## Handoff: What the Next Task Needs From This One

After this task merges, the following will be available for I7-2 (grounding scorer):

```python
from wbsb.eval.extractor import (
    extract_numbers_from_text,
    normalize_number,
    candidate_values,
    build_evidence_allowlist,
    is_grounded,
)

# Contracts:
# extract_numbers_from_text(text: str) -> list[str]
#   — returns raw token strings; dates excluded
# normalize_number(raw: str) -> float | None
#   — strips %, comma, $; returns None if unparseable
# candidate_values(raw: str, pct_normalization: bool) -> list[float]
#   — returns 0–2 candidate floats per token
# build_evidence_allowlist(findings: Findings) -> set[float]
#   — all non-None numeric fields from metrics + signals
# is_grounded(candidate: float, allowlist: set[float], cfg: dict) -> bool
#   — cfg must contain grounding_tolerance_abs and grounding_tolerance_rel
```

---

## Execution Workflow

Follow this sequence exactly.

### Step 0 — Branch setup and draft PR (before anything else)

```bash
git checkout feature/iteration-7
git pull origin feature/iteration-7
git status
# Expected: nothing to commit, working tree clean

git checkout -b feature/i7-1-numeric-extractor
git branch --show-current
# Expected: feature/i7-1-numeric-extractor

git push -u origin feature/i7-1-numeric-extractor

gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-1-numeric-extractor \
  --title "I7-1: Numeric extraction utility" \
  --body "Work in progress. See docs/iterations/i7/prompts/prompt-task-1.md for full spec." \
  --draft
```

### Step 1 — Verify baseline

```bash
pytest
# Expected: 271 passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

### Step 2 — Read before writing

Read all files listed in "Files to Read Before Starting" in order.

### Step 3 — Implement

Create `src/wbsb/eval/extractor.py` and `tests/test_eval_extractor.py`.

### Step 4 — Test and lint

```bash
pytest
# Expected: 284 passing (271 + 13 new)

ruff check .
# Expected: clean
```

### Step 5 — Verify scope

```bash
git diff --name-only feature/iteration-7
```

Expected (exactly these two files, no others):
```
src/wbsb/eval/extractor.py
tests/test_eval_extractor.py
```

### Step 6 — Commit and push

```bash
git add src/wbsb/eval/extractor.py tests/test_eval_extractor.py

git commit -m "$(cat <<'EOF'
feat: add numeric extraction utility for grounding scorer (I7-1)

Creates src/wbsb/eval/extractor.py with five pure functions:
extract_numbers_from_text, normalize_number, candidate_values,
build_evidence_allowlist, and is_grounded. All tolerance values read
from config/rules.yaml eval: section — no hardcoded literals.
Date tokens excluded from extraction. Percent normalization configurable.
Tolerance boundary splits at abs(allowlist_value) < 1.0.
13 unit tests in tests/test_eval_extractor.py.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-1-numeric-extractor
```

### Step 7 — Mark PR ready

```bash
gh pr ready feature/i7-1-numeric-extractor
```

---

## Definition of Done

This task is complete when ALL of the following are true:

- [ ] All five functions implemented with correct signatures in `extractor.py`
- [ ] Date tokens excluded from extraction
- [ ] `candidate_values` returns correct candidates for `%` tokens with normalization on/off
- [ ] `build_evidence_allowlist` collects all non-None numeric fields from metrics and signals
- [ ] `is_grounded` uses abs tolerance for small values, rel tolerance for large values
- [ ] No hardcoded tolerance values — confirmed by `grep -n "0\.01\|0\.001" src/wbsb/eval/extractor.py` returning nothing
- [ ] All 271 prior tests still pass (`pytest` exit code 0)
- [ ] All 13 new tests pass
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only `extractor.py` and `test_eval_extractor.py` in scope diff
- [ ] Draft PR opened, marked ready for review
- [ ] No `except: pass`, no hardcoded thresholds, no silent failures
