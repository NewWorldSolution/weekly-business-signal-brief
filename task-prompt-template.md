# WBSB Task Prompt — {{TASK_ID}}: {{TASK_TITLE}}

<!--
HOW TO USE THIS TEMPLATE
========================
1. Copy this file. Rename it (e.g. `prompt-i6-2.md`).
2. Replace every {{PLACEHOLDER}} with the real value.
3. Fill in every section marked with a [FILL IN] comment.
4. Remove all comments (<!-- ... -->) before sending to an AI.
5. Sections marked [BOILERPLATE] are fixed — do not change them.
6. Send the completed file as the full prompt.

PLACEHOLDER KEY
  {{TASK_ID}}           e.g. I6-2
  {{TASK_TITLE}}        e.g. History Store and Dataset-Scoped HistoryReader
  {{OWNER}}             Claude | Codex
  {{ITERATION}}         e.g. Iteration 6 — Historical Memory & Trend Awareness
  {{FEATURE_BRANCH}}    e.g. feature/i6-2-history-store
  {{DEPENDS_ON}}        e.g. I6-1 | none
  {{BLOCKS}}            e.g. I6-3, I6-4 | none
  {{TEST_COUNT}}        current passing test count, e.g. 217
-->

---

## Project Context
<!-- [BOILERPLATE] — do not change this section -->

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics, detects signals via a config-driven rules engine, and generates a structured business brief. An LLM is optionally used for narrative sections only — never for calculations.

**Core architecture:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Non-negotiable principles:**
- Analytics are deterministic. LLM is explanation only, never analytics.
- All thresholds live in `config/rules.yaml`. Zero hardcoded numbers in code.
- Every module has a strict boundary. Metrics, rules, and rendering never mix.
- No silent failures. Raise clearly or emit an `AuditEvent`.
- LLM is optional. Every mode produces a complete, valid report without it.

---

## Repository State

<!-- [FILL IN] Update these values at task start -->

- **Active branch:** `main` (all prior tasks merged)
- **Feature branch for this task:** `{{FEATURE_BRANCH}}`
- **Tests passing:** {{TEST_COUNT}}
- **Ruff:** clean
- **Last completed task:** <!-- e.g. I6-1 — history: config section added to rules.yaml -->
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | {{TASK_ID}} |
| Title | {{TASK_TITLE}} |
| Iteration | {{ITERATION}} |
| Owner | {{OWNER}} |
| Feature branch | `{{FEATURE_BRANCH}}` |
| Depends on | {{DEPENDS_ON}} |
| Blocks | {{BLOCKS}} |
| PR scope | One PR. One task. Do not combine with adjacent tasks. |

---

## Task Goal

<!-- [FILL IN] One or two paragraphs. What problem does this task solve and why does it matter to the system?
Be specific — reference the module, the function, or the gap being closed. -->

{{GOAL_PARAGRAPH}}

---

## Why {{OWNER}}

<!-- [FILL IN] Explain why this specific AI is assigned this task.
Be explicit about what judgment or knowledge it requires. -->

{{OWNER_RATIONALE}}

---

## Files to Read Before Starting

<!-- [FILL IN] List the specific files the AI must read BEFORE writing a single line.
Order matters: list foundational files first, then files directly adjacent to the work. -->

Read these files in order before touching anything:

```
{{FILE_1}}         ← reason: e.g. understand the existing pipeline call order
{{FILE_2}}         ← reason: e.g. understand the domain model this module extends
{{FILE_3}}         ← reason: e.g. see the test pattern used in adjacent modules
```

<!-- Common candidates:
- src/wbsb/pipeline.py               (always read if touching pipeline)
- src/wbsb/domain/models.py          (always read if touching domain objects)
- config/rules.yaml                  (always read if consuming config)
- src/wbsb/render/llm_adapter.py     (read if touching LLM layer)
- tests/test_e2e_pipeline.py         (read to understand test fixture patterns)
- The most recent similar module     (e.g. src/wbsb/rules/engine.py for a new engine module)
-->

---

## Existing Code This Task Builds On

<!-- [FILL IN] Describe what already exists in the codebase that this task depends on.
Include function signatures, class names, field names — be specific.
This prevents the AI from reinventing things that already exist. -->

### Already exists and must NOT be reimplemented:

<!-- Example entries — replace with real ones -->
```python
# src/wbsb/pipeline.py
def execute(input_path, output_dir, llm_mode, llm_provider, config_path, target_week) -> int:
    # Orchestrates the full pipeline. This task adds a call inside execute().
    ...

# src/wbsb/domain/models.py
class AuditEvent(BaseModel):
    event: str
    detail: str | None = None
    # Emit one of these after any significant state change.
    ...
```

### Contracts established by prior tasks that this task must respect:

<!-- [FILL IN] List function signatures, data shapes, or variable names locked in by prior task PRs -->

