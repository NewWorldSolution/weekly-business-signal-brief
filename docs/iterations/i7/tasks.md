# Iteration 7 — Evaluation Framework & Operator Feedback Loop
## Detailed Task Plan

**Status:** Planning complete. Ready to start.
**Baseline:** 271 tests passing, ruff clean, main stable.

---

## Purpose

Iteration 7 adds a quality control layer around LLM output and a lightweight operator feedback loop.

It does **not** change report generation logic. It only evaluates and observes output quality.

Two systems are introduced:
1. **Automated evaluation scoring** — every LLM output is scored for grounding, signal coverage, and hallucination risk
2. **Operator feedback storage** — operators can label report sections; feedback is stored and queryable via CLI

Feedback delivery via Teams/Slack action buttons is **out of scope for I7**. That wire-up belongs to I9. I7 builds the data model and storage layer only.

---

## Scope Boundaries

| In scope (I7) | Out of scope — moves to I9 |
|---|---|
| Scoring engine (grounding, coverage, hallucination) | Webhook server / HTTP endpoint |
| Eval scores written to `llm_response.json` | Teams / Slack button integration |
| Feedback data model + file storage | Authentication / rate limiting |
| `wbsb eval` CLI command | Automated feedback ingestion from external systems |
| `wbsb feedback list/summary/export` CLI | |

---

## Branching Strategy

```
main
 └── feature/iteration-7              ← iteration integration branch
      ├── feature/i7-0-pre-work
      ├── feature/i7-1-numeric-extractor
      ├── feature/i7-2-grounding-scorer
      ├── feature/i7-3-coverage-scorer
      ├── feature/i7-4-hallucination-scorer
      ├── feature/i7-5-pipeline-integration
      ├── feature/i7-6-golden-runner
      └── feature/i7-7-feedback-system
```

**Rules (same as all iterations):**
- Every task branch is created from `feature/iteration-7` — never from `main`
- Every task PR targets `feature/iteration-7` — never `main`
- `main` stays stable throughout the entire iteration
- `feature/iteration-7` → `main` via one final PR after I7-8 architecture review passes

---

## Execution Order

```
I7-0  [Claude]   Pre-work: domain models, schemas, eval config    → no dependencies
I7-1  [Codex]    Numeric extraction utility                       → depends on I7-0
I7-2  [Codex]    Grounding scorer                                 → depends on I7-1
I7-3  [Codex]    Signal coverage scorer                           → depends on I7-0
I7-4  [Codex]    Hallucination detector                           → depends on I7-0
I7-5  [Claude]   build_eval_scores() + pipeline integration       → depends on I7-2, I7-3, I7-4
I7-6  [Claude]   Golden dataset runner + wbsb eval CLI            → depends on I7-5
I7-7  [Claude]   Feedback storage + CLI commands                  → depends on I7-0
I7-8  [You]      Architecture review                              → depends on I7-7
I7-9  [Claude]   Final cleanup + merge to main                    → depends on I7-8
```

**I7-1 through I7-4 are pure library code with no pipeline edits. I7-5 is the only task that touches the pipeline. This sequencing keeps pipeline risk low and scorer tests stable before wiring.**

---

## Per-Task Workflow

```bash
# 1. Start from the iteration branch
git checkout feature/iteration-7
git pull origin feature/iteration-7

# 2. Create and push the task branch
git checkout -b feature/i7-N-description
git push -u origin feature/i7-N-description

# 3. Open a DRAFT PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-N-description \
  --title "I7-N: Task title" \
  --body "Work in progress." \
  --draft

# 4. Verify baseline before touching anything
pytest && ruff check .

# 5. Implement, then verify
pytest && ruff check .
git diff --name-only feature/iteration-7    # only allowed files

# 6. Push and mark ready
git push origin feature/i7-N-description
gh pr ready
```

---

## Task Summary

| Task | Owner | Description | Depends on |
|------|-------|-------------|------------|
| I7-0 | Claude | Domain models, JSON schemas, eval config section | — |
| I7-1 | Codex | Numeric extraction utility with tolerance rules | I7-0 |
| I7-2 | Codex | Grounding scorer | I7-1 |
| I7-3 | Codex | Signal coverage scorer | I7-0 |
| I7-4 | Codex | Hallucination detector | I7-0 |
| I7-5 | Claude | build_eval_scores() integrator + pipeline wiring | I7-2, I7-3, I7-4 |
| I7-6 | Claude | Golden dataset runner + `wbsb eval` CLI | I7-5 |
| I7-7 | Claude | Feedback storage + `wbsb feedback` CLI | I7-0 |
| I7-8 | You | Architecture review | I7-7 |
| I7-9 | Claude | Final cleanup + merge to main | I7-8 |

