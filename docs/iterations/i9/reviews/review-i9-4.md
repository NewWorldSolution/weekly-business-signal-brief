# WBSB Review Prompt — I9-4: Scheduler (`wbsb run --auto`)

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-4 strictly against `docs/iterations/i9/tasks.md`.
Focus: scheduler boundaries, path safety, file size guard, already-processed logic, delivery boundary.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure.

**Scheduler architecture invariant:** the scheduler decides whether to trigger a pipeline run. It does NOT deliver to Teams or Slack directly. After a successful `--auto` run the pipeline exits; delivery is handled separately in I9-5 via `wbsb deliver` or `wbsb run --deliver`.

**Security requirement:** `find_latest_input` must enforce a path traversal guard AND reject files exceeding the safe size threshold (100 MB) with a warning and skip, to prevent resource exhaustion.

---

## Task Under Review

- Task: I9-4 — Scheduler (`wbsb run --auto`)
- Branch: `feature/i9-4-scheduler`
- Base: `feature/iteration-9`

Expected files in scope:
- `src/wbsb/scheduler/auto.py`
- `src/wbsb/cli.py`
- `tests/test_scheduler.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-4-scheduler
git pull origin feature/i9-4-scheduler
```

### Step 2 — Run validation

```bash
pytest --tb=short -q
ruff check .
```

If either fails: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-9
```

Allowed: `src/wbsb/scheduler/auto.py`, `src/wbsb/cli.py`, `tests/test_scheduler.py`.

### Step 4 — Protected file boundary check

```bash
git diff feature/iteration-9 -- src/wbsb/pipeline.py src/wbsb/history/store.py
```

Expected: no changes to either file.

### Step 5 — Path traversal and file size guard check

```bash
grep -n "resolve\|startswith\|Path outside watch directory\|MAX_INPUT_BYTES\|st_size\|too_large\|oversized" src/wbsb/scheduler/auto.py
```

Verify:
- traversal guard: `resolved.startswith(watch_resolved)` or equivalent
- size guard: file exceeding threshold is rejected with logged warning, not passed to pipeline
- both conditions result in a clean skip (no exception propagation to CLI)

### Step 6 — Already-processed and index logic check

```bash
grep -n "derive_dataset_key\|index.json\|HistoryReader\|already_processed" src/wbsb/scheduler/auto.py
```

Verify dataset-scoped already-processed check using I6 history index.

### Step 7 — Delivery boundary check

```bash
grep -n "deliver\|send_teams\|send_slack\|DeliveryResult\|orchestrator" src/wbsb/scheduler/auto.py src/wbsb/cli.py | grep -v "import\|#"
```

Expected: no delivery calls inside scheduler module. `--auto` mode in CLI must not invoke delivery.

### Step 8 — CLI integration check

```bash
wbsb run --help | grep -- "--auto"
```

### Step 9 — Test presence and coverage check

```bash
grep -n "^def test_" tests/test_scheduler.py
```

Required tests (per tasks.md + security additions):
- `test_find_latest_input_found`
- `test_find_latest_input_no_match`
- `test_find_latest_input_empty_dir`
- `test_find_latest_input_path_traversal`
- `test_find_latest_input_oversized_file_skipped`
- `test_already_processed_true`
- `test_already_processed_false_new_file`
- `test_already_processed_index_absent`

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check (`[PASS]` or `[FAIL]` per line)
7. Exact Fixes Required
8. Final Recommendation (`approve | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] scheduler API (`find_latest_input`, `already_processed`) exists and is importable
- [ ] path traversal guard implemented and tested
- [ ] oversized file rejection implemented and tested
- [ ] already-processed logic uses dataset scoping and I6 index
- [ ] `--auto` integrated into CLI
- [ ] `--auto` does NOT trigger delivery (delivery is I9-5's responsibility)
- [ ] no pipeline/history module modifications
- [ ] only allowed files modified
- [ ] all required tests present and meaningful
- [ ] tests pass
- [ ] ruff clean
