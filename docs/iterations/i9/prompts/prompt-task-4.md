# Task Prompt — I9-4: Scheduler (`wbsb run --auto`)

---

## Context

You are implementing **task I9-4** of Iteration 9.
This task adds scheduler decision logic and CLI auto-run support.

**Critical boundary:** scheduler/CLI decide whether to run; pipeline internals are not modified.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Scheduler does not deliver to Teams/Slack directly. |
| 2 | No daemon process; only CLI-triggered auto mode. |
| 3 | Use I6 history index for already-processed checks. |
| 4 | Enforce path traversal guard in file discovery. |
| 5 | `src/wbsb/pipeline.py` must not be modified. |
| 6 | Open draft PR first (Step 0). |

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-4-scheduler
git push -u origin feature/i9-4-scheduler

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-4-scheduler \
  --title "I9-4: scheduler auto-run support" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

---

## Objective

Implement I9-4 exactly as defined in `docs/iterations/i9/tasks.md`:
- add scheduler module API in `src/wbsb/scheduler/auto.py`
- extend `wbsb run` in `src/wbsb/cli.py` with `--auto`
- add scheduler tests

---

## Allowed Files

```text
src/wbsb/scheduler/auto.py
src/wbsb/cli.py
tests/test_scheduler.py
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/history/store.py
```

---

## Required Public API

Implement in `src/wbsb/scheduler/auto.py` per tasks.md Scheduler Contract.
At minimum include:
- `find_latest_input(watch_dir: Path, pattern: str) -> Path | None`
- `already_processed(input_path: Path, index_path: Path) -> bool`

`already_processed` must use `derive_dataset_key()` and `runs/index.json` matching logic as specified.

---

## Execution Workflow

1. Read I9-4 section in `docs/iterations/i9/tasks.md` fully.
2. Implement scheduler module with path traversal guard:

```python
resolved = file.resolve()
watch_resolved = watch_dir.resolve()
if not str(resolved).startswith(str(watch_resolved)):
    raise ValueError(...)
```

3. Extend `wbsb run` CLI with `--auto` behavior:
   - load scheduler config
   - no new file -> INFO and exit 0
   - already processed -> INFO and exit 0
   - else run normal pipeline path
4. Add required tests from tasks.md in `tests/test_scheduler.py`.
5. Run:

```bash
pytest --tb=short -q
ruff check .
```

6. Verify scope:

```bash
git diff --name-only feature/iteration-9
```

---

## Test Requirements

Include all tests listed in tasks.md:
- `test_find_latest_input_found`
- `test_find_latest_input_no_match`
- `test_find_latest_input_empty_dir`
- `test_find_latest_input_path_traversal`
- `test_already_processed_true`
- `test_already_processed_false_new_file`
- `test_already_processed_index_absent`

No live cron/daemon tests.

---

## Acceptance Criteria

- Scheduler module API implemented.
- Path traversal guard present and tested.
- `--auto` run mode works as specified.
- Already-processed logic uses I6 index and dataset scoping.
- `pipeline.py` unchanged.
- Tests and ruff clean.

---

## Completion Checklist

- [ ] Draft PR created before edits
- [ ] Only allowed files changed
- [ ] Scheduler API implemented
- [ ] `--auto` integrated in CLI
- [ ] Required tests added and meaningful
- [ ] `pytest` passes
- [ ] `ruff check .` passes
