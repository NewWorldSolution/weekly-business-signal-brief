# Task Prompt — I9-5: Delivery Orchestrator + `wbsb deliver` CLI

---

## Context

You are implementing **task I9-5** of Iteration 9.
This task wires delivery through an orchestrator that reads run artifacts from disk.

**Critical boundary:** delivery must stay outside pipeline internals.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Pipeline writes artifacts; orchestrator reads artifacts. |
| 2 | No delivery imports inside `pipeline.py`. |
| 3 | `deliver_run()` never raises; per-target failures captured in `DeliveryResult`. |
| 4 | LLM fallback handling is orchestrator-level via manifest/llm_result checks. |
| 5 | Open draft PR before edits. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-5-cli-integration`
- **Worktree:** `../wbsb-i9-5-cli-integration`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-5-cli-integration

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-5): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-5-cli-integration \
  --title "I9-5: delivery orchestrator and deliver CLI" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

**Dependency:** Do not begin implementation until all of the following are merged into `feature/iteration-9`:
- `feature/i9-2-teams-adapter` (provides `teams.py`)
- `feature/i9-3-slack-adapter` (provides `slack.py`)
- `feature/i9-4-scheduler` (provides `auto.py` and `--auto` CLI flag)

After those merges, sync before implementing:

```bash
git fetch origin && git rebase origin/feature/iteration-9
```

---

## Objective

Implement I9-5 from `docs/iterations/i9/tasks.md`:
- create `src/wbsb/delivery/orchestrator.py`
- add `wbsb deliver --run-id` command
- add `--deliver` flag to `wbsb run` at CLI layer
- add orchestrator tests

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-5 section)
- `src/wbsb/delivery/teams.py`, `src/wbsb/delivery/slack.py` (read only — send functions)
- `src/wbsb/delivery/config.py` (read only — enabled flags, URL resolution)
- `runs/{run_id}/` directory (runtime read — `findings.json`, `manifest.json`, `llm_response.json`)

### Outputs
- `src/wbsb/delivery/orchestrator.py` — `load_run_artifacts()`, `deliver_run()`
- `src/wbsb/cli.py` — `wbsb deliver --run-id`, `wbsb run --deliver` flag
- `tests/test_delivery_orchestrator.py` — orchestrator unit tests

---

## Allowed Files

```text
src/wbsb/delivery/orchestrator.py
src/wbsb/cli.py
tests/test_delivery_orchestrator.py
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/delivery/teams.py
src/wbsb/delivery/slack.py
```

---

## Required Public API

In `src/wbsb/delivery/orchestrator.py`:

```python
def load_run_artifacts(run_id: str, output_dir: Path = Path("runs")) -> dict: ...
def deliver_run(run_id: str, delivery_cfg: dict) -> list[DeliveryResult]: ...
```

Behavior must match I9-5 contract exactly.

---

## Execution Workflow

1. Read I9-5 section in tasks.md fully.
2. Implement artifact loading and clear `FileNotFoundError` behavior for missing required artifacts.
3. Implement delivery dispatch to enabled targets only.
4. Keep fallback banner trigger logic in orchestrator by passing `llm_result=None` when fallback state detected.
5. Extend CLI:
   - `wbsb deliver --run-id`
   - `wbsb run ... --deliver`
   - delivery failure should not crash run command; report clearly.
6. Add tests listed in tasks.md.
7. Run:

```bash
pytest --tb=short -q
ruff check .
```

8. Verify diff scope:

```bash
git diff --name-only feature/iteration-9
```

---

## Test Requirements

Add all required tests from tasks.md:
- `test_load_run_artifacts_success`
- `test_load_run_artifacts_no_llm_response`
- `test_load_run_artifacts_missing_findings`
- `test_deliver_run_teams_only`
- `test_deliver_run_both_targets`
- `test_deliver_run_no_targets`
- `test_deliver_run_failure_captured`
- `test_deliver_run_llm_fallback_flag`

---

## Acceptance Criteria

- Orchestrator API implemented and importable.
- Delivery reads artifacts from `runs/{run_id}`; no direct pipeline coupling.
- `wbsb deliver` works for a given run_id.
- `wbsb run --deliver` triggers delivery from CLI layer only.
- Per-target failures captured, no uncaught exception propagation from orchestrator.
- `pipeline.py` unchanged.
- Tests + ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened before edits
- [ ] Only allowed files changed
- [ ] Orchestrator implemented with required API
- [ ] CLI commands/flags wired correctly
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