---

---

## Schemas (Frozen — Defined in I7-0)

All schemas are defined once in I7-0 and must not drift across tasks.

### eval_scores — appended to llm_response.json

```json
{
  "schema_version": "1.0",
  "grounding": 0.92,
  "grounding_reason": null,
  "flagged_numbers": ["534.3"],
  "signal_coverage": 1.0,
  "group_coverage": 1.0,
  "hallucination_risk": 0,
  "hallucination_violations": [
    {"type": "invalid_watch_signal_id", "severity": "major", "detail": "metric_id 'foo' not in payload"}
  ],
  "model": "claude-haiku-4-5-20251001",
  "evaluated_at": "2026-03-11T12:00:00Z"
}
```

**Field rules:**
- `grounding`: `float [0.0, 1.0]` or `null` — null only when `grounding_reason` is set
- `grounding_reason`: `null` | `"no_numbers_cited"` — null when grounding is computable
- `flagged_numbers`: list of string representations of numbers cited by LLM but outside allowlist
- `signal_coverage`: `float [0.0, 1.0]` — signals with narrative / total signals (WARN + INFO)
- `group_coverage`: `float [0.0, 1.0]` — categories with group narrative / categories in payload
- `hallucination_risk`: `int` — total violation count across all severities
- `hallucination_violations`: list of `{type: str, severity: str, detail: str}`
- `model`: model ID string from `llm_result.model`
- `evaluated_at`: ISO 8601 datetime string

**When LLM fallback (no llm_result):**
```json
{
  "eval_scores": null,
  "eval_skipped_reason": "llm_fallback"
}
```

**When scorer itself errors:**
```json
{
  "eval_scores": null,
  "eval_skipped_reason": "scorer_error",
  "eval_error": "short error message"
}
```

---

### feedback_entry — stored as JSON files in feedback/

```json
{
  "schema_version": "1.0",
  "feedback_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "20260311T132430Z_3485e2",
  "section": "situation",
  "label": "unexpected",
  "comment": "The situation understated the financial risk.",
  "operator": "anonymous",
  "submitted_at": "2026-03-11T13:00:00Z"
}
```

**Field rules:**
- `feedback_id`: UUID4 string, generated at submission time
- `run_id`: must match regex `^\d{8}T\d{6}Z_[a-f0-9]{6}$`
- `section`: one of `situation | key_story | group_narratives | watch_signals`
- `label`: one of `expected | unexpected | incorrect`
- `comment`: string, max 1000 characters, may be empty string `""`
- `operator`: `"anonymous"` for MVP — field reserved for future auth
- `submitted_at`: ISO 8601 datetime string

---

### Numeric tolerance rules (used by grounding scorer)

These are defined in `config/rules.yaml` under `eval:` (added in I7-0).

```yaml
eval:
  grounding_tolerance_abs: 0.01       # absolute tolerance for values where |value| < 1.0
  grounding_tolerance_rel: 0.01       # relative tolerance (1%) for |value| >= 1.0
  grounding_pct_normalization: true   # if true, "40%" is tested against 0.40 and 40.0
```

**Matching algorithm:**
1. Extract candidate string (e.g. `"40%"`, `"1,503"`, `"0.92"`)
2. Normalize: strip `%`, `,`, `$`; parse as float
3. If `grounding_pct_normalization=true` and string ended with `%`: add `raw / 100` to candidate set
4. For each value in evidence allowlist, check: `|candidate - allowlist_value| <= tolerance`
   - Use `grounding_tolerance_abs` when `|allowlist_value| < 1.0`
   - Use `grounding_tolerance_rel * |allowlist_value|` otherwise
5. A candidate is "grounded" if it matches at least one allowlist value

**Allowlist sources (from findings):**
- `MetricResult.current_value` for each metric
- `MetricResult.previous_value` for each metric
- `MetricResult.delta_abs` for each metric
- `MetricResult.delta_pct` for each metric
- `Signal.threshold` for each signal
- `Signal.current_value`, `Signal.previous_value`, `Signal.delta_abs`, `Signal.delta_pct` for each signal

