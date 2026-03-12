# Task Prompt — I9-2: Teams Adaptive Card Builder

---

## Context

Implement **I9-2** from `docs/iterations/i9/tasks.md`.
This task builds Teams card rendering + sender wrapper.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Builder output is deterministic JSON-serializable dict. |
| 2 | Sender never raises; returns `DeliveryResult`. |
| 3 | No live webhook calls in tests. |
| 4 | Keep pipeline untouched. |
| 5 | Open draft PR first. |

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-2-teams-adapter
git push -u origin feature/i9-2-teams-adapter

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-2-teams-adapter \
  --title "I9-2: Teams adaptive card builder" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

---

## Allowed Files

```text
src/wbsb/delivery/teams.py
tests/test_delivery_teams.py
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/cli.py
src/wbsb/delivery/slack.py
```

---

## What to Build

Implement exactly per tasks.md:
- `build_teams_card(findings, llm_result, feedback_webhook_url) -> dict`
- `send_teams_card(card: dict, webhook_url: str) -> DeliveryResult`

Must enforce card contract:
- Adaptive Card `1.4`
- period format `"{week_start} – {week_end}"`
- WARN-only top signals sorted by `rule_id`
- fallback banner text exact
- no WARN -> deterministic no-warning text
- feedback buttons omitted when feedback URL is None
- sender timeout 10s; non-2xx/timeout -> failed result

---

## Execution Workflow

1. Read I9-2 section in tasks.md.
2. Implement card builder and sender wrapper.
3. Add required mocked HTTP tests.
4. Run:

```bash
pytest --tb=short -q
ruff check .
```

5. Verify scope with `git diff --name-only feature/iteration-9`.

---

## Test Requirements

- `test_build_card_with_llm`
- `test_build_card_llm_fallback`
- `test_build_card_warn_signals`
- `test_build_card_no_signals`
- `test_build_card_no_feedback_url`
- `test_build_card_feedback_buttons`
- `test_send_card_success`
- `test_send_card_failure`
- `test_send_card_timeout`

---

## Acceptance Criteria

- Functions implemented with required signatures.
- Card format rules fully respected.
- Sender behavior handles success/failure/timeout without raise.
- Required tests pass.
- Ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened before edits
- [ ] Only allowed files modified
- [ ] Card/sender contract implemented
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
