# WBSB Review Prompt — I11-4: Security Observability

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-4 strictly against `docs/iterations/i11/tasks.md`.
This is a privacy-relevant task. Apply scrutiny to IP pseudonymization correctness, log field hygiene, and the "append-only" constraint on the existing production file.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-4 **extends** the existing production `src/wbsb/observability/logging.py` with security event constants, IP pseudonymization, and a structured log helper.

**Critical constraint:** `src/wbsb/observability/logging.py` is a production file used across the entire pipeline. No existing code may be removed or modified — only appended. Any modification to `get_logger`, `StructLogger`, `JsonlHandler`, or `init_run_logger` is a `BLOCKED` finding.

**Privacy surface:** `log_security_event` must never log sensitive values: no secret, signature, request body, comment, or full nonce. IP addresses must be pseudonymized before logging. Failure here means attacker payloads or credentials could appear in log files.

---

## Task Under Review

- Task: I11-4 — Security Observability
- Branch: `feature/i11-4-observability`
- Base: `feature/iteration-11`

Expected files in scope:
- `src/wbsb/observability/logging.py` (extend — append new constants and functions)
- `tests/test_observability.py` (create)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-4-observability
git pull origin feature/i11-4-observability
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

Allowed: `src/wbsb/observability/logging.py`, `tests/test_observability.py`.

Forbidden: `src/wbsb/feedback/`, `src/wbsb/cli.py`, `Dockerfile`.

### Step 4 — Existing functions untouched (critical)

```bash
git diff feature/iteration-11 -- src/wbsb/observability/logging.py
```

Review the diff carefully. Verify that `StructLogger`, `JsonlHandler`, `get_logger`, and `init_run_logger` are identical to baseline. Any change to these functions → `BLOCKED`.

### Step 5 — Event constants check

```bash
grep -n "EVENT_AUTH_FAILURE\|EVENT_REPLAY_DETECTED\|EVENT_RATE_LIMIT_EXCEEDED\|EVENT_FEEDBACK_RECEIVED\|EVENT_INVALID_INPUT" src/wbsb/observability/logging.py
```

All five constants must be present with exact string values:
- `EVENT_AUTH_FAILURE = "auth_failure"`
- `EVENT_REPLAY_DETECTED = "replay_detected"`
- `EVENT_RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"`
- `EVENT_FEEDBACK_RECEIVED = "feedback_received"`
- `EVENT_INVALID_INPUT = "invalid_input"`

### Step 6 — IP pseudonymization check

```bash
grep -n "def pseudonymize_ip\|split\|\\.0\|last.*octet\|zeroing" src/wbsb/observability/logging.py
```

Verify:
- IPv4: last octet replaced with `0` (e.g. `192.168.1.47` → `192.168.1.0`)
- IPv6: last group replaced with `0`
- Invalid input returned unchanged — function never raises

### Step 7 — Never-raise check for `pseudonymize_ip`

```bash
grep -A 20 "def pseudonymize_ip" src/wbsb/observability/logging.py
```

Verify the function has a broad `except` or explicit format validation that prevents raising on unexpected input.

### Step 8 — `log_security_event` timestamp check

```bash
grep -n "timestamp\|utcnow\|isoformat" src/wbsb/observability/logging.py
```

Every emitted event must include a `timestamp` field in ISO 8601 format.

### Step 9 — Sensitive field leak check

```bash
grep -n "secret\|signature\|body\|comment\|nonce" src/wbsb/observability/logging.py
```

These field names must NOT appear as keys being logged in `log_security_event`. The function may check for or document the exclusion of these fields, but must not log them.

### Step 10 — Test presence check

```bash
grep -n "^def test_" tests/test_observability.py
```

Required tests:
- `test_pseudonymize_ipv4`
- `test_pseudonymize_ipv4_last_zero`
- `test_pseudonymize_ipv6`
- `test_pseudonymize_invalid_input`
- `test_log_security_event_emits`
- `test_log_security_event_has_timestamp`

### Step 11 — Existing tests unaffected

```bash
pytest tests/ -k "not test_observability" --tb=short -q
```

All pre-I11 tests must pass.

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

- [ ] `pseudonymize_ip('192.168.1.47')` returns `'192.168.1.0'`
- [ ] `pseudonymize_ip` handles IPv6 (last group zeroed)
- [ ] `pseudonymize_ip` returns invalid input unchanged — never raises
- [ ] `log_security_event` never raises
- [ ] Every emitted event contains `event` and `timestamp` fields
- [ ] All 5 event constants present with correct string values
- [ ] All 5 constants importable from `wbsb.observability.logging`
- [ ] No sensitive field names (`secret`, `signature`, `body`, `comment`) logged
- [ ] Existing functions (`get_logger`, `StructLogger`, `init_run_logger`) unchanged
- [ ] All 6 required tests present and passing
- [ ] All baseline tests pass
- [ ] Code appended only — no existing code removed or modified
- [ ] Ruff clean
- [ ] Only allowed files modified