---

### Hallucination violation types

| type | severity | condition |
|------|----------|-----------|
| `key_story_when_no_cluster` | critical | `key_story` is non-null when `dominant_cluster_exists=False` |
| `invalid_watch_signal_id` | major | `watch_signals[].metric_or_signal` not in `rule_ids ∪ metric_ids` |
| `invalid_group_narrative_category` | major | `group_narratives` key (normalized) not in payload categories |
| `missing_signal_narrative` | minor | rule_id in payload has no entry in `signal_narratives` |
| `extra_signal_narrative` | minor | `signal_narratives` contains rule_id not in payload |

`hallucination_risk` = count of all violations regardless of severity.
`hallucination_violations` = full list with type, severity, detail string.

---

---

## I7-0 — Pre-Work: Domain Models, Schemas, Eval Config

**Owner:** Claude
**Branch:** `feature/i7-0-pre-work`
**Depends on:** nothing — starts immediately

### Why First
All downstream tasks (I7-1 through I7-7) import from models defined here or read from eval config. No task should guess at types or schema. This task freezes contracts before any implementation begins.

### What to Build

#### New packages

```
src/wbsb/eval/__init__.py          ← empty package marker
src/wbsb/eval/models.py            ← EvalScores, HallucinationViolation Pydantic models
src/wbsb/feedback/__init__.py      ← empty package marker
src/wbsb/feedback/models.py        ← FeedbackEntry Pydantic model
```

#### `src/wbsb/eval/models.py`

```python
from __future__ import annotations
from pydantic import BaseModel

class HallucinationViolation(BaseModel):
    type: str
    severity: str       # "critical" | "major" | "minor"
    detail: str

class EvalScores(BaseModel):
    schema_version: str = "1.0"
    grounding: float | None          # null when grounding_reason is set
    grounding_reason: str | None     # null | "no_numbers_cited"
    flagged_numbers: list[str]
    signal_coverage: float
    group_coverage: float
    hallucination_risk: int
    hallucination_violations: list[HallucinationViolation]
    model: str
    evaluated_at: str                # ISO 8601
```

#### `src/wbsb/feedback/models.py`

```python
from __future__ import annotations
from pydantic import BaseModel

VALID_SECTIONS = {"situation", "key_story", "group_narratives", "watch_signals"}
VALID_LABELS = {"expected", "unexpected", "incorrect"}

class FeedbackEntry(BaseModel):
    schema_version: str = "1.0"
    feedback_id: str
    run_id: str
    section: str
    label: str
    comment: str
    operator: str = "anonymous"
    submitted_at: str
```

#### `config/rules.yaml`

Add the following block after the `history:` section and before `rules:`:

```yaml
eval:
  grounding_tolerance_abs: 0.01
  grounding_tolerance_rel: 0.01
  grounding_pct_normalization: true
```

### Acceptance Criteria
- `EvalScores` and `FeedbackEntry` instantiate without error with valid data
- `config/rules.yaml` loads without error; the three `eval:` keys are present with correct types
- No existing config keys modified
- Ruff clean

### Allowed Files
```
src/wbsb/eval/__init__.py          ← create (empty)
src/wbsb/eval/models.py            ← create
src/wbsb/feedback/__init__.py      ← create (empty)
src/wbsb/feedback/models.py        ← create
config/rules.yaml                  ← add eval: section only
```

### Files Not to Touch
```
src/wbsb/domain/models.py          ← never modified by eval tasks
src/wbsb/pipeline.py               ← touched only in I7-5
src/wbsb/render/llm_adapter.py     ← touched only in I7-5
Any test file                      ← no tests required for this task
```

---

---

## I7-1 — Numeric Extraction Utility

**Owner:** Codex
**Branch:** `feature/i7-1-numeric-extractor`
**Depends on:** I7-0 merged

### Why Codex
Bounded utility function with clear inputs and outputs. The tolerance rules are fully specified in I7-0 config and schemas. No architectural judgment required.

### What to Build

#### `src/wbsb/eval/extractor.py`

