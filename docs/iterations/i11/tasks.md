# Iteration 11 — Security Hardening & Production Readiness
## Detailed Task Plan

**Status:** Planning complete. Ready to start.
**Baseline:** 391 tests passing, ruff clean, main stable.
**Prerequisite:** No prerequisite iterations — I11 starts from current main.

---

## Purpose

I11 moves WBSB from a secured MVP to a defensible system for shared or hosted use. I9 introduced the first inbound HTTP surface (`POST /feedback`) and outbound delivery credentials (Slack/Teams webhooks). Those are sufficient for a single-operator internal MVP. I11 adds cryptographic authentication, replay protection, abuse controls, runtime hardening, supply chain scanning, and structured security observability.

After I11, every inbound request is authenticated, rate-limited, and replay-protected. Secrets are managed consistently. The container runs as non-root. Dependencies are pinned and scanned. Security events are observable without leaking sensitive data.

**I11 is a prerequisite for I12 (server deployment).** Do not deploy to any server reachable from outside localhost until I11 is complete.

---

## Critical Architecture Rules

These rules apply to every I11 task. Any implementation that violates them is wrong regardless of whether tests pass.

**Rule 1 — stdlib only for security primitives**
Use Python stdlib `hmac`, `hashlib`, `secrets`, `time` for all cryptographic operations. No external auth libraries. This keeps the attack surface minimal and the implementation auditable.

**Rule 2 — Never log sensitive values**
The HMAC secret, signatures, webhook URLs, nonce values (full), and request bodies must never appear in log output at any level. Log the *fact* of an event (auth failure, rate limit exceeded) with pseudonymized metadata only.

**Rule 3 — Fail closed**
If auth verification raises an unexpected exception, treat it as auth failure (HTTP 401). If rate limiter raises, allow the request through but log the error — do not block legitimate traffic due to a limiter bug.

**Rule 4 — No silent failures in security paths**
Every rejected request must produce a structured log event. Missing log events = invisible attacks.

**Rule 5 — Server behaviour is unchanged for valid authenticated requests**
After I11 merges, `wbsb eval` golden cases must all pass. Feedback storage behaviour is identical for valid requests. I11 adds guards; it does not change the happy path.

---

## Scope Boundaries

| In scope (I11) | Out of scope |
|---|---|
| HMAC-SHA256 request signing for `/feedback` | OAuth 2.0 / OpenID Connect / SSO |
| Timestamp freshness window (±300s) | Multi-tenant RBAC |
| Nonce-based replay prevention (TTL=10min) | Automatic secret rotation (Key Vault) |
| Per-IP rate limiting (10 req/60s + burst 3) | SIEM integration or log forwarding |
| Global rate limiting (100 req/60s) | Formal penetration testing |
| `WBSB_REQUIRE_HTTPS` startup check | WAF configuration |
| Secrets pre-flight checks at startup | DDoS mitigation beyond in-process rate limiting |
| Pseudonymized structured security log events | Web dashboard security (I8 scope) |
| Dockerfile non-root user (UID 1000) | |
| Feedback artifact file permissions (0o600) | |
| Error response sanitization (no stack traces) | |
| Dependency pinning + `pip-audit` CI | |
| Multi-stage Docker + `trivy` image scan | |

---

## Frozen Contracts (Defined in I11-0, Never Changed After)

All downstream tasks import from these contracts. If a contract needs to change after I11-0 merges, stop and raise it — do not silently drift.

### HTTP Header Names

```python
HEADER_TIMESTAMP  = "X-WBSB-Timestamp"   # Unix timestamp, seconds, integer string
HEADER_SIGNATURE  = "X-WBSB-Signature"   # HMAC-SHA256 hex digest (lowercase)
HEADER_NONCE      = "X-WBSB-Nonce"       # UUID4 string
```

### HMAC Signing String

```python
signing_string = f"{timestamp}.{body_bytes.decode('utf-8')}"
signature = hmac.new(secret.encode(), signing_string.encode(), hashlib.sha256).hexdigest()
```

### Auth Module Public Interface (`src/wbsb/feedback/auth.py`)

```python
def verify_hmac(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify HMAC-SHA256 signature. Uses hmac.compare_digest — constant-time.
    Returns False (never raises) if inputs are malformed.
    """

def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Returns True if abs(now - timestamp) <= max_age_seconds.
    Returns False if timestamp is non-integer or out of window.
    """

class NonceStore:
    """
    In-memory nonce deduplication. TTL = 10 minutes. Max 10,000 entries (LRU eviction).
    Thread-safe via threading.Lock.
    """
    def check_and_record(self, nonce: str) -> bool:
        """
        Returns True if nonce is new (allow).
        Returns False if nonce was seen within TTL window (replay — reject).
        Side effect: records the nonce if new.
        """
```

### Rate Limiter Public Interface (`src/wbsb/feedback/ratelimit.py`)

