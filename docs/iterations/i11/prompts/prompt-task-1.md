# WBSB Task Prompt — I11-1: HMAC Verification + Timestamp Check

---

## Context

You are implementing **I11-1** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-1 implements the HMAC-SHA256 verification and timestamp freshness functions in `src/wbsb/feedback/auth.py`.

**Prerequisite:** I11-0 must be merged. `src/wbsb/feedback/auth.py` already exists with stubs that raise `NotImplementedError`. Your task is to replace those stubs with real implementations.

**Worktree:** Run this task in `worktrees/i11-hmac-auth`:
```bash
git worktree add worktrees/i11-hmac-auth feature/i11-1-hmac-auth
cd worktrees/i11-hmac-auth
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Use Python stdlib only: `hmac`, `hashlib`, `secrets`, `time` — no external auth libraries |
| Rule 2 | Never log sensitive values (secret, signatures, request bodies) |
| Rule 3 | Fail closed: if auth verification raises unexpectedly, return `False` (not raise) |
| Rule 4 | No silent failures in security paths |
| Rule 5 | Server behaviour unchanged for valid authenticated requests |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-hmac-auth directory:

# The branch feature/i11-1-hmac-auth should already exist (created from feature/iteration-11)
git pull origin feature/i11-1-hmac-auth

# Open draft PR
# Verify baseline
pytest && ruff check .
git commit --allow-empty -m "chore(i11-1): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-1-hmac-auth \
  --title "I11-1: HMAC verification + timestamp freshness" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Replace the `verify_hmac` and `verify_timestamp` stubs in `src/wbsb/feedback/auth.py` with correct, tested implementations. Do not touch `NonceStore` — that is I11-2.

---

## Implementation Specification

### `verify_hmac(body, timestamp, signature, secret) -> bool`

```
Algorithm:
1. Reconstruct signing string: f"{timestamp}.{body.decode('utf-8')}"
2. Compute expected: hmac.new(secret.encode(), signing_string.encode(), hashlib.sha256).hexdigest()
3. Compare with hmac.compare_digest(expected, signature) — constant-time, prevents timing attacks
4. Return True if match, False otherwise
5. On ANY exception (malformed input, decode error, etc.) → catch and return False (never raise)
```

**Why `hmac.compare_digest`:** Regular `==` comparison leaks timing information that could allow an attacker to determine how many characters of the signature are correct. `compare_digest` runs in constant time regardless of where the mismatch occurs.

### `verify_timestamp(timestamp, max_age_seconds=300) -> bool`

```
Algorithm:
1. Parse timestamp as integer — return False if not parseable (ValueError, TypeError, etc.)
2. Compute delta = abs(time.time() - int(timestamp))
3. Return True if delta <= max_age_seconds, False otherwise
4. The ±300 second window (5 minutes) covers legitimate clock skew
```

---

## Required Tests (`tests/test_feedback_auth.py`)

Create this file. All 11 tests must be present and meaningful:

```python
# verify_hmac tests
def test_verify_hmac_valid():
    # Correct signature → True

def test_verify_hmac_wrong_secret():
    # Different secret → False

def test_verify_hmac_tampered_body():
    # Body changed after signing → False

def test_verify_hmac_tampered_timestamp():
    # Timestamp changed after signing → False

def test_verify_hmac_malformed_signature():
    # Non-hex string as signature → False (must not raise)

def test_verify_hmac_empty_body():
    # Empty bytes body → handled gracefully, no exception

# verify_timestamp tests
def test_verify_timestamp_fresh():
    # Timestamp within 60s of now → True

def test_verify_timestamp_at_boundary():
    # Exactly 300s ago → True

def test_verify_timestamp_expired():
    # 301s ago → False

def test_verify_timestamp_future():
    # 301s in the future → False

def test_verify_timestamp_non_integer():
    # "abc" string → False, must not raise
```

**Test helper pattern:** Compute real HMAC signatures in your test setup — do not use hardcoded hex strings. Use `hmac.new(secret.encode(), signing_string.encode(), hashlib.sha256).hexdigest()` directly in test fixtures to generate correct expected values.

---

## Allowed Files

```
src/wbsb/feedback/auth.py        ← implement verify_hmac and verify_timestamp only
                                    do NOT modify NonceStore or header constants
tests/test_feedback_auth.py      ← create
```

## Files Not to Touch

```
src/wbsb/feedback/server.py      ← I11-5 only
src/wbsb/feedback/store.py
src/wbsb/feedback/ratelimit.py   ← I11-3
src/wbsb/observability/          ← I11-4
src/wbsb/cli.py                  ← I11-5 only
Dockerfile
```

---

## Execution Workflow

```bash
# 1. Read the current stub file to understand the structure
# 2. Implement verify_hmac and verify_timestamp
# 3. Write tests
# 4. Run verification

pytest && ruff check .

# Security-specific checks
grep -n "compare_digest" src/wbsb/feedback/auth.py
# Must find at least one occurrence — timing attack prevention

grep -n "except.*pass\|except:" src/wbsb/feedback/auth.py
# Must return nothing — no silent except blocks

# Scope check
git diff --name-only feature/iteration-11
# Only auth.py and test_feedback_auth.py should appear

# Push and mark ready
git add src/wbsb/feedback/auth.py tests/test_feedback_auth.py
git commit -m "feat(i11-1): HMAC verification and timestamp freshness check"
git push origin feature/i11-1-hmac-auth
gh pr ready
```

---

## Acceptance Criteria

- [ ] `verify_hmac` returns `True` for a correct signature
- [ ] `verify_hmac` returns `False` for wrong secret, tampered body, tampered timestamp, malformed signature
- [ ] `verify_hmac` never raises — returns `False` on any exception
- [ ] `hmac.compare_digest` used: `grep -n "compare_digest" src/wbsb/feedback/auth.py` finds it
- [ ] `verify_timestamp` returns `True` for timestamps within ±300s
- [ ] `verify_timestamp` returns `False` for non-integer input without raising
- [ ] `NonceStore` stub unchanged (still raises `NotImplementedError`)
- [ ] All 11 tests present and passing
- [ ] No existing tests broken (391 baseline + new)
- [ ] No `except: pass` in the file
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] `grep -n "compare_digest"` confirms constant-time comparison
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