```python
def extract_numbers_from_text(text: str) -> list[str]:
    """Extract all numeric tokens from text. Returns raw string representations."""

def normalize_number(raw: str) -> float | None:
    """Parse a raw token to float. Returns None if unparseable."""

def build_evidence_allowlist(findings: Findings) -> set[float]:
    """Build set of all numeric evidence values from findings (metrics + signals)."""

def is_grounded(candidate: float, allowlist: set[float], cfg: dict) -> bool:
    """Check whether a candidate number is within tolerance of any allowlist value."""
```

**Extraction rules:**
- Match tokens with regex: `-?\d[\d,]*(?:\.\d+)?%?` (handles integers, decimals, percentages, negatives, comma-separated thousands)
- Do not match tokens that are part of dates (e.g. `2024-03-18`), run IDs, or version strings
- Return list of raw string matches (e.g. `["40%", "1,503", "0.92"]`)

**Normalization rules:**
- Strip `%`, `,`, `$` before parsing
- If string ended with `%` and `grounding_pct_normalization=True`: add both `raw_float` and `raw_float / 100` to candidate set
- Return `None` if the stripped string cannot be parsed to float

**Allowlist construction:**
- For every `MetricResult` in `findings.metrics`: add `current_value`, `previous_value`, `delta_abs`, `delta_pct` if not None
- For every `Signal` in `findings.signals`: add `current_value`, `previous_value`, `delta_abs`, `delta_pct`, `threshold` if not None
- All values added as floats

**Tolerance check:**
- Read `grounding_tolerance_abs` and `grounding_tolerance_rel` from `cfg` (eval section of rules.yaml)
- For `|allowlist_value| < 1.0`: use absolute tolerance
- For `|allowlist_value| >= 1.0`: use relative tolerance (`tolerance_rel * |allowlist_value|`)
- Return `True` if `|candidate - allowlist_value| <= tolerance` for any value in allowlist

### Tests Required (`tests/test_eval_extractor.py`)
- `test_extract_numbers_basic` — simple sentence with integers and decimals
- `test_extract_numbers_with_percentages` — tokens ending in `%`
- `test_extract_numbers_negative` — negative numbers
- `test_extract_numbers_comma_separated` — `"1,503"` → `1503.0`
- `test_extract_numbers_skips_dates` — `"2024-03-18"` not extracted
- `test_normalize_number_percent` — `"40%"` → `(40.0, 0.40)` when normalization on
- `test_normalize_number_invalid` — non-numeric token returns `None`
- `test_build_evidence_allowlist` — returns expected set from findings fixture
- `test_is_grounded_within_abs_tolerance` — value within ±0.01 matches
- `test_is_grounded_within_rel_tolerance` — large value within 1% matches
- `test_is_grounded_false` — value far from allowlist returns False

### Allowed Files
```
src/wbsb/eval/extractor.py         ← create
tests/test_eval_extractor.py       ← create
```

### Files Not to Touch
```
src/wbsb/eval/scorer.py            ← created in I7-2
src/wbsb/eval/models.py            ← frozen after I7-0
src/wbsb/pipeline.py
src/wbsb/render/llm_adapter.py
```

---

---

## I7-2 — Grounding Scorer

**Owner:** Codex
**Branch:** `feature/i7-2-grounding-scorer`
**Depends on:** I7-1 merged

### Why Codex
The algorithm is fully specified and uses only utilities built in I7-1. No pipeline changes.

### What to Build

#### `src/wbsb/eval/scorer.py` (create)

