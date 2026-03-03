cat > TASKS.md <<'MD'
# Iteration 1 - Hardening

## Task 1: _get_row missing-week must raise

Paste this into Claude Code (Plan Mode):

You are working on the WBSB repository.

Task: Harden missing-week handling in findings/build.py.

Problem:
Currently _get_row(df, week_start) returns {} when the week is not found.
This allows downstream metric computation to proceed with empty data, causing misleading or cryptic failures.

Required Changes:

1) Modify _get_row() in src/wbsb/findings/build.py:
   - If no row exists for the given week_start_date, raise a ValueError.
   - The error message must include:
       • The missing week_start_date
       • The minimum available week_start_date in the dataset
       • The maximum available week_start_date in the dataset
       • A short suggestion to verify --week argument or dataset completeness
   - Do NOT return {} anymore.

2) Allow the error to propagate naturally through build_findings() and pipeline.execute().
   - Do not swallow the exception.
   - The CLI should exit non-zero (already supported).

3) Add a new unit test:
   - File: tests/test_missing_week.py
   - Create a minimal synthetic DataFrame with two valid weeks.
   - Call build_findings() with a week that does NOT exist.
   - Assert that ValueError is raised.
   - Assert that the error message contains the missing date string.

Constraints:

- Modify ONLY:
    • src/wbsb/findings/build.py
    • tests/test_missing_week.py
- Do NOT modify:
    • metrics
    • rules engine
    • rendering
    • pipeline orchestration
    • validation layer
- Do NOT refactor unrelated code.
- Keep architecture unchanged.

Acceptance Criteria:

- All existing tests must pass.
- The new test must pass.
- Ruff linting must remain clean.
- No additional files are modified.

Before executing:
1) Confirm which files will be changed.
2) Confirm no unrelated modules are touched.
3) Confirm regression safety plan (tests will be re-run).

Acceptance checklist:
- Only src/wbsb/findings/build.py and tests/test_missing_week.py changed
- pytest passes
- ruff check . passes
MD