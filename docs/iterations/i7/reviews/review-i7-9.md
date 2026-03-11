# WBSB Review Prompt — I7-9: Final Cleanup + Merge to Main

---

## Reviewer Role & Mandate

You are an **independent code reviewer** for the WBSB project.

I7-9 is the final cleanup task before `feature/iteration-7` → `main`. Your role is to confirm
that all I7-8 findings were addressed, documentation is accurate, the full test suite is green,
and the iteration branch is ready to merge.

**Your mandate:**

- Verify every finding from I7-8 has been resolved.
- Verify docs accurately reflect the completed iteration state.
- Confirm no scope creep was introduced during cleanup.
- Run the full test suite and golden runner one final time.

**What you must NOT do:**

- Do not fix code. Document findings for resolution before the final PR.
- Do not invent problems. Every finding needs evidence.

**Your verdict has three options:**

| Verdict | Meaning |
|---------|---------|
| `PASS` | I7-8 findings resolved, docs accurate, tests green. Ready for final PR to main. |
| `CHANGES REQUIRED` | One or more issues remain. Must be resolved before final merge. |
| `BLOCKED` | A systemic issue prevents merge. Escalate before proceeding. |

---

## Project Context

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for
appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics,
detects signals via a config-driven rules engine, and generates a structured business brief.
An LLM is optionally used for narrative sections only — never for calculations or decisions.

**Core pipeline:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Architecture principles (violations of any = CHANGES REQUIRED minimum):**

| # | Principle |
|---|-----------|
| 1 | **Deterministic first** — no randomness, no time-dependent logic in metrics or rules |
| 2 | **Config-driven** — all thresholds in `config/rules.yaml`; zero hardcoded numbers in code |
| 3 | **No silent failure** — never `except: pass`; errors must be logged and recorded |
| 4 | **Separation of concerns** — eval and feedback packages must not import from each other |
| 5 | **Domain model is frozen** — `src/wbsb/domain/models.py` must not be modified |

---

## Task Under Review

| Field | Value |
|-------|-------|
| Task ID | I7-9 |
| Title | Final Cleanup + Merge to Main |
| Iteration | Iteration 7 — Evaluation Framework & Operator Feedback Loop |
| Implemented by | Claude |
| Reviewed by | Codex |
| Iteration branch | `feature/iteration-7` |
| Feature branch | `feature/i7-9-final-cleanup` |
| Expected test count | 320 passing — same before and after (no new tests) |

---

## Review Execution Steps

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout feature/i7-9-final-cleanup
git pull origin feature/i7-9-final-cleanup
```

### Step 2 — Run full test suite

```bash
pytest --tb=short -q
# Expected: 320 passing, 0 failures

