# WBSB Comprehensive Review Prompt — I7-8: Architecture Review

---

## Reviewer Role & Mandate

You are an **independent architecture reviewer** for the WBSB project.

Tasks I7-0 through I7-7 have all been merged into `feature/iteration-7`. This is the system-level
gate before I7-9 (final cleanup and merge to main). You are reviewing the entire iteration as a
coherent system, not individual PRs.

**Your mandate:**

- Verify the full evaluation and feedback system works end-to-end.
- Confirm no architecture principles were violated across any task.
- Confirm the pipeline is still non-breaking: `--llm-mode off` works without any eval code.
- Run the full test suite and the golden runner.
- Be thorough. Every item in the architecture checklist must be verified by a command.

**What you must NOT do:**

- Do not fix code. Document findings. I7-9 applies fixes.
- Do not skip checklist items because "it was verified in a task review". Verify again now.

**Your verdict has three options:**

| Verdict | Meaning |
|---------|---------|
| `PASS` | All architecture checks pass. I7-9 may proceed. |
| `CHANGES REQUIRED` | One or more checks fail. I7-9 must fix before final merge. |
| `BLOCKED` | A fundamental design decision is wrong. Must be reconsidered before I7-9. |

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
| 6 | **LLM is optional** — scorer failure must never break report generation |
| 7 | **Non-breaking integration** — `--llm-mode off` produces a full valid report with no eval code |
| 8 | **Stable ordering** — where lists are built from sets, iteration must be `sorted()` |

---

## Scope of Review

All I7-introduced modules and their integration:

```
src/wbsb/eval/__init__.py
src/wbsb/eval/models.py
src/wbsb/eval/extractor.py
src/wbsb/eval/scorer.py
src/wbsb/eval/runner.py
src/wbsb/eval/golden/
src/wbsb/feedback/__init__.py
src/wbsb/feedback/models.py
src/wbsb/feedback/store.py
src/wbsb/render/llm_adapter.py     ← I7-5 modified this
src/wbsb/cli.py                    ← I7-6 and I7-7 modified this
config/rules.yaml                  ← I7-0 added eval: section
```

---

## Review Execution Steps

### Step 1 — Checkout iteration branch

```bash
git fetch origin
git checkout feature/iteration-7
git pull origin feature/iteration-7
```

### Step 2 — Full test suite

```bash
pytest --tb=short -q
# Expected: 320 passing, 0 failures

ruff check .
# Expected: no issues
```

If either fails, verdict is `CHANGES REQUIRED`. Report exact failing tests and lint output.

### Step 3 — Check 1: Scorer isolation (not wired in pipeline.py)

```bash
grep -n "build_eval_scores\|score_grounding\|score_signal_coverage\|score_hallucination" src/wbsb/pipeline.py
```

Expected: **no matches**. Scoring must be wired only through `llm_adapter.py`.

If any match: `severity: critical` — scorer is wired at the wrong level.

### Step 4 — Check 2: Non-breaking scorer path in llm_adapter.py

```bash
grep -n "scorer_error\|eval_skipped_reason\|llm_fallback\|eval_error" src/wbsb/render/llm_adapter.py
```

Expected: all 4 strings present.

Read the surrounding try/except block to verify:
- Scorer call is inside `try/except Exception` — not bare `except:`.
- Exception is NOT re-raised.
- `eval_error` is set to `str(exc)`.
- When `llm_result is None`: scorer is not called, `eval_skipped_reason="llm_fallback"`.

### Step 5 — Check 3: Domain model unchanged

```bash
grep -n "EvalScores\|FeedbackEntry\|HallucinationViolation" src/wbsb/domain/models.py
```

Expected: **no matches**. Eval types must live only in `src/wbsb/eval/models.py`.

```bash
git log --oneline -- src/wbsb/domain/models.py | head -5
# Look for any I7 commits modifying domain/models.py
```

### Step 6 — Check 4: No hardcoded tolerance values

```bash
grep -n "0\.01\|grounding_tolerance_abs\|grounding_tolerance_rel" src/wbsb/eval/scorer.py
# Expected: no literal 0.01 in scorer.py — all tolerance logic is in extractor.py

grep -n "0\.01\|grounding_tolerance_abs\|grounding_tolerance_rel" src/wbsb/eval/extractor.py
# Expected: config keys referenced (cfg["grounding_tolerance_abs"]), not literal 0.01
```

