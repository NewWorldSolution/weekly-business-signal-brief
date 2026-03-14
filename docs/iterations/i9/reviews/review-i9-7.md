# WBSB Review Prompt — I9-7: Feedback Webhook Server

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-7 strictly against `docs/iterations/i9/tasks.md`.
This is a security-critical task. Apply strict scrutiny to every validation and file-write path.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure.

**Security surface:** I9-7 introduces the only inbound HTTP endpoint in the system (`POST /feedback`). It accepts external input from Teams/Slack button payloads. All user-supplied fields must be validated or rejected before any file is written. The feedback file path must always be derived from a UUID, never from user input.

**MVP limitation:** no authentication is implemented; this must be explicitly documented in the server code.

---

## Task Under Review

- Task: I9-7 — Feedback Webhook Server
- Branch: `feature/i9-7-feedback-webhook`
- Base: `feature/iteration-9`

Expected files in scope:
- `src/wbsb/feedback/server.py`
- `src/wbsb/cli.py`
- `tests/test_feedback_server.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-7-feedback-webhook
git pull origin feature/i9-7-feedback-webhook
```

### Step 2 — Run validation

```bash
pytest --tb=short -q
ruff check .
```

If either fails: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-9
```

Allowed: `src/wbsb/feedback/server.py`, `src/wbsb/cli.py`, `tests/test_feedback_server.py`.
Forbidden: `src/wbsb/feedback/store.py`, `src/wbsb/feedback/models.py`.

### Step 4 — Input validation checks

```bash
grep -n "RUN_ID_PATTERN\|VALID_SECTIONS\|VALID_LABELS\|Content-Length\|4096\|1000\|anonymous\|uuid" src/wbsb/feedback/server.py
```

Verify all validation constants are present:
- `RUN_ID_PATTERN`: `^\d{8}T\d{6}Z_[a-f0-9]{6}$`
- `VALID_SECTIONS`: allowlist enforced
- `VALID_LABELS`: allowlist enforced
- Body size cap: reject `Content-Length > 4096` with HTTP 413
- Comment truncated to 1000 chars (not rejected — truncated silently)
- Operator capped and defaulted to `"anonymous"` when absent

### Step 5 — Path safety check

```bash
grep -n "uuid\|feedback/\|file\|open\|Path\|write" src/wbsb/feedback/server.py
```

Verify:
- Output path is always `feedback/{uuid4()}.json`
- No user-supplied value (run_id, section, label, comment, operator) is used in path construction
- No path traversal possible

### Step 6 — Logging hygiene check

```bash
grep -n "comment\|feedback_received\|log\.\|logger\." src/wbsb/feedback/server.py
```

Ensure:
- Comment content is NOT logged at any level
- Operator field is NOT logged
- Only metadata (run_id, section, label, file path written) may appear in logs

### Step 7 — No-auth documentation check

Verify a comment or docstring in `server.py` explicitly notes: "No authentication implemented in MVP."

### Step 8 — CLI check

```bash
wbsb feedback serve --help
```

Verify `--host` and `--port` flags present.

### Step 9 — Test presence check

```bash
grep -n "^def test_" tests/test_feedback_server.py
```

Required tests:
- `test_valid_feedback_returns_200`
- `test_invalid_run_id_returns_400`
- `test_invalid_section_returns_400`
- `test_invalid_label_returns_400`
- `test_body_too_large_returns_413`
- `test_comment_truncated_silently`
- `test_feedback_id_not_derived_from_input`

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

## Acceptance Criteria Check List

- [ ] endpoint route and HTTP responses correct (200/400/413)
- [ ] `run_id` regex validation enforced
- [ ] `section` allowlist enforced
- [ ] `label` allowlist enforced
- [ ] body size cap (4096 bytes / HTTP 413) enforced
- [ ] comment truncated to 1000 chars
- [ ] operator capped and defaulted to `"anonymous"`
- [ ] output file path is UUID-only (no user-derived component)
- [ ] no path traversal possible
- [ ] comment content not logged at any level
- [ ] operator not logged
- [ ] MVP no-auth limitation documented in code
- [ ] `wbsb feedback serve --host --port` command present
- [ ] only allowed files modified
- [ ] all required tests present and meaningful
- [ ] tests pass
- [ ] ruff clean
