# WBSB Review Prompt — I11-8: Architecture Review

---

## Reviewer Role & Mandate

You are performing the I11 architecture gate review.
This review checks the full integrated state of `feature/iteration-11` after all implementation tasks (I11-1 through I11-7) are merged.
Do not fix code during this review. Record findings and assign a verdict.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.

I11 adds full security hardening to the feedback webhook (`POST /feedback`):
- HMAC-SHA256 authentication (I11-1, I11-2, I11-5)
- Rate limiting (I11-3, I11-5)
- Security observability with pseudonymized IPs (I11-4, I11-5)
- Non-root Docker container and feedback artifact permissions (I11-6)
- Multi-stage Docker build, dependency pinning, pip-audit, trivy (I11-7)

**This review is the final gate before I11-9 (cleanup + merge to main). A PASS here authorises I11-9 to proceed.**

---

## Prerequisites

All of the following must be merged to `feature/iteration-11` before starting:
- I11-5 (server integration)
- I11-6 (runtime hardening)
- I11-7 (supply chain)

---

## Task Under Review

- Branch: `feature/iteration-11`
- Review covers: all I11 tasks merged together

---

## Review Execution Steps

### Step 1 — Setup

```bash
git fetch origin
git checkout feature/iteration-11
git pull origin feature/iteration-11
```

### Step 2 — Automated validation

```bash
pytest --tb=short -q
ruff check .
wbsb eval
```

All three must pass. If any fails: `CHANGES REQUIRED` (do not proceed with manual checks).

Record the passing test count for `docs/project/TASKS.md` update in I11-9.

### Step 3 — Authentication behaviour

Start the server in a test terminal with a known secret:
```bash
WBSB_FEEDBACK_SECRET=test-review-secret WBSB_ENV=development wbsb feedback serve --port 8080
```

Use this Python helper to generate valid signed requests:
```python
import hmac, hashlib, time, uuid, json, urllib.request

SECRET = "test-review-secret"

def signed_headers(body: bytes) -> dict:
    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    signing = f"{ts}.{body.decode()}"
    sig = hmac.new(SECRET.encode(), signing.encode(), hashlib.sha256).hexdigest()
    return {
        "X-WBSB-Timestamp": ts,
        "X-WBSB-Signature": sig,
        "X-WBSB-Nonce": nonce,
        "Content-Type": "application/json",
    }

body = json.dumps({
    "run_id": "20240101T120000Z_abc123",
    "section": "situation",
    "label": "expected",
}).encode()

# Valid request — expect 200
print("Valid:", signed_headers(body))
```

Restart server in **production mode** for the remaining auth checks:
```bash
WBSB_FEEDBACK_SECRET=test-review-secret wbsb feedback serve --port 8080
```

For each check below, use curl or the Python helper with the specified modification:

```bash
BODY='{"run_id":"20240101T120000Z_abc123","section":"situation","label":"expected"}'

# Missing X-WBSB-Signature → expect 401
curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -H "X-WBSB-Timestamp: $(date +%s)" \
  -H "X-WBSB-Nonce: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d "$BODY"

# Missing X-WBSB-Nonce → expect 401
curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -H "X-WBSB-Timestamp: $(date +%s)" \
  -H "X-WBSB-Signature: abc" \
  -d "$BODY"

# Malformed nonce (not UUID4) → expect 401
curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -H "X-WBSB-Timestamp: $(date +%s)" \
  -H "X-WBSB-Signature: abc" \
  -H "X-WBSB-Nonce: not-a-uuid" \
  -d "$BODY"

# Invalid HMAC (wrong signature value) → expect 401
curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -H "X-WBSB-Timestamp: $(date +%s)" \
  -H "X-WBSB-Signature: 0000000000000000000000000000000000000000000000000000000000000000" \
  -H "X-WBSB-Nonce: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d "$BODY"

# Expired timestamp (5 minutes ago) → expect 401
EXPIRED_TS=$(python3 -c "import time; print(int(time.time()) - 400)")
curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -H "X-WBSB-Timestamp: $EXPIRED_TS" \
  -H "X-WBSB-Signature: abc" \
  -H "X-WBSB-Nonce: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d "$BODY"
```