If `0.01` appears in extractor.py as a tolerance literal in logic (not a comment): `severity: major`.

### Step 7 — Check 5: Feedback validation enforced

```bash
grep -n "VALID_SECTIONS\|VALID_LABELS\|RUN_ID_PATTERN\|run_id\|ValueError" src/wbsb/feedback/store.py
```

Expected: all three validation guards present and raising `ValueError`.

```bash
python3 -c "
from wbsb.feedback.store import save_feedback
from wbsb.feedback.models import FeedbackEntry

# Invalid run_id must raise
try:
    save_feedback(FeedbackEntry(
        feedback_id='x', run_id='bad', section='situation',
        label='expected', comment='', submitted_at='2026-03-11T12:00:00Z'
    ))
    print('FAIL — run_id not validated')
except ValueError:
    print('OK — run_id validation enforced')
"
```

Expected: `OK — run_id validation enforced`

### Step 8 — Check 6: Cross-package import isolation

```bash
# eval must not import from feedback
grep -n "from wbsb.feedback\|import wbsb.feedback" \
    src/wbsb/eval/models.py src/wbsb/eval/extractor.py \
    src/wbsb/eval/scorer.py src/wbsb/eval/runner.py
# Expected: no matches

# feedback must not import from eval
grep -n "from wbsb.eval\|import wbsb.eval" \
    src/wbsb/feedback/models.py src/wbsb/feedback/store.py
# Expected: no matches
```

Any cross-import = `severity: critical` — violates Principle 4.

### Step 9 — Check 7: eval config section present in rules.yaml

```bash
python3 -c "
import yaml
from pathlib import Path

cfg = yaml.safe_load(Path('config/rules.yaml').read_text())
assert 'eval' in cfg, 'eval: section missing from config/rules.yaml'
ev = cfg['eval']
for key in ('grounding_tolerance_abs', 'grounding_tolerance_rel', 'grounding_pct_normalization'):
    assert key in ev, f'missing eval config key: {key}'
assert isinstance(ev['grounding_tolerance_abs'], float), 'grounding_tolerance_abs must be float'
assert isinstance(ev['grounding_tolerance_rel'], float), 'grounding_tolerance_rel must be float'
assert isinstance(ev['grounding_pct_normalization'], bool), 'grounding_pct_normalization must be bool'
print('eval config: OK')
"
```

Expected: `eval config: OK`

### Step 10 — Check 8: eval_scores present in real artifact

```bash
# Run pipeline in LLM mode and inspect artifact
export $(cat .env | xargs)
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full

# Find the latest run output
latest=$(ls -td runs/*/  2>/dev/null | head -1)
cat "${latest}"*/llm_response.json | python3 -m json.tool | grep -A 25 '"eval_scores"'
```

Expected: `eval_scores` object is present with these keys:
`schema_version`, `grounding`, `grounding_reason`, `flagged_numbers`,
`signal_coverage`, `group_coverage`, `hallucination_risk`,
`hallucination_violations`, `model`, `evaluated_at`.

If `eval_scores` is null, check `eval_skipped_reason` — if it is `"scorer_error"`,
read `eval_error` and report the exact message.

### Step 11 — Check 9: LLM-off mode still produces complete report

```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode off
# Expected: report generated, exit code 0, no eval-related error in output
```

If report fails in `--llm-mode off`: `severity: critical` — scorer is breaking the non-LLM path.

### Step 12 — Check 10: Golden runner passes all cases

```bash
wbsb eval
# Expected: all 6 cases print [PASS], exit code 0

echo "Exit code: $?"
```

If any case fails: report the case name and failure reasons. This is a `CHANGES REQUIRED` finding.

Also verify `--case` routing:

```bash
wbsb eval --case fallback_no_llm
echo "Exit code: $?"
# Expected: [PASS] fallback_no_llm, exit code 0
```

### Step 13 — Check 11: Feedback CLI commands operational

```bash
wbsb feedback summary
# Expected: prints {total: 0, by_label: {...}, by_section: {...}} without error

wbsb feedback list
# Expected: prints empty list or "no entries" without error

wbsb feedback --help
# Expected: shows list, summary, export subcommands
```

