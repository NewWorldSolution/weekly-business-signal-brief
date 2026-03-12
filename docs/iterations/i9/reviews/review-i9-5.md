# WBSB Review Prompt — I9-5: Delivery Orchestrator + `wbsb deliver`

---

## Reviewer Mandate

Review I9-5 strictly against tasks.md.
Primary invariant: pipeline remains delivery-agnostic.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-5-cli-integration
git pull origin feature/i9-5-cli-integration
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
- `src/wbsb/delivery/orchestrator.py`
- `src/wbsb/cli.py`
- `tests/test_delivery_orchestrator.py`

4. Forbidden change check:
```bash
git diff feature/iteration-9 -- src/wbsb/pipeline.py src/wbsb/delivery/teams.py src/wbsb/delivery/slack.py
```
Expected: no diffs.

5. API check:
```bash
python3 -c "from wbsb.delivery.orchestrator import load_run_artifacts, deliver_run; import inspect; print(inspect.signature(load_run_artifacts)); print(inspect.signature(deliver_run))"
```

6. CLI checks:
```bash
wbsb deliver --help
wbsb run --help | grep -- "--deliver"
```

7. Verify behavior requirements in code/tests:
- load artifacts (findings+manifest required, llm optional)
- fallback flag handling passes `llm_result=None` to builders
- deliver_run non-raising; failures captured in `DeliveryResult`

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

- [ ] orchestrator API implemented as specified
- [ ] delivery reads artifacts from runs directory
- [ ] CLI `wbsb deliver` added
- [ ] CLI `wbsb run --deliver` added at CLI layer
- [ ] fallback behavior wired in orchestrator
- [ ] pipeline untouched
- [ ] only allowed files modified
- [ ] required tests present and strong
- [ ] tests pass
- [ ] ruff clean