```python
from enum import Enum

class RateLimitOutcome(str, Enum):
    allowed           = "allowed"
    per_ip_exceeded   = "per_ip_exceeded"    # HTTP 429
    global_exceeded   = "global_exceeded"    # HTTP 503

class RateLimiter:
    """
    Per-IP: 10 req/60s sliding window + burst 3.
    Global: 100 req/60s circuit breaker.
    In-memory only. Does not survive restart.
    """
    def check(self, source_ip: str) -> RateLimitOutcome:
        """Never raises. Returns outcome; caller decides HTTP response."""
```

### Structured Security Log Events (`src/wbsb/observability/logging.py`)

```python
EVENT_AUTH_FAILURE        = "auth_failure"         # missing/invalid HMAC or expired timestamp
EVENT_REPLAY_DETECTED     = "replay_detected"      # nonce already seen
EVENT_RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # per-IP or global
EVENT_FEEDBACK_RECEIVED   = "feedback_received"    # successful feedback write
EVENT_INVALID_INPUT       = "invalid_input"        # schema/validation failure

def pseudonymize_ip(ip: str) -> str:
    """Zero the last octet: '192.168.1.47' → '192.168.1.0'"""

def log_security_event(event: str, **fields) -> None:
    """
    Emit a structured security log entry. Uses existing StructLogger.
    Fields must not include: secret, signature, request body, comment, nonce (full).
    """
```

### Error Response Format

All HTTP error responses from the feedback server return exactly:
```json
{"status": "error", "message": "<user-safe string>"}
```
No stack traces, file paths, module names, or Python version in any HTTP response.

---

## Branching Strategy

```
main
 └── feature/iteration-11
      ├── feature/i11-0-pre-work
      ├── feature/i11-1-hmac-auth
      ├── feature/i11-2-nonce-store
      ├── feature/i11-3-rate-limiter
      ├── feature/i11-4-observability
      ├── feature/i11-5-server-integration
      ├── feature/i11-6-runtime-hardening
      └── feature/i11-7-supply-chain
```

**Rules (same as all iterations):**
- Every task branch is created from `feature/iteration-11` — never from `main`
- Every task PR targets `feature/iteration-11` — never `main`
- `main` stays stable throughout the entire iteration
- `feature/iteration-11` → `main` via one final PR after I11-8 review passes

---

## Execution Order and Dependencies

```
I11-0  [Claude]  Pre-work: docs, frozen contracts scaffold, observability package    → no dependencies
I11-1  [Codex]   HMAC verification + timestamp check (auth.py)                      → I11-0
I11-2  [Codex]   Nonce store (extends auth.py)                                      → I11-1
I11-3  [Codex]   Rate limiter (ratelimit.py)                                        → I11-0
I11-4  [Codex]   Security observability (observability/logging.py)                  → I11-0
I11-5  [Claude]  Wire auth + nonce + rate limit + HTTPS into server.py + cli.py     → I11-2, I11-3, I11-4
I11-6  [Codex]   Runtime hardening: Dockerfile non-root, file permissions           → I11-0
I11-7  [Codex]   Supply chain: pin deps, pip-audit, trivy, multi-stage Docker       → I11-0
I11-8  [You]     Architecture review                                                 → I11-5, I11-6, I11-7
I11-9  [Claude]  Final cleanup + merge to main                                      → I11-8
```

**Parallelism opportunities:**
- After I11-0: I11-1, I11-3, I11-4, I11-6, I11-7 can all start in parallel (4 Codex worktrees simultaneously)
- I11-2 starts after I11-1 (extends the same auth.py)
- I11-5 starts only after I11-2, I11-3, and I11-4 all merge (wires all three together)
- I11-6 and I11-7 are fully independent of auth/ratelimit — run in parallel with I11-1 through I11-4
- I11-8 starts only after I11-5, I11-6, and I11-7 all merge

**Dependency diagram:**
```
I11-0
 ├── I11-1 → I11-2 ──┐
 ├── I11-3 ───────────┼──► I11-5 ──┐
 ├── I11-4 ───────────┘            ├──► I11-8 → I11-9
 ├── I11-6 ────────────────────────┤
 └── I11-7 ────────────────────────┘
```

---

## Worktrees

Each Codex task runs in its own worktree:

```bash
# I11-1
git worktree add worktrees/i11-hmac-auth feature/i11-1-hmac-auth

# I11-2
git worktree add worktrees/i11-nonce-store feature/i11-2-nonce-store

# I11-3
git worktree add worktrees/i11-rate-limiter feature/i11-3-rate-limiter

# I11-4
git worktree add worktrees/i11-observability feature/i11-4-observability

# I11-6
git worktree add worktrees/i11-runtime-hardening feature/i11-6-runtime-hardening

# I11-7
git worktree add worktrees/i11-supply-chain feature/i11-7-supply-chain
```

