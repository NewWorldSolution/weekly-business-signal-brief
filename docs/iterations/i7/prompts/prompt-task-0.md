# WBSB Task Prompt — I7-0: Domain Models, Schemas, and Eval Config

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
- **Feature branch for this task:** `feature/i7-0-pre-work`
- **Tests passing:** 271
- **Ruff:** clean
- **Last completed task:** I6-8 — final cleanup, `feature/iteration-6` merged to `main`
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I7-0 |
| Title | Domain Models, Schemas, and Eval Config |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Owner | Claude |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-0-pre-work` |
| Depends on | none — starts immediately |
| Blocks | I7-1, I7-2, I7-3, I7-4, I7-7 |
| PR scope | One PR into `feature/iteration-7`. Do not combine tasks. Do not PR to `main`. |

---

## Task Goal

Iteration 7 introduces automated evaluation scoring for every LLM output and a lightweight operator feedback storage system. Before any scoring logic can be written, the data contracts must be defined and frozen. Every downstream task (I7-1 through I7-7) imports from models defined here or reads from config keys defined here.

This task creates four new files (two empty package markers and two Pydantic model files) and adds one new config section to `config/rules.yaml`. It establishes the `EvalScores` and `FeedbackEntry` schemas that are the stable contracts for the entire iteration — they must not change after this task merges.

---

## Why Claude

This task establishes architectural contracts that every other I7 task builds against. It requires judgment about what fields are needed, what should be nullable vs required, and how to represent failure states. The tolerance config values have been specified precisely in `docs/iterations/i7/tasks.md` — this task implements them exactly as specified.

---

## Files to Read Before Starting

Read these files in order before touching anything:

```
docs/iterations/i7/tasks.md              ← full I7 spec; schemas section defines exact field types
src/wbsb/domain/models.py                ← existing Pydantic patterns to follow exactly
config/rules.yaml                        ← where to add eval: section; match indentation style
src/wbsb/history/store.py                ← example of a new package added in I6 — follow this structure
```

---

## Existing Code This Task Builds On

### Already exists and must NOT be reimplemented:

```python
# src/wbsb/domain/models.py
class Findings(BaseModel):
    signals: list[Signal]
    metrics: list[MetricResult]
    # ... do not touch this file

class LLMResult(BaseModel):
    situation: str
    key_story: str | None
    group_narratives: dict[str, str]
    signal_narratives: dict[str, str]   # keys are rule_ids
    watch_signals: list[...]
    model: str
    # ... do not touch this file
```

### Contracts this task must honour:

```
Pydantic v2 is used throughout — use BaseModel, not dataclasses
Field names must match exactly what tasks.md specifies — downstream tasks import them by name
schema_version must default to "1.0" — not a required field
```

---

## What to Build

### New files

```
src/wbsb/eval/__init__.py            ← empty package marker
src/wbsb/eval/models.py              ← EvalScores + HallucinationViolation Pydantic models
src/wbsb/feedback/__init__.py        ← empty package marker
src/wbsb/feedback/models.py          ← FeedbackEntry Pydantic model + validation constants
```

### Modified files

```
config/rules.yaml                    ← add eval: section after history: block, before rules:
```

### Public API

```python
# src/wbsb/eval/models.py

from __future__ import annotations
from pydantic import BaseModel


class HallucinationViolation(BaseModel):
    type: str       # e.g. "key_story_when_no_cluster"
    severity: str   # "critical" | "major" | "minor"
    detail: str     # human-readable, e.g. "metric_id 'foo' not in payload"


class EvalScores(BaseModel):
    schema_version: str = "1.0"
    grounding: float | None          # None when grounding_reason is set
    grounding_reason: str | None     # None | "no_numbers_cited"
    flagged_numbers: list[str]       # raw string tokens not grounded in evidence
    signal_coverage: float           # signals_with_narrative / total_signals
    group_coverage: float            # categories_covered / total_categories
    hallucination_risk: int          # total violation count, all severities
    hallucination_violations: list[HallucinationViolation]
    model: str                       # LLM model ID string
    evaluated_at: str                # ISO 8601 UTC datetime string
