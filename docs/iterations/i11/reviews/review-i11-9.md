# WBSB Review Prompt — I11-9: Final Cleanup + Merge to Main

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-9 strictly against `docs/iterations/i11/tasks.md`.
This is the final gate before I11 merges to `main`. Focus on completeness, not re-reviewing implementation details (already reviewed in I11-0 through I11-8).
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-9 applies any I11-8 review findings, updates documentation to reflect I11 completion, and opens the final PR from `feature/iteration-11` to `main`.

---

## Task Under Review

- Task: I11-9 — Final Cleanup + Merge to Main
- Branch: `feature/i11-9-final-cleanup`
- Base: `feature/iteration-11`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-9-final-cleanup
git pull origin feature/i11-9-final-cleanup
```

### Step 2 — Full test suite

```bash
pytest --tb=short -q
```

Must pass. Zero failures, zero errors.

### Step 3 — Ruff

```bash
ruff check .
```

Must pass clean.

### Step 4 — Golden eval cases

```bash
wbsb eval
```

All 6 golden cases must pass.

### Step 5 — I11-8 findings resolved

Review the I11-8 review output. For each `[FAIL]` item:

```bash
# Check each item from I11-8 that was flagged
# Document resolution here before approving
```

If any I11-8 finding is unresolved: `CHANGES REQUIRED`.

### Step 6 — Documentation completeness check

```bash
grep -n "✅.*I11\|I11.*Complete\|I11.*complete" docs/project/TASKS.md
```

I11 must be marked complete.

```bash
grep -n "Security Controls\|HMAC\|rate limit\|non-root" docs/project/HOW_IT_WORKS.md
```

Security Controls section must be present.

```bash
grep -n "[0-9][0-9][0-9] tests\|[0-9][0-9][0-9] passing" docs/project/TASKS.md docs/project/project-iterations.md
```

Test count must match the actual `pytest` output from Step 2.

### Step 7 — Final security spot checks

```bash
# No stack traces in server
grep -rn "traceback\|Traceback" src/wbsb/feedback/server.py
# Must return nothing

# Constant-time comparison present
grep -n "compare_digest" src/wbsb/feedback/auth.py
# Must find it

# Non-root user in Dockerfile
grep -n "USER wbsb" Dockerfile
# Must find it in production stage

# Thread safety in both security modules
grep -n "Lock()" src/wbsb/feedback/auth.py src/wbsb/feedback/ratelimit.py
# Must find in both files

# Lockfile tool check
head -3 requirements.lock
# Must show pip-compile header
```

### Step 8 — PR opened to main

```bash
gh pr list --base main --head feature/iteration-11
```

The final iteration PR to `main` must exist and be open.

---

## Required Output Format

1. **Verdict** (`PASS | CHANGES REQUIRED | BLOCKED`)
2. **What's Correct** — list checks that passed
3. **Problems Found**
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. **Missing or Weak Tests** — any automated coverage gaps noticed during this final review
5. **Scope Violations** — any out-of-scope changes found in the cleanup branch
6. **Acceptance Criteria Check** (`[PASS]` or `[FAIL]` per item — see checklist below)
7. **Exact Fixes Required** — specific, actionable fix for each `[FAIL]` item
8. **Final Recommendation** (`approve | request changes | block`)

---

## Acceptance Criteria Checklist

- [ ] All I11-8 review findings resolved (or confirmed N/A)
- [ ] `pytest` passes — zero failures
- [ ] `ruff check .` clean
- [ ] `wbsb eval` all 6 golden cases pass
- [ ] `docs/project/TASKS.md` marks I11 complete with correct test count
- [ ] `docs/project/HOW_IT_WORKS.md` has Security Controls section
- [ ] `docs/project/project-iterations.md` marks I11 complete
- [ ] `grep traceback server.py` returns nothing
- [ ] `grep compare_digest auth.py` finds constant-time comparison
- [ ] `grep "USER wbsb" Dockerfile` finds non-root user in production stage
- [ ] `requirements.lock` has pip-compile header
- [ ] Final PR `feature/iteration-11` → `main` is open