Claude tasks (I11-0, I11-5, I11-9) run on the main working directory, not in worktrees.

---

## Per-Task Workflow

```bash
# 1. Start from the iteration branch
git checkout feature/iteration-11
git pull origin feature/iteration-11

# 2. Create and push the task branch
git checkout -b feature/i11-N-description
git push -u origin feature/i11-N-description

# 3. Open DRAFT PR immediately — before writing any code
gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-N-description \
  --title "I11-N: Task title" \
  --body "Work in progress." \
  --draft

# 4. Verify baseline before touching anything
pytest && ruff check .

# 5. Implement, verify, check file scope
pytest && ruff check .
git diff --name-only feature/iteration-11    # only allowed files

# 6. Push and mark ready
git push origin feature/i11-N-description
gh pr ready
```

---

## Task Summary

| Task | Owner | Description | Depends on |
|---|---|---|---|
| I11-0 | Claude | Pre-work: docs, frozen contract scaffolding, observability package | — |
| I11-1 | Codex | HMAC verification + timestamp freshness in `auth.py` | I11-0 |
| I11-2 | Codex | Nonce store in `auth.py` — replay prevention | I11-1 |
| I11-3 | Codex | Rate limiter in `ratelimit.py` — per-IP + global | I11-0 |
| I11-4 | Codex | Security observability in `observability/logging.py` | I11-0 |
| I11-5 | Claude | Wire all guards into `server.py`; HTTPS check in `cli.py` | I11-2, I11-3, I11-4 |
| I11-6 | Codex | Runtime hardening: Dockerfile non-root, file permissions | I11-0 |
| I11-7 | Codex | Supply chain: pin deps, pip-audit, trivy, multi-stage Docker | I11-0 |
| I11-8 | You | Architecture review | I11-5, I11-6, I11-7 |
| I11-9 | Claude | Final cleanup + merge to main | I11-8 |

---

---

## I11-0 — Pre-Work: Docs + Frozen Contract Scaffolding

**Owner:** Claude
**Branch:** `feature/i11-0-pre-work`
**Depends on:** nothing — starts immediately

### Why First

All four parallel Codex tasks (I11-1, I11-3, I11-4, I11-6) need:
1. The frozen contracts defined in empty scaffold files so imports resolve
2. The `src/wbsb/observability/` package to exist before I11-4 creates `logging.py`
3. Updated docs reflecting I11 as in-progress

Without this, Codex tasks will create their own inconsistent interfaces.

### What to Build

**Docs updates:**
- `docs/project/project-iterations.md` — mark I11 status as `🔲 In Progress`
- `docs/project/TASKS.md` — add I11 as current active iteration with link to this file
- `docs/deployment/security.md` — threat model summary (from I11 spec threat table); controls overview

**Package scaffolding:**
```
src/wbsb/feedback/auth.py            ← create with frozen interface stubs (raise NotImplementedError)
src/wbsb/feedback/ratelimit.py       ← create with frozen interface stubs (raise NotImplementedError)
src/wbsb/observability/__init__.py   ← create (empty package marker)
src/wbsb/observability/logging.py    ← create with frozen interface stubs
```

The stub files define the exact function signatures and class interfaces from the Frozen Contracts section above. Stubs raise `NotImplementedError` — they are replaced by I11-1 through I11-4. This ensures Codex tasks all implement the same interface.

**`.env.example` update:**
Add `WBSB_FEEDBACK_SECRET`, `WBSB_ENV`, and `WBSB_REQUIRE_HTTPS` to `.env.example`:
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

### Acceptance Criteria
- All frozen interface stubs importable without error: `from wbsb.feedback.auth import verify_hmac, NonceStore`
- `from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome` imports cleanly
- `from wbsb.observability.logging import log_security_event` imports cleanly
- `.env.example` contains `WBSB_FEEDBACK_SECRET` and `WBSB_ENV`
- `docs/deployment/security.md` exists with threat model table
- All 391 existing tests pass; ruff clean

### Allowed Files
```
src/wbsb/feedback/auth.py             ← create (stubs)
src/wbsb/feedback/ratelimit.py        ← create (stubs)
src/wbsb/observability/__init__.py    ← create (empty)
src/wbsb/observability/logging.py     ← create (stubs)
.env.example                          ← update (add 2 vars)
docs/project/project-iterations.md   ← update status
docs/project/TASKS.md                 ← add I11 section
docs/deployment/security.md          ← create
```

### Files Not to Touch
```
src/wbsb/feedback/server.py           ← I11-5 only
src/wbsb/feedback/store.py            ← I11-6 only
src/wbsb/cli.py                       ← I11-5 only
Dockerfile                            ← I11-6 and I11-7 only
pyproject.toml                        ← I11-7 only
Any test file
```

---

---

## I11-1 — HMAC Verification + Timestamp Check

