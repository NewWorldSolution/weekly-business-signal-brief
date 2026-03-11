# Task Prompt — I7-4: Hallucination Detector

---

## Context

You are implementing **task I7-4** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-3 (`score_signal_coverage()` in `src/wbsb/eval/scorer.py`) has been
merged into `feature/iteration-7`. You are extending that file.

**Your task:** Add `score_hallucination()` to the existing `src/wbsb/eval/scorer.py`.
This is a pure library function with no pipeline changes.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Deterministic** — no randomness; same inputs must always produce the same output |
| 2 | **Config-driven** — no hardcoded thresholds anywhere |
| 3 | **No silent failure** — never `except: pass`; surface real errors |
| 4 | **Module boundaries** — `wbsb.eval` must not import from `wbsb.feedback` |
| 5 | **Domain model is frozen** — never modify `src/wbsb/domain/models.py` |
| 6 | **Allowed files only** — touch only the two files listed below |
| 7 | **Draft PR first** — open a draft PR before writing any code |
| 8 | **Test before commit** — `pytest` and `ruff check .` must both pass before every push |

---

## Pre-Check — Verify `Findings.metrics` field type

Before writing any code, verify how `findings.metrics` is typed in `src/wbsb/domain/models.py`:

```bash
grep -n "metrics" src/wbsb/domain/models.py
```

This task uses `findings.metrics.keys()` to build `payload_metric_ids`. That call is only valid
if `metrics` is a `dict`. If it is a `list[MetricResult]`, replace `.keys()` with a set
comprehension over the appropriate attribute (e.g. `{m.metric_id for m in findings.metrics}`).
Do not proceed until you have confirmed the correct access pattern.

---

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch — AFTER I7-3 is merged
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-4-hallucination-scorer
git push -u origin feature/i7-4-hallucination-scorer

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-4-hallucination-scorer \
  --title "I7-4: Hallucination detector" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 295 tests passing (289 after I7-2 + 6 from I7-3), ruff clean
