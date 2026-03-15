# WBSB Task Prompt — I11-5: Server Integration

---

## Context

You are implementing **I11-5** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-5 wires all security guards into `server.py` and adds the startup secret check to `cli.py`.

**Prerequisites:** I11-2, I11-3, and I11-4 must all be merged. The modules `auth.py` (with `NonceStore`), `ratelimit.py`, and the security observability helpers are all available and tested.

**Owner:** Claude (this task requires architectural judgment — error response format consistency, dev bypass logic, understanding of the full request lifecycle).

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Stdlib only for cryptography — `hmac`, `hashlib`, `secrets`, `time` |
| Rule 2 | Never log: secret, signature, full nonce, request body, comment |
| Rule 3 | Fail closed: unexpected exception in auth verification → 401 |
| Rule 4 | Every rejection at steps 1–5 must emit a structured log event via `log_security_event` |
| Rule 5 | Happy path (valid authenticated request) behaviour is identical to I9 — no regressions |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
git checkout feature/iteration-11
git pull origin feature/iteration-11
git checkout -b feature/i11-5-server-integration
git push -u origin feature/i11-5-server-integration

pytest && ruff check .
git commit --allow-empty -m "chore(i11-5): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-5-server-integration \
  --title "I11-5: Wire auth, rate limit, observability into server.py" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Modify `src/wbsb/feedback/server.py` to enforce the full security request handling pipeline. Add a startup secret check to `src/wbsb/cli.py`. Extend `tests/test_feedback_server.py` with auth, rate limit, and error format tests.

---

## Request Handling Order (`POST /feedback`)

Implement these steps in this exact order:

```
Step 0 — X-Forwarded-Proto check
  If WBSB_REQUIRE_HTTPS=true AND X-Forwarded-Proto header present AND value is "http":
    → HTTP 400: {"status": "error", "message": "HTTPS required"}

Step 1 — Rate limit check
  Call RateLimiter.check(source_ip)
  per_ip_exceeded → HTTP 429 + Retry-After: 60
  global_exceeded → HTTP 503 + Retry-After: 60
  Log: log_security_event(EVENT_RATE_LIMIT_EXCEEDED, ...)

Step 2 — Parse auth headers
  Check presence of: X-WBSB-Timestamp, X-WBSB-Signature, X-WBSB-Nonce
  Any missing → HTTP 401: {"status": "error", "message": "Authentication required"}
  X-WBSB-Nonce present but not valid UUID4 format → HTTP 401
  Log: log_security_event(EVENT_AUTH_FAILURE, reason="missing_headers" or "malformed_nonce")

Step 3 — Timestamp freshness
  Call verify_timestamp(timestamp)
  False → HTTP 401: {"status": "error", "message": "Authentication required"}
  Log: log_security_event(EVENT_AUTH_FAILURE, reason="expired_timestamp")

Step 4 — HMAC verification
  Call verify_hmac(body, timestamp, signature, secret)
  False → HTTP 401: {"status": "error", "message": "Authentication required"}
  Log: log_security_event(EVENT_AUTH_FAILURE, reason="invalid_hmac")

Step 5 — Nonce replay check
  Call NonceStore.check_and_record(nonce)
  False (replay) → HTTP 409: {"status": "error", "message": "Request already processed"}
  Log: log_security_event(EVENT_REPLAY_DETECTED, ...)

Step 6 — Existing body validation (unchanged from I9)
  Invalid run_id / section / label → HTTP 400
  Log: log_security_event(EVENT_INVALID_INPUT, ...)

Step 7 — Feedback storage (unchanged from I9)
  Success → HTTP 200
  Log: log_security_event(EVENT_FEEDBACK_RECEIVED, run_id=..., section=..., label=...)
```

**HTTP status code rationale:**
- 401 for all auth failures (steps 2–4) — standard semantics for unauthenticated requests
- 409 for replay (step 5) — authenticated but conflicts with prior request; 401 would be misleading
- 400 for malformed body (step 6) and HTTPS violation (step 0)
- 429/503 for rate limiting (step 1)

