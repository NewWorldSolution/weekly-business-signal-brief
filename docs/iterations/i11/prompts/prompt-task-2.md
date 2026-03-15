# WBSB Task Prompt — I11-2: Nonce Store (Replay Prevention)

---

## Context

You are implementing **I11-2** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-2 adds `NonceStore` to `src/wbsb/feedback/auth.py` — the in-memory replay prevention store.

**Prerequisite:** I11-1 must be merged. `auth.py` now contains working `verify_hmac` and `verify_timestamp` implementations. The `NonceStore` class stub is still present (raises `NotImplementedError`). Your task is to replace that stub.

**Worktree:** Run this task in `worktrees/i11-nonce-store`:
```bash
git worktree add worktrees/i11-nonce-store feature/i11-2-nonce-store
cd worktrees/i11-nonce-store
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Stdlib only: `threading`, `time` — no external concurrency libraries |
| Rule 2 | Never log nonce values (full nonce must not appear in log output) |
| Rule 3 | Fail closed: if store raises unexpectedly, the calling code must treat it as failure |
| Rule 4 | No silent failures in security paths |
| Rule 5 | Server behaviour unchanged for valid authenticated requests |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-nonce-store directory:
git pull origin feature/i11-2-nonce-store

pytest && ruff check .
git commit --allow-empty -m "chore(i11-2): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-2-nonce-store \
  --title "I11-2: Nonce store — replay prevention" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Implement `NonceStore` in `src/wbsb/feedback/auth.py`. Add tests to `tests/test_feedback_auth.py`.

---

## Implementation Specification

### `NonceStore`

```
Internal storage: dict mapping nonce (str) → expiry_timestamp (float)
TTL: 600 seconds (10 minutes)
Max entries: 10,000
Thread safety: threading.Lock on all read/write operations
```

#### `check_and_record(nonce: str) -> bool`

```
Algorithm (all operations under lock):
1. Purge expired entries: remove all entries where expiry < time.time()
2. If nonce is in store and not expired → return False (replay detected)
3. If len(store) >= 10,000 after purge:
   → evict the entry with the smallest expiry timestamp (oldest)
4. Record: store[nonce] = time.time() + 600
5. Return True (new nonce, allow)
```

**Important documentation (add as docstring or inline comment):**
> Store is in-process only. Does not survive restart. On restart, the timestamp freshness window (verify_timestamp, ±300s) provides the only replay protection for the first 5 minutes until the TTL window catches up.

**Thread safety pattern:**
```python
import threading

class NonceStore:
    def __init__(self):
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()

    def check_and_record(self, nonce: str) -> bool:
        with self._lock:
            # all logic here
            ...
```

**LRU eviction — find oldest entry:**
```python
oldest_key = min(self._store, key=lambda k: self._store[k])
del self._store[oldest_key]
```

---

## Required Tests (extend `tests/test_feedback_auth.py`)

Add these 6 tests to the existing file. Do not remove any I11-1 tests.

```python
def test_nonce_store_new_nonce():
    # First use of a nonce → True

def test_nonce_store_replay():
    # Same nonce used twice → False on second call

def test_nonce_store_expiry():
    # Mock time: advance past TTL → nonce is no longer in store → True again
    # Use unittest.mock.patch("time.time") to advance time by 601 seconds

def test_nonce_store_different_nonces():
    # Two different nonces → both return True independently

def test_nonce_store_capacity_eviction():
    # Fill store to 10,001 entries → oldest is evicted → new nonce accepted
    # After filling, total store size must be <= 10,000

def test_nonce_store_thread_safety():
    # Concurrently call check_and_record from 10 threads with the SAME nonce
    # Exactly 1 call must return True; the rest must return False
    # Use threading.Thread and a shared list to collect results
```

---

## Allowed Files

```
src/wbsb/feedback/auth.py        ← add NonceStore implementation
                                    do NOT modify verify_hmac or verify_timestamp
tests/test_feedback_auth.py      ← extend with 6 new NonceStore tests
```

## Files Not to Touch

```
src/wbsb/feedback/server.py
src/wbsb/feedback/ratelimit.py
src/wbsb/observability/
src/wbsb/cli.py
Dockerfile
```

---

## Execution Workflow

```bash
# 1. Read auth.py to understand the current state (verify_hmac, verify_timestamp done)
# 2. Implement NonceStore class
# 3. Extend tests/test_feedback_auth.py with NonceStore tests
# 4. Verify

pytest && ruff check .

# Thread safety check
grep -n "threading.Lock\|Lock()" src/wbsb/feedback/auth.py
# Must find Lock usage

# Scope check
git diff --name-only feature/iteration-11
# Only auth.py and test_feedback_auth.py

# Push and mark ready
git add src/wbsb/feedback/auth.py tests/test_feedback_auth.py
git commit -m "feat(i11-2): nonce store with TTL and LRU eviction for replay prevention"
git push origin feature/i11-2-nonce-store
gh pr ready
```

---

## Acceptance Criteria

- [ ] `NonceStore.check_and_record` returns `True` for new nonce
- [ ] `NonceStore.check_and_record` returns `False` for replayed nonce within TTL
- [ ] Nonce expires after TTL (confirmed by mock-time test)
- [ ] Max 10,000 entries enforced — oldest evicted when at capacity
- [ ] Thread-safe: concurrent calls with same nonce produce exactly one `True`
- [ ] `threading.Lock` used: `grep -n "Lock" src/wbsb/feedback/auth.py` finds it
- [ ] Restart limitation documented in code
- [ ] `verify_hmac` and `verify_timestamp` unchanged from I11-1
- [ ] All 6 new tests plus all I11-1 tests pass
- [ ] All 391 baseline tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] `grep -n "Lock"` confirms thread safety
- [ ] Thread safety test (`test_nonce_store_thread_safety`) uses real threads
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