For replay detection, use the Python helper to send the same signed request twice:
```python
# First request → expect 200
# Second identical request (same nonce) → expect 409
```

### Step 4 — HTTPS enforcement check

```bash
# WBSB_REQUIRE_HTTPS=true + X-Forwarded-Proto: http → expect 400
WBSB_FEEDBACK_SECRET=test-review-secret WBSB_REQUIRE_HTTPS=true wbsb feedback serve --port 8080

curl -s -w "\n%{http_code}" -X POST http://localhost:8080/feedback \
  -H "X-Forwarded-Proto: http" \
  -H "Content-Type: application/json" \
  -d '{}'
# Expected: 400

# Without WBSB_REQUIRE_HTTPS → X-Forwarded-Proto: http should be allowed
```

### Step 5 — Startup secret check

```bash
# Production mode without secret → expect sys.exit(1) with clear error
wbsb feedback serve --port 8080
# Must print error mentioning WBSB_FEEDBACK_SECRET and exit

# Development mode without secret → must start without error
WBSB_ENV=development wbsb feedback serve --port 8080
# Must start (Ctrl-C to stop)
```

### Step 6 — Error response format check

```bash
grep -rn "traceback\|Traceback\|stack_trace\|format_exc" src/wbsb/feedback/server.py
# Must return nothing
```

Send a request that triggers a 401 and inspect the response body:
```bash
curl -s -X POST http://localhost:8080/feedback \
  -H "Content-Type: application/json" \
  -d '{}'
# Body must be: {"status": "error", "message": "..."} — no stack trace
```

### Step 7 — Observability check

```bash
grep -n "log_security_event" src/wbsb/feedback/server.py
# Must appear at every rejection point (rate limit, auth failure, replay, invalid input, feedback received)

grep -n "comment" src/wbsb/feedback/server.py
# "comment" must not appear as a field being logged
```

### Step 8 — Module-level state check

```bash
grep -n "_nonce_store\|_rate_limiter\|NonceStore()\|RateLimiter()" src/wbsb/feedback/server.py
# Must find module-level instantiation — NOT inside a request handler function
```

### Step 9 — Runtime hardening check

```bash
# Non-root Docker user
docker build -t wbsb-review .
docker run --rm wbsb-review id
# Must output uid=1000(wbsb) — NOT uid=0(root)

# Feedback artifact permissions (confirmed by tests)
pytest tests/test_security_hardening.py -v
# test_feedback_artifact_permissions and test_feedback_dir_permissions must pass
```

### Step 10 — Supply chain check

```bash
# pip-audit
pip install pip-audit
pip-audit --requirement requirements.lock --fail-on HIGH
# Must pass — zero HIGH or CRITICAL CVEs

# No build tools in production image
docker history --no-trunc wbsb-review | grep -E "gcc|build-essential"
# Must return nothing

# CI workflow valid
python -c "import yaml; yaml.safe_load(open('.github/workflows/security.yml')); print('valid')"
# Must print 'valid'
```

### Step 11 — Dependency pinning strategy check

```bash
# requirements.lock must be generated by pip-compile (not pip freeze)
head -3 requirements.lock
# Must show pip-compile header comment (e.g. "# This file is autogenerated by pip-compile")

# pyproject.toml must preserve abstract specifiers — not pin with ==
grep -n "==[0-9]" pyproject.toml
# Must return nothing (exact pins belong in requirements.lock, not pyproject.toml)

# pip-tools must be added to dev deps
grep -n "pip-tools" pyproject.toml
# Must find it in a dev/optional section
```

### Step 12 — `.env.example` documentation check