ruff check .
# Expected: no issues
```

If either fails, verdict is `CHANGES REQUIRED` immediately.

### Step 3 — Verify scope — only cleanup files

```bash
git diff --name-only feature/iteration-7
```

Expected — only these categories of files:
- `docs/project/TASKS.md`
- `docs/project/project-iterations.md`
- `feedback/.gitkeep` (if it was missing)
- `.gitignore` (if feedback rules were missing)
- Bug fix files flagged in I7-8 (if any)

**No new features.** Any new module or new public function = scope creep = `severity: major`.

### Step 4 — Verify TASKS.md is updated correctly

```bash
grep -n "I7\|Iteration 7\|Complete\|🔲\|✅" docs/project/TASKS.md
```

Verify:
- I7 row shows `✅ Complete` status.
- I7 Definition of Done section has all boxes ticked `[x]`.
- No other iteration rows changed.

### Step 5 — Verify project-iterations.md is updated

```bash
grep -n "I7\|Iteration 7\|Complete\|Planned\|In Progress" docs/project/project-iterations.md
```

Expected: I7 status updated to `Complete`. No other iterations changed.

### Step 6 — Verify all DoD items are ticked

Read the I7 Definition of Done section in `docs/project/TASKS.md` and confirm every item
is checked `[x]`:

**Evaluation Engine:**
- `[x]` eval_scores written to llm_response.json on every successful LLM run
- `[x]` eval_skipped_reason set correctly on LLM fallback and scorer error
- `[x]` Grounding score computable (or null with reason when no numbers cited)
- `[x]` Signal coverage counts both WARN and INFO signals
- `[x]` Hallucination violations classified by type and severity
- `[x]` No hardcoded tolerance values
- `[x]` Scorer never breaks report generation

**Golden Dataset:**
- `[x]` At least 6 cases present in `src/wbsb/eval/golden/`
- `[x]` `wbsb eval` runs all cases and exits 0 when all pass
- `[x]` `fallback_no_llm` case always present and always passing
- `[x]` Governance rules documented in `eval/golden/README.md`

**Feedback System:**
- `[x]` `save_feedback()` validates run_id, section, label — raises ValueError on violation
- `[x]` Comment truncated to 1000 chars silently
- `[x]` `wbsb feedback list/summary/export` commands operational
- `[x]` `feedback/` directory gitignored, `.gitkeep` committed
- `[x]` No webhook server built in I7

**Quality:**
- `[x]` All 271 baseline tests still passing + 49 new I7 tests (320 total)
- `[x]` Ruff clean
- `[x]` `domain/models.py` unchanged
- `[x]` `main` branch stable

Any unchecked DoD item = `severity: major`.

### Step 7 — Run golden runner final verification

```bash
wbsb eval
echo "Exit code: $?"
# Expected: all 6 cases [PASS], exit code 0
```

### Step 8 — Run feedback CLI final verification

```bash
wbsb feedback summary
wbsb feedback list
# Expected: both commands run without error
```

### Step 9 — Verify feedback/.gitkeep is tracked

```bash
git ls-files feedback/.gitkeep
# Expected: feedback/.gitkeep

git status
# Expected: clean working tree (no untracked feedback files)
```

### Step 10 — Verify no scope creep from cleanup

```bash
git diff --stat feature/iteration-7
```

Confirm no unexpected files were added or changed. Changes should be limited to:
- Documentation files
- Gitignore / gitkeep
- Bug fixes explicitly flagged in I7-8

---

## Required Output Format

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List everything verified correctly. Must not be empty on a PASS verdict.

---

### 3. Problems Found

```
- severity: critical | major | minor
  file: path/to/file:LINE
  exact problem: one or two sentences
  why it matters: one sentence on the consequence
```

If no problems: `None.`

---

### 4. I7-8 Findings Resolution

For each finding from the I7-8 review:

```
- finding: [brief description from I7-8]
  resolved: yes | no | partially
  evidence: file:line or command output confirming resolution
```

If I7-8 verdict was `PASS` (no findings): `None.`

---

### 5. Scope Violations

```
- file: path/to/unexpected_file
  change: what was changed
  verdict: revert | acceptable given I7-8 finding
```

If no violations: `None.`

---

### 6. Acceptance Criteria Check

```
- [PASS | FAIL] I7-8 CHANGES REQUIRED findings all addressed
- [PASS | FAIL] docs/project/TASKS.md: I7 status = Complete
- [PASS | FAIL] docs/project/TASKS.md: all DoD boxes ticked [x]
- [PASS | FAIL] docs/project/project-iterations.md: I7 status = Complete
- [PASS | FAIL] feedback/.gitkeep tracked in git
- [PASS | FAIL] .gitignore feedback rules correct (feedback/* and !feedback/.gitkeep)
- [PASS | FAIL] wbsb eval passes all golden cases, exit code 0
- [PASS | FAIL] wbsb feedback summary/list run without error
- [PASS | FAIL] No scope creep — no new features added during cleanup
- [PASS | FAIL] 320 tests pass, 0 failures
- [PASS | FAIL] Ruff clean
- [PASS | FAIL] feature/iteration-7 branch is ready for final PR to main
```

---

### 7. Exact Fixes Required

Numbered list. Each fix must be actionable.
If verdict is PASS: `None.`

---

### 8. Final Recommendation

```
approve for final merge | request changes | block
```

One sentence explaining the recommendation.
If PASS: include the exact `gh pr create` command for the final iteration PR.