**Owner:** Codex
**Branch:** `feature/i11-1-hmac-auth`
**Depends on:** I11-0 merged
**Worktree:** `worktrees/i11-hmac-auth`

### Why Codex

Self-contained cryptographic utility module. The interface is fully specified in the Frozen Contracts section. No existing pipeline or server code is touched. Pure implementation of well-defined functions.

### What to Build

Replace the stubs in `src/wbsb/feedback/auth.py` with real implementations.

#### `verify_hmac(body, timestamp, signature, secret) -> bool`
- Reconstruct signing string: `f"{timestamp}.{body.decode('utf-8')}"`
- Compute expected: `hmac.new(secret.encode(), signing_string.encode(), hashlib.sha256).hexdigest()`
- Compare with `hmac.compare_digest(expected, signature)` — constant-time, prevents timing attacks
- Return `False` (never raise) on any exception — malformed input is treated as auth failure

#### `verify_timestamp(timestamp, max_age_seconds=300) -> bool`
- Parse `timestamp` as integer (return `False` if not parseable)
- Check `abs(time.time() - int(timestamp)) <= max_age_seconds`
- The ±300 second window covers legitimate clock skew and serves as the replay protection window

### Tests Required (`tests/test_feedback_auth.py`)

```python
# verify_hmac
test_verify_hmac_valid               # correct signature → True
test_verify_hmac_wrong_secret        # wrong secret → False
test_verify_hmac_tampered_body       # body changed after signing → False
test_verify_hmac_tampered_timestamp  # timestamp changed after signing → False
test_verify_hmac_malformed_signature # non-hex string → False (no raise)
test_verify_hmac_empty_body          # empty bytes → handled gracefully

# verify_timestamp
test_verify_timestamp_fresh          # within 60s → True
test_verify_timestamp_at_boundary    # exactly 300s → True
test_verify_timestamp_expired        # 301s ago → False
test_verify_timestamp_future         # 301s in future → False
test_verify_timestamp_non_integer    # "abc" → False (no raise)
```

### Acceptance Criteria
- All tests pass; no existing tests broken
- `hmac.compare_digest` used — confirmed by grep: `grep -n "compare_digest" src/wbsb/feedback/auth.py`
- No `except: pass` anywhere in the file
- Ruff clean

### Allowed Files
```
src/wbsb/feedback/auth.py        ← implement stubs (verify_hmac, verify_timestamp only)
tests/test_feedback_auth.py      ← create
```

### Files Not to Touch
```
src/wbsb/feedback/server.py      ← I11-5 only
src/wbsb/feedback/store.py
src/wbsb/feedback/ratelimit.py   ← I11-3
src/wbsb/observability/          ← I11-4
```

---

---

## I11-2 — Nonce Store (Replay Prevention)

**Owner:** Codex
**Branch:** `feature/i11-2-nonce-store`
**Depends on:** I11-1 merged
**Worktree:** `worktrees/i11-nonce-store`

### Why After I11-1

Both live in `auth.py`. I11-2 extends the file after I11-1's functions are merged and stable. This avoids a merge conflict on the same file.

### What to Build

Add `NonceStore` class to `src/wbsb/feedback/auth.py`.

#### `NonceStore`
- Internal store: dict mapping `nonce → expiry_timestamp`
- TTL: 10 minutes (600 seconds)
- Max entries: 10,000 (LRU eviction — evict oldest when full)
- Thread-safe: use `threading.Lock` for all read/write operations
- `check_and_record(nonce: str) -> bool`:
  - Acquire lock
  - Purge expired entries first (iterate and remove where `expiry < now`)
  - If nonce already in store and not expired → return `False` (replay detected)
  - If at capacity after purge → evict oldest entry
  - Record nonce with `expiry = now + 600`
  - Return `True` (new nonce, allow)

**Limitation documented in docstring:** Store is in-process and does not survive restart. On restart, the timestamp freshness window (I11-1) is the only replay protection for the first 5 minutes.

### Tests Required (extend `tests/test_feedback_auth.py`)

```python
# NonceStore
test_nonce_store_new_nonce           # first use → True
test_nonce_store_replay              # same nonce twice → False on second
test_nonce_store_expiry              # nonce expires after TTL → True again (mock time)
test_nonce_store_different_nonces    # two different nonces → both True
test_nonce_store_capacity_eviction   # fill to 10,001 entries → oldest evicted, new accepted
test_nonce_store_thread_safety       # concurrent check_and_record — no data race (use threading)
```

### Acceptance Criteria
- All new and existing tests pass
- `threading.Lock` present: `grep -n "Lock" src/wbsb/feedback/auth.py`
- Max capacity enforced — confirmed by test
- Ruff clean

### Allowed Files
```
src/wbsb/feedback/auth.py        ← add NonceStore class
tests/test_feedback_auth.py      ← extend with NonceStore tests
```

