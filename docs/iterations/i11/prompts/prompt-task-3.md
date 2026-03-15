# WBSB Task Prompt — I11-3: Rate Limiter

---

## Context

You are implementing **I11-3** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-3 implements the in-memory rate limiter in `src/wbsb/feedback/ratelimit.py`.

**Prerequisite:** I11-0 must be merged. `ratelimit.py` already exists with a stub that raises `NotImplementedError`. Your task is to replace the stub with a real implementation.

**This task is independent of I11-1 and I11-2.** It can run in parallel with those tasks.

**Worktree:** Run this task in `worktrees/i11-rate-limiter`:
```bash
git worktree add worktrees/i11-rate-limiter feature/i11-3-rate-limiter
cd worktrees/i11-rate-limiter
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Stdlib only: `threading`, `time`, `collections` — no external rate limiting libraries |
| Rule 2 | Never log source IPs in raw form — pseudonymization is I11-4/I11-5 concern, but never log PII |
| Rule 3 | Fail open: if limiter raises unexpectedly, log the error and return `allowed` — do not block legitimate traffic |
| Rule 4 | No silent failures — limiter bugs must be logged, not swallowed |
| Rule 5 | Server behaviour unchanged for valid authenticated requests below rate limits |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-rate-limiter directory:
git pull origin feature/i11-3-rate-limiter

pytest && ruff check .
git commit --allow-empty -m "chore(i11-3): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-3-rate-limiter \
  --title "I11-3: Rate limiter — per-IP + global circuit breaker" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Implement `RateLimiter` in `src/wbsb/feedback/ratelimit.py` with per-IP sliding window and global circuit breaker. Write tests in `tests/test_feedback_ratelimit.py`.

---

## Implementation Specification

### Rate Limit Parameters

```
Per-IP:  10 requests per 60-second sliding window
Burst:   3 additional requests above limit (effective: 13 before 429)
Global:  100 requests per 60-second window across all IPs → 503
```

### Sliding Window Implementation

Track timestamps (not counters) for each bucket. A "sliding window" means:
- For each request, record `time.time()` in the IP's deque
- When checking, remove all entries older than 60 seconds from the front of the deque
- Count remaining entries — if > limit → exceeded

```python
from collections import defaultdict, deque
import threading
import time

class RateLimiter:
    _PER_IP_LIMIT = 10
    _PER_IP_BURST = 3      # effective limit = 13
    _GLOBAL_LIMIT = 100
    _WINDOW = 60.0

    def __init__(self):
        self._ip_windows: dict[str, deque] = defaultdict(deque)
        self._global_window: deque = deque()
        self._lock = threading.Lock()
```

### `check(source_ip: str) -> RateLimitOutcome`

```
Algorithm:
1. Try-except entire method body → on exception: log error, return allowed
2. Acquire lock
3. now = time.time()
4. Purge global window: remove entries where timestamp < now - WINDOW
5. Check global: if len(global_window) >= GLOBAL_LIMIT → return global_exceeded
6. Purge per-IP window for source_ip
7. Check per-IP: if len(ip_window) >= PER_IP_LIMIT + PER_IP_BURST → return per_ip_exceeded
8. Record request: append now to both global_window and ip_window
9. Return allowed
```

### Memory bound

Evict per-IP entries not seen in >120 seconds to prevent unbounded memory growth:
- After step 3, scan `_ip_windows` and remove IPs whose deque is now empty (after purging old entries)

---

## Required Tests (`tests/test_feedback_ratelimit.py`)

Create this file with these 7 tests:

```python
def test_rate_limiter_allows_normal_traffic():
    # 10 requests from same IP → all return allowed

def test_rate_limiter_burst_within_limit():
    # 13th request from same IP → still allowed (burst)

def test_rate_limiter_per_ip_exceeded():
    # 14th request from same IP → per_ip_exceeded

def test_rate_limiter_global_exceeded():
    # 101 requests from different IPs (1 per IP) → global_exceeded on 101st
    # Use distinct IP per request: f"10.0.{i//256}.{i%256}"

def test_rate_limiter_window_resets():
    # After mocking time.time() to advance 61 seconds, counters reset
    # Use unittest.mock.patch("wbsb.feedback.ratelimit.time.time")

def test_rate_limiter_different_ips_independent():
    # IP A at per-IP limit does not affect IP B — IP B still returns allowed

def test_rate_limiter_fail_open():
    # Inject an exception inside the limiter (mock internal state to raise)
    # → check() must return allowed, not raise
```

---

## Allowed Files

```
src/wbsb/feedback/ratelimit.py       ← implement stub
tests/test_feedback_ratelimit.py     ← create
```

## Files Not to Touch

```
src/wbsb/feedback/server.py
src/wbsb/feedback/auth.py
src/wbsb/observability/
src/wbsb/cli.py
```

---

## Execution Workflow

```bash
# 1. Read ratelimit.py to understand the stub structure
# 2. Implement RateLimiter
# 3. Write tests
# 4. Verify

pytest && ruff check .

# Thread safety check
grep -n "threading.Lock\|Lock()" src/wbsb/feedback/ratelimit.py

# Fail-open check
grep -n "except\|try:" src/wbsb/feedback/ratelimit.py
# Must find a broad except in check() that returns allowed

# Scope check
git diff --name-only feature/iteration-11
# Only ratelimit.py and test_feedback_ratelimit.py

git add src/wbsb/feedback/ratelimit.py tests/test_feedback_ratelimit.py
git commit -m "feat(i11-3): sliding window rate limiter with per-IP and global circuit breaker"
git push origin feature/i11-3-rate-limiter
gh pr ready
```

---

## Acceptance Criteria

- [ ] 10 requests from same IP → all `allowed`
- [ ] 13th request → `allowed` (burst)
- [ ] 14th request → `per_ip_exceeded`
- [ ] 101st request globally → `global_exceeded`
- [ ] Per-IP window resets after 60 seconds (mock time test)
- [ ] Different IPs are independent
- [ ] Fail-open: exception inside `check()` → returns `allowed` without raising
- [ ] `threading.Lock` used
- [ ] All 7 tests present and passing
- [ ] All 391 baseline tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] Fail-open behaviour confirmed by `test_rate_limiter_fail_open`
- [ ] Thread safety confirmed by `grep -n "Lock"`
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
