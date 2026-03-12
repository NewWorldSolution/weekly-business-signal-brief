# WBSB Review Prompt — I9-10: Final Cleanup + Merge to Main

---

## Reviewer Mandate

Review final cleanup task I9-10.
Confirm all I9-9 findings are addressed and branch is merge-ready.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-10-final-cleanup
git pull origin feature/i9-10-final-cleanup
```

2. Validate:
```bash
pytest --tb=short -q
ruff check .
wbsb eval
```

3. Scope check:
```bash
git diff --name-only feature/iteration-9
```

Allowed by default:
- `docs/project/TASKS.md`
- `docs/project/project-iterations.md`

Conditionally allowed only if tied to I9-9 findings:
- `src/wbsb/delivery/**`
- `src/wbsb/scheduler/**`
- `src/wbsb/feedback/server.py`
- `src/wbsb/pipeline.py`
- `src/wbsb/cli.py`
- `tests/**`

4. Docs completion checks:
```bash
grep -n "I9\|Complete\|Definition of Done\|\[x\]" docs/project/TASKS.md docs/project/project-iterations.md
```

5. I9-9 findings closure check:
- list each I9-9 finding
- map to fix commit/file evidence

6. Final branch readiness:
```bash
git diff --stat feature/iteration-9
git status
```

---

## Required Output Format

1. Verdict
2. What's Correct
3. Problems Found
4. Missing or Weak Tests
5. I9-9 Findings Resolution
6. Scope Violations
7. Acceptance Criteria Check
8. Exact Fixes Required
9. Final Recommendation (`approve for merge to main | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] I9-9 findings fully resolved
- [ ] I9 status updated to Complete in project docs
- [ ] no scope creep in cleanup
- [ ] tests pass
- [ ] ruff clean
- [ ] golden eval passes
- [ ] branch ready for final PR to main
