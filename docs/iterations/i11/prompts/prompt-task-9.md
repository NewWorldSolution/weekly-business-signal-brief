# WBSB Task Prompt — I11-9: Final Cleanup + Merge to Main

---

## Context

You are implementing **I11-9** of the WBSB project.

WBSB is a deterministic analytics engine. I11-9 is the final cleanup and merge task for the Security Hardening iteration. All security implementation tasks (I11-1 through I11-7) and the architecture review (I11-8) are complete.

**Prerequisite:** I11-8 architecture review must have passed. If the review produced findings, they must be resolved before running this task.

**Owner:** Claude

---

## Step 0 — Open Draft PR Before Writing Any Code

```bash
git checkout feature/iteration-11
git pull origin feature/iteration-11
git checkout -b feature/i11-9-final-cleanup
git push -u origin feature/i11-9-final-cleanup

pytest && ruff check .
git commit --allow-empty -m "chore(i11-9): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-11 \
  --head feature/i11-9-final-cleanup \
  --title "I11-9: Final cleanup + merge prep" \
  --body "Work in progress." \
  --draft
```

---

## Objective

1. Fix any issues identified in the I11-8 architecture review
2. Update documentation to reflect I11 completion
3. Final verification: all tests pass, ruff clean, golden eval cases pass
4. Open the final PR to merge `feature/iteration-11` → `main`

---

## Step 1 — Apply Review Findings

Read the I11-8 review output. For each finding marked `FAIL` or flagged as requiring a fix:
- Make the minimum change required — do not refactor beyond what was flagged
- Re-run tests after each fix
- Document what was fixed in the commit message

If the review produced zero findings (PASS with no issues), skip this step.

---

## Step 2 — Update Documentation

### `docs/project/TASKS.md`

- Mark I11 status as `✅ Complete`
- Update the test count baseline to the final passing count (run `pytest` and note the number)
- Add a Definition of Done summary for I11

### `docs/project/project-iterations.md`

- Mark I11 status as `✅ Complete`
- Update baseline test count
- Update execution order section if needed

### `docs/project/HOW_IT_WORKS.md`

Add a Security Controls section to the architecture overview:

```markdown
## Security Controls (I11)

The feedback webhook (`POST /feedback`) is protected by:

- **HMAC-SHA256 signing** — every request must include a valid signature computed from the request body and timestamp using `WBSB_FEEDBACK_SECRET`
- **Timestamp freshness** — requests are rejected if the `X-WBSB-Timestamp` header is more than 300 seconds old
- **Nonce replay prevention** — each request must carry a unique UUID4 in `X-WBSB-Nonce`; reused nonces are rejected for 10 minutes
- **Rate limiting** — per-IP (10 req/60s + burst 3) and global (100 req/60s) circuit breaker
- **HTTPS enforcement** — optional `WBSB_REQUIRE_HTTPS=true` flag rejects plain HTTP requests
- **Non-root container** — Docker container runs as UID 1000
- **File permissions** — feedback artifacts written at `0o600`
- **Sanitized error responses** — no stack traces, paths, or module names in HTTP responses
- **Pseudonymized log events** — IPs zeroed at last octet in all security log entries
```

---

## Step 3 — Final Verification

```bash
# Full test suite
pytest -v

# Lint
ruff check .

# Eval golden cases
wbsb eval
# Must show: all 6 cases PASS

# Security-specific checks
grep -rn "traceback\|Traceback" src/wbsb/feedback/server.py
# Must return nothing

grep -n "compare_digest" src/wbsb/feedback/auth.py
# Must find it

grep -n "USER wbsb" Dockerfile
# Must find it

grep -n "threading.Lock\|Lock()" src/wbsb/feedback/auth.py src/wbsb/feedback/ratelimit.py
# Must find Lock usage in both files

pip-audit --requirement requirements.lock --fail-on HIGH
# Must pass
```

Record the final test count. Update docs to reflect the actual count.

---

## Step 4 — Open Final PR to Main

```bash
# Push cleanup branch and merge into feature/iteration-11
git add <changed files>
git commit -m "chore(i11-9): final cleanup, docs update, I11 complete"
git push origin feature/i11-9-final-cleanup
gh pr ready

# After the cleanup PR merges into feature/iteration-11, open the iteration PR:
gh pr create \
  --base main \
  --head feature/iteration-11 \
  --title "I11: Security Hardening & Production Readiness" \
  --body "$(cat <<'EOF'
## Summary

- HMAC-SHA256 authentication for POST /feedback (I11-1, I11-2, I11-5)
- Per-IP + global rate limiting (I11-3, I11-5)
- Structured security observability with pseudonymized IPs (I11-4, I11-5)
- Non-root Docker container (UID 1000) and feedback artifact permissions 0o600 (I11-6)
- Multi-stage Docker build, pip-audit CI, trivy image scan (I11-7)

## Test plan
- [ ] All tests pass
- [ ] Ruff clean
- [ ] wbsb eval all 6 golden cases pass
- [ ] docker run as UID 1000 confirmed
- [ ] pip-audit passes with no HIGH/CRITICAL CVEs
EOF
)"
```

---

## Allowed Files

```
Any file that requires fixing based on I11-8 review findings
docs/project/TASKS.md
docs/project/project-iterations.md
docs/project/HOW_IT_WORKS.md
```

---

## Acceptance Criteria

- [ ] All I11-8 review findings resolved (or confirmed as not applicable)
- [ ] `docs/project/TASKS.md` marks I11 complete with correct test count
- [ ] `docs/project/HOW_IT_WORKS.md` has Security Controls section
- [ ] `pytest` passes with all tests (count matches updated docs)
- [ ] `ruff check .` passes
- [ ] `wbsb eval` — all 6 golden cases pass
- [ ] Final PR `feature/iteration-11` → `main` opened

---

## Completion Checklist

- [ ] I11-8 review findings addressed
- [ ] Docs updated (TASKS.md, project-iterations.md, HOW_IT_WORKS.md)
- [ ] Final pytest count recorded and docs updated
- [ ] `wbsb eval` all 6 golden cases pass
- [ ] Security spot checks passed (traceback grep, compare_digest grep, USER grep, Lock grep)
- [ ] `pip-audit` clean
- [ ] Cleanup PR merged into `feature/iteration-11`
- [ ] Final PR `feature/iteration-11` → `main` opened and ready for review
