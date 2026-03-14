# WBSB Review Prompt — I9-10: Final Cleanup + Merge to Main

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-10 against the I9-9 architecture review findings.
This is the merge gate. Only I9-9-driven fixes are permitted.
Do not fix code. Report scope creep, missing closures, and quality failures.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 delivers the deployment and delivery infrastructure. I9-10 is the final task: it closes all I9-9 findings and updates project docs to mark the iteration Complete.

**Scope discipline:** any change not traceable to a specific I9-9 finding is out of scope and must be rejected.

---

## Task Under Review

- Task: I9-10 — Final Cleanup + Merge to Main
- Branch: `feature/i9-10-final-cleanup`
- Base: `feature/iteration-9`

Allowed by default:
- `docs/project/TASKS.md`
- `docs/project/project-iterations.md`

Conditionally allowed (only if tied to a specific I9-9 finding with evidence):
- `src/wbsb/delivery/**`
- `src/wbsb/scheduler/**`
- `src/wbsb/feedback/server.py`
- `src/wbsb/pipeline.py`
- `src/wbsb/cli.py`
- `tests/**`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-10-final-cleanup
git pull origin feature/i9-10-final-cleanup
```

### Step 2 — Full validation

```bash
pytest --tb=short -q
ruff check .
wbsb eval
```

All three must pass. Any failure: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-9
```

Review all changed files. Each changed file outside the default-allowed list must be justified by a specific I9-9 finding reference.

### Step 4 — I9-9 findings closure audit

For each finding in the I9-9 review output, verify it is closed:

```
Finding: [description from I9-9]
Fix: [commit hash or file:line where fix is applied]
Evidence: [grep or test output confirming the fix]
Status: CLOSED | OPEN
```

Any finding marked OPEN: `CHANGES REQUIRED`. Any critical finding without evidence: `BLOCKED`.

### Step 5 — Project docs completion check

```bash
grep -n "I9\|Complete\|Definition of Done\|\[x\]" docs/project/TASKS.md docs/project/project-iterations.md
```

Verify I9 is marked Complete in both files.

### Step 6 — Final branch readiness

```bash
git diff --stat feature/iteration-9
git status
```

No uncommitted changes. Branch is clean and ready for final PR to `main`.

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. I9-9 Findings Resolution (table: finding → fix → evidence → status)
5. Scope Violations (changes not traceable to I9-9 findings)
6. Acceptance Criteria Check (`[PASS]` or `[FAIL]` per line)
7. Exact Fixes Required
8. Final Recommendation (`approve for merge to main | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] all I9-9 findings explicitly closed with evidence
- [ ] no critical or major findings left open
- [ ] I9 status updated to Complete in `TASKS.md`
- [ ] I9 status updated to Complete in `project-iterations.md`
- [ ] no scope creep (all changes traceable to I9-9 findings)
- [ ] tests pass (`pytest --tb=short -q`)
- [ ] ruff clean
- [ ] golden eval passes (`wbsb eval`)
- [ ] branch is clean and ready for final PR to `main`
