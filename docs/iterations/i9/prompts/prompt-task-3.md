# Task Prompt — I9-3: Slack Block Kit Builder

---

## Context

Implement **I9-3** from `docs/iterations/i9/tasks.md`.
This task builds Slack block rendering + sender wrapper.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Builder output is deterministic JSON-serializable list of blocks. |
| 2 | Sender never raises; returns `DeliveryResult`. |
| 3 | No live webhook calls in tests. |
| 4 | Keep pipeline untouched. |
| 5 | Open draft PR first. |
| 6 | Webhook URL is a credential: read from config (which resolves from env only); never log at any level (info, debug, warning); do not include in test output or error messages. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-3-slack-adapter`
- **Worktree:** `../wbsb-i9-3-slack-adapter`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-3-slack-adapter

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-3): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-3-slack-adapter \
  --title "I9-3: Slack block kit builder" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

**Dependency:** Do not begin implementation until `feature/i9-1-delivery-config` is merged into `feature/iteration-9` (this task needs `DeliveryConfig` and the resolved webhook URL from I9-1). After that merge, sync before implementing:

```bash
git fetch origin && git rebase origin/feature/iteration-9
```

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-3 section — block contract)
- `src/wbsb/delivery/models.py` (read only — `DeliveryResult`, `DeliveryTarget`)
- `src/wbsb/domain/models.py` (read only — `Findings`, `Signal`, `LLMResult`)
- Webhook URL provided by caller at runtime (never hardcoded)

### Outputs
- `src/wbsb/delivery/slack.py` — `build_slack_blocks()`, `send_slack_message()`
- `tests/test_delivery_slack.py` — block/sender unit tests (no live HTTP)

---

## Allowed Files

```text
src/wbsb/delivery/slack.py
tests/test_delivery_slack.py
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/cli.py
src/wbsb/delivery/teams.py
```

---

## Objective

Implement exactly per tasks.md:
- `build_slack_blocks(findings, llm_result, feedback_webhook_url) -> list[dict]`
- `send_slack_message(blocks, webhook_url) -> DeliveryResult`

Must enforce block contract:
- header/context/divider/situation/signals/divider/actions pattern
- top 3 WARN signals by `rule_id`, extras as `+ N more`
- no WARN -> deterministic no-warning text
- fallback banner text exact
- actions omitted when feedback URL missing
- sender timeout 10s; non-2xx/timeout -> failed result

---

## Execution Workflow

1. Read I9-3 section in tasks.md.
2. Implement block builder and sender wrapper.
3. Add required tests with mocked HTTP.
4. Run:

```bash
pytest --tb=short -q
ruff check .
```

5. Verify scope via git diff.

---

## Test Requirements

- `test_build_blocks_with_llm`
- `test_build_blocks_llm_fallback`
- `test_build_blocks_warn_signals`
- `test_build_blocks_no_signals`
- `test_build_blocks_no_feedback_url`
- `test_build_blocks_feedback_actions`
- `test_send_message_success`
- `test_send_message_failure`
- `test_send_message_timeout`

---

## Acceptance Criteria

- Functions implemented with required signatures.
- Block Kit contract respected.
- Sender handles failure paths without raising.
- Required tests pass.
- Ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened before edits
- [ ] Only allowed files modified
- [ ] Block/sender contract implemented
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