### Files Not to Touch
```
src/wbsb/feedback/server.py
src/wbsb/feedback/ratelimit.py
src/wbsb/observability/
```

---

---

## I11-3 — Rate Limiter

**Owner:** Codex
**Branch:** `feature/i11-3-rate-limiter`
**Depends on:** I11-0 merged (independent of I11-1 and I11-2)
**Worktree:** `worktrees/i11-rate-limiter`

### Why Codex

Self-contained utility class with a fully specified interface. No existing code touched.

### What to Build

Replace the stub in `src/wbsb/feedback/ratelimit.py` with a real implementation.

#### `RateLimiter`
- Per-IP sliding window: 10 requests per 60-second window
- Burst allowance: 3 additional requests above limit before backpressure kicks in (effective limit = 13 before 429)
- Global circuit breaker: 100 requests per 60-second window across all IPs → HTTP 503
- Both limits use sliding window (not fixed window) — track timestamps of recent requests
- Thread-safe: `threading.Lock`
- Memory bounded: per-IP store evicts IPs not seen in >120 seconds

#### `check(source_ip: str) -> RateLimitOutcome`
- Check global limit first (503 if exceeded)
- Then check per-IP limit (429 if exceeded)
- Return `allowed` otherwise
- Never raises — on internal error return `allowed` and log

**Fail-open rule:** If the limiter raises an unexpected exception, log the error and return `allowed`. Rate limiter bugs must not block legitimate traffic.

### Tests Required (`tests/test_feedback_ratelimit.py`)

```python
test_rate_limiter_allows_normal_traffic      # 10 requests → all allowed
test_rate_limiter_per_ip_exceeded            # 14th request from same IP → per_ip_exceeded
test_rate_limiter_burst_within_limit         # 13th request → still allowed (burst)
test_rate_limiter_global_exceeded            # 101 requests from many IPs → global_exceeded
test_rate_limiter_window_resets              # after 60s, counter resets (mock time)
test_rate_limiter_different_ips_independent  # IP A at limit does not affect IP B
test_rate_limiter_returns_retry_after        # not tested here — HTTP layer tested in I11-5
```

### Acceptance Criteria
- All tests pass; ruff clean
- `threading.Lock` used
- Fail-open behaviour confirmed by test (inject exception → returns `allowed`)

### Allowed Files
```
src/wbsb/feedback/ratelimit.py       ← implement stub
tests/test_feedback_ratelimit.py     ← create
```

### Files Not to Touch
```
src/wbsb/feedback/server.py
src/wbsb/feedback/auth.py
src/wbsb/observability/
```

---

---

## I11-4 — Security Observability

**Owner:** Codex
**Branch:** `feature/i11-4-observability`
**Depends on:** I11-0 merged (independent of I11-1 through I11-3)
**Worktree:** `worktrees/i11-observability`

### Why Codex

Bounded utility module. Interface fully specified. No pipeline or server changes.

### What to Build

Replace stubs in `src/wbsb/observability/logging.py`.

#### `pseudonymize_ip(ip: str) -> str`
- Split on `.` and `:` to detect IPv4 vs IPv6
- IPv4: zero last octet (`192.168.1.47` → `192.168.1.0`)
- IPv6: zero last group (`2001:db8::1` → `2001:db8::0`)
- Return input unchanged if format not recognised (never raise)

#### `log_security_event(event: str, **fields) -> None`
- Use existing `get_logger()` from `wbsb.utils` (or equivalent StructLogger)
- Always emit at INFO level
- Automatically add `timestamp` (ISO 8601) to every event
- Never include in fields: `secret`, `signature`, `body`, `comment`, `nonce` (full value)
- Log event name as `event` field

**Usage pattern (for I11-5 reference):**
```python
log_security_event(
    EVENT_AUTH_FAILURE,
    source_ip=pseudonymize_ip(request_ip),
    reason="invalid_hmac",
)

log_security_event(
    EVENT_RATE_LIMIT_EXCEEDED,
    source_ip=pseudonymize_ip(request_ip),
    outcome="per_ip_exceeded",
    window_seconds=60,
)
```

### Tests Required (`tests/test_observability.py`)

```python
test_pseudonymize_ipv4               # '192.168.1.47' → '192.168.1.0'
test_pseudonymize_ipv4_last_zero     # '10.0.0.1' → '10.0.0.0'
test_pseudonymize_ipv6               # basic IPv6 last group zeroed
test_pseudonymize_invalid_input      # 'not-an-ip' → returned unchanged, no raise
test_log_security_event_emits        # log_security_event('auth_failure', ...) → captured in log
test_log_security_event_has_timestamp # emitted event contains 'timestamp' field
```

### Acceptance Criteria
- All tests pass; ruff clean
- `pseudonymize_ip` never raises — confirmed by test with invalid input

### Allowed Files
```
src/wbsb/observability/logging.py    ← implement stubs
tests/test_observability.py          ← create
```

