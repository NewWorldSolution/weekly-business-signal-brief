# Task Prompt — I7-3: Signal Coverage Scorer

---

## Context

You are implementing **task I7-3** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-2 (`score_grounding()` in `src/wbsb/eval/scorer.py`) has been merged
into `feature/iteration-7`. You are extending that file.

**Your task:** Add `score_signal_coverage()` to the existing `src/wbsb/eval/scorer.py`.
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

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch — AFTER I7-2 is merged
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-3-coverage-scorer
git push -u origin feature/i7-3-coverage-scorer

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-3-coverage-scorer \
  --title "I7-3: Signal coverage scorer" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 289 tests passing (271 + 13 from I7-1 + 5 from I7-2), ruff clean
```

---

## What to Build

### Allowed files (exactly these two, no others)

```
src/wbsb/eval/scorer.py          ← extend (add coverage function)
tests/test_eval_scorer.py        ← extend (add 6 new tests)
```

### Add to `src/wbsb/eval/scorer.py`

Append this function to the existing file. Do not modify `score_grounding()`.

```python
def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict:
    """
    Score how many signals and categories are covered by the LLM narratives.

    Args:
        findings:   Pydantic Findings object from the pipeline.
        llm_result: Pydantic LLMResult object from the LLM adapter.

    Returns:
        {
            "signal_coverage": float,   # [0.0, 1.0]
            "group_coverage": float,    # [0.0, 1.0]
        }
    """
```

### Algorithm

**Signal coverage:**

```python
total_signals = len(findings.signals)   # includes WARN and INFO signals

if total_signals == 0:
    signal_coverage = 1.0
else:
    payload_rule_ids = {signal.rule_id for signal in findings.signals}
    signals_with_narrative = sum(
        1 for rule_id in payload_rule_ids
        if rule_id in (llm_result.signal_narratives or {})
    )
    signal_coverage = signals_with_narrative / total_signals
```

**Group coverage:**

```python
payload_categories = {
    signal.category.lower().replace(" ", "_")
    for signal in findings.signals
}

if not payload_categories:
    group_coverage = 1.0
else:
    covered_categories = sum(
        1 for cat in payload_categories
        if cat in (llm_result.group_narratives or {})
    )
    group_coverage = covered_categories / len(payload_categories)
```

**Return:**

```python
return {
    "signal_coverage": signal_coverage,
    "group_coverage": group_coverage,
}
```

---

## What NOT to Do

- Do not modify `score_grounding()` — it is frozen after I7-2.
- Do not add `score_hallucination()` — that is I7-4.
- Do not add `build_eval_scores()` — that is I7-5.
- Do not modify `src/wbsb/eval/extractor.py`, `src/wbsb/eval/models.py`.
- Do not modify `src/wbsb/pipeline.py` or `src/wbsb/render/llm_adapter.py`.
- Do not hardcode coverage thresholds.
- Do not use `except: pass` or any silent failure.
- Do not rewrite or reformat any existing code in `scorer.py`.

---

## Tests Required

Add these 6 test functions to the existing `tests/test_eval_scorer.py`.
Do not delete or modify existing tests.

### Category normalization

Category keys in `group_narratives` are normalized: `signal.category.lower().replace(" ", "_")`.
Build your test fixtures with this in mind.

Example: a signal with `category="Financial Health"` matches a `group_narratives` key of
`"financial_health"`.

### `cfg` dict for tests (not needed for coverage — no config params)

Coverage scorer takes no `cfg` argument.

### Required tests

#### `test_coverage_all_signals_covered`

All signals in findings have entries in `signal_narratives`.

```python
def test_coverage_all_signals_covered():
    # 2 signals, both have signal_narratives entries
    # Expected: signal_coverage=1.0
```

#### `test_coverage_partial_signals`

Some signals have narratives, some do not.

```python
def test_coverage_partial_signals():
    # 3 signals, 2 have signal_narratives entries
    # Expected: signal_coverage == 2/3
```

#### `test_coverage_no_signals`

Findings has no signals.

```python
def test_coverage_no_signals():
    # findings.signals == []
    # Expected: signal_coverage=1.0
```

#### `test_group_coverage_all_categories`

All payload categories appear in `group_narratives`.

```python
def test_group_coverage_all_categories():
    # 2 categories from signals, both in group_narratives (normalized keys)
    # Expected: group_coverage=1.0
```

#### `test_group_coverage_partial`

Some categories covered, some not.

```python
def test_group_coverage_partial():
    # 2 categories from signals, 1 in group_narratives
    # Expected: group_coverage=0.5
```

#### `test_group_coverage_no_categories`

No signals, therefore no payload categories.

```python
def test_group_coverage_no_categories():
    # findings.signals == []  →  payload_categories == set()
    # Expected: group_coverage=1.0
```

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 295 passing (289 existing + 6 new), 0 failures

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
feat(eval): add score_signal_coverage() to scorer.py

Computes signal coverage (signals with narrative / total signals) and
group coverage (covered categories / payload categories), both defaulting
to 1.0 when the denominator is zero. No config parameters required.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-3-coverage-scorer
gh pr ready
```

---

## Handoff to I7-4

When this task is merged into `feature/iteration-7`, I7-4 will extend `scorer.py` by adding
`score_hallucination()`. I7-4's branch must be created from `feature/iteration-7` **after**
this PR is merged.

Exports consumed by I7-5 (do not rename or remove):
```python
# src/wbsb/eval/scorer.py
def score_signal_coverage(findings: Findings, llm_result: LLMResult) -> dict: ...
```
