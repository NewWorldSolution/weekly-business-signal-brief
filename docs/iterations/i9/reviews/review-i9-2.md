# WBSB Review Prompt — I9-2: Teams Adaptive Card Builder

---

## Reviewer Role & Mandate

You are an independent reviewer for WBSB.
Review only I9-2 contract from `docs/iterations/i9/tasks.md`.
Do not implement fixes.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Task Under Review

- Task: I9-2 — Teams Adaptive Card Builder
- Branch: `feature/i9-2-teams-adapter`
- Base: `feature/iteration-9`

Allowed files:
- `src/wbsb/delivery/teams.py`
- `tests/test_delivery_teams.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-2-teams-adapter
git pull origin feature/i9-2-teams-adapter
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

Fail if scope drift.

### Step 4 — API contract check

```bash
python3 -c "from wbsb.delivery.teams import build_teams_card, send_teams_card; import inspect; print(inspect.signature(build_teams_card)); print(inspect.signature(send_teams_card))"
```

### Step 5 — Card structure checks

Verify in code and tests:
- Adaptive Card version `1.4`
- Metadata includes run ID, period, WARN count
- Situation uses `llm_result.situation` when available
- Fallback banner text exact match when llm_result is None/empty
- WARN signals only; sorted by `rule_id`
- No WARN -> deterministic no-warning text
- Feedback buttons omitted when feedback URL absent
- 3 feedback labels with proper payload data

### Step 6 — Sender behavior checks

Verify `send_teams_card`:
- timeout = 10s
- non-2xx -> failed `DeliveryResult`
- timeout/exception captured into failed result
- no uncaught exception

### Step 7 — Security checks

```bash
grep -n "webhook_url\|log\.info\|logger\.info" src/wbsb/delivery/teams.py
```

Verify no webhook URL exposure in logs.

### Step 8 — Required tests presence

```bash
grep -n "^def test_" tests/test_delivery_teams.py
```

Confirm required tests from tasks.md exist and assertions are meaningful.

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

- [ ] `build_teams_card()` implemented with required signature
- [ ] `send_teams_card()` implemented with required signature
- [ ] Adaptive Card structure contract respected
- [ ] fallback banner behavior correct
- [ ] WARN-only rendering, sorted by rule_id
- [ ] no-warning case handled
- [ ] feedback buttons behavior correct
- [ ] send timeout/non-2xx/error handling correct
- [ ] only allowed files modified
- [ ] required tests present and meaningful
- [ ] tests pass
- [ ] ruff clean
