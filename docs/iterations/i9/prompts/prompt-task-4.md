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
| 7 | I9-4 exits after the pipeline run completes. Post-run delivery to Teams/Slack is NOT part of this task — it is wired in I9-5 via `wbsb deliver` or `wbsb run --deliver`. |
| 8 | Reject files that exceed a safe size threshold before passing to the pipeline. If a matched file is unexpectedly large, log a warning and treat the run as skipped (same as "no processable file found"), to prevent resource exhaustion from corrupt or accidental oversized inputs. |

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

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-4 section)
- `src/wbsb/history/store.py` (read only — for `derive_dataset_key`, `HistoryReader`)
- `config/delivery.yaml` (read only — for watch_directory, filename_pattern, scheduler config)
- `runs/index.json` (runtime read — for already-processed check)

### Outputs
- `src/wbsb/scheduler/auto.py` — scheduler module with `find_latest_input`, `already_processed`
- `src/wbsb/cli.py` — extended with `--auto` flag on `wbsb run`
- `tests/test_scheduler.py` — scheduler unit tests

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
2. Implement scheduler module with path traversal guard and file size check:

```python
resolved = file.resolve()
watch_resolved = watch_dir.resolve()
if not str(resolved).startswith(str(watch_resolved)):
    raise ValueError(...)
# Reject files over a safe threshold (e.g. 100 MB) with logged warning
MAX_INPUT_BYTES = 100 * 1024 * 1024
if resolved.stat().st_size > MAX_INPUT_BYTES:
    log.warning("input_file_too_large", path=str(resolved), size=resolved.stat().st_size)
    return None
```

3. Extend `wbsb run` CLI with `--auto` behavior:
   - load scheduler config
   - no new file (including oversized file rejection) -> INFO and exit 0
   - already processed -> INFO and exit 0
   - else run normal pipeline path
   - **do not trigger delivery** — I9-4 exits after pipeline run; delivery is handled by I9-5
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
- `test_find_latest_input_oversized_file_skipped`
- `test_already_processed_true`
- `test_already_processed_false_new_file`
- `test_already_processed_index_absent`

No live cron/daemon tests.

---

## Acceptance Criteria

- Scheduler module API implemented.
- Path traversal guard present and tested.
- Oversized file rejection present and tested (`test_find_latest_input_oversized_file_skipped`).
- `--auto` run mode works as specified.
- `--auto` exits after pipeline run — delivery is NOT triggered in I9-4.
- Already-processed logic uses I6 index and dataset scoping.
- `pipeline.py` unchanged.
- Tests and ruff clean.

---

## Completion Checklist

- [ ] Draft PR created before edits
- [ ] Only allowed files changed
- [ ] Scheduler API implemented
- [ ] Path traversal guard implemented and tested
- [ ] Oversized file guard implemented and tested
- [ ] `--auto` integrated in CLI (delivery NOT triggered)
- [ ] Required tests added and meaningful
- [ ] `pytest` passes
- [ ] `ruff check .` passes
