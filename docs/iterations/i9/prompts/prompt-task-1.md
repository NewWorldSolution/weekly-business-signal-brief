# Task Prompt — I9-1: Delivery Config Schema

---

## Context

Implement **I9-1** from `docs/iterations/i9/tasks.md`.
This task defines delivery config contract used by all downstream delivery tasks.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Config is source-of-truth; no hardcoded delivery values. |
| 2 | Webhook URLs resolve from env only. |
| 3 | Do not log raw webhook URLs. |
| 4 | Keep scope limited to config module + tests. |
| 5 | Open draft PR before editing. |

---

## Step 0 — Worktree Setup and Draft PR

Your dedicated branch and worktree are already created:
- **Branch:** `feature/i9-1-delivery-config`
- **Worktree:** `../wbsb-i9-1-delivery-config`

```bash
# 1. Confirm you are on the correct branch
git branch --show-current   # must output: feature/i9-1-delivery-config

# 2. Sync with any upstream changes to the iteration base
git fetch origin
git rebase origin/feature/iteration-9

# 3. Verify baseline before any edits
pytest --tb=short -q
ruff check .

# 4. Open draft PR before implementing
#    Branch must have at least one commit ahead of base:
git commit --allow-empty -m "chore(i9-1): open draft — baseline verified"
git push

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-1-delivery-config \
  --title "I9-1: delivery config schema" \
  --body "Work in progress." \
  --draft
```

**Do not implement in any other branch or worktree.**

**Dependency:** Do not begin implementation until `feature/i9-0-pre-work` is merged into `feature/iteration-9` (this task needs the `delivery/` package scaffolding from I9-0). After that merge, sync before implementing:

```bash
git fetch origin && git rebase origin/feature/iteration-9
```

---

## Inputs and Outputs

### Inputs
- `docs/iterations/i9/tasks.md` (I9-1 section — frozen delivery config schema)
- `.env.example` (read only — env var names to document in YAML placeholders)

### Outputs
- `config/delivery.yaml` — delivery config with env-placeholder webhook URLs
- `src/wbsb/delivery/config.py` — loader, resolver, and enabled-flag helpers
- `tests/test_delivery_config.py` — config unit tests

---

## Allowed Files

```text
config/delivery.yaml
src/wbsb/delivery/config.py
tests/test_delivery_config.py
```

## Forbidden Files

```text
src/wbsb/delivery/models.py
src/wbsb/pipeline.py
src/wbsb/cli.py
config/rules.yaml
```

---

## Objective

Implement exactly per I9-1 in tasks.md:

- `config/delivery.yaml` with required sections (`delivery`, `scheduler`, `alerts`)
- `load_delivery_config(path=Path("config/delivery.yaml")) -> dict`
- `resolve_webhook_url(template: str) -> str | None`
- `teams_enabled(cfg: dict) -> bool`
- `slack_enabled(cfg: dict) -> bool`

Required behavior:
- missing required keys -> `ValueError`
- missing env var in placeholder -> `None` (no raise)
- enabled helpers return true only when both flag=true and URL resolved

---

## Execution Workflow

1. Read I9-1 section in `docs/iterations/i9/tasks.md`.
2. Implement `config/delivery.yaml` from frozen schema.
3. Implement delivery config loader/resolver helpers.
4. Add required tests from tasks.md.
5. Run:

```bash
pytest --tb=short -q
ruff check .
```

6. Verify scope:

```bash
git diff --name-only feature/iteration-9
```

---

## Test Requirements

Required tests:
- `test_load_delivery_config_valid`
- `test_load_delivery_config_missing_required_key`
- `test_resolve_webhook_url_set`
- `test_resolve_webhook_url_missing`
- `test_teams_enabled_true`
- `test_teams_enabled_flag_false`
- `test_teams_enabled_no_url`
- `test_slack_enabled_same_logic`

---

## Acceptance Criteria

- Config schema file created as specified.
- All four config functions implemented with correct behavior.
- URL placeholders resolve through env only.
- No URL leakage in logs.
- Required tests present and passing.
- Ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened before code edits
- [ ] Only allowed files modified
- [ ] Required functions implemented
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
