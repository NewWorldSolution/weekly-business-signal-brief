# Task Prompt — I9-10: Final Cleanup + Merge to Main

---

## Context

You are implementing **task I9-10** of Iteration 9.
This is final cleanup after I9-9 architecture review.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Fix only review-identified issues; no new feature scope. |
| 2 | Keep cleanup changes minimal and traceable to I9-9 findings. |
| 3 | Update project status docs for I9 completion. |
| 4 | Full test and lint must pass before final PR. |
| 5 | Open draft PR first. |

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-10-final-cleanup
git push -u origin feature/i9-10-final-cleanup

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-10-final-cleanup \
  --title "I9-10: final cleanup for merge" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

---

## Objective

Execute final cleanup exactly per tasks.md:
1. resolve I9-9 findings
2. update I9 status/docs to Complete
3. verify green build
4. prepare final `feature/iteration-9 -> main` PR

---

## Allowed Files

```text
docs/project/TASKS.md
docs/project/project-iterations.md
src/wbsb/delivery/           (only if I9-9 found bugs)
src/wbsb/scheduler/          (only if I9-9 found bugs)
src/wbsb/feedback/server.py  (only if I9-9 found bugs)
src/wbsb/pipeline.py         (only if I9-9 found bugs)
src/wbsb/cli.py              (only if I9-9 found bugs)
tests/                       (only if I9-9 found gaps)
```

---

## Execution Workflow

1. Read I9-9 review output and list exact required fixes.
2. Apply only those fixes.
3. Update docs:
   - `docs/project/TASKS.md` (I9 complete + DoD)
   - `docs/project/project-iterations.md` (I9 complete)
4. Run full verification:

```bash
pytest --tb=short -q
ruff check .
wbsb eval
```

5. Verify scope vs iteration branch:

```bash
git diff --name-only feature/iteration-9
```

6. Push and mark PR ready.

---

## Test Requirements

- Full suite must pass.
- Ruff must be clean.
- Golden eval command must pass.

---

## Acceptance Criteria

- All I9-9 findings resolved.
- I9 status updated to Complete in both project docs.
- No scope creep introduced.
- Tests/lint/eval pass.
- Iteration branch ready for final PR to main.

---

## Completion Checklist

- [ ] Draft PR opened first
- [ ] Only review-driven fixes applied
- [ ] Project docs updated to I9 Complete
- [ ] `pytest` passes
- [ ] `ruff check .` passes
- [ ] `wbsb eval` passes
- [ ] Branch ready for final merge PR
