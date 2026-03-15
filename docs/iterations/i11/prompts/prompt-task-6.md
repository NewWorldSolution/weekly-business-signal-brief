# WBSB Task Prompt — I11-6: Runtime Hardening

---

## Context

You are implementing **I11-6** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-6 adds container runtime hardening (non-root user in Dockerfile) and file permission hardening for feedback artifacts.

**Prerequisite:** I11-0 must be merged. This task is independent of I11-1 through I11-5 and can run in parallel with them.

**Important sequencing note:** I11-7 will convert this same Dockerfile to multi-stage. I11-7 must run AFTER I11-6 — it will preserve the non-root user you add here. Do not worry about multi-stage — that is I11-7's job.

**Worktree:** Run this task in `worktrees/i11-runtime-hardening`:
```bash
git worktree add worktrees/i11-runtime-hardening feature/i11-6-runtime-hardening
cd worktrees/i11-runtime-hardening
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Container must not run as root — UID 1000 |
| Rule 2 | Feedback artifacts must not be readable by other processes — `0o600` |
| Rule 3 | `feedback/` directory must not be accessible by other processes — `0o700` |
| Rule 4 | No silent failures — errors in file operations must raise |
| Rule 5 | Do not touch `server.py` — error response sanitization is I11-5 only |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-runtime-hardening directory:
git pull origin feature/i11-6-runtime-hardening

pytest && ruff check .
git commit --allow-empty -m "chore(i11-6): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-6-runtime-hardening \
  --title "I11-6: Runtime hardening — non-root Docker user, feedback file permissions" \
  --body "Work in progress." \
  --draft
```

---

## Objective

1. Add non-root user to `Dockerfile` (UID 1000)
2. Add `os.chmod` calls in `src/wbsb/feedback/store.py` after every feedback file write
3. Write tests confirming the file permissions

---

## Dockerfile — Non-Root User

Read the current `Dockerfile` first. Then add before the final `CMD` instruction:

```dockerfile
# Run as non-root user (I11-6)
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb
```

**Placement:** These lines must come after all `COPY` and `RUN pip install` instructions (so the files exist before chown), and immediately before the final `CMD` or `ENTRYPOINT`.

**Acceptance check (manual — not automated in CI):**
```bash
docker build -t wbsb-test .
docker run --rm wbsb-test id
# Must output: uid=1000(wbsb) gid=... — NOT uid=0(root)
```

---

## `src/wbsb/feedback/store.py` — File Permission Hardening

Read the current `store.py` to understand how feedback files are written. Then:

### Directory creation

When the `feedback/` directory is created, use mode `0o700`:
```python
import os
from pathlib import Path

feedback_dir = Path("feedback")
feedback_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
```

**Note:** `mkdir` with `mode=` sets the mode at creation time. On some systems you may need to follow with `os.chmod(feedback_dir, 0o700)` to ensure umask does not interfere.

### File permission after write

After writing each feedback JSON file, apply:
```python
os.chmod(feedback_path, 0o600)
```

The file write must succeed before `os.chmod`. If `os.chmod` fails, let the exception propagate — do not silently ignore a permission-setting failure.

**Pattern to follow:**
```python
feedback_path.write_text(json.dumps(entry_dict, indent=2))
os.chmod(feedback_path, 0o600)   # owner read-write only
```

---

## Required Tests (`tests/test_security_hardening.py`)

Create this new file with 2 tests:

```python
def test_feedback_artifact_permissions(tmp_path):
    # Call the feedback storage function with a valid entry
    # Use tmp_path to set the feedback directory
    # After the call, verify:
    stat = oct(os.stat(feedback_file).st_mode)
    assert stat.endswith('600')

def test_feedback_dir_permissions(tmp_path):
    # Ensure feedback/ directory is created fresh
    # Call the storage function
    # Verify feedback/ directory has mode 0o700
    stat = oct(os.stat(feedback_dir).st_mode)
    assert stat.endswith('700')
```

**Notes:**
- On macOS and Linux `os.stat().st_mode` includes file type bits, so use `& 0o777` to extract only permission bits: `assert (os.stat(path).st_mode & 0o777) == 0o600`
- Use `monkeypatch` or `tmp_path` to redirect the feedback directory in tests
- These tests confirm the permissions at the Python level; the Docker user confirmation is manual

---

## Allowed Files

```
Dockerfile                            ← add non-root user (do not convert to multi-stage)
src/wbsb/feedback/store.py            ← add chmod after file writes, use 0o700 for dir
tests/test_security_hardening.py      ← create
```

## Files Not to Touch

```
src/wbsb/feedback/server.py           ← I11-5 only
src/wbsb/cli.py                       ← I11-5 only
docker-compose.yml                    ← I11-7 only
pyproject.toml                        ← I11-7 only
src/wbsb/feedback/auth.py
src/wbsb/feedback/ratelimit.py
```

---

## Execution Workflow

```bash
# 1. Read Dockerfile in full
# 2. Read src/wbsb/feedback/store.py in full
# 3. Add non-root user to Dockerfile
# 4. Add chmod to store.py
# 5. Write tests

pytest && ruff check .

# Scope check
git diff --name-only feature/iteration-11
# Only: Dockerfile, store.py, test_security_hardening.py

git add Dockerfile src/wbsb/feedback/store.py tests/test_security_hardening.py
git commit -m "feat(i11-6): non-root Docker user UID 1000, feedback artifacts at 0o600"
git push origin feature/i11-6-runtime-hardening
gh pr ready
```

---

## Acceptance Criteria

- [ ] `Dockerfile` has `USER wbsb` (UID 1000) before final `CMD`
- [ ] `groupadd` and `useradd` commands present in Dockerfile
- [ ] `chown -R wbsb:wbsb /app` present before `USER` directive
- [ ] `test_feedback_artifact_permissions` confirms `0o600`
- [ ] `test_feedback_dir_permissions` confirms `0o700`
- [ ] No `except: pass` around `os.chmod` calls
- [ ] All existing tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] `Dockerfile` and `store.py` read in full before modifying
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] `USER wbsb` is the last line before `CMD`
- [ ] `os.chmod` called after every feedback file write in `store.py`
- [ ] File permission tests use `& 0o777` mask for portability
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
