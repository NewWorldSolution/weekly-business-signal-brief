# WBSB Review Prompt — I9-0: Pre-Work Docs Normalisation + Scaffolding

---

## Reviewer Role & Mandate

Review I9-0 against `docs/iterations/i9/tasks.md` only.
Do not fix code. Report scope drift and contract violations.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout branch:
```bash
git fetch origin
git checkout feature/i9-0-pre-work
git pull origin feature/i9-0-pre-work
```

2. Validate:
```bash
pytest --tb=short -q
ruff check .
```

3. Scope check:
```bash
git diff --name-only feature/iteration-9
```

Allowed files:
- `docs/project/project-iterations.md`
- `docs/project/HOW_IT_WORKS.md`
- `docs/project/PROJECT_BRIEF.md`
- `docs/project/TASKS.md`
- `src/wbsb/delivery/__init__.py`
- `src/wbsb/delivery/models.py`
- `src/wbsb/scheduler/__init__.py`
- `.env.example`

4. Verify docs content updates:
```bash
grep -n "I9\|In Progress\|324" docs/project/project-iterations.md docs/project/HOW_IT_WORKS.md docs/project/PROJECT_BRIEF.md docs/project/TASKS.md
```

5. Verify scaffolding/models import:
```bash
python3 -c "from wbsb.delivery.models import DeliveryResult, DeliveryTarget, DeliveryStatus; print('OK')"
```

6. Verify `.env.example` vars present:
```bash
grep -n "ANTHROPIC_API_KEY\|WBSB_LLM_MODEL\|WBSB_LLM_MODE\|TEAMS_WEBHOOK_URL\|SLACK_WEBHOOK_URL" .env.example
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

- [ ] project docs normalized to current I9 state
- [ ] 324 baseline references updated where required
- [ ] delivery/scheduler package markers created
- [ ] `DeliveryResult` model import/instantiation works
- [ ] `.env.example` includes all five env vars
- [ ] only allowed files changed
- [ ] tests pass
- [ ] ruff clean
