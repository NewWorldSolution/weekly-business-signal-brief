# WBSB Review Prompt — I9-8: Containerisation + Security Hardening

---

## Reviewer Mandate

Review I9-8 strictly against tasks.md.
Focus on container behavior and secrets hygiene.

Verdict: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Review Steps

1. Checkout:
```bash
git fetch origin
git checkout feature/i9-8-containerization
git pull origin feature/i9-8-containerization
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
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

4. Build/runtime checks:
```bash
docker build -t wbsb .
docker run --rm wbsb wbsb --help
docker run --rm wbsb ls -la | grep -c ".env"
```

5. Security checks:
```bash
grep -rn "ANTHROPIC_API_KEY\s*=" src/ config/
grep -rn "webhook_url" src/ | grep -v "log.error\|log.debug\|#"
grep -rn "os.environ" src/
```

6. Compose check:
```bash
docker compose config
```

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

- [ ] Dockerfile follows required pattern
- [ ] docker-compose is valid and aligned with task contract
- [ ] `.dockerignore` includes required exclusions
- [ ] image builds and `wbsb --help` runs
- [ ] `.env` absent from image
- [ ] security grep checks pass
- [ ] only allowed files modified
- [ ] tests pass
- [ ] ruff clean