```bash
grep -n "WBSB_FEEDBACK_SECRET\|WBSB_ENV\|WBSB_REQUIRE_HTTPS" .env.example
# All three must be present with comments
```

---

## Required Output Format

1. **Verdict** (`PASS | CHANGES REQUIRED | BLOCKED`)
2. **What's Correct** — list checks that passed cleanly
3. **Problems Found**
   - severity: `critical | major | minor`
   - location: `file:line` or check step number
   - exact problem
   - why it matters
4. **Missing or Weak Tests** — any gaps in automated test coverage noticed during review
5. **Scope Violations** — any out-of-scope changes found
6. **Acceptance Criteria Check** (`[PASS]` or `[FAIL]` per item — see checklist below)
7. **Exact Fixes Required** — specific, actionable fix for each `[FAIL]` item
8. **Final Recommendation** (`approve | request changes | block`)

---

## Acceptance Criteria Checklist

**Authentication**
- [ ] `POST /feedback` missing `X-WBSB-Signature` → HTTP 401
- [ ] `POST /feedback` missing `X-WBSB-Timestamp` → HTTP 401
- [ ] `POST /feedback` missing `X-WBSB-Nonce` → HTTP 401
- [ ] `POST /feedback` malformed `X-WBSB-Nonce` (not UUID4) → HTTP 401
- [ ] `POST /feedback` invalid HMAC → HTTP 401
- [ ] `POST /feedback` expired timestamp (>300s) → HTTP 401
- [ ] `POST /feedback` replayed nonce → HTTP 409 (not 401)
- [ ] `POST /feedback` valid HMAC + fresh timestamp + fresh nonce → HTTP 200

**Transport**
- [ ] `X-Forwarded-Proto: http` rejected with HTTP 400 when `WBSB_REQUIRE_HTTPS=true`
- [ ] `WBSB_REQUIRE_HTTPS` absent → `X-Forwarded-Proto: http` allowed

**Rate Limiting**
- [ ] 14th request from same IP in 60s → HTTP 429 with `Retry-After` header
- [ ] 101st request globally → HTTP 503 with `Retry-After` header

**Secrets & Startup**
- [ ] `wbsb feedback serve` exits with clear error when `WBSB_FEEDBACK_SECRET` unset in production
- [ ] `WBSB_ENV=development` bypasses HMAC (requires explicit opt-in — not default)
- [ ] `.env.example` documents `WBSB_FEEDBACK_SECRET`, `WBSB_ENV`, `WBSB_REQUIRE_HTTPS`
- [ ] `docker history --no-trunc wbsb-review | grep SECRET` returns nothing

**Error Responses**
- [ ] All HTTP error responses use `{"status": "error", "message": "..."}` format
- [ ] `grep traceback server.py` returns nothing

**Runtime Hardening**
- [ ] `docker run --rm wbsb-review id` shows uid=1000 (not root)
- [ ] Feedback artifacts have `0o600` permissions — confirmed by test
- [ ] `feedback/` directory has `0o700` permissions — confirmed by test

**Observability**
- [ ] `log_security_event` called at every rejection point in `server.py`
- [ ] `comment` not logged at any point
- [ ] IPs pseudonymized (last octet zeroed) in security log events

**Supply Chain**
- [ ] `requirements.lock` generated by `pip-compile` (header comment present)
- [ ] `pip-audit --requirement requirements.lock --fail-on HIGH` passes
- [ ] `pyproject.toml` preserves abstract specifiers — no `==` pins added to direct deps
- [ ] `pip-tools` in dev deps in `pyproject.toml`
- [ ] `.github/workflows/security.yml` present and valid YAML
- [ ] No build tools in production Docker image

**Regression**
- [ ] All tests pass
- [ ] Ruff clean
- [ ] `wbsb eval` all 6 golden cases pass
- [ ] Valid authenticated requests behave identically to I9 behaviour