```python
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

**Algorithm:**
1. Collect text from all LLM sections: `situation`, `key_story`, all values in `group_narratives`, all values in `signal_narratives`, all `observation` values in `watch_signals`
2. Call `extract_numbers_from_text()` on the concatenated text — collect all raw tokens
3. If total tokens == 0: return `{"grounding": None, "grounding_reason": "no_numbers_cited", "flagged_numbers": []}`
4. For each token: normalize → candidate float(s). Call `is_grounded()` against `build_evidence_allowlist(findings)`
5. `flagged_numbers` = raw string tokens where no candidate was grounded
6. `grounding` = `(total_tokens - len(flagged_numbers)) / total_tokens`

### Tests Required (add to `tests/test_eval_scorer.py`, create file)
- `test_grounding_no_numbers_cited` — all text is prose, no numbers → grounding=None
- `test_grounding_all_grounded` — all cited numbers within allowlist → grounding=1.0
- `test_grounding_one_flagged` — one number outside allowlist → grounding < 1.0, flagged_numbers has 1 entry
- `test_grounding_pct_normalization` — "40%" grounded against 0.40 in allowlist
- `test_grounding_empty_llm_result` — handles None / empty fields without error

### Allowed Files
```
src/wbsb/eval/scorer.py            ← create (grounding function only)
tests/test_eval_scorer.py          ← create
```

---

---

## I7-3 — Signal Coverage Scorer

**Owner:** Codex
**Branch:** `feature/i7-3-coverage-scorer`
**Depends on:** I7-0 merged (can run parallel to I7-1 and I7-2)

### What to Build

Add to `src/wbsb/eval/scorer.py`:

```python
def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Returns:
        {
            "signal_coverage": float,
            "group_coverage": float,
        }
    """
```

**Signal coverage:**
- `total_signals` = `len(findings.signals)` — includes WARN and INFO
- `signals_with_narrative` = count of `signal.rule_id` values that appear as keys in `llm_result.signal_narratives`
- `signal_coverage = signals_with_narrative / total_signals` — `1.0` if `total_signals == 0`

**Group coverage:**
- `payload_categories` = set of normalized category keys from signals (`signal.category.lower().replace(" ", "_")`)
- `covered_categories` = count of payload categories that appear as keys in `llm_result.group_narratives`
- `group_coverage = covered_categories / len(payload_categories)` — `1.0` if no categories

### Tests Required (add to `tests/test_eval_scorer.py`)
- `test_coverage_all_signals_covered` → signal_coverage=1.0
- `test_coverage_partial_signals` → correct ratio
- `test_coverage_no_signals` → signal_coverage=1.0
- `test_group_coverage_all_categories` → group_coverage=1.0
- `test_group_coverage_partial` → correct ratio
- `test_group_coverage_no_categories` → group_coverage=1.0

### Allowed Files
```
src/wbsb/eval/scorer.py            ← extend (add coverage function)
tests/test_eval_scorer.py          ← extend
```

---

---

## I7-4 — Hallucination Detector

**Owner:** Codex
**Branch:** `feature/i7-4-hallucination-scorer`
**Depends on:** I7-0 merged (can run parallel to I7-1, I7-2, I7-3)

### What to Build

Add to `src/wbsb/eval/scorer.py`:

```python
def score_hallucination(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Returns:
        {
            "hallucination_risk": int,
            "hallucination_violations": list[dict],
        }
    """
```

**Violation checks (in order):**

```
1. key_story_when_no_cluster (critical)
   Condition: llm_result.key_story is not None
              AND findings.dominant_cluster_exists is False

2. invalid_watch_signal_id (major)
   For each entry in llm_result.watch_signals:
   Condition: entry.metric_or_signal not in (payload_rule_ids ∪ payload_metric_ids)
   detail: "metric_or_signal '{value}' not in payload"

3. invalid_group_narrative_category (major)
   For each key in llm_result.group_narratives:
   Condition: normalize(key) not in payload_category_keys
   detail: "group_narratives key '{key}' not in payload categories"

4. extra_signal_narrative (minor)
   For each key in llm_result.signal_narratives:
   Condition: key not in payload_rule_ids
   detail: "signal_narratives key '{rule_id}' not in payload"

5. missing_signal_narrative (minor)
   For each rule_id in payload_rule_ids:
   Condition: rule_id not in llm_result.signal_narratives
   detail: "signal '{rule_id}' has no narrative"
```

`hallucination_risk` = total violation count. `hallucination_violations` = full list.

### Tests Required (add to `tests/test_eval_scorer.py`)
- `test_hallucination_clean_output` → risk=0, violations=[]
- `test_hallucination_key_story_no_cluster` → critical violation detected
- `test_hallucination_invalid_watch_signal` → major violation detected
- `test_hallucination_invalid_group_category` → major violation detected
- `test_hallucination_extra_signal_narrative` → minor violation detected
- `test_hallucination_missing_signal_narrative` → minor violation detected
- `test_hallucination_multiple_violations` → correct total count

### Allowed Files
```
src/wbsb/eval/scorer.py            ← extend (add hallucination function)
tests/test_eval_scorer.py          ← extend
```

---

---

## I7-5 — build_eval_scores() + Pipeline Integration

**Owner:** Claude
**Branch:** `feature/i7-5-pipeline-integration`
**Depends on:** I7-2, I7-3, I7-4 all merged

### Why Claude
First task that touches existing pipeline code. Requires architectural judgment about the non-breaking path, logging, and the fallback schema.

### What to Build

#### `src/wbsb/eval/scorer.py` — add integrator

```python
def build_eval_scores(
    findings: Findings,
    llm_result: LLMResult,
    cfg: dict,
) -> EvalScores:
    """
    Combine grounding, coverage, and hallucination into a single EvalScores object.
    cfg = raw eval section from rules.yaml.
    """
