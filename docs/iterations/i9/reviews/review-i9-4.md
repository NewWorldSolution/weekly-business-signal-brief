# WBSB Review Prompt — I9-4: Scheduler (`wbsb run --auto`)

---

## Reviewer Mandate

Strictly validate I9-4 against `docs/iterations/i9/tasks.md`.
Focus: scheduler boundaries, path safety, already-processed logic.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-4-scheduler
git pull origin feature/i9-4-scheduler
```

2. Validate:
```bash
pytest --tb=short -q
ruff check .
```

3. Scope:
```bash
git diff --name-only feature/iteration-9
```

Allowed:
- `src/wbsb/scheduler/auto.py`
- `src/wbsb/cli.py`
- `tests/test_scheduler.py`

4. Boundary guard:
```bash
git diff feature/iteration-9 -- src/wbsb/pipeline.py src/wbsb/history/store.py
```
Expected: no changes.

5. Path traversal and index logic checks:
```bash
grep -n "resolve\|startswith\|Path outside watch directory\|derive_dataset_key\|index.json" src/wbsb/scheduler/auto.py
```

6. CLI behavior checks:
```bash
wbsb run --help | grep -- "--auto"
```

7. Test presence:
```bash
grep -n "^def test_" tests/test_scheduler.py
```

Required tests: all listed in tasks.md.

---

## Required Output Format

1. Verdict
2. What's Correct
3. Problems Found
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check
7. Exact Fixes Required
8. Final Recommendation

---

## Acceptance Criteria Check List

- [ ] scheduler API exists and is importable
- [ ] path traversal guard implemented
- [ ] already_processed logic uses dataset scoping and index
- [ ] `--auto` integrated into CLI
- [ ] no pipeline/history module modifications
- [ ] only allowed files modified
- [ ] required tests present/meaningful
- [ ] tests pass
- [ ] ruff clean
