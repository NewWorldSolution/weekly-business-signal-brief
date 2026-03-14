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

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-10-final-cleanup`
- **Worktree:** `../wbsb-i9-10-final-cleanup`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-10-final-cleanup

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-10): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-10-final-cleanup \
  --title "I9-10: final cleanup for merge" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

**Dependency:** Do not begin implementation until the I9-9 architecture review has passed and all findings are documented. After I9-9 is complete, sync with the latest `feature/iteration-9` before implementing:

```bash
git fetch origin && git rebase origin/feature/iteration-9
```

---

## Objective

Execute final cleanup exactly per tasks.md:
1. resolve I9-9 findings
2. update I9 status/docs to Complete
3. verify green build
4. prepare final `feature/iteration-9 -> main` PR

---

## Inputs and Outputs

### Inputs
- I9-9 review output (list of findings with severity and fix evidence)
- `docs/project/TASKS.md` (current I9 status)
- `docs/project/project-iterations.md` (iteration status)

### Outputs
- `docs/project/TASKS.md` — I9 marked Complete with Definition of Done
- `docs/project/project-iterations.md` — I9 status updated to Complete
- Source/test fixes (only if required by I9-9 findings; must be traceable to specific finding)

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
