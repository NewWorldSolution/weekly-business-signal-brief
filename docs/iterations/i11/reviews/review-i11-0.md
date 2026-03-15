# WBSB Review Prompt — I11-0: Pre-Work, Docs, and Frozen Contract Scaffolding

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-0 strictly against `docs/iterations/i11/tasks.md`.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-0 is the scaffolding task for the Security Hardening iteration. It creates stub files that downstream Codex tasks depend on, updates environment variable documentation, and creates the security threat model.

**Critical:** `src/wbsb/observability/logging.py` is an existing production file and must be unchanged. The stub files are `auth.py` and `ratelimit.py` in `src/wbsb/feedback/`. Any modification to `observability/logging.py` is a scope violation.

---

## Task Under Review

- Task: I11-0 — Pre-Work: Docs + Frozen Contract Scaffolding
- Branch: `feature/i11-0-pre-work`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/feedback/auth.py` (create)
- `src/wbsb/feedback/ratelimit.py` (create)
- `.env.example` (update)
- `docs/project/project-iterations.md` (update)
- `docs/project/TASKS.md` (update)
- `docs/deployment/security.md` (create)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-0-pre-work
git pull origin feature/i11-0-pre-work
```

### Step 2 — Run validation

```bash
pytest --tb=short -q
ruff check .
```

If either fails: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-11
```

Allowed: `src/wbsb/feedback/auth.py`, `src/wbsb/feedback/ratelimit.py`, `.env.example`, `docs/project/project-iterations.md`, `docs/project/TASKS.md`, `docs/deployment/security.md`.

Forbidden: `src/wbsb/observability/logging.py`, `src/wbsb/feedback/server.py`, `src/wbsb/feedback/store.py`, `src/wbsb/cli.py`, `Dockerfile`, `pyproject.toml`, any test file.

**Any change to `src/wbsb/observability/logging.py` → `BLOCKED`.**

### Step 4 — Stub imports check

```bash
python -c "from wbsb.feedback.auth import verify_hmac, verify_timestamp, NonceStore; print('auth OK')"
python -c "from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome; print('ratelimit OK')"
```

Both must succeed without ImportError.

### Step 5 — Stub correctness check

```bash
grep -n "NotImplementedError" src/wbsb/feedback/auth.py
grep -n "NotImplementedError" src/wbsb/feedback/ratelimit.py
```

Verify:
- `verify_hmac`, `verify_timestamp`, and `NonceStore.check_and_record` all raise `NotImplementedError`
- `RateLimiter.check` raises `NotImplementedError`

### Step 6 — Header constants check

```bash
grep -n "HEADER_TIMESTAMP\|HEADER_SIGNATURE\|HEADER_NONCE" src/wbsb/feedback/auth.py
```

Verify all three constants are defined with correct values:
- `HEADER_TIMESTAMP = "X-WBSB-Timestamp"`
- `HEADER_SIGNATURE = "X-WBSB-Signature"`
- `HEADER_NONCE = "X-WBSB-Nonce"`

### Step 7 — `RateLimitOutcome` enum check

```bash
grep -n "RateLimitOutcome\|allowed\|per_ip_exceeded\|global_exceeded" src/wbsb/feedback/ratelimit.py
```

Verify all three enum values are present with correct string values.

### Step 8 — `.env.example` check

```bash
grep -n "WBSB_FEEDBACK_SECRET\|WBSB_ENV\|WBSB_REQUIRE_HTTPS" .env.example
```

All three must be present with comments explaining each variable.

### Step 9 — Security docs check

```bash
cat docs/deployment/security.md
```

Verify:
- Threat model table exists (at minimum 5 rows)
- Each row has: threat, control, task reference
- Scope boundaries documented

### Step 10 — Observability module unchanged

```bash
git diff feature/iteration-11 -- src/wbsb/observability/logging.py
```

Must return empty diff (no changes).

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. Scope Violations
5. Acceptance Criteria Check (`[PASS]` or `[FAIL]` per line)
6. Exact Fixes Required
7. Final Recommendation (`approve | request changes | block`)

---

## Acceptance Criteria Checklist

- [ ] `from wbsb.feedback.auth import verify_hmac, verify_timestamp, NonceStore` — no ImportError
- [ ] `from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome` — no ImportError
- [ ] All stubs raise `NotImplementedError` when called
- [ ] `HEADER_TIMESTAMP`, `HEADER_SIGNATURE`, `HEADER_NONCE` constants correct
- [ ] `RateLimitOutcome` enum has `allowed`, `per_ip_exceeded`, `global_exceeded`
- [ ] `.env.example` has `WBSB_FEEDBACK_SECRET`, `WBSB_ENV`, `WBSB_REQUIRE_HTTPS` with comments
- [ ] `docs/deployment/security.md` exists with threat model table
- [ ] `src/wbsb/observability/logging.py` unchanged
- [ ] All 391 existing tests pass
- [ ] Ruff clean
- [ ] Only allowed files modified
