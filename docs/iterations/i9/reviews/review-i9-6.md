# WBSB Review Prompt — I9-6: Failure Alerting Path

---

## Reviewer Mandate

Review I9-6 strictly against tasks.md.
Validate all 3 alert scenarios and non-raising dispatch behavior.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-6-failure-alerting
git pull origin feature/i9-6-failure-alerting
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
- `src/wbsb/delivery/alerts.py`
- `src/wbsb/scheduler/watcher.py`
- `src/wbsb/cli.py`
- `tests/test_delivery_alerts.py`

4. Verify alert APIs:
```bash
python3 -c "from wbsb.delivery.alerts import build_pipeline_error_alert, build_no_file_alert, send_alert; import inspect; print(inspect.signature(build_pipeline_error_alert)); print(inspect.signature(build_no_file_alert)); print(inspect.signature(send_alert))"
```

5. Verify 3 scenarios covered (code + tests):
- llm fallback
- pipeline error
- no new file

6. Ensure non-raising alert dispatch:
```bash
grep -n "except.*pass\|raise" src/wbsb/delivery/alerts.py
```

7. Ensure CLI visible output for alert scenarios.

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

- [ ] alert builder APIs implemented
- [ ] all 3 alert scenarios implemented
- [ ] `send_alert` dispatch is non-raising
- [ ] CLI emits visible warnings for alert scenarios
- [ ] only allowed files modified
- [ ] required tests present/meaningful
- [ ] tests pass
- [ ] ruff clean
