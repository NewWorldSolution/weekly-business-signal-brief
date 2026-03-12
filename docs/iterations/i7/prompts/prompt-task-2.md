# Task Prompt — I7-2: Grounding Scorer

---

## Context

You are implementing **task I7-2** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-1 (`src/wbsb/eval/extractor.py`) has been merged into
`feature/iteration-7`. You are building on top of it.

**Your task:** Implement `score_grounding()` in a new `src/wbsb/eval/scorer.py` file.
This is a pure library function with no pipeline changes.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Deterministic** — no randomness; same inputs must always produce the same output |
| 2 | **Config-driven** — all tolerance values read from `cfg` dict; zero hardcoded numbers |
| 3 | **No silent failure** — never `except: pass`; surface real errors |
| 4 | **Module boundaries** — `wbsb.eval` must not import from `wbsb.feedback` |
| 5 | **Domain model is frozen** — never modify `src/wbsb/domain/models.py` |
| 6 | **Allowed files only** — touch only the two files listed below |
| 7 | **Draft PR first** — open a draft PR before writing any code |
| 8 | **Test before commit** — `pytest` and `ruff check .` must both pass before every push |

---

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch — always, never from main
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-2-grounding-scorer
git push -u origin feature/i7-2-grounding-scorer

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-2-grounding-scorer \
  --title "I7-2: Grounding scorer" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 284 tests passing, ruff clean
```

---

## What to Build

### Allowed files (exactly these two, no others)

```
src/wbsb/eval/scorer.py          ← create (grounding function only)
tests/test_eval_scorer.py        ← create
```

### `src/wbsb/eval/scorer.py`

Create this file with a single public function:

```python
from __future__ import annotations

from wbsb.domain.models import Findings, LLMResult
from wbsb.eval.extractor import (
    build_evidence_allowlist,
    candidate_values,
    extract_numbers_from_text,
    is_grounded,
    normalize_number,
)


def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict:
    """
    Score how well LLM-cited numbers are grounded in the findings evidence.

    Args:
        findings:   Pydantic Findings object from the pipeline.
        llm_result: Pydantic LLMResult object from the LLM adapter.
        cfg:        The eval section from config/rules.yaml (a dict).

    Returns:
        {
            "grounding": float | None,
            "grounding_reason": str | None,
            "flagged_numbers": list[str],
        }
    """
```

### Algorithm (implement exactly as described)

**Step 1 — Collect text from all LLM sections:**
- `llm_result.situation` — if not None
- `llm_result.key_story` — if not None
- All string values in `llm_result.group_narratives` (dict values)
- All string values in `llm_result.signal_narratives` (dict values)
- All `entry.observation` values in `llm_result.watch_signals` list — if the list is not empty

Concatenate all collected non-None strings into a single text block.

**Step 2 — Extract numeric tokens:**

```python
tokens = extract_numbers_from_text(combined_text)
```

**Step 3 — Handle empty case:**

If `len(tokens) == 0`, return:

```python
{"grounding": None, "grounding_reason": "no_numbers_cited", "flagged_numbers": []}
```

**Step 4 — Build evidence allowlist:**

```python
allowlist = build_evidence_allowlist(findings)
```

**Step 5 — Score each token:**

For each raw token:
1. Get `pct_normalization` from `cfg["grounding_pct_normalization"]`
2. Get candidates: `candidates = candidate_values(raw_token, pct_normalization)`
3. A token is **grounded** if any candidate passes `is_grounded(candidate, allowlist, cfg)`.
4. If no candidate is grounded: add `raw_token` to `flagged_numbers`.

**Step 6 — Compute and return:**

```python
grounding = (len(tokens) - len(flagged_numbers)) / len(tokens)
return {
    "grounding": grounding,
    "grounding_reason": None,
    "flagged_numbers": flagged_numbers,
}
```

---

## What NOT to Do

- Do not add `score_signal_coverage()` or `score_hallucination()` — those are I7-3 and I7-4.
- Do not add `build_eval_scores()` — that is I7-5.
- Do not modify `src/wbsb/eval/extractor.py` — it is frozen after I7-1.
- Do not modify `src/wbsb/eval/models.py` — it is frozen after I7-0.
- Do not modify `src/wbsb/pipeline.py` or `src/wbsb/render/llm_adapter.py`.
- Do not hardcode `0.01` or any tolerance value — all tolerance logic lives in `extractor.py` and reads from `cfg`.
- Do not use `except: pass` or any silent failure.

---

## Tests Required

Create `tests/test_eval_scorer.py` with exactly these 5 test functions.

### Fixtures you will need

Build minimal Findings and LLMResult fixtures. Use only what the test requires.

For a minimal `LLMResult` with no numbers:
```python
llm = LLMResult(
    situation="Revenue improved significantly this week.",
    key_story=None,
    group_narratives={},
    signal_narratives={},
    watch_signals=[],
    model="claude-haiku-4-5-20251001",
)
```

For a minimal `Findings` with known metric values — use real `MetricResult` objects from
`wbsb.domain.models`. The exact fields depend on your domain model — check
`src/wbsb/domain/models.py` for the correct constructor.

The `cfg` dict for tests:
```python
cfg = {
    "grounding_tolerance_abs": 0.01,
    "grounding_tolerance_rel": 0.01,
    "grounding_pct_normalization": True,
}
```

### Required tests

#### `test_grounding_no_numbers_cited`

LLM output contains only prose text with no numeric tokens.

```python
def test_grounding_no_numbers_cited():
    # LLM text is pure prose — no numbers
    # Expected: grounding=None, grounding_reason="no_numbers_cited", flagged_numbers=[]