```

Calls `score_grounding()`, `score_signal_coverage()`, `score_hallucination()` and assembles an `EvalScores` instance. Sets `model` from `llm_result.model`, `evaluated_at` to current UTC ISO datetime.

#### `src/wbsb/render/llm_adapter.py` — wire scorer after validate_response()

After the existing `validate_response()` call succeeds, add:

```python
try:
    eval_scores = build_eval_scores(findings, llm_result, eval_cfg)
except Exception as exc:
    log.error("eval.scorer.error", error=str(exc))
    eval_scores = None
    eval_skipped_reason = "scorer_error"
    eval_error = str(exc)
else:
    eval_skipped_reason = None
    eval_error = None
```

The `eval_scores` result (or null + reason) must be included in the data written to `llm_response.json`.

**Non-breaking rule:** if `build_eval_scores` raises for any reason, the report generation continues. The pipeline never returns exit code 1 due to a scorer failure.

**When LLM fallback (llm_result is None):**
- Do not call scorer
- Write `eval_scores: null`, `eval_skipped_reason: "llm_fallback"` to artifact

### Tests Required
- Add to `tests/test_eval_scorer.py`: `test_build_eval_scores_returns_eval_scores_model`
- Add to `tests/test_llm_adapter.py`:
  - `test_eval_scores_written_to_artifact_on_success`
  - `test_eval_scores_null_on_scorer_error` — monkeypatch `build_eval_scores` to raise; verify pipeline continues
  - `test_eval_scores_null_on_llm_fallback`

### Allowed Files
```
src/wbsb/eval/scorer.py            ← extend (add build_eval_scores)
src/wbsb/render/llm_adapter.py     ← extend (wire scorer after validate_response)
tests/test_eval_scorer.py          ← extend
tests/test_llm_adapter.py          ← extend
```

### Files Not to Touch
```
src/wbsb/pipeline.py               ← scorer is wired in llm_adapter, not pipeline
src/wbsb/domain/models.py
src/wbsb/eval/extractor.py
```

---

---

## I7-6 — Golden Dataset Runner + wbsb eval CLI

**Owner:** Claude
**Branch:** `feature/i7-6-golden-runner`
**Depends on:** I7-5 merged

### What to Build

#### Directory structure

```
src/wbsb/eval/golden/
├── README.md                  ← governance rules (see below)
├── clean_week/
│   ├── findings.json
│   ├── llm_response.json
│   └── criteria.json
├── single_dominant_cluster/
│   └── ...
├── independent_signals/
│   └── ...
├── low_volume_guardrail/
│   └── ...
├── zero_signals/
│   └── ...
└── fallback_no_llm/
    ├── findings.json
    └── criteria.json          ← no llm_response.json; eval_skipped_reason=llm_fallback
```

#### `criteria.json` schema

```json
{
  "schema_version": "1.0",
  "description": "human-readable description of this case",
  "expect_eval_scores": true,
  "min_grounding": 0.80,
  "min_signal_coverage": 1.0,
  "max_hallucination_risk": 0,
  "expected_skipped_reason": null
}
```

For `fallback_no_llm`: `expect_eval_scores: false`, `expected_skipped_reason: "llm_fallback"`.

#### Golden dataset governance (in README.md)

- Golden cases are created from real production runs after I9 deployment
- A new case requires: findings.json + llm_response.json from a real run + manually reviewed criteria.json
- Criteria values must be set conservatively (do not set `min_grounding: 1.0` unless you have verified every number)
- Case updates require re-review — open a PR, do not edit in place without review
- The `fallback_no_llm` case must always be present and must always pass

#### `src/wbsb/eval/runner.py`

```python
def load_case(name: str) -> dict:
    """Load findings.json, llm_response.json (if present), and criteria.json for a named case."""

def run_case(case: dict) -> dict:
    """Evaluate a single case against its criteria. Returns {name, passed, failures, scores}."""

def run_all_cases() -> list[dict]:
    """Run all cases in eval/golden/. Returns list of per-case results."""
