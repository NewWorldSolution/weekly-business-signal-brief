# WBSB Review Prompt — {{TASK_ID}}: {{TASK_TITLE}}

<!--
HOW TO USE THIS TEMPLATE
========================
1. Copy this file. Rename it (e.g. `review-i6-2.md`).
2. Replace every {{PLACEHOLDER}} with the real value.
3. Fill in every section marked with a [FILL IN] comment.
4. Remove all comments (<!-- ... -->) before sending to the AI reviewer.
5. Sections marked [BOILERPLATE] are fixed — do not change them.
6. Send the completed file as the full prompt to the reviewing AI.
   Use a DIFFERENT AI than the one that implemented the task.

PLACEHOLDER KEY
  {{TASK_ID}}             e.g. I6-2
  {{TASK_TITLE}}          e.g. History Store and Dataset-Scoped HistoryReader
  {{ITERATION}}           e.g. Iteration 6 — Historical Memory & Trend Awareness
  {{ITERATION_BRANCH}}    e.g. iteration-6  (used as feature/iteration-6)
  {{FEATURE_BRANCH}}      e.g. feature/i6-2-history-store
  {{PR_NUMBER}}           e.g. 27
  {{IMPLEMENTER}}         Claude | Codex  (who built it — reviewer must be different)
  {{REVIEWER}}            Claude | Codex
  {{TEST_COUNT_BEFORE}}   test count before this task, e.g. 217
  {{TEST_COUNT_AFTER}}    expected test count after, e.g. 235
-->

---

## Reviewer Role & Mandate

<!--
[BOILERPLATE] — do not change this section.
This section tells the AI reviewer exactly who they are and what they must do.
-->

You are an **independent code reviewer** for the WBSB project.

Your role is to evaluate a completed task implementation with the same rigour as a senior
engineer reviewing a PR for a production system. You did not write this code. You have no
bias toward approving it. Your job is to protect the codebase.

**Your mandate:**

- Verify the implementation satisfies every acceptance criterion — not approximately, exactly.
- Identify violations of the architecture constraints — even minor ones.
- Flag silent failures, hardcoded values, scope creep, and weak tests.
- Report problems precisely: file path, line number, exact issue, why it matters.
- Be specific. "Looks fine" is not an acceptable assessment. "Line 139: `except OSError: pass`
  silently suppresses cleanup failures, violating the no-silent-failure policy" is acceptable.

**What you must NOT do:**

- Do not fix the code. Report problems. Fixing is the implementer's job.
- Do not approve based on tests passing alone — tests can be incomplete.
- Do not overlook an issue because it seems minor. Log it with `severity: minor`.
- Do not invent problems that are not there. Every finding must be backed by evidence
  (file path + line number or command output).

**Your verdict has three options:**

| Verdict | Meaning |
|---------|---------|
| `PASS` | All acceptance criteria met, no architecture violations, tests adequate. Ready to merge. |
| `CHANGES REQUIRED` | One or more problems found. List every fix needed before re-review. |
| `BLOCKED` | A fundamental design decision is wrong and the approach must be reconsidered. |

---

## Project Context

<!-- [BOILERPLATE] — do not change this section -->

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for
appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics,
detects signals via a config-driven rules engine, and generates a structured business brief.
An LLM is optionally used for narrative sections only — never for calculations or decisions.

**Core pipeline:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Architecture principles (violations of any of these = CHANGES REQUIRED minimum):**

| # | Principle |
|---|-----------|
| 1 | **Deterministic first** — no randomness, no time-dependent logic in metrics or rules |
| 2 | **Config-driven** — all thresholds in `config/rules.yaml`; zero hardcoded numbers in code |
| 3 | **Auditability** — emit `AuditEvent` after every significant state change |
| 4 | **No silent failure** — never `except: pass`; raise `ValueError` with a clear message |
| 5 | **Separation of concerns** — metrics, rules, and rendering are strictly isolated |
| 6 | **LLM is optional** — `--llm-mode off` must always produce a complete, valid report |
| 7 | **Stable ordering** — signals sorted by `rule_id`; metrics in deterministic order |
| 8 | **Secrets never in code** — API keys from env vars only; never logged |

