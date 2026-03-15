# WBSB Review Prompt — I11-3: Rate Limiter

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-3 strictly against `docs/iterations/i11/tasks.md`.
This is a security-relevant task. Apply scrutiny to sliding window correctness, thread safety, and fail-open behaviour.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-3 implements the in-memory rate limiter (`RateLimiter`) in `src/wbsb/feedback/ratelimit.py`.

**Security surface:** The rate limiter is the first defence against flooding attacks. A fixed-window implementation (instead of sliding window) is exploitable by bursting at window boundaries. Missing thread safety allows concurrent requests to bypass the limit. A fail-closed bug (returning `per_ip_exceeded` on internal error) would deny legitimate traffic.

---

## Task Under Review

- Task: I11-3 — Rate Limiter
- Branch: `feature/i11-3-rate-limiter`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/feedback/ratelimit.py` (modify — implement `RateLimiter`)
- `tests/test_feedback_ratelimit.py` (create)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-3-rate-limiter
git pull origin feature/i11-3-rate-limiter
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

Allowed: `src/wbsb/feedback/ratelimit.py`, `tests/test_feedback_ratelimit.py`.

Forbidden: `src/wbsb/feedback/server.py`, `src/wbsb/feedback/auth.py`, `src/wbsb/observability/`, `src/wbsb/cli.py`.

### Step 4 — Sliding window check (not fixed window)

```bash
grep -n "deque\|timestamps\|append.*time\|time.*append" src/wbsb/feedback/ratelimit.py
```

Verify the implementation tracks request timestamps (not counters). A `deque` or list of timestamps that are purged based on `time.time() - WINDOW` is the correct sliding window pattern. A simple counter that resets every 60 seconds is a fixed window — exploitable.

### Step 5 — Thread safety check

```bash
grep -n "threading.Lock\|with self._lock" src/wbsb/feedback/ratelimit.py
```

Must find `Lock` usage protecting the sliding window read/write.

### Step 6 — Fail-open check (critical)

```bash
grep -n "except\|try:" src/wbsb/feedback/ratelimit.py
```

Verify `check()` wraps its entire body in a broad `except Exception` and returns `RateLimitOutcome.allowed` on error. A fail-closed limiter that returns `per_ip_exceeded` or raises on error would deny legitimate traffic during a bug — this is unacceptable.

### Step 7 — Burst allowance check

```bash
grep -n "burst\|13\|PER_IP_BURST\|_BURST" src/wbsb/feedback/ratelimit.py
```

Verify burst is 3 (effective limit = 13). The 14th request must return `per_ip_exceeded`, but the 13th must return `allowed`.

### Step 8 — Global limit check

```bash
grep -n "GLOBAL_LIMIT\|global.*100\|100.*global\|global_window\|global_exceeded" src/wbsb/feedback/ratelimit.py
```

Verify global circuit breaker at 100 req/60s, returning `global_exceeded` (HTTP 503).

### Step 9 — Memory bound check

```bash
grep -n "120\|evict\|cleanup\|_ip_windows" src/wbsb/feedback/ratelimit.py
```

Verify per-IP windows are cleaned up for inactive IPs (not seen in >120 seconds) to prevent unbounded memory growth.

### Step 10 — Test presence check

```bash
grep -n "^def test_" tests/test_feedback_ratelimit.py
```

Required tests:
- `test_rate_limiter_allows_normal_traffic`
- `test_rate_limiter_burst_within_limit`
- `test_rate_limiter_per_ip_exceeded`
- `test_rate_limiter_global_exceeded`
- `test_rate_limiter_window_resets`
- `test_rate_limiter_different_ips_independent`
- `test_rate_limiter_fail_open`

### Step 11 — Fail-open test check

```bash
grep -A 15 "test_rate_limiter_fail_open" tests/test_feedback_ratelimit.py
```

Verify the test injects an exception (mock internal state to raise) and asserts `check()` returns `allowed` without raising.

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

- [ ] 10 requests from same IP → all `allowed`
- [ ] 13th request from same IP → `allowed` (burst)
- [ ] 14th request from same IP → `per_ip_exceeded`
- [ ] 101st request globally → `global_exceeded`
- [ ] Sliding window (timestamp-based) — not fixed window counter
- [ ] `threading.Lock` present
- [ ] Per-IP window resets after 60 seconds (mock-time test)
- [ ] Different IPs are independent
- [ ] Fail-open: exception inside `check()` → returns `allowed` without raising
- [ ] Fail-open confirmed by test (not just assertion)
- [ ] Memory bound: inactive IPs cleaned up
- [ ] All 7 required tests present and passing
- [ ] All baseline tests pass
- [ ] Ruff clean
- [ ] Only allowed files modified
