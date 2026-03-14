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
| 6 | Webhook URL is a credential: read from config (which resolves from env only); never log at any level (info, debug, warning); do not include in test output or error messages. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-2-teams-adapter`
- **Worktree:** `../wbsb-i9-2-teams-adapter`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-2-teams-adapter

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-2): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-2-teams-adapter \
  --title "I9-2: Teams adaptive card builder" \
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
- `docs/iterations/i9/tasks.md` (I9-2 section — card contract)
- `src/wbsb/delivery/models.py` (read only — `DeliveryResult`, `DeliveryTarget`)
- `src/wbsb/domain/models.py` (read only — `Findings`, `Signal`, `LLMResult`)
- Webhook URL provided by caller at runtime (never hardcoded)

### Outputs
- `src/wbsb/delivery/teams.py` — `build_teams_card()`, `send_teams_card()`
- `tests/test_delivery_teams.py` — card/sender unit tests (no live HTTP)

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

## Objective

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