```

```python
# src/wbsb/feedback/models.py

from __future__ import annotations
from pydantic import BaseModel

VALID_SECTIONS: frozenset[str] = frozenset({
    "situation",
    "key_story",
    "group_narratives",
    "watch_signals",
})

VALID_LABELS: frozenset[str] = frozenset({
    "expected",
    "unexpected",
    "incorrect",
})


class FeedbackEntry(BaseModel):
    schema_version: str = "1.0"
    feedback_id: str           # UUID4 hex string, generated at submission
    run_id: str                # e.g. "20260311T132430Z_3485e2"
    section: str               # must be in VALID_SECTIONS
    label: str                 # must be in VALID_LABELS
    comment: str               # max 1000 chars; may be empty string
    operator: str = "anonymous"
    submitted_at: str          # ISO 8601 UTC datetime string
```

### Config section to add

Add this block to `config/rules.yaml` **after the `history:` section** and **before the `rules:` list**. Use 2-space indentation consistent with the rest of the file.

```yaml
eval:
  grounding_tolerance_abs: 0.01       # absolute tolerance for values where |value| < 1.0
  grounding_tolerance_rel: 0.01       # relative tolerance (1%) for values where |value| >= 1.0
  grounding_pct_normalization: true   # if true, "40%" is tested against 0.40 and 40.0
```

### Behaviour rules

- **Schema version:** `schema_version` must default to `"1.0"` without being a required field. Do not make it a required constructor argument.
- **Immutable constants:** `VALID_SECTIONS` and `VALID_LABELS` must be `frozenset` — not plain `set` — to prevent accidental mutation.
- **No validation logic here:** `FeedbackEntry` and `EvalScores` are data containers only. Input validation (run_id regex check, section/label membership check) belongs in `src/wbsb/feedback/store.py` (I7-7). Do not add validators to these models.
- **No imports from eval in feedback:** The two packages (`wbsb.eval` and `wbsb.feedback`) must not import from each other. They are independent.
- **Config section placement:** The `eval:` block must appear between the existing `history:` block and the `rules:` list — not appended at the end of the file.

### Input/output examples

```python
# EvalScores — valid instantiation
EvalScores(
    grounding=0.92,
    grounding_reason=None,
    flagged_numbers=["534.3"],
    signal_coverage=1.0,
    group_coverage=1.0,
    hallucination_risk=1,
    hallucination_violations=[
        HallucinationViolation(
            type="invalid_watch_signal_id",
            severity="major",
            detail="metric_id 'foo' not in payload",
        )
    ],
    model="claude-haiku-4-5-20251001",
    evaluated_at="2026-03-11T12:00:00Z",
)

# EvalScores — no numbers cited
EvalScores(
    grounding=None,
    grounding_reason="no_numbers_cited",
    flagged_numbers=[],
    signal_coverage=1.0,
    group_coverage=1.0,
    hallucination_risk=0,
    hallucination_violations=[],
    model="claude-haiku-4-5-20251001",
    evaluated_at="2026-03-11T12:00:00Z",
)