```
{{CONTRACT_1}}     ← e.g. derive_dataset_key() returns lowercase str, no path separators
{{CONTRACT_2}}     ← e.g. HistoryReader is scoped to dataset_key at construction time
```

---

## What to Build

<!-- [FILL IN] The most important section. Be exhaustive.
Include:
  - New files and their purpose
  - Public API: function/class signatures with types
  - Data shapes (TypedDicts, dicts) with field names and types
  - Behaviour rules (e.g. append-only, fail loudly, never raise from X)
  - Config keys to read and where they live
  - Exact examples of inputs and expected outputs
Do NOT leave implementation decisions open-ended. Specify them here.
-->

### New files

```
{{NEW_FILE_1}}     ← purpose
{{NEW_FILE_2}}     ← purpose
```

### Modified files

```
{{MODIFIED_FILE_1}}  ← what changes and why
```

### Public API

<!-- [FILL IN] Define every public function and class this task must produce.
Use Python type annotations. Include docstrings inline. -->

```python
# {{NEW_FILE_1}}

def {{FUNCTION_NAME}}(
    {{PARAM_1}}: {{TYPE}},
    {{PARAM_2}}: {{TYPE}} = {{DEFAULT}},
) -> {{RETURN_TYPE}}:
    """{{DOCSTRING}}

    Args:
        {{PARAM_1}}: {{description}}
        {{PARAM_2}}: {{description}}

    Returns:
        {{description}}

    Raises:
        ValueError: {{when}}
        FileNotFoundError: {{when}}
    """
```

### Data shapes

<!-- [FILL IN] Define TypedDicts, dataclasses, or dict shapes used across module boundaries.
Every field must have a name, type, and a one-line description. -->

```python
# Example — replace with real shape
class {{RecordName}}(TypedDict):
    field_one: str        # e.g. run_id "20260309T094756Z_4c43f0"
    field_two: int        # e.g. signal_count
    field_three: str | None  # e.g. None when not applicable
```

### Behaviour rules

<!-- [FILL IN] Specific rules the implementation must enforce. Be explicit about failure modes. -->

- **{{Rule 1}}:** e.g. Write atomically — write to a temp file, then `os.replace()`. Never leave partial state.
- **{{Rule 2}}:** e.g. Fail loudly if `findings_path` does not exist at registration time.
- **{{Rule 3}}:** e.g. First run (no index file) must work without error — create the file.
- **{{Rule 4}}:** e.g. Never expose raw historical arrays to the LLM layer.

### Config keys consumed

<!-- [FILL IN] If this task reads from config/rules.yaml, list the exact keys and their expected types. -->

```yaml
# config/rules.yaml — keys this task reads
{{section_name}}:
  {{key_1}}: {{type}}     # {{description, default value}}
  {{key_2}}: {{type}}     # {{description, default value}}
```

Load pattern (always use this — do not re-read the file on every call):
```python
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[N] / "config" / "rules.yaml"

def _load_config_section() -> dict:
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f).get("{{section_name}}", {})
```

### Input/output examples

<!-- [FILL IN] Concrete examples for the most important functions. -->

```python
# Example: {{FUNCTION_NAME}}
{{FUNCTION_NAME}}("input_a")   # → expected_output_a
{{FUNCTION_NAME}}("input_b")   # → expected_output_b
{{FUNCTION_NAME}}("")          # → raises ValueError("...")
```

---

## Architecture Constraints
<!-- [BOILERPLATE] — do not change this section -->

These apply to every task without exception. No PR is approved if any of these are violated.

1. **Deterministic first** — no randomness, no time-dependent logic in metrics or rules.
2. **Config-driven** — all thresholds in `config/rules.yaml`. Zero hardcoded numbers.
3. **Auditability** — emit `AuditEvent` after every significant state change.
4. **No silent failure** — never use `except: pass`. Raise `ValueError` with a clear message.
5. **Separation of concerns** — metrics, rules, and rendering are strictly isolated. Do not mix them.
6. **LLM is optional** — `--llm-mode off` must always produce a complete, valid report.
7. **Stable ordering** — signals sorted by `rule_id`. Metrics in a stable, deterministic order.
8. **Secrets never in code** — API keys and tokens from environment variables only. Never logged.

---

## Allowed Files

<!-- [FILL IN] The complete and exhaustive list. Only these files may be created or modified.
If the implementation requires touching a file not on this list, STOP and ask before proceeding. -->

```
{{FILE_PATH_1}}     ← new | modify: {{why}}
{{FILE_PATH_2}}     ← new | modify: {{why}}
{{FILE_PATH_3}}     ← new | modify: {{why}}
```

---

## Files NOT to Touch

<!-- [FILL IN] Files adjacent to the work that must NOT be modified.
This prevents scope creep into neighbouring modules. -->

