# Task Prompt — I7-7: Feedback Storage + `wbsb feedback` CLI

---

## Context

You are implementing **task I7-7** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-0 has been merged — `FeedbackEntry`, `VALID_SECTIONS`, and
`VALID_LABELS` exist in `src/wbsb/feedback/models.py`.

**Your task:** Build `src/wbsb/feedback/store.py` with four storage functions and add three
`wbsb feedback` CLI subcommands. No pipeline changes. No HTTP server.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Deterministic** — same query inputs must always produce the same output |
| 2 | **No silent validation failure** — invalid `run_id`, `section`, `label` raise `ValueError` |
| 3 | **Silent truncation** — `comment > 1000 chars` is silently truncated (do not raise) |
| 4 | **Module boundaries** — `wbsb.feedback` must not import from `wbsb.eval` |
| 5 | **Domain model is frozen** — never modify `src/wbsb/domain/models.py` |
| 6 | **Allowed files only** — touch only the four files listed below |
| 7 | **Draft PR first** — open a draft PR before writing any code |
| 8 | **Test before commit** — `pytest` and `ruff check .` must both pass before every push |

---

## Step 0 — Branch Setup (before writing any code)

```bash
# Start from the iteration branch (depends on I7-0 only — but create after I7-6 is merged
# so test count baseline is consistent)
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-7-feedback-system
git push -u origin feature/i7-7-feedback-system

# Open a draft PR immediately — before writing any code
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-7-feedback-system \
  --title "I7-7: Feedback storage + wbsb feedback CLI" \
  --body "Work in progress." \
  --draft

# Verify baseline before touching anything
pytest --tb=short -q
ruff check .
# Expected: 312 tests passing (after I7-6 merge), ruff clean
```

---

## What to Build

### Allowed files (exactly these five, no others)

```
src/wbsb/feedback/store.py       ← create
src/wbsb/cli.py                  ← extend (add wbsb feedback commands)
.gitignore                       ← add feedback/* + !feedback/.gitkeep
tests/test_feedback.py           ← create
feedback/.gitkeep                ← empty file to track feedback/ directory in git
```

`feedback/.gitkeep` is at the repo root (not in `src/`). Create it:
```bash
mkdir -p feedback && touch feedback/.gitkeep
```

---

### `.gitignore` changes

Add these two lines (order matters — negation must follow the glob):

```
feedback/*
!feedback/.gitkeep
```

---

### `src/wbsb/feedback/store.py`

```python
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from wbsb.feedback.models import VALID_LABELS, VALID_SECTIONS, FeedbackEntry

FEEDBACK_DIR = Path("feedback")

RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[a-f0-9]{6}$")


def save_feedback(entry: FeedbackEntry) -> Path:
    """
    Validate and persist a FeedbackEntry as JSON.

    Validation (raises ValueError on failure):
        - run_id must match RUN_ID_PATTERN
        - section must be in VALID_SECTIONS
        - label must be in VALID_LABELS

    Truncation (silent, no exception):
        - comment is truncated to 1000 characters

    Auto-generation:
        - feedback_id is set to uuid.uuid4().hex if entry.feedback_id is falsy

    Returns:
        Path to the written file: FEEDBACK_DIR / f"{entry.feedback_id}.json"
    """


def list_feedback(limit: int = 50) -> list[FeedbackEntry]:
    """
    Load and return all FeedbackEntry objects from FEEDBACK_DIR,
    sorted by submitted_at descending (newest first).
    Returns up to `limit` entries.
    """


def summarize_feedback() -> dict:
    """
    Return aggregated counts from all feedback entries.

    Returns:
        {
            "total": int,
            "by_label": {
                "expected": int,
                "unexpected": int,
                "incorrect": int,
            },
            "by_section": {
                "situation": int,
                "key_story": int,
                "group_narratives": int,
                "watch_signals": int,
            },
        }
    """


def export_feedback(run_id: str) -> list[FeedbackEntry]:
    """
    Return all FeedbackEntry objects for a specific run_id.
    Sorted by submitted_at ascending (chronological order).
    """
```

#### Implementation notes

**`save_feedback`:**
- Validate `run_id` first: `if not RUN_ID_PATTERN.match(entry.run_id): raise ValueError(...)`.
- Validate `section`: `if entry.section not in VALID_SECTIONS: raise ValueError(...)`.
- Validate `label`: `if entry.label not in VALID_LABELS: raise ValueError(...)`.
- Truncate comment: `entry = entry.model_copy(update={"comment": entry.comment[:1000]})`.
- Generate `feedback_id`: `if not entry.feedback_id: entry = entry.model_copy(update={"feedback_id": uuid.uuid4().hex})`.
- Write: `FEEDBACK_DIR / f"{entry.feedback_id}.json"` with `entry.model_dump_json(indent=2)`.
- Create `FEEDBACK_DIR` if it does not exist: `FEEDBACK_DIR.mkdir(exist_ok=True)`.

**`list_feedback`:**
- Load all `.json` files from `FEEDBACK_DIR`.
- Parse each as `FeedbackEntry.model_validate_json(path.read_text())`.
- Sort by `submitted_at` descending.
- Return `entries[:limit]`.
- Skip files that fail to parse (log warning, do not crash).