# FeedbackEntry — valid instantiation
FeedbackEntry(
    feedback_id="550e8400e29b41d4a716446655440000",
    run_id="20260311T132430Z_3485e2",
    section="situation",
    label="unexpected",
    comment="The situation understated the financial risk.",
    submitted_at="2026-03-11T13:00:00Z",
)
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
src/wbsb/eval/__init__.py            ← new: empty package marker
src/wbsb/eval/models.py              ← new: EvalScores + HallucinationViolation
src/wbsb/feedback/__init__.py        ← new: empty package marker
src/wbsb/feedback/models.py          ← new: FeedbackEntry + constants
config/rules.yaml                    ← modify: add eval: section only
```

---

## Files NOT to Touch

```
src/wbsb/domain/models.py            ← frozen; eval types are separate from domain types
src/wbsb/pipeline.py                 ← touched only in I7-5
src/wbsb/render/llm_adapter.py       ← touched only in I7-5
src/wbsb/eval/scorer.py              ← created in I7-2 (does not exist yet)
src/wbsb/eval/extractor.py           ← created in I7-1 (does not exist yet)
src/wbsb/feedback/store.py           ← created in I7-7 (does not exist yet)
Any test file                        ← no tests required for this task
```

If any of these files seem like they need to change to complete this task, **stop and raise it** rather than modifying them.

---

## Acceptance Criteria

- [ ] `EvalScores` instantiates with all required fields and correct types
- [ ] `EvalScores.schema_version` defaults to `"1.0"` without being passed explicitly
- [ ] `EvalScores.grounding` accepts `float | None`; `EvalScores.grounding_reason` accepts `str | None`
- [ ] `HallucinationViolation` instantiates with `type`, `severity`, `detail` fields
- [ ] `FeedbackEntry` instantiates with all required fields and correct types
- [ ] `FeedbackEntry.schema_version` defaults to `"1.0"` without being passed explicitly
- [ ] `VALID_SECTIONS` is a `frozenset` containing exactly: `situation`, `key_story`, `group_narratives`, `watch_signals`
- [ ] `VALID_LABELS` is a `frozenset` containing exactly: `expected`, `unexpected`, `incorrect`
- [ ] `config/rules.yaml` loads without error via `yaml.safe_load()`
- [ ] `eval:` section present with exactly three keys: `grounding_tolerance_abs` (float), `grounding_tolerance_rel` (float), `grounding_pct_normalization` (bool)
- [ ] No existing `config/rules.yaml` keys modified
- [ ] `from wbsb.eval.models import EvalScores, HallucinationViolation` works without error
- [ ] `from wbsb.feedback.models import FeedbackEntry, VALID_SECTIONS, VALID_LABELS` works without error
- [ ] All 271 existing tests still pass — `pytest` exit code 0
- [ ] Ruff clean — `ruff check .` exit code 0

---

## Tests Required

No new tests are required for this task. The models are data containers with no logic. They will be covered by tests in I7-1 through I7-7 where they are used.

The acceptance criteria above (import checks, instantiation checks) are verified by the reviewer manually and via the existing test suite import chain.

---

## Edge Cases to Handle Explicitly

| Edge case | Expected behaviour |
|-----------|-------------------|
| `grounding=None` with `grounding_reason=None` | Pydantic allows it — validation logic is the scorer's job (I7-2), not the model's |
| `hallucination_violations=[]` with `hallucination_risk=1` | Pydantic allows it — consistency is the scorer's responsibility |
| `comment=""` | Valid — empty comment is permitted |
| `operator` field omitted | Defaults to `"anonymous"` silently |
| `schema_version` field omitted | Defaults to `"1.0"` silently |

---

## What NOT to Do

- Do not add Pydantic validators (`@field_validator`) to `FeedbackEntry` or `EvalScores` — validation logic belongs in `store.py` (I7-7) and `scorer.py` (I7-5)
- Do not import `wbsb.eval` from `wbsb.feedback` or vice versa — they are independent packages
- Do not modify `src/wbsb/domain/models.py` — eval types are separate from domain types by design
- Do not add the `eval:` config block at the end of `config/rules.yaml` — it must go between `history:` and `rules:`
- Do not use plain `set` for `VALID_SECTIONS` or `VALID_LABELS` — use `frozenset`
- Do not write any scorer, extractor, or storage logic — this task is models and config only
- Do not refactor code outside the allowed files

---

## Handoff: What the Next Tasks Need From This One

After this task merges, the following will be available for I7-1, I7-2, I7-3, I7-4, I7-7:

```python
# from wbsb.eval.models import EvalScores, HallucinationViolation
# from wbsb.feedback.models import FeedbackEntry, VALID_SECTIONS, VALID_LABELS