---

## Task Under Review

<!-- [FILL IN] -->

| Field | Value |
|-------|-------|
| Task ID | {{TASK_ID}} |
| Title | {{TASK_TITLE}} |
| Iteration | {{ITERATION}} |
| Implemented by | {{IMPLEMENTER}} |
| Reviewed by | {{REVIEWER}} |
| Iteration branch | `feature/{{ITERATION_BRANCH}}` |
| Feature branch | `{{FEATURE_BRANCH}}` |
| PR | #{{PR_NUMBER}} |
| Expected test count | {{TEST_COUNT_BEFORE}} before → {{TEST_COUNT_AFTER}} after |

---

## What This Task Was Supposed to Build

<!-- [FILL IN] Copy the "What to Build" section from the task prompt verbatim.
Do not summarise — the reviewer needs the exact spec to check against. -->

### New files

```
{{NEW_FILE_1}}     ← purpose
{{NEW_FILE_2}}     ← purpose
```

### Modified files

```
{{MODIFIED_FILE_1}}  ← what changes and why
```

### Public API (required signatures)

<!-- [FILL IN] Paste the exact function/class signatures from the task prompt -->

```python
{{PASTE_PUBLIC_API_FROM_TASK_PROMPT}}
```

### Data shapes

```python
{{PASTE_DATA_SHAPES_FROM_TASK_PROMPT}}
```

### Behaviour rules the implementation must enforce

<!-- [FILL IN] Copy from task prompt — these are what you will verify -->

- **Rule 1:** {{e.g. Writes are atomic — temp file + os.replace. No partial state.}}
- **Rule 2:** {{e.g. Fail loudly if findings_path does not exist at registration time.}}
- **Rule 3:** {{e.g. First run (no index file) must work without error.}}
- **Rule 4:** {{e.g. Never expose raw historical arrays to the LLM layer.}}

---

## Allowed Files

<!-- [FILL IN] Copy from task prompt. Only these files may have been created or modified. -->

```
{{FILE_PATH_1}}     ← new | modify: {{why}}
{{FILE_PATH_2}}     ← new | modify: {{why}}
{{FILE_PATH_3}}     ← new | modify: {{why}}
```

**Files that must NOT have been touched:**

```
{{ADJACENT_FILE_1}}    ← reason
{{ADJACENT_FILE_2}}    ← reason
```

---

## Acceptance Criteria to Verify

<!-- [FILL IN] Copy from task prompt exactly. You will mark each PASS or FAIL. -->

- [ ] {{Criterion 1}}
- [ ] {{Criterion 2}}
- [ ] {{Criterion 3}}
- [ ] {{Criterion 4}}
- [ ] All {{TEST_COUNT_BEFORE}}+ prior tests still pass (`pytest` exit code 0)
- [ ] New tests for this task all pass
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only allowed files were modified

---

## Tests Required (from task prompt)

<!-- [FILL IN] Copy the test table from the task prompt.
The reviewer will check that each test exists AND that the assertion is strong enough. -->

| Test function | What it verifies |
|---------------|-----------------|
| `test_{{subject}}_{{condition}}` | {{expected behaviour}} |
| `test_{{subject}}_{{condition}}` | {{expected behaviour}} |
| `test_{{subject}}_{{condition}}` | {{expected behaviour}} |

---

## Edge Cases to Check

<!-- [FILL IN] Copy from task prompt. Reviewer verifies each is handled AND tested. -->

| Edge case | Required behaviour |
|-----------|-------------------|
| {{Edge case 1}} | {{expected}} |
| {{Edge case 2}} | {{expected}} |
| {{Edge case 3}} | {{expected}} |

---

## Review Execution Steps

<!-- [BOILERPLATE] — do not change this section -->

Run these commands in order. Report the output for each.

### Step 1 — Checkout and baseline

```bash
git fetch origin
git checkout {{FEATURE_BRANCH}}
git pull origin {{FEATURE_BRANCH}}
```

### Step 2 — Run tests and lint

```bash
pytest --tb=short -q
# Expected: {{TEST_COUNT_AFTER}} passing, 0 failures

ruff check .
# Expected: no issues
```

