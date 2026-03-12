# WBSB Review Prompt — I9-1: Delivery Config Schema

---

## Reviewer Role & Mandate

You are an independent code reviewer for WBSB.
Review I9-1 strictly against `docs/iterations/i9/tasks.md`.
Do not fix code. Report issues with evidence.

Verdict options: `PASS | CHANGES REQUIRED | BLOCKED`.

---

## Task Under Review

- Task: I9-1 — Delivery Config Schema
- Branch: `feature/i9-1-delivery-config`
- Base: `feature/iteration-9`

Expected files in scope:
- `config/delivery.yaml`
- `src/wbsb/delivery/config.py`
- `tests/test_delivery_config.py`

---

## Review Execution Steps

### Step 1 — Checkout

```bash
git fetch origin
git checkout feature/i9-1-delivery-config
git pull origin feature/i9-1-delivery-config
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

Fail if files outside allowed list are changed.

### Step 4 — API/signature check

```bash
python3 -c "from wbsb.delivery.config import load_delivery_config, resolve_webhook_url, teams_enabled, slack_enabled; import inspect; print(inspect.signature(load_delivery_config)); print(inspect.signature(resolve_webhook_url)); print(inspect.signature(teams_enabled)); print(inspect.signature(slack_enabled))"
```

Verify required functions exist with expected parameters.

### Step 5 — Config schema check

```bash
python3 -c "import yaml; from pathlib import Path; cfg=yaml.safe_load(Path('config/delivery.yaml').read_text()); print(cfg.keys()); print(cfg.get('delivery',{}).keys()); print(cfg.get('scheduler',{}).keys()); print(cfg.get('alerts',{}).keys())"
```

Verify schema matches tasks.md and webhook URLs use env placeholders.

### Step 6 — Security checks

```bash
grep -n "TEAMS_WEBHOOK_URL\|SLACK_WEBHOOK_URL" config/delivery.yaml
grep -n "print\|log\.info\|logger\.info" src/wbsb/delivery/config.py
```

Ensure no logging of raw URLs.

### Step 7 — Tests quality check

Verify presence and quality of required tests:
- `test_load_delivery_config_valid`
- `test_load_delivery_config_missing_required_key`
- `test_resolve_webhook_url_set`
- `test_resolve_webhook_url_missing`
- `test_teams_enabled_true`
- `test_teams_enabled_flag_false`
- `test_teams_enabled_no_url`
- `test_slack_enabled_same_logic`

---

## Required Output Format

1. Verdict (`PASS | CHANGES REQUIRED | BLOCKED`)
2. What's Correct
3. Problems Found (severity, file:line, exact problem, why it matters)
4. Missing or Weak Tests
5. Scope Violations
6. Acceptance Criteria Check (PASS/FAIL for each criterion)
7. Exact Fixes Required
8. Final Recommendation (`approve | request changes | block`)

---

## Acceptance Criteria Check List

- [ ] `config/delivery.yaml` created with required top-level sections
- [ ] `load_delivery_config()` implemented
- [ ] `resolve_webhook_url()` implemented correctly
- [ ] `teams_enabled()` logic correct
- [ ] `slack_enabled()` logic correct
- [ ] env placeholders used for webhook URLs
- [ ] no webhook URL logging at info level
- [ ] only allowed files modified
- [ ] required tests present and meaningful
- [ ] tests pass
- [ ] ruff clean