```

#### `test_grounding_all_grounded`

All numbers cited by LLM exist in the findings evidence within tolerance.

```python
def test_grounding_all_grounded():
    # All cited numbers are in allowlist
    # Expected: grounding=1.0, flagged_numbers=[]
```

#### `test_grounding_one_flagged`

One number cited is outside the allowlist; others are grounded.

```python
def test_grounding_one_flagged():
    # 3 tokens cited, 1 not in allowlist
    # Expected: grounding=2/3, len(flagged_numbers)==1
```

#### `test_grounding_pct_normalization`

LLM cites `"40%"` — the allowlist contains `0.40` (not `40.0`).
With `pct_normalization=True`, the token `"40%"` should be grounded because
`candidate_values("40%", True)` returns `[40.0, 0.4]` and `0.4` matches `0.40`.

```python
def test_grounding_pct_normalization():
    # allowlist has 0.40
    # LLM cites "40%"
    # With pct_normalization=True → grounded (0.4 ≈ 0.40)
    # Expected: grounding=1.0, flagged_numbers=[]
```

#### `test_grounding_empty_llm_sections`

`llm_result` has all fields set to None or empty. No crash expected.

```python
def test_grounding_empty_llm_sections():
    # situation=None, key_story=None, group_narratives={}, signal_narratives={}, watch_signals=[]
    # Expected: grounding=None, grounding_reason="no_numbers_cited"
```

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 289 passing (284 existing + 5 new), 0 failures

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
feat(eval): implement score_grounding() in scorer.py

Adds grounding scorer that extracts numeric tokens from all LLM narrative
sections, checks each against the findings evidence allowlist using
config-driven abs/rel tolerances, and returns grounding score with
flagged_numbers list. Returns None grounding when no numbers are cited.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-2-grounding-scorer
gh pr ready
```

---

## Handoff to I7-3

When this task is merged into `feature/iteration-7`, I7-3 will extend `scorer.py` by adding
`score_signal_coverage()`. I7-3's branch must be created from `feature/iteration-7` **after**
this PR is merged — not from `feature/i7-2-grounding-scorer`.

Exports consumed by I7-3 (do not rename or remove):
```python
# src/wbsb/eval/scorer.py
def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict: ...
```

Exports consumed by I7-5 (do not rename or remove):
```python
# src/wbsb/eval/scorer.py
def score_grounding(findings: Findings, llm_result: LLMResult, cfg: dict) -> dict: ...
```
