# WBSB Task Prompt — I11-7: Supply Chain Security

---

## Context

You are implementing **I11-7** of the WBSB project.

WBSB is a deterministic analytics engine. I11 is the Security Hardening iteration. I11-7 adds dependency pinning, `pip-audit` CI, `trivy` image scan, and converts the Dockerfile to a multi-stage build.

**Prerequisite:** I11-6 must be merged. The non-root user (`USER wbsb`, UID 1000) is already in the Dockerfile. You will restructure the Dockerfile to multi-stage while preserving that user in the production stage.

**This task also modifies `docker-compose.yml` and `pyproject.toml`** — both are exclusively in this task's scope.

**Worktree:** Run this task in `worktrees/i11-supply-chain`:
```bash
git worktree add worktrees/i11-supply-chain feature/i11-7-supply-chain
cd worktrees/i11-supply-chain
```

---

## Architecture Rules (apply to all I11 tasks)

| Rule | Description |
|---|---|
| Rule 1 | Use `pip-compile` from `pip-tools` — not `pip freeze` — to generate the lockfile |
| Rule 2 | Do NOT change `>=` to `==` in `pyproject.toml` — abstract specifiers stay abstract |
| Rule 3 | Non-root user from I11-6 must be preserved in the production stage of the multi-stage Dockerfile |
| Rule 4 | No build tools (`gcc`, `build-essential`) in the final Docker image layer |
| Rule 5 | CI job must fail on HIGH or CRITICAL CVEs — not just warn |

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
# From worktrees/i11-supply-chain directory:
git pull origin feature/i11-7-supply-chain

pytest && ruff check .
git commit --allow-empty -m "chore(i11-7): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-7-supply-chain \
  --title "I11-7: Supply chain — dep pinning, pip-audit, trivy, multi-stage Docker" \
  --body "Work in progress." \
  --draft
```

---

## Objective

1. Generate `requirements.lock` using `pip-compile`
2. Add `pip-tools` to dev dependencies in `pyproject.toml`
3. Convert `Dockerfile` to multi-stage (preserve non-root user)
4. Add `cap_drop: ALL` to `docker-compose.yml`
5. Create `.github/workflows/security.yml` with `pip-audit` and `trivy` jobs

---

## `requirements.lock` — Dependency Lockfile

**Why `pip-compile` instead of `pip freeze`:**
`pip freeze` captures everything in the current virtualenv — including editable installs (`-e .`) and local-only packages. This produces a lockfile that cannot be reproduced on CI or another machine. `pip-compile` resolves the full dependency graph from `pyproject.toml` and produces a platform-neutral, reproducible lockfile with only the packages declared or transitively needed.

```bash
pip install pip-tools
pip-compile pyproject.toml --output-file requirements.lock --strip-extras
```

Commit the resulting `requirements.lock`. This file will be used by:
- The production Docker image (replace `pip install -e .` with `pip install -r requirements.lock`)
- The `pip-audit` CI job

---

## `pyproject.toml` — Dev Dependencies Only

Add `pip-tools` to the development/optional dependencies section only. Do NOT change any existing version specifiers (e.g. do not change `pydantic>=2.0` to `pydantic==2.x.y`). The lockfile handles exact pinning; pyproject.toml keeps abstract ranges for packaging compatibility.

```toml
# Example — find the correct section in the existing pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
    "pip-tools",   # ← add this
    # ... existing dev deps
]
```

---

## `Dockerfile` — Multi-Stage Build

Read the current Dockerfile (which already has the non-root user from I11-6). Convert it to this two-stage structure:

```dockerfile
# Stage 1: builder
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml requirements.lock ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.lock
RUN pip install --no-cache-dir -e .

# Stage 2: production
FROM python:3.11-slim AS production
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and config
COPY src/ ./src/
COPY config/ ./config/

# Runtime directories
RUN mkdir -p /app/output /app/runs /app/feedback

# Non-root user (from I11-6 — preserve exactly as-is)
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb

CMD ["wbsb", "--help"]
```

**Key requirement:** The `builder` stage can have build tools. The `production` stage must not contain `gcc`, `build-essential`, or any other build toolchain. Verify with:
```bash
docker history --no-trunc wbsb | grep -E "gcc|build-essential"
# Must return nothing for production stage layers
```

---

## `docker-compose.yml` — Cap Drop

Add to each service definition:
```yaml
services:
  wbsb:
    # ... existing config ...
    cap_drop:
      - ALL