The following files are adjacent to this task but must not be modified:

```
{{ADJACENT_FILE_1}}    ← reason: e.g. owned by next task (I6-3)
{{ADJACENT_FILE_2}}    ← reason: e.g. domain model is frozen until I7
{{ADJACENT_FILE_3}}    ← reason: e.g. not in scope for this iteration
```

If any of these files seem like they need to change to complete this task, **stop and raise it** rather than modifying them.

---

## Acceptance Criteria

<!-- [FILL IN] Checkable, binary criteria. Each item must be true for the PR to merge.
Avoid vague criteria like "works correctly" — specify what correct means. -->

- [ ] {{Criterion 1}} — e.g. `runs/index.json` is created on the first pipeline run
- [ ] {{Criterion 2}} — e.g. Duplicate `run_id` raises `ValueError` with a descriptive message
- [ ] {{Criterion 3}} — e.g. All thresholds read from config — verified by grep: `grep -n "0\.02" src/wbsb/history/trends.py` returns nothing
- [ ] {{Criterion 4}} — e.g. `dataset_key` filter confirmed: a run registered under `"weekly_data"` is not returned by a query scoped to `"other_dataset"`
- [ ] All {{TEST_COUNT}}+ existing tests still pass — `pytest` exit code 0
- [ ] Ruff clean — `ruff check .` exit code 0

---

## Tests Required

<!-- [FILL IN] Specific test cases. Each row = one test function.
Name tests descriptively. The test name should read as a sentence: test_<subject>_<condition>_<expected>
All new tests go in {{TEST_FILE}}. -->

**Test file:** `{{TEST_FILE}}`

| Test function | What it verifies |
|---------------|-----------------|
| `test_{{subject}}_{{condition}}` | {{expected behaviour in plain English}} |
| `test_{{subject}}_{{condition}}` | {{expected behaviour in plain English}} |
| `test_{{subject}}_{{condition}}` | {{expected behaviour in plain English}} |

<!-- Test pattern used in this project — follow this exactly: -->

```python
# Pattern: use tmp_path for file I/O, avoid touching real runs/ directory
def test_example_behaviour(tmp_path):
    # Arrange
    index_path = tmp_path / "index.json"
    # ... set up inputs

    # Act
    result = function_under_test(...)

    # Assert
    assert result == expected
```

```python
# Pattern: test for raises
def test_raises_on_invalid_input(tmp_path):
    with pytest.raises(ValueError, match="descriptive message fragment"):
        function_under_test(invalid_input)
```

---

## Edge Cases to Handle Explicitly

<!-- [FILL IN] List edge cases the implementation must handle.
These are the cases most likely to be silently ignored without this prompt. -->

| Edge case | Expected behaviour |
|-----------|-------------------|
| {{Edge case 1}} | e.g. No index file exists on first run → create it gracefully |
| {{Edge case 2}} | e.g. Findings file referenced by index has been deleted → skip entry, log warning |
| {{Edge case 3}} | e.g. Metric absent from historical findings (schema evolution) → skip silently |
| {{Edge case 4}} | e.g. All metric trends are `insufficient_history` → LLM prompt section omitted entirely |
| {{Edge case 5}} | e.g. Config key missing from `rules.yaml` → raise `KeyError` with useful message |

---

## What NOT to Do

<!-- [FILL IN] Common mistakes to pre-empt. Be specific to this task.
Use the permanent architecture rules above as a starting point, then add task-specific ones. -->

- Do not introduce `{{specific_temptation}}` — e.g. SQLite or any external database
- Do not hardcode `{{specific_value}}` — e.g. `0.02` or `2` as threshold values; read from config
- Do not modify `{{adjacent_file}}` — e.g. `domain/models.py` is frozen for this iteration
- Do not mix `{{concern_A}}` into `{{concern_B}}` — e.g. trend computation logic into the pipeline
- Do not silently return empty results when an error occurs — fail loudly with a message
- Do not add `except: pass` or any bare exception swallow
- Do not refactor code outside the allowed files, even if you notice improvements

---

## Handoff: What the Next Task Needs From This One

<!-- [FILL IN] Describe the contract this task establishes for the tasks that depend on it (listed in BLOCKS above).
Be explicit — the downstream AI will use this as its "Existing Code This Task Builds On" section. -->

After this task merges, the following will be available for `{{BLOCKS}}`:

```python
# {{WHAT_IS_EXPORTED}}
# e.g. from wbsb.history.store import HistoryReader, derive_dataset_key, register_run

# Contract:
# - derive_dataset_key(path) → str: pure function, no I/O
# - HistoryReader(index_path, dataset_key) scopes all queries to that dataset
# - register_run(record, index_path) is the sole write path to the index
```

<!-- Also note any variable names, context keys, or template variables that downstream tasks must consume exactly as named: -->

