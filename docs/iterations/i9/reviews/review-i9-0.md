# WBSB Review Prompt — I9-0: Pre-Work Docs Normalisation + Scaffolding

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-0 strictly against `docs/iterations/i9/tasks.md`.
Do not fix code. Report scope drift, missing deliverables, and contract violations with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure (Teams/Slack delivery, scheduler, feedback webhook, Docker).

I9-0 is the pre-work task: it normalises project docs to the current state and scaffolds the delivery/scheduler Python packages before any implementation task begins. Nothing in this task produces runtime functionality — it prepares the ground.

---

## Task Under Review

- Task: I9-0 — Pre-Work Docs Normalisation + Package Scaffolding
- Branch: `feature/i9-0-pre-work`
- Base: `feature/iteration-9`

Expected files in scope:
- `docs/project/project-iterations.md`
- `docs/project/HOW_IT_WORKS.md`
- `docs/project/PROJECT_BRIEF.md`
- `docs/project/TASKS.md`
- `src/wbsb/delivery/__init__.py`
- `src/wbsb/delivery/models.py`
- `src/wbsb/scheduler/__init__.py`
- `.env.example`

---

## Review Execution Steps

### Step 1 — Checkout branch

```bash
git fetch origin
git checkout feature/i9-0-pre-work
git pull origin feature/i9-0-pre-work
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

Fail if any file outside the allowed list is changed.

### Step 4 — Verify docs content updates

```bash
grep -n "I9\|In Progress\|324" docs/project/project-iterations.md docs/project/HOW_IT_WORKS.md docs/project/PROJECT_BRIEF.md docs/project/TASKS.md
```

Verify:
- I9 status is "In Progress" where applicable
- 324 test baseline referenced correctly
- I6 and I7 marked complete
- I9 roadmap ordering correct

### Step 5 — Verify scaffolding and model imports

```bash
python3 -c "from wbsb.delivery.models import DeliveryResult, DeliveryTarget, DeliveryStatus; print('OK')"
```

### Step 6 — Verify `.env.example` env vars

```bash
grep -n "ANTHROPIC_API_KEY\|WBSB_LLM_MODEL\|WBSB_LLM_MODE\|TEAMS_WEBHOOK_URL\|SLACK_WEBHOOK_URL" .env.example
```

All five env vars must be present as placeholder-only entries (no real values).

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. Missing or Weak Items
5. Scope Violations
6. Acceptance Criteria Check (`[PASS]` or `[FAIL]` per line)
7. Exact Fixes Required
8. Final Recommendation (`approve | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] project docs normalised to current I9 state
- [ ] 324 baseline references updated where required
- [ ] I6 and I7 completion reflected accurately
- [ ] delivery/scheduler package markers created
- [ ] `DeliveryResult` model import/instantiation works
- [ ] `.env.example` includes all five env vars (no real values)
- [ ] only allowed files changed
- [ ] tests pass
- [ ] ruff clean
