# WBSB Review Prompt — I9-5: Delivery Orchestrator + `wbsb deliver`

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-5 strictly against `docs/iterations/i9/tasks.md`.
Primary invariant: pipeline remains delivery-agnostic; pipeline.py must not be touched.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure.

**Architecture invariant:** the pipeline produces artifacts (in `runs/{run_id}/`); the delivery orchestrator reads those artifacts from disk. The pipeline never imports from `wbsb.delivery`. Delivery must be idempotent — re-running `wbsb deliver --run-id` with the same ID must produce the same outcome.

**Failure handling:** `deliver_run()` must never raise. Per-target failures are captured in `DeliveryResult`. Delivery failure must not crash the `wbsb run` command.

---

## Task Under Review

- Task: I9-5 — Delivery Orchestrator + `wbsb deliver` CLI
- Branch: `feature/i9-5-cli-integration`
- Base: `feature/iteration-9`

Expected files in scope:
- `src/wbsb/delivery/orchestrator.py`
- `src/wbsb/cli.py`
- `tests/test_delivery_orchestrator.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-5-cli-integration
git pull origin feature/i9-5-cli-integration
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

Allowed: `src/wbsb/delivery/orchestrator.py`, `src/wbsb/cli.py`, `tests/test_delivery_orchestrator.py`.

### Step 4 — Pipeline isolation check (critical)

```bash
git diff feature/iteration-9 -- src/wbsb/pipeline.py src/wbsb/delivery/teams.py src/wbsb/delivery/slack.py
```

Expected: **no diffs**. If pipeline.py is touched: `BLOCKED`.

```bash
grep -n "delivery\|deliver\|DeliveryResult\|teams\|slack" src/wbsb/pipeline.py
```

Expected: no delivery coupling in pipeline internals (pre-existing or introduced).

### Step 5 — Orchestrator API check

```bash
python3 -c "from wbsb.delivery.orchestrator import load_run_artifacts, deliver_run; import inspect; print(inspect.signature(load_run_artifacts)); print(inspect.signature(deliver_run))"
```

Verify signatures match tasks.md contract.

### Step 6 — Artifact loading behavior check

Verify in code and tests:
- `findings.json` and `manifest.json` required — `FileNotFoundError` raised if absent
- `llm_response.json` optional — `llm_result=None` when absent
- `llm_result=None` triggers fallback banner in card/block builders

### Step 7 — Non-raising delivery dispatch check

```bash
grep -n "except\|raise" src/wbsb/delivery/orchestrator.py
```

Verify: per-target failures captured in `DeliveryResult`; no uncaught exception from `deliver_run()`.

### Step 8 — CLI integration check

```bash
wbsb deliver --help
wbsb run --help | grep -- "--deliver"
```

Both flags must be present. `--deliver` failure must not crash `wbsb run`.

### Step 9 — Test presence check

```bash
grep -n "^def test_" tests/test_delivery_orchestrator.py
```

Required tests (from tasks.md):
- `test_load_run_artifacts_success`
- `test_load_run_artifacts_no_llm_response`
- `test_load_run_artifacts_missing_findings`
- `test_deliver_run_teams_only`
- `test_deliver_run_both_targets`
- `test_deliver_run_no_targets`
- `test_deliver_run_failure_captured`
- `test_deliver_run_llm_fallback_flag`

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

- [ ] orchestrator API (`load_run_artifacts`, `deliver_run`) implemented as specified
- [ ] delivery reads artifacts from `runs/{run_id}/`; no direct pipeline coupling
- [ ] `pipeline.py` untouched (zero diff)
- [ ] `wbsb deliver --run-id` command added
- [ ] `wbsb run --deliver` flag added at CLI layer only
- [ ] fallback behavior wired (llm_result=None when llm_response.json absent)
- [ ] delivery failure does not crash `wbsb run`
- [ ] `deliver_run()` never raises
- [ ] only allowed files modified
- [ ] required tests present and strong
- [ ] tests pass
- [ ] ruff clean
