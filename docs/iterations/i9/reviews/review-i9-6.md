# WBSB Review Prompt — I9-6: Failure Alerting Path

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-6 strictly against `docs/iterations/i9/tasks.md`.
Validate all three alert scenarios and non-raising dispatch behavior.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure.

**Alerting scope:** I9-6 adds failure-state delivery alerts (LLM fallback, pipeline error, no-new-file). These are delivery-level concerns only — no pipeline logic is changed. Alert dispatch must never crash the CLI flow; all failures are captured and logged.

**Scheduler file note:** `src/wbsb/scheduler/auto.py` was created in I9-4 as the canonical file discovery module and must not be modified here. `src/wbsb/scheduler/watcher.py` is a new, separate file introduced in I9-6 for the no-new-file alert path only. Both files may coexist in the scheduler package.

---

## Task Under Review

- Task: I9-6 — Failure Alerting Path
- Branch: `feature/i9-6-failure-alerting`
- Base: `feature/iteration-9`

Expected files in scope:
- `src/wbsb/delivery/alerts.py`
- `src/wbsb/scheduler/watcher.py` ← new alerting helper; must not modify `auto.py`
- `src/wbsb/cli.py`
- `tests/test_delivery_alerts.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-6-failure-alerting
git pull origin feature/i9-6-failure-alerting
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

Allowed: `src/wbsb/delivery/alerts.py`, `src/wbsb/scheduler/watcher.py`, `src/wbsb/cli.py`, `tests/test_delivery_alerts.py`.

### Step 4 — Protected file boundary check

```bash
git diff feature/iteration-9 -- src/wbsb/pipeline.py src/wbsb/delivery/teams.py src/wbsb/delivery/slack.py src/wbsb/scheduler/auto.py
```

Expected: **no diffs**. If `auto.py` is modified: `BLOCKED`.

### Step 5 — Alert API check

```bash
python3 -c "from wbsb.delivery.alerts import build_pipeline_error_alert, build_no_file_alert, send_alert; import inspect; print(inspect.signature(build_pipeline_error_alert)); print(inspect.signature(build_no_file_alert)); print(inspect.signature(send_alert))"
```

Verify signatures match tasks.md contract.

### Step 6 — Three scenario coverage check

Verify in code and tests:
- **LLM fallback alert**: triggered when `llm_result` is None / fallback state
- **Pipeline error alert**: triggered on pipeline exception; includes `error` message and `run_id`
- **No-new-file alert**: triggered when scheduler finds no processable file

### Step 7 — Non-raising dispatch check

```bash
grep -n "except.*pass\|raise" src/wbsb/delivery/alerts.py
```

`send_alert` must never raise. Failures must be captured and returned/logged.

### Step 8 — CLI visible output check

Verify CLI emits visible warning (stdout/stderr) for each alert scenario, in addition to any dispatch attempt.

### Step 9 — Test presence check

```bash
grep -n "^def test_" tests/test_delivery_alerts.py
```

Required tests:
- `test_pipeline_error_alert_structure`
- `test_no_file_alert_structure`
- `test_send_alert_non_raising`
- `test_send_alert_skipped_when_disabled`

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

- [ ] alert builder APIs (`build_pipeline_error_alert`, `build_no_file_alert`, `send_alert`) implemented
- [ ] all three alert scenarios implemented
- [ ] `send_alert` dispatch is non-raising
- [ ] CLI emits visible warnings for alert scenarios
- [ ] `auto.py` not modified (scheduler file boundary respected)
- [ ] `watcher.py` is a new file (not a rename of `auto.py`)
- [ ] only allowed files modified
- [ ] required tests present and meaningful
- [ ] tests pass
- [ ] ruff clean