Report the exact output. If either fails, the verdict is `CHANGES REQUIRED` immediately.

### Step 3 — Verify scope

```bash
git diff --name-only feature/{{ITERATION_BRANCH}}
```

Every file listed must appear in the "Allowed Files" section above.
Any unexpected file = scope violation = `CHANGES REQUIRED`.

### Step 4 — Read the implementation

Read every file listed in "Allowed Files" in full. Then:

- Compare each public API signature against the spec in "What to Build".
- Check each behaviour rule is implemented as specified.
- Check each edge case is handled.
- Check for architecture principle violations (see Project Context).

### Step 5 — Audit the tests

For each test in "Tests Required":

1. Confirm the test function exists by name.
2. Read the test body — does the assertion actually verify what the test claims?
3. Flag any test where passing could mask a real bug (e.g. only checks `len`, not values).

### Step 6 — Check for hardcoded values

```bash
# Replace thresholds with the actual numeric values from config/rules.yaml
grep -rn "{{THRESHOLD_1}}\|{{THRESHOLD_2}}" src/wbsb/
# Expected: no matches (all thresholds must come from config)
```

### Step 7 — Check for silent failures

```bash
grep -n "except.*pass\|except:$" src/wbsb/{{MODULE_PATH}}/
# Expected: no matches
```

---

## Required Output Format

<!-- [BOILERPLATE] — do not change this section -->

Your review must be structured exactly as follows. Do not add extra sections.
Do not omit a section even if it has no findings.

---

### 1. Verdict

```
PASS | CHANGES REQUIRED | BLOCKED
```

---

### 2. What's Correct

List everything that is implemented correctly and matches the spec. Be specific — reference
file paths and line numbers where helpful. This section must not be empty on a PASS verdict.

---

### 3. Problems Found

For each problem, use this format:

```
- severity: critical | major | minor
  file: src/wbsb/path/to/file.py:LINE
  exact problem: one or two sentences describing what is wrong
  why it matters: one sentence explaining the consequence
```

Severity guide:
- `critical` — incorrect output, data loss, or security issue. Blocks merge.
- `major` — violates an architecture constraint or acceptance criterion. Blocks merge.
- `minor` — code quality issue, weak test, or style deviation. Must be fixed but lower urgency.

If no problems found, write: `None.`

---

### 4. Missing or Weak Tests

For each test that is absent or has a weak assertion:

```
- test: test_function_name (missing | weak assertion)
  issue: what is missing or what the assertion fails to verify
  suggestion: what a correct assertion would look like
```

If all required tests are present and strong, write: `None.`

---

### 5. Scope Violations

List any files modified that are not in the "Allowed Files" list.

```
- file: path/to/unexpected_file.py
  change: what was changed
  verdict: revert | move to correct task
```

If no violations, write: `None.`

---

### 6. Acceptance Criteria Check

Copy the criteria list and mark each:

```
- [PASS | FAIL] {{Criterion 1}}
- [PASS | FAIL] {{Criterion 2}}
...
```

---

### 7. Exact Fixes Required

Numbered list. Each fix must be actionable — file path, line number, what to change.
If verdict is PASS, write: `None.`

```
1. file.py:LINE — replace X with Y because Z
2. tests/test_file.py — add test_X to verify Y
3. ...
```

---

### 8. Final Recommendation

```
approve | request changes | block
```

One sentence explaining the recommendation.

---

<!--
CHECKLIST FOR THE PERSON FILLING THIS TEMPLATE
===============================================
Before sending to the reviewer:

[ ] All {{PLACEHOLDER}} values replaced
[ ] "What to Build" section populated from task prompt (not summarised)
[ ] Acceptance criteria copied verbatim from task prompt
[ ] Test table populated from task prompt
[ ] Edge cases table populated from task prompt
[ ] Allowed files list complete
[ ] Files NOT to touch list complete
[ ] Hardcoded threshold values filled into Step 6 grep command
[ ] Module path filled into Step 7 grep command
[ ] All [FILL IN] comments removed
[ ] All [BOILERPLATE] section content unchanged
[ ] Template instructions and this checklist removed before sending
[ ] Reviewer AI is different from implementer AI
-->