### Files Not to Touch
```
src/wbsb/feedback/
src/wbsb/cli.py
```

---

---

## I11-5 — Server Integration

**Owner:** Claude
**Branch:** `feature/i11-5-server-integration`
**Depends on:** I11-2, I11-3, I11-4 all merged

### Why Claude

This task wires four independently built modules (auth, nonce, rate limiter, observability) into the existing `server.py` and adds the startup check to `cli.py`. It requires architectural judgment about request handling order, error response format consistency, and the `WBSB_ENV` development bypass. It also adds error response sanitization throughout server.py — touching code that must be understood holistically before editing.

### What to Build

#### `src/wbsb/feedback/server.py` — middleware wiring

Request handling order for `POST /feedback`:
```
1. Rate limit check          → 429 (per-IP) or 503 (global) if exceeded
2. Parse headers             → 400 if X-WBSB-Timestamp or X-WBSB-Signature absent
3. Timestamp freshness       → 401 if expired or malformed
4. HMAC verification         → 401 if invalid
5. Nonce check               → 409 if replay detected
6. Existing body validation  → 400 (unchanged from I9)
7. Feedback storage          → 200 (unchanged from I9)
```

**Dev bypass:** If `WBSB_ENV=development`, steps 2–5 are skipped. This requires explicit opt-in — default `WBSB_ENV=production`.

**Error response sanitization:** All existing error responses in server.py are replaced with the frozen format `{"status": "error", "message": "<user-safe string>"}`. No exception messages, no stack traces, no file paths in responses. Verify with tests.

**Security log events:** Every rejection at steps 1–5 emits the appropriate structured event via `log_security_event`. `comment` field is never logged (unchanged from I9).

**`Retry-After` header:** HTTP 429 responses include `Retry-After: 60`. HTTP 503 responses include `Retry-After: 60`.

#### `src/wbsb/feedback/server.py` — `X-Forwarded-Proto` check

When `WBSB_REQUIRE_HTTPS=true` in environment, add a per-request check before rate limiting:
```
If X-Forwarded-Proto header is present and value is "http" → reject with HTTP 400
{"status": "error", "message": "HTTPS required"}
```
This enforces TLS at the application layer when behind a reverse proxy (Caddy/nginx). If `WBSB_REQUIRE_HTTPS` is absent or not `"true"`, skip the check (allows local HTTP development).

Insert this as step 0 in the request handling order:
```
0. X-Forwarded-Proto check    → 400 if http and WBSB_REQUIRE_HTTPS=true
1. Rate limit check           → 429 / 503
2. Parse headers              → 400
...
```

#### `src/wbsb/cli.py` — startup check

In the `wbsb feedback serve` command, before starting the server:
- If `WBSB_ENV != "development"` and `WBSB_FEEDBACK_SECRET` is not set in environment → print error and `sys.exit(1)` with message: `"WBSB_FEEDBACK_SECRET is required in production mode. Set WBSB_ENV=development to bypass."`
- Log startup state: `{"event": "server_starting", "env": WBSB_ENV, "hmac_enabled": True/False, "https_required": True/False}`

### Tests Required (`tests/test_feedback_server.py` — extend existing)

```python
# Auth rejection tests
test_post_feedback_missing_signature          # no X-WBSB-Signature → 401
test_post_feedback_missing_timestamp          # no X-WBSB-Timestamp → 401
test_post_feedback_invalid_hmac               # wrong signature → 401
test_post_feedback_expired_timestamp          # >300s ago → 401
test_post_feedback_replay_nonce               # same nonce twice → 409

# Rate limit tests
test_post_feedback_per_ip_rate_limit          # 14th request → 429 + Retry-After header
test_post_feedback_global_rate_limit          # 101st request → 503 + Retry-After header

# Error response format
test_error_response_no_stack_trace            # 400/401/409/429/503 → no stack trace in body
test_error_response_format                    # body is {"status": "error", "message": ...}

# X-Forwarded-Proto
test_https_required_rejects_http_proto        # WBSB_REQUIRE_HTTPS=true + X-Forwarded-Proto:http → 400
test_https_required_allows_https_proto        # WBSB_REQUIRE_HTTPS=true + X-Forwarded-Proto:https → passes through
test_https_not_required_allows_http_proto     # WBSB_REQUIRE_HTTPS unset → X-Forwarded-Proto:http allowed

# Dev bypass
test_dev_bypass_skips_hmac                    # WBSB_ENV=development → 200 without signature

# Startup check
test_startup_fails_without_secret_in_prod     # WBSB_ENV=production, no secret → sys.exit(1)
test_startup_ok_in_dev_without_secret         # WBSB_ENV=development → starts fine

# Happy path still works
test_valid_authenticated_request_returns_200  # correct HMAC + fresh nonce → 200
```

