# WBSB Review Prompt — I9-7: Feedback Webhook Server

---

## Reviewer Mandate

Review I9-7 strictly against tasks.md.
This is security-critical. Be strict.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-7-feedback-webhook
git pull origin feature/i9-7-feedback-webhook
```

2. Validate:
```bash
pytest --tb=short -q
ruff check .
```

3. Scope:
```bash
git diff --name-only feature/iteration-9
```

Allowed:
- `src/wbsb/feedback/server.py`
- `src/wbsb/cli.py`
- `tests/test_feedback_server.py`

4. Security validation checks:
```bash
grep -n "RUN_ID_PATTERN\|VALID_SECTIONS\|VALID_LABELS\|Content-Length\|4096\|1000\|anonymous\|uuid" src/wbsb/feedback/server.py
```

Verify:
- run_id regex enforcement
- section/label allowlist enforcement
- body cap (413 over 4096)
- comment truncation to 1000
- operator cap/default
- uuid-based filename, not user-derived path

5. Logging hygiene check:
```bash
grep -n "comment\|feedback_received\|log\." src/wbsb/feedback/server.py
```

Ensure comment value not logged.

6. CLI check:
```bash
wbsb feedback serve --help
```

7. Tests presence check:
```bash
grep -n "^def test_" tests/test_feedback_server.py
```

---

## Required Output Format

1. Verdict
2. What's Correct
3. Problems Found
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check
7. Exact Fixes Required
8. Final Recommendation

---

## Acceptance Criteria Check List

- [ ] endpoint route and responses correct
- [ ] run_id/section/label validation enforced
- [ ] body size cap enforced
- [ ] comment/operator capping behavior correct
- [ ] safe file-write path (uuid only)
- [ ] no comment content logging
- [ ] `wbsb feedback serve` added
- [ ] only allowed files modified
- [ ] required tests present/meaningful
- [ ] tests pass
- [ ] ruff clean
