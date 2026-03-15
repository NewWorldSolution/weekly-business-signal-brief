# WBSB Task Prompt — I11-4: Security Observability

---

## Context

You are implementing **I11-4** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-4 **extends** the existing `src/wbsb/observability/logging.py` with security event constants, IP pseudonymization, and a structured security log helper.

**Prerequisite:** I11-0 must be merged.

**This task is independent of I11-1, I11-2, and I11-3.** It can run in parallel.

**Critical:** `src/wbsb/observability/logging.py` is an existing production file. **Do not replace, restructure, or stub it.** Append new code at the end of the file. Do not modify any existing functions (`StructLogger`, `JsonlHandler`, `get_logger`, `init_run_logger`).

**Worktree:** Run this task in `worktrees/i11-observability`:
```bash
git worktree add worktrees/i11-observability feature/i11-4-observability
cd worktrees/i11-observability
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Use existing `get_logger()` from `wbsb.observability.logging` (already in this file) |
| Rule 2 | Never log: secret, signature, request body, comment, full nonce value |
| Rule 3 | `log_security_event` must never raise — if logging fails, silently discard |
| Rule 4 | Every security event must emit a structured JSON entry with `event` and `timestamp` fields |
| Rule 5 | `pseudonymize_ip` must never raise — return input unchanged on unrecognised format |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-observability directory:
git pull origin feature/i11-4-observability

pytest && ruff check .
git commit --allow-empty -m "chore(i11-4): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-4-observability \
  --title "I11-4: Security observability — pseudonymize_ip and log_security_event" \
  --body "Work in progress." \
  --draft
```

---

## Objective

Append to `src/wbsb/observability/logging.py`:
1. Five event name constants
2. `pseudonymize_ip(ip: str) -> str`
3. `log_security_event(event: str, **fields) -> None`

Write tests in `tests/test_observability.py`.

---

## Implementation Specification

### Event Constants (append at module level after existing imports/constants)

```python
# Security event constants
EVENT_AUTH_FAILURE        = "auth_failure"         # missing/invalid HMAC or expired timestamp
EVENT_REPLAY_DETECTED     = "replay_detected"      # nonce already seen
EVENT_RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # per-IP or global
EVENT_FEEDBACK_RECEIVED   = "feedback_received"    # successful feedback write
EVENT_INVALID_INPUT       = "invalid_input"        # schema/validation failure
```

### `pseudonymize_ip(ip: str) -> str`

```
IPv4: '192.168.1.47' → '192.168.1.0'
  Algorithm: split on '.', replace last octet with '0', rejoin

IPv6: '2001:db8::1' → '2001:db8::0'
  Algorithm: split on ':', replace last group with '0', rejoin

Unrecognised format: return input unchanged (no raise)

Detection logic:
  if '.' in ip and ':' not in ip → treat as IPv4
  elif ':' in ip → treat as IPv6
  else → return unchanged
```

**Edge cases to handle without raising:**
- Empty string → return unchanged
- Single octet → return unchanged
- Already ending in `.0` → return `.0` (idempotent)

### `log_security_event(event: str, **fields) -> None`

```
1. Get logger via get_logger() (already defined in this file)
2. Build log entry:
   {
     "event": event,
     "timestamp": datetime.utcnow().isoformat() + "Z",
     **fields
   }
3. Emit at INFO level
4. Wrap entire function in try-except → silently discard if logging fails (never raise)
```

**Fields must NEVER include:** `secret`, `signature`, `body`, `comment`, `nonce` (full value).
This is a convention — `log_security_event` does not enforce it programmatically, but callers (I11-5) follow it.

**Usage pattern (for I11-5 reference):**
```python
from wbsb.observability.logging import (
    log_security_event,
    pseudonymize_ip,
    EVENT_AUTH_FAILURE,
    EVENT_RATE_LIMIT_EXCEEDED,
    EVENT_FEEDBACK_RECEIVED,
    EVENT_REPLAY_DETECTED,
    EVENT_INVALID_INPUT,
)

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

---

## Required Tests (`tests/test_observability.py`)

Create this file with these 6 tests:

```python
def test_pseudonymize_ipv4():
    # '192.168.1.47' → '192.168.1.0'

def test_pseudonymize_ipv4_last_zero():
    # '10.0.0.1' → '10.0.0.0'

def test_pseudonymize_ipv6():
    # '2001:db8:0:0:0:0:0:1' → '2001:db8:0:0:0:0:0:0'

def test_pseudonymize_invalid_input():
    # 'not-an-ip' → returned unchanged
    # Must not raise

def test_log_security_event_emits():
    # Call log_security_event(EVENT_AUTH_FAILURE, source_ip='1.2.3.0', reason='test')
    # Verify it does not raise and returns None
    # Use caplog or mock to verify emission if possible

def test_log_security_event_has_timestamp():
    # Emitted event contains 'timestamp' field in ISO 8601 format
```

---

## Allowed Files

```
src/wbsb/observability/logging.py    ← APPEND ONLY — do not modify existing code
tests/test_observability.py          ← create
```

## Files Not to Touch

```
src/wbsb/feedback/           ← I11-1/2/3/5
src/wbsb/cli.py              ← I11-5
```

---

## Execution Workflow

```bash
# 1. Read the ENTIRE existing logging.py before touching it
#    Understand: StructLogger, JsonlHandler, get_logger, init_run_logger
#    Do not change any of these

# 2. Append event constants and new functions AT THE END of logging.py

# 3. Write tests

pytest && ruff check .

# Verify existing observability functions still work
python -c "from wbsb.observability.logging import get_logger, init_run_logger; print('existing OK')"

# Verify new exports
python -c "from wbsb.observability.logging import pseudonymize_ip, log_security_event, EVENT_AUTH_FAILURE; print('new OK')"

# Scope check
git diff --name-only feature/iteration-11
# Only logging.py and test_observability.py

git add src/wbsb/observability/logging.py tests/test_observability.py
git commit -m "feat(i11-4): security observability — pseudonymize_ip and log_security_event"
git push origin feature/i11-4-observability
gh pr ready
```

---

## Acceptance Criteria

- [ ] `pseudonymize_ip('192.168.1.47')` returns `'192.168.1.0'`
- [ ] `pseudonymize_ip` never raises — invalid input returned unchanged
- [ ] `log_security_event` never raises
- [ ] Every emitted event contains `event` and `timestamp` fields
- [ ] All 5 event constants importable from `wbsb.observability.logging`
- [ ] Existing functions (`get_logger`, `init_run_logger`, `StructLogger`) unchanged — all existing tests still pass
- [ ] All 6 new tests present and passing
- [ ] All 391 baseline tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Existing `logging.py` read before modifying
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] Code appended — no existing functions modified
- [ ] `pseudonymize_ip` never-raise confirmed by test with invalid input
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
