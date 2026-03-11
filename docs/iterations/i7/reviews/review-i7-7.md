# WBSB Review Prompt — I7-7: Feedback Storage + `wbsb feedback` CLI

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
- Do not invent problems that are not there. Every finding must be backed by evidence.

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
| 1 | **Deterministic first** — same query inputs must always produce the same output |
| 2 | **No silent validation failure** — invalid run_id / section / label must raise `ValueError` |
| 3 | **Silent truncation** — comment > 1000 chars is silently truncated; must not raise |
| 4 | **Separation of concerns** — `wbsb.feedback` must not import from `wbsb.eval` |
| 5 | **Domain model is frozen** — `src/wbsb/domain/models.py` must not be modified |

---

## Task Under Review

| Field | Value |
|-------|-------|
| Task ID | I7-7 |
| Title | Feedback Storage + `wbsb feedback` CLI |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Claude |
| Reviewed by | Codex |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-7-feedback-system` |
| PR | #TBD |
| Expected test count | 312 before → 320 after (expected +8) |

---

## What This Task Was Supposed to Build

### New/modified files (exactly these, no more)

```
src/wbsb/feedback/store.py       ← create
src/wbsb/cli.py                  ← extend (wbsb feedback list/summary/export)
.gitignore                       ← add feedback/* + !feedback/.gitkeep
tests/test_feedback.py           ← create
feedback/.gitkeep                ← empty file (tracks directory in git)
```

### Required storage API

```python
FEEDBACK_DIR = Path("feedback")
RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[a-f0-9]{6}$")

def save_feedback(entry: FeedbackEntry) -> Path: ...
def list_feedback(limit: int = 50) -> list[FeedbackEntry]: ...
def summarize_feedback() -> dict: ...
def export_feedback(run_id: str) -> list[FeedbackEntry]: ...
```

### Required `summarize_feedback` return structure

```python
{
    "total": int,
    "by_label": {"expected": int, "unexpected": int, "incorrect": int},
    "by_section": {"situation": int, "key_story": int, "group_narratives": int, "watch_signals": int},
}
```

All label and section keys must be present even with 0 count.

### What must NOT have been built

- No HTTP server or webhook endpoint.
- No modifications to `src/wbsb/feedback/models.py`.
- No modifications to `src/wbsb/pipeline.py` or `src/wbsb/render/llm_adapter.py`.
- No imports from `wbsb.eval` inside `wbsb.feedback`.

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-7-feedback-system
git pull origin feature/i7-7-feedback-system
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: 320 passing, 0 failures

ruff check .
# Expected: no issues
```

If either fails, verdict is `CHANGES REQUIRED` immediately.

### Step 3 — Verify scope

```bash
git diff --name-only feature/iteration-7
```

Expected — these files only:
```
.gitignore
feedback/.gitkeep
src/wbsb/cli.py
src/wbsb/feedback/store.py
tests/test_feedback.py
```

Any other file = scope violation. In particular, `feedback/models.py` must NOT be changed.

### Step 4 — Verify all 4 storage functions importable

```bash
python3 -c "
from wbsb.feedback.store import save_feedback, list_feedback, summarize_feedback, export_feedback
import inspect

for fn in [save_feedback, list_feedback, summarize_feedback, export_feedback]:
    print(f'{fn.__name__}: {list(inspect.signature(fn).parameters.keys())}')
print('storage imports: OK')
"
```

Expected:
- `save_feedback(entry)`
- `list_feedback(limit=50)` — `limit` has default `50`
- `summarize_feedback()` — no required params
- `export_feedback(run_id)`

### Step 5 — Verify run_id regex validation

```bash
python3 -c "
from wbsb.feedback.store import save_feedback
from wbsb.feedback.models import FeedbackEntry

# Invalid run_id — should raise ValueError
try:
    entry = FeedbackEntry(
        feedback_id='test',
        run_id='invalid_run_id',
        section='situation',
        label='expected',
        comment='test',
        submitted_at='2026-03-11T12:00:00Z',
    )
    save_feedback(entry)
    print('FAIL — should have raised ValueError for invalid run_id')
except ValueError as e:
    print(f'OK — ValueError raised: {e}')
"
```

Expected: `OK — ValueError raised: ...`

Also verify the exact regex pattern:

```bash
grep -n "RUN_ID_PATTERN\|run_id\|regex\|re\.compile" src/wbsb/feedback/store.py
```

Expected: pattern `^\d{8}T\d{6}Z_[a-f0-9]{6}$` or equivalent.

### Step 6 — Verify section and label validation

```bash
python3 -c "
from wbsb.feedback.store import save_feedback
from wbsb.feedback.models import FeedbackEntry

base = dict(
    feedback_id='test',
    run_id='20260311T132430Z_3485e2',
    label='expected',
    comment='test',
    submitted_at='2026-03-11T12:00:00Z',
)

# Invalid section
try:
    save_feedback(FeedbackEntry(**{**base, 'section': 'invalid_section'}))
    print('FAIL — section not validated')
except ValueError as e:
    print(f'OK — section: {e}')

# Invalid label
try:
    save_feedback(FeedbackEntry(**{**base, 'section': 'situation', 'label': 'invalid_label'}))
    print('FAIL — label not validated')
except ValueError as e:
    print(f'OK — label: {e}')
"
```

Expected: both print `OK`.

### Step 7 — Verify comment truncation (not rejection)

```bash
python3 -c "
import tempfile
from pathlib import Path
import wbsb.feedback.store as store
from wbsb.feedback.models import FeedbackEntry

with tempfile.TemporaryDirectory() as tmp:
    store.FEEDBACK_DIR = Path(tmp)
    entry = FeedbackEntry(
        feedback_id='trunc_test',
        run_id='20260311T132430Z_3485e2',
        section='situation',
        label='expected',
        comment='x' * 1500,
        submitted_at='2026-03-11T12:00:00Z',
    )
    path = save_feedback(entry)
    import json
    saved = json.loads(path.read_text())
    assert len(saved['comment']) == 1000, f'Expected 1000 chars, got {len(saved[\"comment\"])}'
    print('comment truncation: OK')
"
```

Expected: `comment truncation: OK`

### Step 8 — Verify feedback_id auto-generation

```bash
grep -n "uuid\|feedback_id\|uuid4" src/wbsb/feedback/store.py
```

Expected: `uuid.uuid4().hex` used to generate `feedback_id` when it is falsy.

### Step 9 — Verify list_feedback sorts newest first

```bash
grep -n "sorted\|sort\|submitted_at\|reverse" src/wbsb/feedback/store.py
```

Expected: `list_feedback` sorts by `submitted_at` descending (newest first).
If sorted ascending: `severity: major` — list command shows oldest entries first.

### Step 10 — Verify summarize_feedback return structure

```bash
python3 -c "
import tempfile
from pathlib import Path
import wbsb.feedback.store as store

with tempfile.TemporaryDirectory() as tmp:
    store.FEEDBACK_DIR = Path(tmp)
    summary = store.summarize_feedback()
    assert 'total' in summary, 'missing total'
    assert 'by_label' in summary, 'missing by_label'
    assert 'by_section' in summary, 'missing by_section'
    # All label keys must be present even at 0
    for key in ('expected', 'unexpected', 'incorrect'):
        assert key in summary['by_label'], f'missing by_label key: {key}'
    # All section keys must be present even at 0
    for key in ('situation', 'key_story', 'group_narratives', 'watch_signals'):
        assert key in summary['by_section'], f'missing by_section key: {key}'
    print('summarize_feedback structure: OK')
"
```

Expected: `summarize_feedback structure: OK`

### Step 11 — Verify gitignore rules

```bash
grep "feedback" .gitignore
```

Expected — both lines present:
```
feedback/*
!feedback/.gitkeep
```

If `feedback/` (without `*`) is used instead of `feedback/*`: `severity: major` —
`!feedback/.gitkeep` negation will not work because git ignores the entire directory.

```bash
# Verify .gitkeep is tracked
git ls-files feedback/.gitkeep
# Expected: feedback/.gitkeep
```

### Step 12 — Verify CLI commands present

```bash
wbsb feedback --help
# Expected: shows list, summary, export subcommands

wbsb feedback summary
# Expected: prints summary with 0 counts (no feedback exists yet)

wbsb feedback list
# Expected: empty list or "no entries"
```

### Step 13 — Forbidden patterns

```bash
# No silent failure
grep -n "except.*pass\|except:$" src/wbsb/feedback/store.py tests/test_feedback.py
# Expected: no matches

# No cross-imports (feedback must not import from eval)
grep -n "from wbsb.eval\|import wbsb.eval" src/wbsb/feedback/store.py
# Expected: no matches

# feedback/models.py not modified
git diff feature/iteration-7 src/wbsb/feedback/models.py
# Expected: no output

# domain/models.py not modified
git diff feature/iteration-7 src/wbsb/domain/models.py
# Expected: no output
```

### Step 14 — Verify all 8 test functions exist

```bash
grep -n "^def test_" tests/test_feedback.py
```

Expected — all 8 present:
```
test_save_feedback_valid
test_save_feedback_invalid_run_id
test_save_feedback_invalid_section
test_save_feedback_invalid_label
test_save_feedback_comment_truncated
test_list_feedback_sorted
test_summarize_feedback_counts
test_export_feedback_by_run_id
```

For `test_summarize_feedback_counts` — verify it asserts that keys with 0 count are present:

```bash
grep -A 20 "def test_summarize_feedback_counts" tests/test_feedback.py
```

If the test only asserts non-zero counts: `severity: minor` — zero-count keys may be absent.

---

## Required Output Format

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List everything implemented correctly. Reference file paths and line numbers.
Must not be empty on a PASS verdict.

---

### 3. Problems Found

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
- [PASS | FAIL] save_feedback importable from wbsb.feedback.store
- [PASS | FAIL] list_feedback importable with default limit=50
- [PASS | FAIL] summarize_feedback importable with no required params
- [PASS | FAIL] export_feedback importable from wbsb.feedback.store
- [PASS | FAIL] save_feedback raises ValueError for invalid run_id
- [PASS | FAIL] save_feedback raises ValueError for invalid section
- [PASS | FAIL] save_feedback raises ValueError for invalid label
- [PASS | FAIL] comment silently truncated to 1000 chars (no exception)
- [PASS | FAIL] feedback_id auto-generated via uuid.uuid4().hex when falsy
- [PASS | FAIL] list_feedback sorted by submitted_at descending (newest first)
- [PASS | FAIL] summarize_feedback returns {total, by_label, by_section} with all keys at 0
- [PASS | FAIL] export_feedback filters correctly by run_id
- [PASS | FAIL] .gitignore has feedback/* and !feedback/.gitkeep (in correct order)
- [PASS | FAIL] feedback/.gitkeep tracked in git
- [PASS | FAIL] wbsb feedback list command operational
- [PASS | FAIL] wbsb feedback summary command operational
- [PASS | FAIL] wbsb feedback export --run-id command operational
- [PASS | FAIL] No HTTP server or webhook code added
- [PASS | FAIL] feedback/models.py not modified
- [PASS | FAIL] No cross-imports from wbsb.eval into wbsb.feedback
- [PASS | FAIL] domain/models.py not modified
- [PASS | FAIL] All 8 test functions present
- [PASS | FAIL] test_summarize_feedback_counts checks zero-count keys
- [PASS | FAIL] 320 tests pass (312 existing + 8 new)
- [PASS | FAIL] Ruff clean
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
