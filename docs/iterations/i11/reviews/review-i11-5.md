# WBSB Review Prompt — I11-5: Server Integration

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-5 strictly against `docs/iterations/i11/tasks.md`.
This is the highest-risk task in I11 — it wires all security guards into the live HTTP server and must not break existing feedback behaviour.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-5 wires HMAC auth, nonce replay prevention, rate limiting, observability, HTTPS enforcement, and dev bypass into `server.py`, and adds a startup secret check to `cli.py`.

**Security surface:** This task touches the entire request lifecycle. Incorrect ordering of middleware steps, wrong HTTP status codes, a broken dev bypass, or missing log events could create authentication bypasses, information leaks, or silent failures.

**Regression risk:** Happy path (valid authenticated request) must behave identically to I9. Existing tests in `test_feedback_server.py` must all still pass.

---

## Task Under Review

- Task: I11-5 — Server Integration
- Branch: `feature/i11-5-server-integration`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/feedback/server.py`
- `src/wbsb/cli.py`
- `tests/test_feedback_server.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-5-server-integration
git pull origin feature/i11-5-server-integration
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

Allowed: `src/wbsb/feedback/server.py`, `src/wbsb/cli.py`, `tests/test_feedback_server.py`.

Forbidden: `src/wbsb/feedback/auth.py`, `src/wbsb/feedback/ratelimit.py`, `src/wbsb/feedback/store.py`, `src/wbsb/pipeline.py`, `src/wbsb/domain/models.py`.

### Step 4 — Request handling order check

```bash
grep -n "rate_limit\|check.*ip\|verify_timestamp\|verify_hmac\|check_and_record\|X-Forwarded-Proto\|WBSB_REQUIRE_HTTPS" src/wbsb/feedback/server.py
```

Verify the following order in the handler (top to bottom):
1. `X-Forwarded-Proto` check (HTTPS enforcement)
2. Rate limit check → 429/503
3. Auth header presence check → 401
4. UUID4 nonce format check → 401
5. `verify_timestamp` → 401
6. `verify_hmac` → 401
7. `check_and_record` (nonce replay) → 409
8. Body validation → 400
9. Feedback storage → 200

**If rate limit check is AFTER auth headers → this allows a DoS by exhausting connections before auth is enforced. Report as major.**

### Step 5 — HTTP status code check (critical)

```bash
grep -n "401\|409\|429\|503\|400\|200" src/wbsb/feedback/server.py
```

Verify:
- Missing or invalid auth headers → `401` (not `400`)
- Nonce replay → `409` (not `401`)
- Per-IP rate limit → `429`
- Global rate limit → `503`
- `X-Forwarded-Proto: http` when `WBSB_REQUIRE_HTTPS=true` → `400`
- Body validation → `400`

**Any auth failure returning `400` instead of `401` → `CHANGES REQUIRED`.**

### Step 6 — Retry-After header check

```bash
grep -n "Retry-After" src/wbsb/feedback/server.py
```

HTTP 429 and HTTP 503 responses must include `Retry-After: 60` header.

### Step 7 — Error response format check

```bash
grep -n '\"status\".*\"error\"\|status.*error.*message' src/wbsb/feedback/server.py
```

All error responses must use the format: `{"status": "error", "message": "<user-safe string>"}`.

```bash
grep -rn "traceback\|Traceback\|stack_trace\|exc_info\|format_exc" src/wbsb/feedback/server.py
```

Must return nothing — no stack traces in server code.

### Step 8 — Observability check

```bash
grep -n "log_security_event\|EVENT_AUTH_FAILURE\|EVENT_REPLAY_DETECTED\|EVENT_RATE_LIMIT_EXCEEDED" src/wbsb/feedback/server.py
```

Verify `log_security_event` is called at every rejection point (steps 1–7). Missing log events = invisible attacks.

```bash
grep -n "comment.*log\|log.*comment" src/wbsb/feedback/server.py
```

`comment` field must NOT appear in any log call.

### Step 9 — Dev bypass check

```bash
grep -n "WBSB_ENV\|development\|dev_mode\|bypass" src/wbsb/feedback/server.py
```

Verify:
- Default is production (`os.environ.get("WBSB_ENV", "production")`)
- `development` skips steps 2–5 only (auth + nonce)
- Rate limiting still applies in dev mode

### Step 10 — Module-level state check

```bash
grep -n "_nonce_store\|_rate_limiter\|NonceStore()\|RateLimiter()" src/wbsb/feedback/server.py
```

`NonceStore` and `RateLimiter` must be instantiated at module level (not inside the request handler). Per-request instantiation resets state on every request — replay protection would not work.

### Step 11 — CLI startup check

```bash
grep -n "WBSB_FEEDBACK_SECRET\|sys.exit\|production.*secret\|secret.*required" src/wbsb/cli.py
```

Verify:
- If `WBSB_ENV != "development"` and `WBSB_FEEDBACK_SECRET` not set → `sys.exit(1)` with clear error message
- Error message mentions `WBSB_ENV=development` as the bypass

### Step 12 — Test presence check

```bash
grep -n "^def test_" tests/test_feedback_server.py
```

Required new tests (17):
- `test_post_feedback_missing_signature`
- `test_post_feedback_missing_timestamp`
- `test_post_feedback_missing_nonce`
- `test_post_feedback_malformed_nonce`
- `test_post_feedback_invalid_hmac`
- `test_post_feedback_expired_timestamp`
- `test_post_feedback_replay_nonce`
- `test_post_feedback_per_ip_rate_limit`
- `test_post_feedback_global_rate_limit`
- `test_error_response_no_stack_trace`
- `test_error_response_format`
- `test_https_required_rejects_http_proto`
- `test_https_required_allows_https_proto`
- `test_https_not_required_allows_http_proto`
- `test_dev_bypass_skips_hmac`
- `test_startup_fails_without_secret_in_prod`
- `test_startup_ok_in_dev_without_secret`
- `test_valid_authenticated_request_returns_200`

### Step 13 — All I9 tests still passing

```bash
pytest tests/test_feedback_server.py -v --tb=short
```

No I9 tests must be broken.

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

- [ ] Request handling order: X-Forwarded-Proto → rate limit → headers → timestamp → HMAC → nonce → body → storage
- [ ] Missing auth headers → HTTP 401 (not 400)
- [ ] Malformed nonce format → HTTP 401
- [ ] Invalid HMAC → HTTP 401
- [ ] Expired timestamp → HTTP 401
- [ ] Replay nonce → HTTP 409 (not 401)
- [ ] Per-IP exceeded → HTTP 429 + `Retry-After: 60`
- [ ] Global exceeded → HTTP 503 + `Retry-After: 60`
- [ ] `WBSB_REQUIRE_HTTPS=true` + `X-Forwarded-Proto: http` → HTTP 400
- [ ] All error responses: `{"status": "error", "message": "..."}`
- [ ] No `traceback` in server.py: grep returns nothing
- [ ] `log_security_event` at every rejection point
- [ ] `comment` never logged
- [ ] `_nonce_store` and `_rate_limiter` module-level (not per-request)
- [ ] `WBSB_ENV=development` → auth skipped, rate limit still applies
- [ ] `wbsb feedback serve` → `sys.exit(1)` without `WBSB_FEEDBACK_SECRET` in production
- [ ] Valid authenticated request → HTTP 200 (regression confirmed)
- [ ] All required new tests present and passing
- [ ] All I9 tests still passing
- [ ] Ruff clean
- [ ] Only allowed files modified
