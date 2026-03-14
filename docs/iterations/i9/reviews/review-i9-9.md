# WBSB Comprehensive Review Prompt — I9-9: Architecture Review

---

## Reviewer Role & Mandate

You are an independent architecture reviewer for WBSB.
All tasks I9-0 through I9-8 are assumed merged into `feature/iteration-9`.
This is the final architecture gate before I9-10 cleanup.

You must verify end-to-end deployment and delivery architecture integrity.
Do not fix code. Report findings with evidence.

Verdict options:
- `PASS`
- `CHANGES REQUIRED`
- `BLOCKED`

---

## Architecture Principles to Enforce

1. Pipeline produces artifacts; delivery reads artifacts.
2. Scheduler decides run/no-run; does not send Teams/Slack directly.
3. Delivery must be idempotent (`wbsb deliver --run-id` re-delivery path).
4. No silent failures (`except: pass` forbidden).
5. Secrets never hardcoded or logged at INFO.
6. Feedback webhook validates inputs and writes safely.

---

## Review Execution Steps

### Step 1 — Checkout iteration branch

```bash
git fetch origin
git checkout feature/iteration-9
git pull origin feature/iteration-9
```

### Step 2 — Full suite + lint

```bash
pytest --tb=short -q
ruff check .
```

### Step 3 — Pipeline isolation check

```bash
grep -n "delivery\|deliver\|DeliveryResult\|teams\|slack" src/wbsb/pipeline.py
```

Expected: no delivery coupling in pipeline internals.

### Step 4 — Delivery orchestrator contract check

```bash
python3 -c "from wbsb.delivery.orchestrator import load_run_artifacts, deliver_run; import inspect; print(inspect.signature(load_run_artifacts)); print(inspect.signature(deliver_run))"
```

Verify orchestrator is artifact-reader and non-raising dispatcher.

### Step 5 — Scheduler boundary check

```bash
grep -n "send_teams\|send_slack\|deliver_run\|webhook" src/wbsb/scheduler/*.py
```

Expected: no direct channel delivery calls in scheduler.

### Step 6 — Path traversal, file size guard, and safe file checks

```bash
grep -n "resolve\|Path outside watch directory\|startswith\|MAX_INPUT_BYTES\|st_size\|too_large\|oversized" src/wbsb/scheduler/auto.py
grep -n "uuid\|feedback/\|run_id" src/wbsb/feedback/server.py
```

Verify:
- traversal guard in scheduler (`resolved.startswith(watch_resolved)` or equivalent)
- oversized file guard in scheduler (files exceeding safe threshold skipped with warning, not passed to pipeline)
- input-independent feedback file paths (UUID only)

### Step 7 — Security checks (secrets/logging)

```bash
grep -rn "ANTHROPIC_API_KEY\s*=" src/ config/
grep -rn "TEAMS_WEBHOOK_URL\s*=\s*[\"'][^$]" src/ config/
grep -rn "SLACK_WEBHOOK_URL\s*=\s*[\"'][^$]" src/ config/
grep -rn "webhook_url" src/wbsb/ | grep -v "log\.error\|log\.debug\|#\|\.yaml\|test_"
```

Expected: env-based reads only, no hardcoded secret values, no webhook URL appearing in info/warning/print-level output.

### Step 8 — Docker/security hardening checks

```bash
docker build -t wbsb-i9-review .
docker run --rm wbsb-i9-review wbsb --help
docker run --rm wbsb-i9-review ls -la | grep ".env"
```

Expected: image works; `.env` absent from image.

### Step 9 — Delivery CLI checks

```bash
wbsb deliver --help
wbsb run --help | grep -- "--deliver\|--auto"
```

Verify delivery/scheduler flags are wired in CLI.

### Step 10 — End-to-end run checks

Run deterministic + delivery path:

```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode off
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode off --deliver
```

Expected: no crash; delivery either succeeds or reports skipped when targets disabled.

### Step 11 — Golden + feedback CLI checks

```bash
wbsb eval
wbsb feedback summary
wbsb feedback list
```

Expected: all commands run without error.

### Step 12 — Feedback webhook validation checks

```bash
python3 -c "from wbsb.feedback.server import RUN_ID_PATTERN, VALID_SECTIONS, VALID_LABELS; print(RUN_ID_PATTERN.pattern); print(sorted(VALID_SECTIONS)); print(sorted(VALID_LABELS))"
```

Verify regex and allowlists exist and match task contract.

### Step 13 — Silent failure scan

```bash
grep -rn "except.*pass\|except:$" src/wbsb/delivery src/wbsb/scheduler src/wbsb/feedback
```

Expected: no silent failure patterns.

### Step 14 — Scope sanity of iteration branch

```bash
git diff --name-only main...feature/iteration-9
```

Review for unexpected modules outside I9 scope.

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
- severity: critical | major | minor
- file: path:line
- exact problem
- why it matters
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check (PASS/FAIL per line)
7. Exact Fixes Required
8. Final Recommendation (`approve for I9-10 | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] Pipeline has no delivery coupling
- [ ] Scheduler has no direct Teams/Slack delivery calls
- [ ] Scheduler path traversal guard implemented and tested
- [ ] Scheduler oversized file guard implemented and tested
- [ ] `--auto` mode does NOT trigger delivery (delivery is I9-5 responsibility)
- [ ] Orchestrator reads artifacts and dispatches safely
- [ ] `wbsb deliver --run-id` path available
- [ ] `--auto` scheduler mode available in CLI
- [ ] Feedback webhook validates run_id/section/label
- [ ] Feedback path handling is safe (no user-derived file paths)
- [ ] No secret hardcoding anywhere in source or config
- [ ] No webhook URL logging at info, warning, or debug level
- [ ] Docker image builds and excludes `.env`
- [ ] End-to-end run with `--deliver` does not crash
- [ ] `wbsb eval` still passes
- [ ] feedback CLI commands operational
- [ ] no silent failure patterns
- [ ] tests pass
- [ ] ruff clean