### Acceptance Criteria
- All new tests pass; all 391 existing tests pass
- `grep -rn "traceback\|Traceback\|stack_trace" src/wbsb/feedback/server.py` returns nothing
- `WBSB_ENV=development` bypass requires explicit env var — default is production
- Ruff clean

### Allowed Files
```
src/wbsb/feedback/server.py          ← wire middleware, sanitize error responses
src/wbsb/cli.py                      ← add startup HMAC secret check
tests/test_feedback_server.py        ← extend with auth/rate limit/error format tests
```

### Files Not to Touch
```
src/wbsb/feedback/auth.py            ← frozen after I11-2
src/wbsb/feedback/ratelimit.py       ← frozen after I11-3
src/wbsb/feedback/store.py           ← I11-6 only
src/wbsb/pipeline.py
src/wbsb/domain/models.py
```

---

---

## I11-6 — Runtime Hardening

**Owner:** Codex
**Branch:** `feature/i11-6-runtime-hardening`
**Depends on:** I11-0 merged (independent of I11-1 through I11-5)
**Worktree:** `worktrees/i11-runtime-hardening`

### Why Codex

Bounded changes to Dockerfile and `store.py`. The Dockerfile non-root user pattern is well-documented. The file permission changes are straightforward Python. No architectural judgment needed.

### What to Build

#### `Dockerfile` — non-root user

Add before the final `CMD`:
```dockerfile
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb
```

Verify: `docker inspect <container> --format '{{.Config.User}}'` → `wbsb` (or UID 1000).

#### `src/wbsb/feedback/store.py` — file permission hardening

When writing feedback JSON artifacts, apply permissions after creation:
```python
import os
# after writing the file:
os.chmod(feedback_path, 0o600)   # owner read-write only
```

The `feedback/` directory itself should be created with `0o700` if it does not exist:
```python
feedback_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
```

Log files (if any written by the feedback server) should use `0o640`.

#### Error response hardening note

Error response sanitization in `server.py` is handled by I11-5, not this task. Do not touch `server.py`.

### Tests Required (extend `tests/test_feedback.py` or create `tests/test_security_hardening.py`)

```python
test_feedback_artifact_permissions    # written file has mode 0o600
test_feedback_dir_permissions         # feedback/ dir has mode 0o700 when created fresh
```

**Dockerfile test (manual acceptance, not automated):**
```bash
docker build -t wbsb-test .
docker run --rm wbsb-test id    # must show uid=1000
```

### Acceptance Criteria
- `docker inspect` confirms UID 1000 (non-root)
- Feedback artifacts created with `0o600`: confirmed by test
- `feedback/` directory created with `0o700`: confirmed by test
- All existing tests pass; ruff clean

### Allowed Files
```
Dockerfile                            ← add non-root user
src/wbsb/feedback/store.py            ← add chmod after file writes
tests/test_security_hardening.py      ← create (or extend test_feedback.py)
```

### Files Not to Touch
```
src/wbsb/feedback/server.py           ← I11-5 only
src/wbsb/cli.py                       ← I11-5 only
docker-compose.yml                    ← I11-7 only
pyproject.toml                        ← I11-7 only
```

---

---

## I11-7 — Supply Chain Security

**Owner:** Codex
**Branch:** `feature/i11-7-supply-chain`
**Depends on:** I11-0 merged (independent of I11-1 through I11-6)
**Worktree:** `worktrees/i11-supply-chain`

### Why Codex

Mechanical changes: pin versions, generate lock file, update CI config, update Dockerfile to multi-stage. No logic changes.

### What to Build

#### `pyproject.toml` — pin direct dependencies to exact versions

Change all `>=` specifiers to `==` for direct dependencies. Run `pip freeze` in the current venv to get exact versions. Example:
```toml
# Before
dependencies = ["pandas>=2.0", "pydantic>=2.0"]

# After
dependencies = ["pandas==2.2.3", "pydantic==2.10.6"]
```

#### `requirements.lock`

Generate via `pip-compile` (if available) or `pip freeze > requirements.lock`. This is the reproducible build anchor. Committed to repo.

#### `.github/workflows/security.yml` — new CI job

```yaml
name: Security Scan
on: [push, pull_request]
jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pip-audit
      - run: pip-audit --requirement requirements.lock --fail-on HIGH

  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with: { tags: wbsb:test, push: false }
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: wbsb:test
          severity: CRITICAL
          exit-code: 1
```

#### `Dockerfile` — multi-stage build

```dockerfile
# Stage 1: build
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Stage 2: production
FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY src/ ./src/
COPY config/ ./config/
# ... (non-root user from I11-6 remains)
```

Multi-stage ensures no build tools (`gcc`, `build-essential`) in the final image.

#### `docker-compose.yml` — cap-drop

Add to each service:
```yaml
cap_drop:
  - ALL
```