# Contracts:
# - EvalScores(grounding, grounding_reason, flagged_numbers, signal_coverage,
#              group_coverage, hallucination_risk, hallucination_violations,
#              model, evaluated_at) — schema_version defaults to "1.0"
# - FeedbackEntry(feedback_id, run_id, section, label, comment,
#                 submitted_at, operator="anonymous") — schema_version defaults to "1.0"
# - VALID_SECTIONS: frozenset — section membership check
# - VALID_LABELS: frozenset — label membership check
```

Config keys available from `config/rules.yaml["eval"]`:

```
grounding_tolerance_abs    → float, e.g. 0.01
grounding_tolerance_rel    → float, e.g. 0.01
grounding_pct_normalization → bool, e.g. True
```

---

## Execution Workflow

Follow this sequence exactly.

### Step 0 — Branch setup and draft PR

```bash
git checkout feature/iteration-7
git pull origin feature/iteration-7
git status
# Expected: nothing to commit, working tree clean

git checkout -b feature/i7-0-pre-work
git branch --show-current
# Expected: feature/i7-0-pre-work

git push -u origin feature/i7-0-pre-work

gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-0-pre-work \
  --title "I7-0: Domain models, schemas, and eval config" \
  --body "Work in progress. See docs/iterations/i7/prompts/prompt-task-0.md for full spec." \
  --draft
```

### Step 1 — Verify baseline

```bash
pytest
# Expected: 271 tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

### Step 2 — Read before writing

Read the four files listed in "Files to Read Before Starting" in order.

### Step 3 — Implement

Create the four new files and add the `eval:` section to `config/rules.yaml`.

### Step 4 — Test and lint

```bash
pytest
# Expected: 271 tests passing (no new tests in this task)

ruff check .
# Expected: clean
```

### Step 5 — Verify scope

```bash
git diff --name-only feature/iteration-7
```

Expected output (exactly these files, no others):
```
config/rules.yaml
src/wbsb/eval/__init__.py
src/wbsb/eval/models.py
src/wbsb/feedback/__init__.py
src/wbsb/feedback/models.py
```

### Step 6 — Commit and push

```bash
git add config/rules.yaml \
        src/wbsb/eval/__init__.py \
        src/wbsb/eval/models.py \
        src/wbsb/feedback/__init__.py \
        src/wbsb/feedback/models.py

git commit -m "feat: add eval and feedback domain models + eval config section (I7-0)

Creates wbsb.eval.models (EvalScores, HallucinationViolation) and
wbsb.feedback.models (FeedbackEntry, VALID_SECTIONS, VALID_LABELS) as
frozen data contracts for Iteration 7. Adds eval: section to
config/rules.yaml with grounding tolerance parameters. No logic — models
are data containers only. All downstream I7 tasks import from these.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push origin feature/i7-0-pre-work
```

### Step 7 — Mark PR ready

```bash
gh pr ready feature/i7-0-pre-work
```

---

## Definition of Done

This task is complete when ALL of the following are true:

- [ ] `EvalScores` and `HallucinationViolation` importable from `wbsb.eval.models`
- [ ] `FeedbackEntry`, `VALID_SECTIONS`, `VALID_LABELS` importable from `wbsb.feedback.models`
- [ ] `schema_version` defaults to `"1.0"` on both models
- [ ] `VALID_SECTIONS` and `VALID_LABELS` are `frozenset`
- [ ] `config/rules.yaml` has `eval:` section with three keys, correct types, correct placement
- [ ] No existing config keys modified
- [ ] `domain/models.py` not touched
- [ ] All 271 prior tests still pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only allowed files modified (`git diff --name-only feature/iteration-7` shows exactly 5 files)
- [ ] No `except: pass`, no hardcoded values, no validation logic in models
