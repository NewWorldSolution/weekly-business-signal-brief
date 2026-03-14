# Task Prompt — I9-8: Containerisation + Security Hardening

---

## Context

You are implementing **task I9-8** of Iteration 9.
This task packages WBSB for deployment and enforces security hygiene checks.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | No secrets in image, code, logs, or committed env files. |
| 2 | Docker runtime uses env injection; no hardcoded keys. |
| 3 | Do not change app logic in this task. |
| 4 | Security grep checklist must pass before ready-for-review. |
| 5 | Open draft PR first. |

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-8-containerization
git push -u origin feature/i9-8-containerization

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-8-containerization \
  --title "I9-8: containerization and security hardening" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

---

## Objective

Implement exactly the I9-8 contract from tasks.md:
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- run and document security checks

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-8 section — container spec + security checklist)
- `src/` (read only — source to be containerized; must not be modified)
- `.env.example` (read only — documents required runtime env vars)

### Outputs
- `Dockerfile` — single-stage build from `python:3.11-slim`
- `docker-compose.yml` — env injection via `env_file`, volume mounts, run command
- `.dockerignore` — excludes `.env`, `tests/`, `docs/`, `runs/`, `feedback/`, etc.
- Security checklist results (documented in PR description)

---

## Allowed Files

```text
Dockerfile
docker-compose.yml
.dockerignore
```

## Forbidden Files

```text
src/**
config/**
tests/**
```

---

## Execution Workflow

1. Read I9-8 section in tasks.md.
2. Create Dockerfile following specified single-stage pattern.
3. Create docker-compose with volumes/env-file and command.
4. Create `.dockerignore` with required exclusions.
5. Run required verification commands from tasks.md:

```bash
docker build -t wbsb .
docker run --rm wbsb wbsb --help
docker run --rm wbsb ls -la | grep -c ".env"

grep -rn "ANTHROPIC_API_KEY\s*=" src/ config/
grep -rn "webhook_url" src/ | grep -v "log.error\|log.debug\|#"
grep -rn "os.environ" src/
```

6. Run global quality checks:

```bash
pytest --tb=short -q
ruff check .
```

7. Verify scope via git diff.

---

## Test Requirements

- No new tests required by I9-8.
- Existing tests must remain green.

---

## Acceptance Criteria

- Docker image builds and runs `wbsb --help`.
- `.env` not present in built image.
- Security grep checks pass.
- `docker-compose.yml` starts cleanly in local test.
- Existing tests pass; ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened before edits
- [ ] Only allowed files changed
- [ ] Dockerfile/compose/dockerignore created as specified
- [ ] Security checklist commands executed and verified
- [ ] `pytest` passes
- [ ] `ruff check .` passes
