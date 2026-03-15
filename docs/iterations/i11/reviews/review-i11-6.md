# WBSB Review Prompt — I11-6: Runtime Hardening

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I11-6 strictly against `docs/iterations/i11/tasks.md`.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`

---

## Project Context

WBSB is a deterministic analytics engine. I11-6 adds container runtime hardening: non-root Docker user (UID 1000) and feedback artifact file permissions (`0o600`/`0o700`).

**Sequencing note:** I11-7 will convert this Dockerfile to multi-stage. I11-6 only adds the non-root user to the existing single-stage Dockerfile. Do not flag the single-stage structure as a problem here — it is correct for this task.

---

## Task Under Review

- Task: I11-6 — Runtime Hardening
- Branch: `feature/i11-6-runtime-hardening`
- Base: `feature/iteration-11`

Expected files in scope:
- `Dockerfile`
- `src/wbsb/feedback/store.py`
- `tests/test_security_hardening.py` (or extension of `tests/test_feedback.py`)

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i11-6-runtime-hardening
git pull origin feature/i11-6-runtime-hardening
```

### Step 2 — Run validation

```bash
pytest --tb=short -q
ruff check .
```

If either fails: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-11
```

Allowed: `Dockerfile`, `src/wbsb/feedback/store.py`, `tests/test_security_hardening.py` (or `tests/test_feedback.py`).

Forbidden: `src/wbsb/feedback/server.py`, `src/wbsb/cli.py`, `docker-compose.yml`, `pyproject.toml`.

### Step 4 — Dockerfile non-root user check

```bash
grep -n "groupadd\|useradd\|USER wbsb\|chown.*wbsb\|uid.*1000\|1000.*wbsb" Dockerfile
```

Verify all three lines are present:
```
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb
```

`USER wbsb` must appear AFTER `chown` and before `CMD`.

### Step 5 — Dockerfile ordering check

```bash
grep -n "COPY\|RUN pip\|USER\|CMD\|ENTRYPOINT" Dockerfile
```

Verify ordering:
1. `COPY` commands first
2. `RUN pip install` before `USER wbsb`
3. `chown` before `USER wbsb`
4. `USER wbsb` immediately before `CMD`

If `USER wbsb` appears before `COPY` or before `pip install`, the container may not have permissions to read the application files — report as `MAJOR`.

### Step 6 — `store.py` chmod check

```bash
grep -n "chmod\|0o600\|0o700\|os.chmod" src/wbsb/feedback/store.py
```

Verify:
- `os.chmod(feedback_path, 0o600)` after every feedback file write
- `mkdir(mode=0o700, ...)` or `os.chmod(feedback_dir, 0o700)` for the feedback directory

### Step 7 — No silent permission errors

```bash
grep -n "except.*chmod\|chmod.*except\|pass" src/wbsb/feedback/store.py
```

`os.chmod` must not be silently swallowed. If it fails, the exception should propagate. Any `try/except` around `os.chmod` that discards the error → `CHANGES REQUIRED`.

### Step 8 — Test file permission check

```bash
grep -n "^def test_" tests/test_security_hardening.py 2>/dev/null || grep -n "test_feedback_artifact_permissions\|test_feedback_dir_permissions" tests/test_feedback.py
```

Required tests:
- `test_feedback_artifact_permissions` — confirms `0o600`
- `test_feedback_dir_permissions` — confirms `0o700`

### Step 9 — Permission mask portability check

```bash
grep -A 10 "test_feedback_artifact_permissions\|test_feedback_dir_permissions" tests/test_security_hardening.py 2>/dev/null || grep -A 10 "test_feedback_artifact_permissions" tests/test_feedback.py
```

Verify tests use `& 0o777` mask when reading `st_mode`:
```python
assert (os.stat(path).st_mode & 0o777) == 0o600
```

Using raw `os.stat().st_mode` without masking includes file type bits and will produce incorrect comparison. Report as `MINOR` if mask is absent.

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found
   - severity: `critical | major | minor`
   - file: `path:line`
   - exact problem
   - why it matters
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check (`[PASS]` or `[FAIL]` per line)
7. Exact Fixes Required
8. Final Recommendation (`approve | request changes | block`)

---

## Acceptance Criteria Checklist

- [ ] `USER wbsb` (UID 1000) in Dockerfile before `CMD`
- [ ] `groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb` present
- [ ] `chown -R wbsb:wbsb /app` before `USER wbsb`
- [ ] `USER wbsb` after all `COPY` and `pip install` instructions
- [ ] `os.chmod(feedback_path, 0o600)` after every feedback file write in `store.py`
- [ ] `feedback/` directory created with mode `0o700`
- [ ] `os.chmod` not silently swallowed
- [ ] `test_feedback_artifact_permissions` tests `0o600` with `& 0o777` mask
- [ ] `test_feedback_dir_permissions` tests `0o700` with `& 0o777` mask
- [ ] All existing tests pass
- [ ] Ruff clean
- [ ] Only allowed files modified
