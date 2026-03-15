# WBSB Task Prompt — I11-0: Pre-Work, Docs, and Frozen Contract Scaffolding

---

## Context

You are implementing **I11-0** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-0 is the pre-work task: update docs, create frozen contract stub files, and update `.env.example`. All downstream I11 Codex tasks (I11-1, I11-3, I11-4, I11-6) depend on this task being merged first.

**Critical:** `src/wbsb/observability/` already exists and is in production use. Do not touch it. The stub files you create are `auth.py` and `ratelimit.py` in `src/wbsb/feedback/`. I11-4 will extend the existing observability module.

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Use Python stdlib only for security primitives (`hmac`, `hashlib`, `secrets`, `time`) |
| Rule 2 | Never log sensitive values (secret, signatures, webhook URLs, request bodies, full nonce values) |
| Rule 3 | Fail closed: if auth verification raises, treat as auth failure (HTTP 401) |
| Rule 4 | No silent failures in security paths — every rejected request must produce a structured log event |
| Rule 5 | Server behaviour unchanged for valid authenticated requests after I11 merges |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# 1. Start from the iteration branch
git checkout feature/iteration-11
git pull origin feature/iteration-11

# 2. Create and push the task branch
git checkout -b feature/i11-0-pre-work
git push -u origin feature/i11-0-pre-work

# 3. Verify baseline before touching anything
pytest && ruff check .
git commit --allow-empty -m "chore(i11-0): open draft — baseline verified"
git push

# 4. Open draft PR
gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-0-pre-work \
  --title "I11-0: Pre-work, docs, frozen contract scaffolding" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Create the scaffolding that unblocks four parallel Codex tasks. Specifically:

1. Create `src/wbsb/feedback/auth.py` with stub implementations (raise `NotImplementedError`)
2. Create `src/wbsb/feedback/ratelimit.py` with stub implementations (raise `NotImplementedError`)
3. Update `.env.example` with three new environment variables
4. Create `docs/deployment/security.md` with threat model
5. Update `docs/project/project-iterations.md` — mark I11 as In Progress
6. Update `docs/project/TASKS.md` — add I11 as current active iteration

---

## Stub File Specifications

### `src/wbsb/feedback/auth.py`

Implement the following stubs exactly — correct signatures and docstrings, bodies raise `NotImplementedError`:

```python
import hashlib
import hmac


HEADER_TIMESTAMP = "X-WBSB-Timestamp"
HEADER_SIGNATURE = "X-WBSB-Signature"
HEADER_NONCE = "X-WBSB-Nonce"


def verify_hmac(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify HMAC-SHA256 signature. Uses hmac.compare_digest — constant-time.
    Returns False (never raises) if inputs are malformed.
    Signing string: f"{timestamp}.{body.decode('utf-8')}"
    """
    raise NotImplementedError


def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Returns True if abs(now - timestamp) <= max_age_seconds.
    Returns False if timestamp is non-integer or out of window.
    """
    raise NotImplementedError


class NonceStore:
    """
    In-memory nonce deduplication. TTL = 10 minutes. Max 10,000 entries (LRU eviction).
    Thread-safe via threading.Lock.
    Does not survive process restart — timestamp freshness window is the fallback.
    """

    def check_and_record(self, nonce: str) -> bool:
        """
        Returns True if nonce is new (allow).
        Returns False if nonce was seen within TTL window (replay — reject).
        Side effect: records the nonce if new.
        """
        raise NotImplementedError
```

### `src/wbsb/feedback/ratelimit.py`

```python
from enum import Enum


class RateLimitOutcome(str, Enum):
    allowed = "allowed"
    per_ip_exceeded = "per_ip_exceeded"   # HTTP 429
    global_exceeded = "global_exceeded"   # HTTP 503


class RateLimiter:
    """
    Per-IP: 10 req/60s sliding window + burst 3.
    Global: 100 req/60s circuit breaker.
    In-memory only. Does not survive restart.
    Thread-safe via threading.Lock.
    Fail-open: on internal error returns allowed and logs.
    """

    def check(self, source_ip: str) -> RateLimitOutcome:
        """Never raises. Returns outcome; caller decides HTTP response."""
        raise NotImplementedError
```

---

## `.env.example` Update

Add these three lines (with comments) to `.env.example`:

```bash
# Required for production feedback endpoint (HMAC signing)
WBSB_FEEDBACK_SECRET=

# Environment flag: "production" | "development"
# In development mode, HMAC auth is bypassed (explicit opt-in only)
WBSB_ENV=production

# Set to "true" to reject requests where X-Forwarded-Proto: http
# Enable when running behind a TLS-terminating reverse proxy (Caddy, nginx)
WBSB_REQUIRE_HTTPS=true
```

