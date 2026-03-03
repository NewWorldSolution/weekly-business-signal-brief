# TASKS.md — Iteration Control

## Weekly Business Signal Brief (WBSB)

This document defines controlled development tasks and execution discipline for the WBSB repository.

Purpose:
- Prevent scope creep
- Enforce architectural stability
- Coordinate iteration work
- Keep the engine deterministic and auditable

---

## Development Rules

- One task at a time.
- One task per PR.
- Plan Mode required for multi-file changes.
- Only modify files explicitly allowed in each task.
- Always run before committing:
  - `pytest`
  - `ruff check .`
- No architectural rewrites unless explicitly defined.
- No hidden behavior changes.
- No silent error handling (`except: pass` is forbidden).
- No refactors outside the allowed task scope.

---

# Iteration 1 — Hardening & Reliability

## Theme

Make the deterministic engine fail loudly, predictably, and safely.

### Constraints

- No new features
- No LLM implementation
- No architecture changes
- No performance optimizations
- No refactoring beyond task scope

---

## Task 1 — Missing Week Must Raise Explicit Error (HIGH)

### Problem

`_get_row()` returns `{}` when a week is missing.  
This allows silent downstream corruption and cryptic failures.

### Required Changes

Modify:
- `src/wbsb/findings/build.py`

Requirements:
- If a week is missing:
  - Raise `ValueError`
  - Error message must include:
    - Missing `week_start_date`
    - Minimum available week in dataset
    - Maximum available week in dataset
    - Suggestion to verify `--week` or dataset completeness
- Do **not** return `{}` anymore.
- Allow the exception to propagate naturally (do not swallow it).

### Test

Create:
- `tests/test_missing_week.py`

Test must:
- Build a minimal DataFrame with two valid weeks
- Call `build_findings()` using a non-existing week
- Assert `ValueError`
- Assert missing date appears in error message

### Allowed Files

- `src/wbsb/findings/build.py`
- `tests/test_missing_week.py`

### Acceptance Criteria

- All existing tests pass
- New test passes
- Ruff clean
- No unrelated files modified

---

## Task 2 — End-to-End Integration Test (HIGH)

### Problem

No full pipeline integration test exists.

### Required Changes

Add:
- `tests/test_e2e_pipeline.py`

Test must:
- Use `examples/sample_weekly.csv` (preferred for now; guaranteed to exist on main)
- Call `execute(...)` with `llm_mode="off"`
- Use `tmp_path` for output
- Assert:
  - A run directory is created
  - `findings.json` exists
  - `brief.md` exists
  - `manifest.json` exists
  - `logs.jsonl` exists
  - Findings contains `schema_version == "1.0"`

### Allowed Files

- `tests/test_e2e_pipeline.py`

### Acceptance Criteria

- Test passes
- No production code modified
- Ruff clean

---

## Task 3 — Export Layer Must Not Pretend Success (HIGH)

### Problem

Artifact writing failures could appear as success.

### Required Changes

Modify:
- `src/wbsb/export/write.py`

Requirements:
- Wrap file writes in `try/except`
- Log the error
- Re-raise the exception
- Never silently continue
- Pipeline must fail on write failure

### Test

Create:
- `tests/test_export_write_failures.py`

Test must:
- Simulate write failure using monkeypatch (e.g., patch `Path.write_text` / `Path.write_bytes`)
- Assert exception propagates (or execute returns non-zero if testing at pipeline level)

### Allowed Files

- `src/wbsb/export/write.py`
- `tests/test_export_write_failures.py`

### Acceptance Criteria

- Write failure causes pipeline failure
- Tests pass
- Ruff clean

---

## Task 4 — Logging Must Not Swallow Exceptions (MEDIUM)

### Problem

Silent exception swallowing in the logging layer hides failures.

### Required Changes

Modify:
- `src/wbsb/observability/logging.py`

Requirements:
- Remove any fully-silent exception swallowing.
- Provide minimal fallback (stderr once OR counter) without spamming.
- Do not break existing behavior.

### Allowed Files

- `src/wbsb/observability/logging.py`
- (Optional) `tests/test_logging_fallback.py`

### Acceptance Criteria

- Logging failures are not completely silent
- Tests pass
- Ruff clean

---

## Task 5 — Implement `volume_metric` in Rules Engine (MEDIUM)

### Problem

`volume_metric` is defined in YAML but ignored in the engine.

### Required Changes

Modify:
- `src/wbsb/rules/engine.py`

Requirements:
- For `hybrid_delta_pct_lte`:
  - Use `volume_metric` if defined in YAML
  - Fallback to `metric_id` if not defined
- Add test coverage.

### Allowed Files

- `src/wbsb/rules/engine.py`
- `tests/test_rules.py`

### Acceptance Criteria

- `volume_metric` behavior correct
- Existing tests unaffected
- Ruff clean

---

## Task 6 — Move `safe_div` to `utils.math` (MEDIUM)

### Problem

`safe_div` currently lives in `hash.py`, which is the wrong responsibility.

### Required Changes

- Create: `src/wbsb/utils/math.py`
- Move `safe_div` there
- Update imports in:
  - `src/wbsb/metrics/calculate.py`
  - `src/wbsb/compare/delta.py`
- Remove from `src/wbsb/utils/hash.py`

### Acceptance Criteria

- No behavior change
- All tests pass
- Ruff clean
- No circular imports

---

## Task 7 — Strengthen Integer Validation (LOW)

### Problem

Integer columns allow floats silently.

### Required Changes

Modify:
- `src/wbsb/validate/schema.py`

Requirements:
- Detect non-integer numeric values in INT columns
- Emit `AuditEvent` with:
  - `event_type: "non_integer_value"`
- Do not crash pipeline

### Acceptance Criteria

- AuditEvent emitted correctly
- No regression
- Ruff clean

---

## Task 8 — Dataset Pack Completion (LOW)

### Goal

Improve synthetic dataset coverage.

### Required Changes

- Add datasets to: `examples/datasets/`
- Add documentation: `examples/datasets/README.md`
- No engine changes

### Acceptance Criteria

- Datasets added and documented
- No production code changes
- Ruff clean

---

# Execution Workflow

For each task:

1. Create feature branch
2. Use Plan Mode if multi-file or behavioral change
3. Confirm allowed files before executing changes
4. Implement changes
5. Run:
   - `pytest`
   - `ruff check .`
6. Commit with a clear message
7. Push
8. Open PR
9. Merge after review

Never combine multiple tasks in a single PR unless explicitly approved.

---

# Iteration 1 — Definition of Done

Iteration 1 is complete when:

- Missing week raises explicit error (Task 1)
- End-to-end integration test exists (Task 2)
- No silent I/O failures (Task 3)
- Logging does not swallow exceptions (Task 4)
- All tests passing
- Ruff clean
- `main` branch stable and CI passing