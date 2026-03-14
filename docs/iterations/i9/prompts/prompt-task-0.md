# Task Prompt — I9-0: Pre-Work (Docs Normalisation + Package Scaffolding)

---

## Context

You are implementing **task I9-0** of Iteration 9 (Deployment & Delivery) for WBSB.
This task prepares the repo before delivery/scheduler work starts.

**Task outcome:** normalize project docs to current state, add minimal package scaffolding,
and add `.env.example`.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Documentation must reflect real project state (324 tests baseline, I9 in progress). |
| 2 | No silent failure patterns introduced. |
| 3 | Do not modify pipeline logic in this task. |
| 4 | Do not modify tests in this task. |
| 5 | Open a draft PR before code/doc edits (Step 0). |
| 6 | Touch only allowed files. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-0-pre-work`
- **Worktree:** `../wbsb-i9-0-pre-work`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-0-pre-work

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-0): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-0-pre-work \
  --title "I9-0: pre-work docs normalization and scaffolding" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

---

## Objective

Implement exactly what `docs/iterations/i9/tasks.md` defines for I9-0:

1. Docs normalization in project-level docs
2. Package scaffolding for delivery/scheduler packages
3. `.env.example` with documented env vars (no secret values)

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-0 section)
- Current project docs under `docs/project/`

### Outputs
- Updated project docs aligned with I9 current state
- New package marker files and `delivery/models.py`
- Root `.env.example`

---

## Allowed Files

```text
docs/project/project-iterations.md
docs/project/HOW_IT_WORKS.md
docs/project/PROJECT_BRIEF.md
docs/project/TASKS.md
src/wbsb/delivery/__init__.py
src/wbsb/delivery/models.py
src/wbsb/scheduler/__init__.py
.env.example
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/cli.py
src/wbsb/domain/models.py
config/rules.yaml
Any test file
```

---

## Execution Workflow

1. Read I9-0 section in `docs/iterations/i9/tasks.md` fully.
2. Update docs exactly as specified:
   - I9 status to In Progress where required
   - baseline/test count references to 324
   - roadmap ordering statements corrected
   - I7 completion reflected accurately
3. Create package scaffolding files:
   - `src/wbsb/delivery/__init__.py`
   - `src/wbsb/delivery/models.py` with `DeliveryTarget`, `DeliveryStatus`, `DeliveryResult`
   - `src/wbsb/scheduler/__init__.py`
4. Create root `.env.example` with the exact env var contract from tasks.md.
5. Run verification:

```bash
pytest --tb=short -q
ruff check .
```

6. Validate scope:

```bash
git diff --name-only feature/iteration-9
```

7. Push branch and mark PR ready.

---

## Test Requirements

- Existing suite must stay green.
- No new tests are required by this task.

---

## Acceptance Criteria

- `docs/project/project-iterations.md` uses 324 baseline references and marks I9 In Progress.
- `docs/project/HOW_IT_WORKS.md` includes I6/I7 modules and updated command set (`wbsb eval`, `wbsb feedback`).
- `docs/project/PROJECT_BRIEF.md` marks I6 and I7 complete; I9 in progress.
- `src/wbsb/delivery/models.py` can instantiate `DeliveryResult` without error.
- `.env.example` exists at repo root with all five env vars documented.
- No existing tests broken.
- Ruff clean.

---

## Completion Checklist

- [ ] Step 0 completed (draft PR opened before edits)
- [ ] Only allowed files changed
- [ ] Docs updated per I9-0 specification
- [ ] Scaffolding files created
- [ ] `.env.example` created with no real values
- [ ] `pytest` passes
- [ ] `ruff check .` passes