---

## `docs/deployment/security.md`

Create this file. It must include:
- Threat model table (threat, control, I11 task)
- Overview of all security controls implemented in I11
- Scope boundaries (what is and is not in scope)
- Environment variables reference (`WBSB_FEEDBACK_SECRET`, `WBSB_ENV`, `WBSB_REQUIRE_HTTPS`)

Content example structure:
```markdown
# WBSB Security Controls

## Threat Model

| Threat | Control | Task |
|---|---|---|
| Unauthenticated feedback submission | HMAC-SHA256 request signing | I11-1, I11-5 |
| Replay attack | Nonce deduplication (TTL=10min) + timestamp window (±300s) | I11-2, I11-5 |
| Brute-force / flooding | Per-IP rate limit (10/60s + burst 3) + global circuit breaker (100/60s) | I11-3, I11-5 |
| Credential leak via logs | Pseudonymized IPs; no secret/signature/body in log output | I11-4, I11-5 |
| Container privilege escalation | Non-root user UID 1000 | I11-6 |
| Feedback file read by other processes | File permissions 0o600 | I11-6 |
| Error responses leaking internals | Sanitized error responses — no stack traces | I11-5 |
| Vulnerable dependencies | pip-audit CI gate (no HIGH/CRITICAL CVEs) | I11-7 |
| Build tool exposure in image | Multi-stage Docker build | I11-7 |
| TLS bypass via HTTP downgrade | X-Forwarded-Proto enforcement | I11-5 |

## Out of Scope (I11)
- OAuth 2.0 / OpenID Connect
- Multi-tenant RBAC
- Automatic secret rotation
- SIEM integration
- Formal penetration testing
- WAF configuration
```

---

## Docs Updates

### `docs/project/project-iterations.md`

Find the I11 row and update status from `🔲 Next` to `🔲 In Progress`.

### `docs/project/TASKS.md`

Add I11 to the iteration status table with status `🔲 In Progress`. Add a brief I11 section pointing to `docs/iterations/i11/tasks.md` for full detail.

---

## Allowed Files

```
src/wbsb/feedback/auth.py             ← create (stubs only)
src/wbsb/feedback/ratelimit.py        ← create (stubs only)
.env.example                          ← update (add 3 vars)
docs/project/project-iterations.md   ← update status
docs/project/TASKS.md                 ← add I11 section
docs/deployment/security.md          ← create
```

## Files Not to Touch

```
src/wbsb/observability/              ← already exists; I11-4 extends it, not I11-0
src/wbsb/feedback/server.py          ← I11-5 only
src/wbsb/feedback/store.py           ← I11-6 only
src/wbsb/cli.py                      ← I11-5 only
Dockerfile                           ← I11-6 and I11-7 only
pyproject.toml                       ← I11-7 only
Any test file
```

---

## Execution Workflow

```bash
# After baseline commit:

# 1. Create docs/deployment/ directory if it doesn't exist
# 2. Create src/wbsb/feedback/auth.py with stubs
# 3. Create src/wbsb/feedback/ratelimit.py with stubs
# 4. Update .env.example
# 5. Create docs/deployment/security.md
# 6. Update docs/project/project-iterations.md
# 7. Update docs/project/TASKS.md

# Verify no existing functionality broken
pytest && ruff check .

# Verify imports work
python -c "from wbsb.feedback.auth import verify_hmac, verify_timestamp, NonceStore; print('auth OK')"
python -c "from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome; print('ratelimit OK')"

# Verify observability unchanged (no import error)
python -c "from wbsb.observability.logging import get_logger; print('observability OK')"

# Scope check — only allowed files should appear
git diff --name-only feature/iteration-11

# Push and mark ready
git add <only allowed files>
git commit -m "feat(i11-0): frozen contract stubs, env vars, security docs"
git push origin feature/i11-0-pre-work
gh pr ready
```

---

## Acceptance Criteria

- [ ] `from wbsb.feedback.auth import verify_hmac, verify_timestamp, NonceStore` — no import error
- [ ] `from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome` — no import error
- [ ] All stub functions raise `NotImplementedError` when called
- [ ] `HEADER_TIMESTAMP`, `HEADER_SIGNATURE`, `HEADER_NONCE` constants defined in `auth.py`
- [ ] `.env.example` contains `WBSB_FEEDBACK_SECRET`, `WBSB_ENV`, and `WBSB_REQUIRE_HTTPS`
- [ ] `docs/deployment/security.md` exists with threat model table
- [ ] `src/wbsb/observability/logging.py` is unchanged from baseline
- [ ] All 391 existing tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
