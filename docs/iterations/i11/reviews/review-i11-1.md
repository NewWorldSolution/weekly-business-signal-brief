# WBSB Review Prompt — I11-1: HMAC Verification + Timestamp Check

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-1 strictly against `docs/iterations/i11/tasks.md`.
This is a security-critical task. Apply strict scrutiny to every cryptographic operation.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-1 implements HMAC-SHA256 signature verification and timestamp freshness checking in `src/wbsb/feedback/auth.py`.

**Security surface:** These functions are the primary authentication layer for the feedback webhook. A timing vulnerability in `verify_hmac` could allow signature forgery by oracle. Failure to return `False` (instead of raising) could expose internal state. Missing boundary cases could create an authentication bypass.

---

## Task Under Review

- Task: I11-1 — HMAC Verification + Timestamp Check
- Branch: `feature/i11-1-hmac-auth`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/feedback/auth.py` (modify — implement `verify_hmac` and `verify_timestamp`)
- `tests/test_feedback_auth.py` (create)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-1-hmac-auth
git pull origin feature/i11-1-hmac-auth
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

Allowed: `src/wbsb/feedback/auth.py`, `tests/test_feedback_auth.py`.

Forbidden: `src/wbsb/feedback/server.py`, `src/wbsb/feedback/ratelimit.py`, `src/wbsb/observability/`, `src/wbsb/cli.py`, `Dockerfile`.

### Step 4 — Timing attack check (critical)

```bash
grep -n "compare_digest" src/wbsb/feedback/auth.py
```

**Must find at least one occurrence.** If `hmac.compare_digest` is NOT used — or if a regular `==` comparison is used for signature comparison — this is a `CRITICAL` finding. Timing attacks allow an attacker to determine how many characters of a signature are correct, eventually reconstructing the full HMAC secret.

### Step 5 — Fail-closed check

```bash
grep -n "except\|try:" src/wbsb/feedback/auth.py
```

Verify `verify_hmac` has a broad `except Exception` (or similar) that catches all exceptions and returns `False` — never raises. Malformed input (bad encoding, wrong types) must produce `False`, not an unhandled exception that could expose error information.

### Step 6 — Signing string check

```bash
grep -n "signing_string\|timestamp.*body\|f\"{timestamp}" src/wbsb/feedback/auth.py
```

Verify signing string is constructed as: `f"{timestamp}.{body.decode('utf-8')}"` — this exact format must match the client side.

### Step 7 — `verify_timestamp` boundary check

```bash
grep -n "abs\|max_age\|300" src/wbsb/feedback/auth.py
```

Verify:
- `abs(time.time() - int(timestamp)) <= max_age_seconds`
- Default `max_age_seconds = 300` (not hardcoded 300 — must be a parameter with default)
- Returns `False` on non-integer input without raising

### Step 8 — `NonceStore` unchanged

```bash
grep -n "NotImplementedError" src/wbsb/feedback/auth.py
```

`NonceStore.check_and_record` must still raise `NotImplementedError` (it is I11-2's job).

### Step 9 — Test presence check

```bash
grep -n "^def test_" tests/test_feedback_auth.py
```

Required tests:
- `test_verify_hmac_valid`
- `test_verify_hmac_wrong_secret`
- `test_verify_hmac_tampered_body`
- `test_verify_hmac_tampered_timestamp`
- `test_verify_hmac_malformed_signature`
- `test_verify_hmac_empty_body`
- `test_verify_timestamp_fresh`
- `test_verify_timestamp_at_boundary`
- `test_verify_timestamp_expired`
- `test_verify_timestamp_future`
- `test_verify_timestamp_non_integer`

### Step 10 — No hardcoded signature check

```bash
grep -n "abc123\|deadbeef\|[0-9a-f]\{64\}" tests/test_feedback_auth.py
```

Tests must compute real HMAC signatures using `hmac.new(...)` — not use hardcoded hex strings that might silently pass or fail for the wrong reasons.

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

## Acceptance Criteria Checklist

- [ ] `verify_hmac` returns `True` for valid signature
- [ ] `verify_hmac` returns `False` for wrong secret
- [ ] `verify_hmac` returns `False` for tampered body
- [ ] `verify_hmac` returns `False` for tampered timestamp
- [ ] `verify_hmac` returns `False` for malformed signature (no raise)
- [ ] `hmac.compare_digest` used — confirmed by grep
- [ ] `verify_hmac` never raises — broad except returns `False`
- [ ] Signing string format: `f"{timestamp}.{body.decode('utf-8')}"`
- [ ] `verify_timestamp` returns `True` within ±300s
- [ ] `verify_timestamp` returns `False` for non-integer input (no raise)
- [ ] `verify_timestamp` boundary: exactly 300s → `True`; 301s → `False`
- [ ] `NonceStore.check_and_record` still raises `NotImplementedError`
- [ ] All 11 required tests present
- [ ] No hardcoded hex signatures in tests
- [ ] No `except: pass` anywhere
- [ ] All baseline tests pass
- [ ] Ruff clean
- [ ] Only allowed files modified