```

---

## `.github/workflows/security.yml` — New CI Job

Create this file:

```yaml
name: Security Scan
on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]

jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install pip-tools and pip-audit
        run: pip install pip-tools pip-audit
      - name: Regenerate lockfile
        run: pip-compile pyproject.toml --output-file requirements.lock --strip-extras
      - name: Audit dependencies
        run: pip-audit --requirement requirements.lock --fail-on HIGH

  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          tags: wbsb:test
          push: false
      - name: Scan image for vulnerabilities
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: wbsb:test
          severity: CRITICAL
          exit-code: 1
          format: table
```

---

## Allowed Files

```
requirements.lock                     ← create (pip-compile output)
Dockerfile                            ← convert to multi-stage (preserve non-root user from I11-6)
docker-compose.yml                    ← add cap_drop: ALL
.github/workflows/security.yml        ← create
pyproject.toml                        ← add pip-tools to dev deps only; no version specifier changes
```

## Files Not to Touch

```
src/wbsb/feedback/store.py            ← I11-6 only
src/wbsb/feedback/server.py           ← I11-5 only
src/wbsb/cli.py                       ← I11-5 only
config/rules.yaml
Any test file
```

---

## Execution Workflow

```bash
# 1. Read Dockerfile (understand I11-6 non-root user additions)
# 2. Read docker-compose.yml
# 3. Read pyproject.toml (understand existing structure)

# 4. Generate lockfile
pip install pip-tools
pip-compile pyproject.toml --output-file requirements.lock --strip-extras

# 5. Convert Dockerfile to multi-stage

# 6. Update docker-compose.yml

# 7. Create .github/workflows/security.yml

# 8. Update pyproject.toml (pip-tools in dev deps only)

# 9. Verify Python tests pass (Docker/CI checks are manual)
pytest && ruff check .

# Supply chain checks
pip-audit --requirement requirements.lock --fail-on HIGH
# Must pass (no HIGH/CRITICAL CVEs)

grep -n "gcc\|build-essential" Dockerfile
# Must find nothing in production stage

grep -n "USER wbsb\|useradd" Dockerfile
# Must find non-root user in production stage

# pyproject.toml check — no version specifiers changed
git diff feature/iteration-11 -- pyproject.toml
# Only the pip-tools addition should appear

# Scope check
git diff --name-only feature/iteration-11

git add requirements.lock Dockerfile docker-compose.yml .github/workflows/security.yml pyproject.toml
git commit -m "feat(i11-7): dep pinning with pip-compile, pip-audit CI, trivy scan, multi-stage Docker"
git push origin feature/i11-7-supply-chain
gh pr ready
```

---

## Acceptance Criteria

- [ ] `requirements.lock` generated by `pip-compile` — not `pip freeze`
- [ ] `pip-audit --requirement requirements.lock --fail-on HIGH` passes (zero HIGH/CRITICAL CVEs)
- [ ] `Dockerfile` has two stages: `builder` and `production`
- [ ] `USER wbsb` (UID 1000) present in production stage of Dockerfile
- [ ] `grep -n "gcc\|build-essential" Dockerfile` returns nothing in production stage lines
- [ ] `docker-compose.yml` has `cap_drop: [ALL]` for each service
- [ ] `.github/workflows/security.yml` exists and is valid YAML
- [ ] `pip-tools` added to dev deps in `pyproject.toml` — no existing version specifiers changed
- [ ] All existing tests pass
- [ ] Ruff clean

---

## Completion Checklist

- [ ] Draft PR opened before any code written
- [ ] Current `Dockerfile` read before modifying
- [ ] Baseline `pytest && ruff check .` passed before first commit
- [ ] Non-root user from I11-6 preserved in production stage
- [ ] `pip-audit` run locally with zero HIGH/CRITICAL CVEs
- [ ] `pyproject.toml` diff shows only `pip-tools` addition (no specifier changes)
- [ ] All acceptance criteria met
- [ ] `git diff --name-only feature/iteration-11` shows only allowed files
- [ ] PR marked ready for review
