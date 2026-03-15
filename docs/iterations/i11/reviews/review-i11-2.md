# WBSB Review Prompt — I11-2: Nonce Store (Replay Prevention)

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-2 strictly against `docs/iterations/i11/tasks.md`.
This is a security-critical task. Apply strict scrutiny to thread safety, eviction logic, and TTL correctness.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-2 adds the `NonceStore` class to `src/wbsb/feedback/auth.py` — an in-memory replay prevention store with TTL expiry, bounded capacity, and thread safety.

**Security surface:** A race condition in `check_and_record` could allow two concurrent requests with the same nonce to both return `True` — both would be accepted, defeating replay protection. A missing TTL expiry would cause the store to grow unbounded and run out of memory. Incorrect eviction could silently drop valid nonces or retain replayed ones past TTL.

---

## Task Under Review

- Task: I11-2 — Nonce Store (Replay Prevention)
- Branch: `feature/i11-2-nonce-store`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/feedback/auth.py` (modify — add `NonceStore`)
- `tests/test_feedback_auth.py` (extend — add 6 `NonceStore` tests)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-2-nonce-store
git pull origin feature/i11-2-nonce-store
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

### Step 4 — Thread safety check (critical)

```bash
grep -n "threading.Lock\|threading.RLock\|with self._lock" src/wbsb/feedback/auth.py
```

**Must find `Lock` and `with self._lock` pattern.** The lock must wrap the entire `check_and_record` body — check, evict, record — as a single atomic operation. If the lock is absent or only wraps part of the operation, this is a `CRITICAL` finding.

### Step 5 — TTL check

```bash
grep -n "600\|TTL\|expiry\|time.time" src/wbsb/feedback/auth.py
```

Verify:
- TTL = 600 seconds (10 minutes)
- Expiry calculated as `time.time() + 600`
- Expired entries purged before checking for replay

### Step 6 — Capacity check

```bash
grep -n "10.000\|10000\|max.*entri\|evict\|oldest" src/wbsb/feedback/auth.py
```

Verify:
- Maximum 10,000 entries enforced
- Eviction occurs when at capacity (after purging expired entries)
- Eviction strategy is LRU (remove entry with smallest expiry timestamp)

### Step 7 — Restart limitation documented

```bash
grep -n "restart\|in-process\|in-memory\|survive" src/wbsb/feedback/auth.py
```

Verify the in-memory limitation is documented (docstring or inline comment): store does not survive restart; timestamp freshness window is the fallback for the first 5 minutes.

### Step 8 — `verify_hmac`/`verify_timestamp` unchanged

```bash
git diff feature/i11-1-hmac-auth -- src/wbsb/feedback/auth.py | grep "^[-+]" | grep -v "^---\|^+++" | grep -v "NonceStore\|check_and_record\|_store\|_lock"
```

Changes to the file must only be additions for `NonceStore`. The `verify_hmac` and `verify_timestamp` functions must be unchanged from I11-1.

### Step 9 — Test presence check

```bash
grep -n "^def test_nonce" tests/test_feedback_auth.py
```

Required new tests (6):
- `test_nonce_store_new_nonce`
- `test_nonce_store_replay`
- `test_nonce_store_expiry`
- `test_nonce_store_different_nonces`
- `test_nonce_store_capacity_eviction`
- `test_nonce_store_thread_safety`

### Step 10 — Thread safety test uses real threads

```bash
grep -A 20 "test_nonce_store_thread_safety" tests/test_feedback_auth.py
```

Verify:
- Uses `threading.Thread` (not `asyncio`, not `multiprocessing`)
- Multiple threads (at least 10) call `check_and_record` with the same nonce concurrently
- Collects results and asserts exactly 1 `True` (one thread wins)

### Step 11 — I11-1 tests unchanged

```bash
grep -n "^def test_verify_hmac\|^def test_verify_timestamp" tests/test_feedback_auth.py
```

All 11 I11-1 tests must still be present.

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

- [ ] `NonceStore.check_and_record` returns `True` for new nonce
- [ ] `NonceStore.check_and_record` returns `False` for replayed nonce within TTL
- [ ] Nonce expires after TTL — confirmed by mock-time test
- [ ] Max 10,000 entries enforced — oldest evicted when at capacity
- [ ] `threading.Lock` wraps entire check+record operation atomically
- [ ] Thread safety test uses real threads, asserts exactly 1 True
- [ ] Restart limitation documented in code
- [ ] `verify_hmac` and `verify_timestamp` unchanged from I11-1
- [ ] All 6 new tests present and passing
- [ ] All 11 I11-1 tests present and passing
- [ ] All baseline tests pass
- [ ] No `except: pass`
- [ ] Ruff clean
- [ ] Only allowed files modified