```
{{variable_name}}    → type: {{type}}, shape: {{description}}
{{variable_name}}    → type: {{type}}, shape: {{description}}
```

---

## Execution Workflow
<!-- [BOILERPLATE] — do not change this section -->

Follow this sequence exactly. Do not skip or reorder steps.

### Step 0 — Branch setup (before anything else)

```bash
# Confirm you are on the correct base branch and it is up to date
git checkout main
git pull origin main

# Confirm the working tree is clean before branching
git status
# Expected: "nothing to commit, working tree clean"
# If not clean: stop and resolve before continuing

# Create and switch to the feature branch for this task
git checkout -b {{FEATURE_BRANCH}}

# Confirm you are on the right branch
git branch --show-current
# Expected: {{FEATURE_BRANCH}}
```

If the branch already exists (e.g. you are resuming work):
```bash
git checkout {{FEATURE_BRANCH}}
git status
# Confirm no unexpected changes before resuming
```

### Step 1 — Verify the baseline

Before writing a single line of code, confirm the existing suite is green:

```bash
pytest
# Expected: all {{TEST_COUNT}}+ tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

If either command fails, **stop**. Do not proceed until the baseline is clean. The failure is not caused by this task — it is a pre-existing issue that must be resolved or reported first.

### Step 2 — Read before writing

Read all files listed in "Files to Read Before Starting" in the specified order. Do not write a line of implementation until you understand the existing code those files represent.

### Step 3 — Plan before multi-file changes

If this task touches more than 2 files, enter Plan Mode and present the full plan (which files, what changes, in what order) before implementing. Wait for confirmation before proceeding.

### Step 4 — Confirm allowed files

Before editing any file, cross-check it against the "Allowed Files" list. If a file you need to touch is not on that list, **stop and ask** — do not modify it and explain later.

### Step 5 — Implement

Write code that satisfies all acceptance criteria and handles all edge cases listed above.

### Step 6 — Test and lint

```bash
pytest
# Must pass: all prior tests + all new tests. Zero failures permitted.

ruff check .
# Must be clean. Fix all issues before committing.
```

Do not submit if either command fails.

### Step 7 — Verify scope

```bash
git diff --name-only main
```

Every file in the output must appear in the "Allowed Files" list. If any unexpected file appears, review and revert it before committing.

### Step 8 — Commit

Use the commit message format defined below. One commit per logical unit of work.

### Step 9 — Push and open PR

```bash
git push -u origin {{FEATURE_BRANCH}}
```

Open a PR from `{{FEATURE_BRANCH}}` into `main`. Do not merge — merging is a human decision.

---

## Commit Message Format
<!-- [BOILERPLATE] — do not change this section -->

```
{{type}}: {{concise imperative description}} ({{TASK_ID}})

{{Body: what was built and why. One paragraph.
Reference the task ID. Mention key design decisions.
If a behaviour rule was enforced (e.g. atomic write, dataset scoping), say so.}}

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat` (new code), `fix` (bug), `test` (tests only), `docs` (docs only), `refactor` (no behaviour change)

**Example:**
```
feat: implement dataset-scoped HistoryReader and run index (I6-2)

Adds src/wbsb/history/store.py with derive_dataset_key(), register_run(),
and HistoryReader. Index is an append-only JSON file at runs/index.json.
Writes are atomic (temp file + os.replace). All queries are filtered by
dataset_key at the store layer — contamination across datasets is impossible
by construction. First-run (no index) handled gracefully.

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Definition of Done

<!-- [FILL IN] Final checklist. Copy from Acceptance Criteria and add the boilerplate items below. -->

This task is complete when ALL of the following are true:

- [ ] {{Criterion 1}}
- [ ] {{Criterion 2}}
- [ ] {{Criterion 3}}
- [ ] All {{TEST_COUNT}}+ prior tests still pass (`pytest` exit code 0)
- [ ] All new tests listed in "Tests Required" pass
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only files in "Allowed Files" were modified (verify with `git diff --name-only main`)
- [ ] Feature branch pushed, PR open
- [ ] No `except: pass`, no hardcoded thresholds, no silent failures introduced

---

<!--
CHECKLIST FOR THE PERSON FILLING THIS TEMPLATE
===============================================
Before sending:

[ ] All {{PLACEHOLDER}} values replaced
[ ] "Files to Read Before Starting" is specific (not generic)
[ ] "What to Build" includes actual function signatures and data shapes
[ ] "Allowed Files" is a complete and exhaustive list
[ ] "Files NOT to Touch" lists the obvious adjacent files
[ ] "Handoff" section is filled in if this task has downstream dependents (BLOCKS is not "none")
[ ] All [FILL IN] comments removed
[ ] All [BOILERPLATE] section content is unchanged
[ ] Template instructions and this checklist removed before sending
-->
