# Task Prompt — I7-9: Final Cleanup + Merge to Main

---

## Context

You are implementing **task I7-9** of Iteration 7 (Evaluation Framework & Operator Feedback Loop)
for the WBSB project. I7-8 (architecture review) is complete. All findings from the review
have been documented. This task closes the iteration.

**Your task:** Fix any issues found in I7-8, update status docs, verify everything is green,
and open the final PR from `feature/iteration-7` → `main`.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | **Only fix what I7-8 flagged** — do not introduce new features or refactors |
| 2 | **No silent failure** — never `except: pass` |
| 3 | **Allowed files only** — see allowed file list below |
| 4 | **Draft PR first** — open a draft PR before writing any code |
| 5 | **Test before commit** — `pytest` and `ruff check .` must both pass before every push |

---

## Step 0 — Branch Setup (before making any changes)

```bash
# Start from the iteration branch — AFTER I7-8 review is complete
git checkout feature/iteration-7
git pull origin feature/iteration-7

# Create and push the task branch
git checkout -b feature/i7-9-final-cleanup
git push -u origin feature/i7-9-final-cleanup

# Open a draft PR immediately
gh pr create \
  --base feature/iteration-7 \
  --head feature/i7-9-final-cleanup \
  --title "I7-9: Final cleanup + merge to main" \
  --body "Work in progress." \
  --draft

# Verify full test suite is green before touching anything
pytest --tb=short -q
ruff check .
# Expected: all I7 tests passing, ruff clean
```

---

## What to Do

### 1 — Fix any issues flagged in I7-8

Read the I7-8 architecture review output. Fix every `CHANGES REQUIRED` item before continuing.
If I7-8 verdict was `PASS`, skip this step.

### 2 — Ensure `feedback/.gitkeep` is committed

```bash
ls -la feedback/.gitkeep
# Must exist. If missing:
touch feedback/.gitkeep
git add feedback/.gitkeep
```

### 3 — Verify `.gitignore` feedback rules

```bash
grep "feedback" .gitignore
# Must contain both lines:
# feedback/*
# !feedback/.gitkeep
```

### 4 — Update `docs/project/TASKS.md`

Update the I7 section:
- Change I7 status from `🔲 Next` to `✅ Complete`.
- Tick every Definition of Done checkbox:
  - `[x]` for all items under Evaluation Engine, Golden Dataset, Feedback System, Quality.

### 5 — Update `docs/project/project-iterations.md`

Change I7 status from `Planned` or `In Progress` to `Complete`.

### 6 — Run full validation

```bash
pytest --tb=short -q
# Expected: all tests passing, 0 failures

ruff check .
# Expected: no issues

# Smoke test CLI commands
wbsb eval
# Expected: all golden cases PASS, exit code 0

wbsb feedback summary
# Expected: prints summary (0 counts is fine)
```

### 7 — Verify eval_scores in a real run (optional but recommended)

```bash
export $(cat .env | xargs)
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full
cat runs/$(ls -t runs/ | head -1)/*/llm_response.json | python3 -m json.tool | grep -A 15 '"eval_scores"'
# Expected: eval_scores object with grounding, signal_coverage, group_coverage,
#           hallucination_risk, hallucination_violations, model, evaluated_at
```

---

## Allowed Files

```
docs/project/TASKS.md
docs/project/project-iterations.md
.gitignore                              ← only if feedback rules missing
feedback/.gitkeep                       ← only if missing
src/wbsb/eval/                          ← only if I7-8 found bugs here
src/wbsb/feedback/                      ← only if I7-8 found bugs here
src/wbsb/render/llm_adapter.py          ← only if I7-8 found bugs here
tests/                                  ← only if I7-8 found test gaps
```

No new code or features. Only fixes and docs.

---

## Definition of Done

```bash
pytest --tb=short -q
# Expected: 320 passing, 0 failures (271 baseline + 49 from I7)

ruff check .
# Expected: no issues

git diff --name-only feature/iteration-7
# Expected: only docs + gitkeep + any I7-8 fixes
```

---

## Commit and PR

```bash
# Stage only the files you changed
git add docs/project/TASKS.md docs/project/project-iterations.md
# Add any bug-fix files from I7-8 findings
git add feedback/.gitkeep  # if needed

git commit -m "$(cat <<'EOF'
chore(i7): final cleanup — update docs, verify iteration complete

Ticks all I7 DoD checkboxes, updates TASKS.md and project-iterations.md
to mark Iteration 7 as Complete. Applies any fixes from I7-8 review.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

git push origin feature/i7-9-final-cleanup
gh pr ready
```

---

## Final Iteration PR — `feature/iteration-7` → `main`

After this task's PR is merged into `feature/iteration-7`, open the final iteration PR:

```bash
git checkout feature/iteration-7
git pull origin feature/iteration-7

gh pr create \
  --base main \
  --head feature/iteration-7 \
  --title "Iteration 7: Evaluation Framework & Operator Feedback Loop" \
  --body "$(cat <<'EOF'
## Summary

- Automated eval scoring wired into LLM adapter: grounding, signal coverage, hallucination
- build_eval_scores() records results in llm_response.json on every LLM run
- Golden dataset runner (wbsb eval) with 6 initial cases
- Feedback storage (save/list/summarize/export) + wbsb feedback CLI
- Non-breaking design: scorer failure never causes pipeline failure
- 49 new tests added across I7 tasks (271 → 320 total)
- Ruff clean

## Test plan

- [ ] All 320 tests pass: pytest --tb=short -q
- [ ] Ruff clean: ruff check .
- [ ] wbsb eval passes all golden cases
- [ ] wbsb feedback summary prints correctly
- [ ] eval_scores present in llm_response.json on real --llm-mode full run
EOF
)"
```

Do not push directly to `main`. Wait for this PR to be reviewed and merged.
