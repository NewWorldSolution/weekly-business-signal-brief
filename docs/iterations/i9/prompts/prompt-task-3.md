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

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-3-slack-adapter
git push -u origin feature/i9-3-slack-adapter

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-3-slack-adapter \
  --title "I9-3: Slack block kit builder" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

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

## What to Build

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