### Acceptance Criteria
- `pip-audit` passes with no HIGH or CRITICAL CVEs: `pip-audit -r requirements.lock`
- `docker history --no-trunc wbsb` shows no build tools in final image layers
- `grep -r "gcc\|build-essential" Dockerfile` returns nothing in the production stage
- `.github/workflows/security.yml` is valid YAML and triggers on push
- All existing tests pass; ruff clean

### Allowed Files
```
pyproject.toml                        ← pin direct dependencies
requirements.lock                     ← create (pip freeze output)
Dockerfile                            ← multi-stage build
docker-compose.yml                    ← add cap_drop: ALL
.github/workflows/security.yml        ← create
```

### Files Not to Touch
```
src/wbsb/feedback/store.py            ← I11-6 only
src/wbsb/feedback/server.py           ← I11-5 only
src/wbsb/cli.py                       ← I11-5 only
config/rules.yaml
```

---

---

## I11-8 — Architecture Review

**Owner:** You
**Depends on:** I11-5, I11-6, I11-7 all merged to `feature/iteration-11`

### Review Checklist

**Authentication:**
- [ ] `POST /feedback` with missing `X-WBSB-Signature` returns HTTP 401
- [ ] `POST /feedback` with invalid HMAC returns HTTP 401
- [ ] `POST /feedback` with expired timestamp (>300s) returns HTTP 401
- [ ] `POST /feedback` with replayed nonce returns HTTP 409
- [ ] `POST /feedback` with valid HMAC and fresh nonce returns HTTP 200

**Transport:**
- [ ] `X-Forwarded-Proto: http` request rejected with HTTP 400 when `WBSB_REQUIRE_HTTPS=true`
- [ ] `WBSB_REQUIRE_HTTPS` absent → `X-Forwarded-Proto: http` allowed (dev/local mode)

**Rate limiting:**
- [ ] 14th request in 60s from same IP returns HTTP 429 with `Retry-After` header
- [ ] 101st request globally returns HTTP 503 with `Retry-After` header

**Secrets:**
- [ ] `wbsb feedback serve` exits with clear error if `WBSB_FEEDBACK_SECRET` unset in production mode
- [ ] `WBSB_ENV=development` bypasses HMAC — requires explicit opt-in
- [ ] `.env.example` documents `WBSB_FEEDBACK_SECRET` and `WBSB_ENV`
- [ ] No secrets in `docker history --no-trunc wbsb`

**Runtime hardening:**
- [ ] `docker inspect` confirms container runs as UID 1000
- [ ] Feedback artifacts have `0o600` permissions
- [ ] HTTP error responses contain no stack traces, paths, or module names

**Observability:**
- [ ] `auth_failure` event logged on rejected request; no secret in log entry
- [ ] `rate_limit_exceeded` event logged with pseudonymized IP
- [ ] `comment` field never appears in any log event

**Supply chain:**
- [ ] `pip-audit` passes with no HIGH/CRITICAL CVEs
- [ ] `.github/workflows/security.yml` present and valid
- [ ] All direct dependencies pinned to `==` in `pyproject.toml`

**Regression:**
- [ ] All 391+ tests pass
- [ ] Ruff clean
- [ ] `wbsb eval` all 6 golden cases pass
- [ ] Valid authenticated requests behave identically to current I9 behaviour

---

---

## I11-9 — Final Cleanup + Merge to Main

**Owner:** Claude
**Depends on:** I11-8 review passed

### What to Do
- Fix any issues identified in I11-8 review
- Update test count baseline in `docs/project/project-iterations.md`
- Update `docs/project/TASKS.md` — mark I11 complete
- Update `docs/project/HOW_IT_WORKS.md` — add security controls to architecture section
- Final `pytest && ruff check .` — both must pass clean
- Open final PR: `feature/iteration-11` → `main`

---

## Definition of Done

- [ ] Every inbound `POST /feedback` request is cryptographically authenticated (HMAC-SHA256)
- [ ] Timestamp freshness enforced (±300 seconds)
- [ ] Replay attacks prevented via nonce deduplication (TTL=10min, max 10k entries)
- [ ] Per-IP rate limit (10/60s + burst 3) and global circuit breaker (100/60s) operational
- [ ] `wbsb feedback serve` refuses to start without `WBSB_FEEDBACK_SECRET` in production mode
- [ ] Container runs as UID 1000 (non-root) — confirmed by `docker inspect`
- [ ] Feedback artifacts created with `0o600` permissions
- [ ] All HTTP error responses are sanitized — no stack traces in responses
- [ ] Security events logged with pseudonymized IPs — no sensitive values in logs
- [ ] All direct dependencies pinned to exact versions
- [ ] `pip-audit` passes with no HIGH/CRITICAL CVEs in CI
- [ ] `docker history` shows no build tools in production image
- [ ] All existing tests pass; ruff clean; `wbsb eval` golden cases pass
- [ ] `main` branch stable