```

---

## What to Build

### Allowed files (exactly these two, no others)

```
src/wbsb/eval/scorer.py          ← extend (add hallucination function)
tests/test_eval_scorer.py        ← extend (add 7 new tests)
```

### Add to `src/wbsb/eval/scorer.py`

Append this function to the existing file. Do not modify `score_grounding()` or
`score_signal_coverage()`.

```python
def score_hallucination(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Detect structural hallucinations in LLM output by comparing it to findings.

    Args:
        findings:   Pydantic Findings object from the pipeline.
        llm_result: Pydantic LLMResult object from the LLM adapter.

    Returns:
        {
            "hallucination_risk": int,                  # total violation count
            "hallucination_violations": list[dict],     # each: {type, severity, detail}
        }
    """
```

### Algorithm

Build these sets first — they are reused across checks:

```python
payload_rule_ids = {signal.rule_id for signal in findings.signals}
payload_metric_ids = set(findings.metrics.keys())
payload_valid_ids = payload_rule_ids | payload_metric_ids

payload_category_keys = {
    signal.category.lower().replace(" ", "_")
    for signal in findings.signals
}
```

Run the five violation checks **in this order**:

---

#### Check 1 — `key_story_when_no_cluster` (severity: `critical`)

```python
if llm_result.key_story is not None and findings.dominant_cluster_exists is False:
    violations.append({
        "type": "key_story_when_no_cluster",
        "severity": "critical",
        "detail": "key_story is present but dominant_cluster_exists is False",
    })
```

---

#### Check 2 — `invalid_watch_signal_id` (severity: `major`)

For each entry in `llm_result.watch_signals` (the list may be empty):

```python
for entry in (llm_result.watch_signals or []):
    if entry.metric_or_signal not in payload_valid_ids:
        violations.append({
            "type": "invalid_watch_signal_id",
            "severity": "major",
            "detail": f"metric_or_signal '{entry.metric_or_signal}' not in payload",
        })
```

---

#### Check 3 — `invalid_group_narrative_category` (severity: `major`)

For each key in `llm_result.group_narratives`:

```python
for key in (llm_result.group_narratives or {}):
    normalized = key.lower().replace(" ", "_")
    if normalized not in payload_category_keys:
        violations.append({
            "type": "invalid_group_narrative_category",
            "severity": "major",
            "detail": f"group_narratives key '{key}' not in payload categories",
        })
```

---

#### Check 4 — `extra_signal_narrative` (severity: `minor`)

For each key in `llm_result.signal_narratives` that is NOT in `payload_rule_ids`:

```python
for rule_id in (llm_result.signal_narratives or {}):
    if rule_id not in payload_rule_ids:
        violations.append({
            "type": "extra_signal_narrative",
            "severity": "minor",
            "detail": f"signal_narratives key '{rule_id}' not in payload",
        })
```

---

#### Check 5 — `missing_signal_narrative` (severity: `minor`)

For each rule_id in `payload_rule_ids` that is NOT in `llm_result.signal_narratives`:

```python
for rule_id in sorted(payload_rule_ids):     # sorted for determinism
    if rule_id not in (llm_result.signal_narratives or {}):
        violations.append({
            "type": "missing_signal_narrative",
            "severity": "minor",
            "detail": f"signal '{rule_id}' has no narrative",
        })
```

---

#### Return

```python
return {
    "hallucination_risk": len(violations),
    "hallucination_violations": violations,
}
```

---

## Violation Type Reference

| type | severity | trigger |
|------|----------|---------|
| `key_story_when_no_cluster` | critical | `key_story` not None AND `dominant_cluster_exists=False` |
| `invalid_watch_signal_id` | major | watch entry id not in `rule_ids ∪ metric_ids` |
| `invalid_group_narrative_category` | major | group_narratives key (normalized) not in payload categories |
| `extra_signal_narrative` | minor | signal_narratives has rule_id not in payload |
| `missing_signal_narrative` | minor | payload rule_id has no entry in signal_narratives |

`hallucination_risk` = total count across all severities.

---

## What NOT to Do

- Do not modify `score_grounding()` or `score_signal_coverage()` — they are frozen.
- Do not add `build_eval_scores()` — that is I7-5.
- Do not modify `src/wbsb/eval/extractor.py`, `src/wbsb/eval/models.py`.
- Do not modify `src/wbsb/pipeline.py` or `src/wbsb/render/llm_adapter.py`.
- Do not hardcode severity levels as magic values in logic — use the strings exactly as specified.
- Do not use `except: pass` or any silent failure.
- Do not sort violations by severity — preserve detection order (check 1 first, check 5 last).
  Only `payload_rule_ids` iteration in check 5 is sorted (for determinism).

---

## Tests Required

Add these 7 test functions to the existing `tests/test_eval_scorer.py`.
Do not delete or modify existing tests.

### `cfg` dict

Coverage and hallucination scorers take no `cfg` argument.

### Required tests

#### `test_hallucination_clean_output`

LLM output is fully consistent with findings. No violations expected.

```python
def test_hallucination_clean_output():
    # All signal_narratives keys match payload rule_ids
    # No watch_signals with invalid ids
    # All group_narratives keys match payload categories
    # dominant_cluster_exists=True and key_story is set (or key_story=None)
    # Expected: hallucination_risk=0, hallucination_violations=[]
```

#### `test_hallucination_key_story_no_cluster`

`key_story` is not None but `dominant_cluster_exists` is False.

```python
def test_hallucination_key_story_no_cluster():
    # findings.dominant_cluster_exists = False
    # llm_result.key_story = "Some key story text"
    # Expected: one violation with type="key_story_when_no_cluster", severity="critical"
```

#### `test_hallucination_invalid_watch_signal`

A watch signal entry references an ID that does not exist in rule_ids or metric_ids.

```python
def test_hallucination_invalid_watch_signal():
    # watch_signals has entry with metric_or_signal="nonexistent_id"
    # Expected: one violation with type="invalid_watch_signal_id", severity="major"
    # detail must contain "nonexistent_id"
```

#### `test_hallucination_invalid_group_category`

A `group_narratives` key normalizes to a category not in payload.

```python
def test_hallucination_invalid_group_category():
    # group_narratives = {"Nonexistent Category": "some text"}
    # payload has different categories
    # Expected: one violation with type="invalid_group_narrative_category", severity="major"
```

#### `test_hallucination_extra_signal_narrative`

`signal_narratives` contains a rule_id not in payload.

```python
def test_hallucination_extra_signal_narrative():
    # signal_narratives = {"rule_not_in_findings": "..."}
    # findings.signals has different rule_ids
    # Expected: one violation with type="extra_signal_narrative", severity="minor"
```

#### `test_hallucination_missing_signal_narrative`

A rule_id in payload has no entry in `signal_narratives`.

```python
def test_hallucination_missing_signal_narrative():
    # findings.signals has rule_id "missing_rule"
    # llm_result.signal_narratives does not contain "missing_rule"
    # Expected: one violation with type="missing_signal_narrative", severity="minor"
    # detail must contain "missing_rule"
```

#### `test_hallucination_multiple_violations`

Multiple violation types present simultaneously.

```python
def test_hallucination_multiple_violations():
    # Set up: key_story without cluster + one extra signal narrative
    # Expected: hallucination_risk=2, violations has both types
    # Verify: hallucination_risk == len(hallucination_violations)
```

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 302 passing (295 existing + 7 new), 0 failures

ruff check .
# Expected: no issues

git diff --name-only feature/iteration-7
# Expected exactly:
# src/wbsb/eval/scorer.py
# tests/test_eval_scorer.py
```

---

## Commit and PR

```bash
git add src/wbsb/eval/scorer.py tests/test_eval_scorer.py

git commit -m "$(cat <<'EOF'
feat(eval): add score_hallucination() to scorer.py

Detects five structural violation types in LLM output: key story without
dominant cluster (critical), invalid watch signal id (major), invalid group
narrative category (major), extra signal narrative (minor), missing signal
narrative (minor). Returns total risk count and full violations list.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-4-hallucination-scorer
gh pr ready
```

---

## Handoff to I7-5

When this task is merged into `feature/iteration-7`, Claude will implement I7-5 which:
1. Adds `build_eval_scores()` to `scorer.py` — calls all three scorer functions and assembles `EvalScores`
2. Wires the scorer into `llm_adapter.py` after `validate_response()`

Exports consumed by I7-5 (do not rename or remove):
```python
# src/wbsb/eval/scorer.py
def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict: ...
def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict: ...
def score_hallucination(findings: Findings, llm_result: LLMResult) -> dict: ...
```