---

## Dev Bypass

When `WBSB_ENV=development` (env var):
- Skip steps 2–5 (auth + nonce)
- Rate limiting still applies
- Default is production (bypass requires explicit opt-in)

```python
import os
dev_mode = os.environ.get("WBSB_ENV", "production") == "development"
```

---

## Error Response Sanitization

**Replace all existing error responses in `server.py`** with the frozen format:
```json
{"status": "error", "message": "<user-safe string>"}
```

No exception messages, stack traces, file paths, module names, or Python version must appear in any HTTP response body. This applies to all error paths including unexpected exceptions (wrap entire handler in broad except → HTTP 500 with generic message).

---

## Shared Module-Level State

`NonceStore` and `RateLimiter` must be instantiated once at module level (not per-request). Instantiating per-request would reset their state on every call, making them useless.

```python
# At module level in server.py
from wbsb.feedback.auth import NonceStore, verify_hmac, verify_timestamp, HEADER_TIMESTAMP, HEADER_SIGNATURE, HEADER_NONCE
from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome
from wbsb.observability.logging import (
    log_security_event, pseudonymize_ip,
    EVENT_AUTH_FAILURE, EVENT_REPLAY_DETECTED, EVENT_RATE_LIMIT_EXCEEDED,
    EVENT_FEEDBACK_RECEIVED, EVENT_INVALID_INPUT,
)

_nonce_store = NonceStore()
_rate_limiter = RateLimiter()
```

---

## UUID4 Nonce Validation

To check if a nonce is a valid UUID4:
```python
import re
_UUID4_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE,
)
```

---

## `src/wbsb/cli.py` — Startup Check

In the `wbsb feedback serve` command handler, before starting the server:

```python
import os, sys

wbsb_env = os.environ.get("WBSB_ENV", "production")
secret = os.environ.get("WBSB_FEEDBACK_SECRET", "")

if wbsb_env != "development" and not secret:
    print(
        "Error: WBSB_FEEDBACK_SECRET is required in production mode. "
        "Set WBSB_ENV=development to bypass.",
        file=sys.stderr,
    )
    sys.exit(1)

# Log startup state (never log the secret value)
log_security_event(
    "server_starting",
    env=wbsb_env,
    hmac_enabled=(wbsb_env != "development"),
    https_required=(os.environ.get("WBSB_REQUIRE_HTTPS", "") == "true"),
)
```

---

## Required Tests (extend `tests/test_feedback_server.py`)

All tests must use the test client pattern established in existing tests. Use environment variable patching (`monkeypatch` or `unittest.mock.patch.dict`) for secret/env configuration.

```python
# Auth rejection — missing headers (all → 401)
def test_post_feedback_missing_signature():
def test_post_feedback_missing_timestamp():
def test_post_feedback_missing_nonce():
def test_post_feedback_malformed_nonce():  # not UUID4 format → 401

# Auth rejection — invalid values (all → 401)
def test_post_feedback_invalid_hmac():       # wrong signature → 401
def test_post_feedback_expired_timestamp():  # >300s ago → 401

# Replay (409, not 401)
def test_post_feedback_replay_nonce():

# Rate limits
def test_post_feedback_per_ip_rate_limit():  # 14th request → 429 + Retry-After header
def test_post_feedback_global_rate_limit():  # 101st request → 503 + Retry-After header

# Error response format
def test_error_response_no_stack_trace():
def test_error_response_format():  # body is {"status": "error", "message": ...}

# X-Forwarded-Proto
def test_https_required_rejects_http_proto():   # WBSB_REQUIRE_HTTPS=true → 400
def test_https_required_allows_https_proto():   # WBSB_REQUIRE_HTTPS=true + https → passes
def test_https_not_required_allows_http_proto() # WBSB_REQUIRE_HTTPS unset → allowed

# Dev bypass
def test_dev_bypass_skips_hmac():  # WBSB_ENV=development → 200 without signature

# Startup check
def test_startup_fails_without_secret_in_prod():
def test_startup_ok_in_dev_without_secret():

# Happy path regression
def test_valid_authenticated_request_returns_200():
```