**`summarize_feedback`:**
- Load all entries (no limit).
- Count by label and section using the exact keys from `VALID_LABELS` and `VALID_SECTIONS`.
- Initialize all counts to 0 — even labels/sections with no entries must appear in the dict.

**`export_feedback`:**
- Load all entries.
- Filter: `[e for e in all_entries if e.run_id == run_id]`.
- Sort by `submitted_at` ascending.

---

### `src/wbsb/cli.py` — add feedback subcommands

Add a `feedback` subgroup with three commands:

```python
feedback_app = typer.Typer()
app.add_typer(feedback_app, name="feedback")


@feedback_app.command("list")
def feedback_list(limit: int = typer.Option(50, "--limit", help="Max entries to show.")):
    """List recent feedback entries."""
    from wbsb.feedback.store import list_feedback
    entries = list_feedback(limit=limit)
    for e in entries:
        typer.echo(f"[{e.submitted_at}] {e.run_id} | {e.section} | {e.label} | {e.comment[:80]}")


@feedback_app.command("summary")
def feedback_summary():
    """Show feedback summary by label and section."""
    from wbsb.feedback.store import summarize_feedback
    summary = summarize_feedback()
    typer.echo(f"Total: {summary['total']}")
    typer.echo("By label:")
    for label, count in summary["by_label"].items():
        typer.echo(f"  {label}: {count}")
    typer.echo("By section:")
    for section, count in summary["by_section"].items():
        typer.echo(f"  {section}: {count}")


@feedback_app.command("export")
def feedback_export(run_id: str = typer.Option(..., "--run-id", help="Run ID to export.")):
    """Export all feedback for a specific run."""
    from wbsb.feedback.store import export_feedback
    entries = export_feedback(run_id)
    import json
    typer.echo(json.dumps([e.model_dump() for e in entries], indent=2))
```

---

## What NOT to Do

- Do not modify `src/wbsb/feedback/models.py` — it is frozen after I7-0.
- Do not build a webhook server or HTTP endpoint — that belongs to I9.
- Do not modify `src/wbsb/pipeline.py` or `src/wbsb/render/llm_adapter.py`.
- Do not modify `src/wbsb/domain/models.py`.
- Do not raise on `comment` truncation — silently truncate.
- Do not use `except: pass` anywhere.
- Do not import from `wbsb.eval` inside `wbsb.feedback`.

---

## Tests Required

Create `tests/test_feedback.py` with exactly these 8 test functions.

Use `tmp_path` and monkeypatch `store.FEEDBACK_DIR` to isolate file writes.

#### `test_save_feedback_valid`
Saves a valid entry, verifies the file exists at the expected path, and the loaded JSON matches.

#### `test_save_feedback_invalid_run_id`
Passes a `run_id` that does not match the regex. Asserts `ValueError` is raised.

#### `test_save_feedback_invalid_section`
Passes a `section` not in `VALID_SECTIONS`. Asserts `ValueError` is raised.

#### `test_save_feedback_invalid_label`
Passes a `label` not in `VALID_LABELS`. Asserts `ValueError` is raised.

#### `test_save_feedback_comment_truncated`
Passes a `comment` of 1500 chars. Asserts saved entry has `comment` of exactly 1000 chars.
Asserts no exception is raised.

#### `test_list_feedback_sorted`
Saves 3 entries with different `submitted_at` values. Calls `list_feedback()`.
Asserts entries returned newest-first (`submitted_at` descending).

#### `test_summarize_feedback_counts`
Saves 2 entries with label `"expected"`, 1 with `"unexpected"`.
Calls `summarize_feedback()`. Asserts `total == 3`, `by_label["expected"] == 2`,
`by_label["unexpected"] == 1`, `by_label["incorrect"] == 0`.
All section and label keys must be present in the dict even with 0 count.

#### `test_export_feedback_by_run_id`
Saves 3 entries — 2 with `run_id = "A"`, 1 with `run_id = "B"`.
Calls `export_feedback("A")`. Asserts exactly 2 entries returned, all with `run_id == "A"`.

---

## Definition of Done

Before marking the PR ready for review, confirm:

```bash
pytest --tb=short -q
# Expected: 320 passing (312 existing + 8 new), 0 failures

ruff check .
# Expected: no issues

# Verify CLI works
wbsb feedback summary
# Expected: prints summary with 0 counts (no feedback saved yet)

git diff --name-only feature/iteration-7
# Expected:
# .gitignore
# feedback/.gitkeep
# src/wbsb/cli.py
# src/wbsb/feedback/store.py
# tests/test_feedback.py
```

---

## Commit and PR

```bash
git add src/wbsb/feedback/store.py src/wbsb/cli.py \
        .gitignore feedback/.gitkeep tests/test_feedback.py

git commit -m "$(cat <<'EOF'
feat(feedback): add feedback storage + wbsb feedback CLI

Adds store.py with save/list/summarize/export functions; validates run_id
regex, section, and label on save; silently truncates comment at 1000
chars; generates feedback_id via uuid4 if not provided. Adds wbsb
feedback list/summary/export commands. feedback/ dir gitignored.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-7-feedback-system
gh pr ready
```
