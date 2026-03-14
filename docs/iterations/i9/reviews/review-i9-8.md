# WBSB Review Prompt — I9-8: Containerisation + Security Hardening

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-8 strictly against `docs/iterations/i9/tasks.md`.
Focus on container behaviour and secrets hygiene. This is a deployment-facing task.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Project Context

WBSB is a deterministic analytics engine for appointment-based service businesses.
Iteration 9 adds deployment and delivery infrastructure.

**Security requirements for I9-8:**
- No secrets (API keys, webhook URLs) hardcoded anywhere in source or config
- No `.env` file baked into the Docker image
- Webhook URLs treated as credentials: must be read from env at runtime and never appear in logs at info, debug, or warning level
- Docker image must run on minimal assumptions; runtime env injection via `docker-compose` `env_file`
- Application logic must not be changed in this task

---

## Task Under Review

- Task: I9-8 — Containerisation + Security Hardening
- Branch: `feature/i9-8-containerization`
- Base: `feature/iteration-9`

Expected files in scope:
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-8-containerization
git pull origin feature/i9-8-containerization
```

### Step 2 — Run validation

```bash
pytest --tb=short -q
ruff check .
```

If either fails: `CHANGES REQUIRED`.

### Step 3 — Scope check

```bash
git diff --name-only feature/iteration-9
```

Allowed: `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
If any `src/`, `config/`, or `tests/` file is changed: `BLOCKED`.

### Step 4 — Build and runtime checks

```bash
docker build -t wbsb .
docker run --rm wbsb wbsb --help
docker run --rm wbsb ls -la | grep ".env"
```

Expected: image builds; `wbsb --help` runs; `.env` absent from container filesystem.

### Step 5 — Secrets hygiene check (hardcoded values)

```bash
grep -rn "ANTHROPIC_API_KEY\s*=" src/ config/
grep -rn "TEAMS_WEBHOOK_URL\s*=\s*[\"'][^$]" src/ config/
grep -rn "SLACK_WEBHOOK_URL\s*=\s*[\"'][^$]" src/ config/
```

Expected: no hardcoded secret values. Only env-placeholder references (e.g., `${TEAMS_WEBHOOK_URL}`) are allowed.

### Step 6 — Webhook URL logging check

```bash
grep -rn "webhook_url" src/wbsb/ | grep -v "log\.error\|log\.debug\|#\|\.yaml\|\.example\|test_"
```

Expected: no webhook URL appearing in `log.info`, `log.warning`, `print`, or equivalent. Any result here is a finding.

```bash
grep -rn "os\.environ\[.*(WEBHOOK|API_KEY)" src/wbsb/ | grep -v "#"
```

Verify env vars are accessed via `os.environ.get()` with None handling, not `os.environ[]` (which raises on missing).

### Step 7 — Compose and dockerignore check

```bash
docker compose config
```

Verify compose is valid and uses `env_file` for secret injection.

```bash
grep -n "\.env\|tests\|docs\|runs\|feedback" .dockerignore
```

Verify `.env`, `tests/`, `docs/`, `runs/`, `feedback/` are excluded from build context.

### Step 8 — App logic boundary check

```bash
git diff feature/iteration-9 -- src/ config/ tests/
```

Expected: no diff. If any application code is changed: `BLOCKED`.

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

## Acceptance Criteria Check List

- [ ] Dockerfile follows required single-stage pattern (`python:3.11-slim`)
- [ ] `docker-compose.yml` is valid; uses `env_file` for secret injection
- [ ] `.dockerignore` excludes `.env`, `tests/`, `docs/`, `runs/`, `feedback/`
- [ ] image builds and `wbsb --help` runs inside container
- [ ] `.env` absent from built image
- [ ] no hardcoded API key or webhook URL values in source or config
- [ ] webhook URLs not logged at info, warning, or debug level
- [ ] env vars accessed via `os.environ.get()` (not bare `os.environ[]`)
- [ ] application source code unchanged (zero diff in `src/`, `config/`, `tests/`)
- [ ] existing tests pass
- [ ] ruff clean