**Building a valid HMAC in tests:**
```python
import hmac, hashlib, time, uuid

def make_auth_headers(body: bytes, secret: str = "test-secret") -> dict:
    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    signing = f"{ts}.{body.decode()}"
    sig = hmac.new(secret.encode(), signing.encode(), hashlib.sha256).hexdigest()
    return {
        "X-WBSB-Timestamp": ts,
        "X-WBSB-Signature": sig,
        "X-WBSB-Nonce": nonce,
    }
```

---

## Allowed Files

```
src/wbsb/feedback/server.py          ← wire middleware, sanitize all error responses
src/wbsb/cli.py                      ← add startup HMAC secret check
tests/test_feedback_server.py        ← extend with all new tests
```

## Files Not to Touch

```
src/wbsb/feedback/auth.py            ← frozen after I11-2
src/wbsb/feedback/ratelimit.py       ← frozen after I11-3
src/wbsb/feedback/store.py           ← I11-6 only
src/wbsb/pipeline.py
src/wbsb/domain/models.py
```

---

## Execution Workflow

```bash
# 1. Read the current server.py and cli.py in full before modifying
# 2. Implement changes
# 3. Run all tests

pytest && ruff check .

# Security-specific checks
grep -rn "traceback\|Traceback\|stack_trace" src/wbsb/feedback/server.py
# Must return nothing — no stack traces in server code

grep -n "compare_digest\|verify_hmac\|verify_timestamp" src/wbsb/feedback/server.py
# Must find the auth calls

grep -n "log_security_event" src/wbsb/feedback/server.py
# Must find event emission at every rejection point

# Scope check
git diff --name-only feature/iteration-11
# Only: server.py, cli.py, test_feedback_server.py

git add src/wbsb/feedback/server.py src/wbsb/cli.py tests/test_feedback_server.py
git commit -m "feat(i11-5): wire HMAC auth, nonce replay, rate limiting, and HTTPS enforcement into server"
git push origin feature/i11-5-server-integration
gh pr ready
```

---

## Acceptance Criteria

- [ ] Missing `X-WBSB-Signature` → HTTP 401
- [ ] Missing `X-WBSB-Timestamp` → HTTP 401
- [ ] Missing `X-WBSB-Nonce` → HTTP 401
- [ ] Malformed `X-WBSB-Nonce` (not UUID4) → HTTP 401
- [ ] Invalid HMAC → HTTP 401
- [ ] Expired timestamp → HTTP 401
- [ ] Replay nonce → HTTP 409 (not 401)
- [ ] 14th request from same IP → HTTP 429 + `Retry-After: 60`
- [ ] 101st request globally → HTTP 503 + `Retry-After: 60`
- [ ] `WBSB_REQUIRE_HTTPS=true` + `X-Forwarded-Proto: http` → HTTP 400
- [ ] `WBSB_ENV=development` → auth steps skipped, valid request returns 200
- [ ] `wbsb feedback serve` exits with error if `WBSB_FEEDBACK_SECRET` unset in production
- [ ] All error responses use `{"status": "error", "message": "..."}` format
- [ ] No stack traces in any error response: `grep -rn "traceback\|Traceback" server.py` returns nothing
- [ ] `log_security_event` called at every rejection point
- [ ] Valid authenticated request still returns 200 (no regression)
- [ ] All 391 + new tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] `server.py` and `cli.py` read in full before modifying
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] `_nonce_store` and `_rate_limiter` instantiated at module level (not per-request)
- [ ] `grep -rn "traceback"` in server.py returns nothing
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
