# Task Prompt — I9-7: Feedback Webhook Server

---

## Context

You are implementing **task I9-7** of Iteration 9.
This adds the first inbound HTTP endpoint: `POST /feedback`.

**Security-critical task.** Validation and file-write safety are mandatory.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Validate `run_id`, `section`, `label` before writing anything. |
| 2 | Cap request body size and reject oversized requests. |
| 3 | Never derive output file path from user input. |
| 4 | Do not log comment content. |
| 5 | No auth for MVP, but explicitly document that limitation. |
| 6 | Open draft PR before changes. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-7-feedback-webhook`
- **Worktree:** `../wbsb-i9-7-feedback-webhook`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-7-feedback-webhook

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-7): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-7-feedback-webhook \
  --title "I9-7: feedback webhook server" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

**Dependency:** Do not begin implementation until `feature/i9-5-cli-integration` is merged into `feature/iteration-9`. After that merge, sync before implementing:

```bash
git fetch origin && git rebase origin/feature/iteration-9
```

**Parallel conflict note:** I9-6 (`feature/i9-6-failure-alerting`) runs in parallel with this task and also modifies `src/wbsb/cli.py`. The second of these tasks to merge into `feature/iteration-9` will need to resolve a conflict on that file. Keep CLI additions minimal and scoped to the `wbsb feedback serve` command only.

---

## Objective

Implement I9-7 exactly as defined in tasks.md:
- create stdlib HTTP server endpoint `POST /feedback`
- add `wbsb feedback serve` CLI command
- add webhook server tests

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-7 section — full webhook contract)
- `src/wbsb/feedback/store.py` (read only — `save_feedback()`)
- `src/wbsb/feedback/models.py` (read only — `FeedbackEntry`)
- `feedback/` directory (runtime write target — UUID-named JSON files)

### Outputs
- `src/wbsb/feedback/server.py` — `FeedbackHandler` (stdlib `http.server`), validation constants
- `src/wbsb/cli.py` — `wbsb feedback serve --host --port` command
- `tests/test_feedback_server.py` — webhook server unit tests

---

## Allowed Files

```text
src/wbsb/feedback/server.py
src/wbsb/cli.py
tests/test_feedback_server.py
```

## Forbidden Files

```text
src/wbsb/feedback/store.py
src/wbsb/feedback/models.py
```

---

## Required Behavior

From tasks.md (must be exact):
- run_id regex: `^\d{8}T\d{6}Z_[a-f0-9]{6}$`
- valid sections and labels allowlist enforced
- comment stripped + truncated to 1000 chars
- operator capped to 100 chars, default anonymous
- reject `Content-Length > 4096` with HTTP 413
- response 200 on valid, 400 on validation errors
- path always `feedback/{uuid4}.json`

---

## Execution Workflow

1. Read I9-7 section in tasks.md fully.
2. Implement `FeedbackHandler` using `http.server` only.
3. Add secure validation and capped field handling.
4. Ensure no user-derived file paths.
5. Add `wbsb feedback serve --host --port` command in CLI.
6. Add required tests.
7. Run:

```bash
pytest --tb=short -q
ruff check .
```

8. Verify file scope via git diff.

---

## Test Requirements

Required tests:
- `test_valid_feedback_returns_200`
- `test_invalid_run_id_returns_400`
- `test_invalid_section_returns_400`
- `test_invalid_label_returns_400`
- `test_body_too_large_returns_413`
- `test_comment_truncated_silently`
- `test_feedback_id_not_derived_from_input`

---

## Acceptance Criteria

- `POST /feedback` works with strict validation.
- Oversized payload rejected with 413.
- Comment and operator limits applied as specified.
- File path safe and user-input independent.
- `wbsb feedback serve` command functional.
- No sensitive comment logging.
- Tests + ruff clean.

---

## Completion Checklist

- [ ] Draft PR created first
- [ ] Only allowed files changed
- [ ] Endpoint validation complete
- [ ] Body/file safety checks implemented
- [ ] CLI serve command added
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