### Step 14 — Check 12: gitignore feedback rules correct

```bash
grep "feedback" .gitignore
# Expected: both lines present:
#   feedback/*
#   !feedback/.gitkeep

git ls-files feedback/.gitkeep
# Expected: feedback/.gitkeep (tracked in git)

git ls-files --others --exclude-standard feedback/
# Expected: empty (no untracked feedback files to accidentally commit)
```

### Step 15 — Check 13: Silent failure scan across all I7 files

```bash
grep -rn "except.*pass\|except:$" \
    src/wbsb/eval/ src/wbsb/feedback/ \
    src/wbsb/render/llm_adapter.py
# Expected: no matches
```

### Step 16 — Verify EvalScores and FeedbackEntry model contracts

```bash
python3 -c "
from wbsb.eval.models import EvalScores, HallucinationViolation
from wbsb.feedback.models import FeedbackEntry, VALID_SECTIONS, VALID_LABELS

# EvalScores defaults
s = EvalScores(
    grounding=None, grounding_reason='no_numbers_cited', flagged_numbers=[],
    signal_coverage=1.0, group_coverage=1.0,
    hallucination_risk=0, hallucination_violations=[],
    model='claude-haiku-4-5-20251001', evaluated_at='2026-03-11T12:00:00Z'
)
assert s.schema_version == '1.0'
assert s.grounding is None

# FeedbackEntry defaults
f = FeedbackEntry(
    feedback_id='abc', run_id='20260311T132430Z_3485e2',
    section='situation', label='expected',
    comment='test', submitted_at='2026-03-11T12:00:00Z',
)
assert f.schema_version == '1.0'
assert f.operator == 'anonymous'

# Frozensets
assert isinstance(VALID_SECTIONS, frozenset)
assert isinstance(VALID_LABELS, frozenset)

print('model contracts: OK')
"
```

Expected: `model contracts: OK`

---

## Required Output Format

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List every architecture check that passed. Reference file paths and line numbers.
This section must not be empty on a PASS verdict.

---

### 3. Problems Found

For each problem:

```
- severity: critical | major | minor
  check: which architecture check this relates to
  file: path/to/file.py:LINE
  exact problem: one or two sentences
  why it matters: one sentence on the consequence
```

If no problems: `None.`

---

### 4. Architecture Checklist Results

```
- [PASS | FAIL] Check 1: Scorer isolated to llm_adapter.py — not wired in pipeline.py
- [PASS | FAIL] Check 2: Non-breaking scorer path — error produces eval_skipped_reason, no pipeline crash
- [PASS | FAIL] Check 3: domain/models.py unchanged — EvalScores and FeedbackEntry not added to it
- [PASS | FAIL] Check 4: No hardcoded tolerance values in scorer.py or extractor.py
- [PASS | FAIL] Check 5: Feedback validation enforced — run_id/section/label all raise ValueError
- [PASS | FAIL] Check 6: No cross-imports between wbsb.eval and wbsb.feedback
- [PASS | FAIL] Check 7: eval: section present in config/rules.yaml with correct keys and types
- [PASS | FAIL] Check 8: eval_scores present in llm_response.json on real --llm-mode full run
- [PASS | FAIL] Check 9: --llm-mode off produces complete report with no scorer errors
- [PASS | FAIL] Check 10: wbsb eval passes all 6 golden cases, exit code 0
- [PASS | FAIL] Check 11: wbsb feedback list/summary/export operational without errors
- [PASS | FAIL] Check 12: feedback/.gitkeep tracked; feedback/* gitignored; negation order correct
- [PASS | FAIL] Check 13: No silent failures in any I7 file
- [PASS | FAIL] EvalScores and FeedbackEntry model contracts verified
- [PASS | FAIL] 320 tests pass (271 baseline + 49 from I7)
- [PASS | FAIL] Ruff clean
```

---

### 5. Fixes Required for I7-9

Numbered list. Each fix must be actionable — file path, line number, what to change.
If all checks pass: `None.`

---

### 6. Final Recommendation

```
approve for I7-9 | request changes before I7-9 | block — revisit design
```

One sentence explaining the recommendation.
