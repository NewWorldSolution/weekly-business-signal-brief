# WBSB Review Prompt — I9-3: Slack Block Kit Builder

---

## Reviewer Role & Mandate

You are an independent reviewer for WBSB.
Review I9-3 implementation strictly against `docs/iterations/i9/tasks.md`.
Do not fix code.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Task Under Review

- Task: I9-3 — Slack Block Kit Builder
- Branch: `feature/i9-3-slack-adapter`
- Base: `feature/iteration-9`

Allowed files:
- `src/wbsb/delivery/slack.py`
- `tests/test_delivery_slack.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-3-slack-adapter
git pull origin feature/i9-3-slack-adapter
```

### Step 2 — Validate

```bash
pytest --tb=short -q
ruff check .
```

If fail -> `CHANGES REQUIRED`.

### Step 3 — Scope

```bash
git diff --name-only feature/iteration-9
```

Must contain only allowed files.

### Step 4 — API contract check

```bash
python3 -c "from wbsb.delivery.slack import build_slack_blocks, send_slack_message; import inspect; print(inspect.signature(build_slack_blocks)); print(inspect.signature(send_slack_message))"
```

### Step 5 — Block contract check

Verify implementation matches tasks.md:
- header block text exact
- context includes week range + run ID
- situation or fallback banner logic correct
- signals section shows top 3 WARN by rule_id
- extras summarized as `+ N more`
- no WARN -> deterministic no-warning text
- actions omitted when feedback URL absent
- action `value` contains JSON for `{run_id, label}`

### Step 6 — Sender behavior check

Verify `send_slack_message`:
- posts `{"blocks": blocks}`
- timeout 10s
- non-2xx -> failed `DeliveryResult`
- timeout/exception -> failed `DeliveryResult`
- no uncaught exception

### Step 7 — Security checks

```bash
grep -n "webhook_url\|log\.info\|logger\.info" src/wbsb/delivery/slack.py
```

No webhook URL leakage.

### Step 8 — Test quality check

```bash
grep -n "^def test_" tests/test_delivery_slack.py
```

Confirm required tests exist and assertions verify structure/content, not only existence.

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

- [ ] `build_slack_blocks()` implemented
- [ ] `send_slack_message()` implemented
- [ ] block structure contract matched
- [ ] fallback banner behavior correct
- [ ] top-3 WARN + extras summary behavior correct
- [ ] no-warning behavior correct
- [ ] feedback actions behavior correct
- [ ] sender timeout/non-2xx/error handling correct
- [ ] only allowed files modified
- [ ] required tests present/meaningful
- [ ] tests pass
- [ ] ruff clean