```

#### `src/wbsb/cli.py` — new command

```
wbsb eval
```

- Calls `run_all_cases()`
- Prints per-case PASS / FAIL with failure reasons
- Exits with code 0 if all pass, 1 if any fail
- Accepts optional `--case NAME` to run a single case

### Tests Required (`tests/test_eval_runner.py`)
- `test_load_case_valid` — loads a valid case directory
- `test_load_case_missing_findings` — raises with clear message
- `test_run_case_passes` — case that meets all criteria returns passed=True
- `test_run_case_fails_grounding` — case below min_grounding returns passed=False
- `test_run_case_fallback_no_llm` — fallback case with no llm_response.json passes correctly
- `test_run_all_cases_returns_list` — returns list of results

### Allowed Files
```
src/wbsb/eval/runner.py            ← create
src/wbsb/eval/golden/              ← create directory + initial cases
src/wbsb/cli.py                    ← extend (add wbsb eval command)
tests/test_eval_runner.py          ← create
```

---

---

## I7-7 — Feedback Storage + wbsb feedback CLI

**Owner:** Claude
**Branch:** `feature/i7-7-feedback-system`
**Depends on:** I7-0 merged (can run parallel to I7-1 through I7-6)

### Scope reminder
Storage + CLI only. No HTTP server. No Teams/Slack integration. Those belong to I9.

### What to Build

#### Storage directory

```
feedback/         ← gitignored, one JSON file per entry
.gitkeep          ← tracks the directory in git
```

Add to `.gitignore`:
```
feedback/*
!feedback/.gitkeep
```

#### `src/wbsb/feedback/store.py`

```python
FEEDBACK_DIR = Path("feedback")

def save_feedback(entry: FeedbackEntry) -> Path:
    """Write entry as JSON to feedback/{feedback_id}.json. Returns path written."""

def list_feedback(limit: int = 50) -> list[FeedbackEntry]:
    """Load and return entries sorted by submitted_at descending."""

def summarize_feedback() -> dict:
    """
    Returns:
        {
            "total": int,
            "by_label": {"expected": int, "unexpected": int, "incorrect": int},
            "by_section": {"situation": int, ...},
        }
    """

def export_feedback(run_id: str) -> list[FeedbackEntry]:
    """Return all entries for a specific run_id."""
```

**Validation in `save_feedback`:**
- Validate `run_id` against regex `^\d{8}T\d{6}Z_[a-f0-9]{6}$` — raise `ValueError` on mismatch
- Validate `section` is in `VALID_SECTIONS` — raise `ValueError` on mismatch
- Validate `label` is in `VALID_LABELS` — raise `ValueError` on mismatch
- Truncate `comment` to 1000 characters silently (do not raise)
- Generate `feedback_id` as `uuid.uuid4().hex` if not provided

#### `src/wbsb/cli.py` — new commands

```
wbsb feedback list [--limit N]
wbsb feedback summary
wbsb feedback export --run-id RUN_ID
```

### Tests Required (`tests/test_feedback.py`)
- `test_save_feedback_valid` — entry written to correct path
- `test_save_feedback_invalid_run_id` — ValueError raised
- `test_save_feedback_invalid_section` — ValueError raised
- `test_save_feedback_invalid_label` — ValueError raised
- `test_save_feedback_comment_truncated` — comment > 1000 chars silently truncated
- `test_list_feedback_sorted` — entries returned newest first
- `test_summarize_feedback_counts` — correct counts per label and section
- `test_export_feedback_by_run_id` — returns only matching entries

### Allowed Files
```
src/wbsb/feedback/store.py         ← create
src/wbsb/cli.py                    ← extend (add wbsb feedback commands)
.gitignore                         ← add feedback/* + !feedback/.gitkeep
tests/test_feedback.py             ← create
```

### Files Not to Touch
```
src/wbsb/feedback/models.py        ← frozen after I7-0
src/wbsb/pipeline.py
src/wbsb/render/llm_adapter.py
```

---

---

## I7-8 — Architecture Review

**Owner:** You
**Depends on:** I7-7 merged

### What to Check

**Scorer isolation:**
```bash
grep -rn "build_eval_scores\|score_grounding\|score_hallucination" src/wbsb/pipeline.py
```
Expected: no matches. Scoring must be wired only through `llm_adapter.py`.

**Non-breaking path:**
```bash
grep -n "scorer_error\|eval_skipped" src/wbsb/render/llm_adapter.py
```
Expected: both strings present — confirms fallback is implemented.

**Domain model unchanged:**
```bash
grep -n "EvalScores\|FeedbackEntry" src/wbsb/domain/models.py
```
Expected: no matches. Eval types live in `src/wbsb/eval/models.py`.

**No hardcoded tolerances:**
```bash
grep -n "0\.01\|0\.001\|tolerance" src/wbsb/eval/scorer.py
```
Expected: no literal tolerance values — all read from `cfg` dict passed in from rules.yaml.

**Feedback validation enforced:**
```bash
grep -n "VALID_SECTIONS\|VALID_LABELS\|run_id.*regex" src/wbsb/feedback/store.py
```
Expected: all three validation guards present.

**Eval scores in artifact:**
Run a pipeline end-to-end with `--llm-mode full` and open the resulting `llm_response.json`:
```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full
cat runs/<latest>/*/llm_response.json | python3 -m json.tool | grep -A 20 '"eval_scores"'
```
Expected: `eval_scores` object present with all fields.

**wbsb eval runs:**
```bash
wbsb eval
```
Expected: all golden cases PASS, exit code 0.

**All tests pass:**
```bash
pytest --tb=short -q
ruff check .
```

### Review Checklist
- [ ] Scorer wired only in `llm_adapter.py`, not in `pipeline.py`
- [ ] Non-breaking path confirmed: scorer error produces `eval_skipped_reason`, not pipeline failure
- [ ] `domain/models.py` unchanged
- [ ] No hardcoded tolerance values in scorer code
- [ ] Feedback validation enforced for all three fields
- [ ] `eval_scores` present in `llm_response.json` on real run
- [ ] `wbsb eval` runs and all cases pass
- [ ] All 271+ tests passing
- [ ] Ruff clean

---

---

## I7-9 — Final Cleanup + Merge to Main

**Owner:** Claude
**Branch:** `feature/i7-9-final-cleanup`
**Depends on:** I7-8 complete

### What to Do
1. Fix any issues flagged in I7-8 review
2. Create `feedback/.gitkeep` if not already committed
3. Update `docs/project/TASKS.md` — all DoD boxes ticked, I7 status → Complete
4. Update `docs/project/project-iterations.md` — I7 status → Complete
5. Run `pytest` and `ruff check .`, confirm clean
6. Open final PR: `feature/iteration-7` → `main`

### Allowed Files
```
docs/project/TASKS.md
docs/project/project-iterations.md
.gitignore
feedback/.gitkeep
src/wbsb/eval/        ← only if review found bugs
src/wbsb/feedback/    ← only if review found bugs
src/wbsb/render/llm_adapter.py  ← only if review found bugs
tests/                ← only if review found gaps
```

---

---

## Definition of Done — Iteration 7

**Evaluation Engine**
- [ ] `eval_scores` written to `llm_response.json` on every successful LLM run
- [ ] `eval_skipped_reason` set correctly on LLM fallback and scorer error
- [ ] Grounding score computable (or null with reason when no numbers cited)
- [ ] Signal coverage counts both WARN and INFO signals
- [ ] Hallucination violations classified by type and severity
- [ ] No hardcoded tolerance values — all read from `config/rules.yaml`
- [ ] Scorer never breaks report generation

**Golden Dataset**
- [ ] At least 6 cases present in `src/wbsb/eval/golden/`
- [ ] `wbsb eval` runs all cases and exits 0 when all pass
- [ ] `fallback_no_llm` case always present and always passing
- [ ] Governance rules documented in `eval/golden/README.md`

**Feedback System**
- [ ] `save_feedback()` validates run_id, section, label — raises ValueError on violation
- [ ] Comment truncated to 1000 chars silently
- [ ] `wbsb feedback list/summary/export` commands operational
- [ ] `feedback/` directory gitignored, `.gitkeep` committed
- [ ] No webhook server built in I7

**Quality**
- [ ] All 271 baseline tests still passing + new I7 tests added
- [ ] Ruff clean
- [ ] `domain/models.py` unchanged
- [ ] `main` branch stable

---

*Created: 2026-03-11*
*Incorporates review feedback from three rounds: architecture, implementation quality, and final decision pass.*
*Feedback webhook and Teams/Slack wiring deferred to I9.*
