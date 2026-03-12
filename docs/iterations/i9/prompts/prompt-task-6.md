# Task Prompt — I9-6: Failure Alerting Path

---

## Context

You are implementing **task I9-6** of Iteration 9.
This task introduces delivery alerts for failure/degraded states.

---

## Architecture Rules (Non-Negotiable)

| # | Rule |
|---|------|
| 1 | Alerts are delivery-level concerns, not pipeline-level analytics changes. |
| 2 | Alert dispatch must never crash CLI flow. |
| 3 | Distinguish three scenarios: llm fallback, pipeline error, no-new-file. |
| 4 | Keep payloads minimal and deterministic. |
| 5 | Open draft PR first. |

---

## Step 0 — Branch Setup

```bash
git checkout feature/iteration-9
git pull origin feature/iteration-9

git checkout -b feature/i9-6-failure-alerting
git push -u origin feature/i9-6-failure-alerting

gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-6-failure-alerting \
  --title "I9-6: failure alerting path" \
  --body "Work in progress." \
  --draft

pytest --tb=short -q
ruff check .
```

---

## Objective

Implement I9-6 from tasks.md with three alert payload paths:
- LLM fallback alert rendering path
- Pipeline error alert
- No-new-file detected alert

---

## Allowed Files

```text
src/wbsb/delivery/alerts.py
src/wbsb/scheduler/watcher.py
src/wbsb/cli.py
tests/test_delivery_alerts.py
```

## Forbidden Files

```text
src/wbsb/pipeline.py
src/wbsb/delivery/teams.py
src/wbsb/delivery/slack.py
```

---

## Required Public API

In `src/wbsb/delivery/alerts.py`:

```python
def build_pipeline_error_alert(error: str, run_id: str | None) -> dict: ...
def build_no_file_alert(watch_directory: str) -> dict: ...
def send_alert(alert: dict, delivery_cfg: dict) -> list[DeliveryResult]: ...
```

`send_alert` must never raise.

---

## Execution Workflow

1. Read I9-6 section in tasks.md.
2. Implement alert payload builders with required fields/text.
3. Implement `send_alert` dispatch to enabled targets, capturing failures in `DeliveryResult`.
4. Wire CLI/scheduler paths so each scenario is visible in stdout and can dispatch alert.
5. Add required tests.
6. Run:

```bash
pytest --tb=short -q
ruff check .
```

7. Verify allowed-file scope with git diff.

---

## Test Requirements

Implement required tests:
- `test_pipeline_error_alert_structure`
- `test_no_file_alert_structure`
- `test_send_alert_non_raising`
- `test_send_alert_skipped_when_disabled`

---

## Acceptance Criteria

- All three alert scenarios implemented.
- Alert payloads match task contract.
- Alert dispatch never raises.
- CLI prints visible warning for alert scenarios.
- Tests and ruff clean.

---

## Completion Checklist

- [ ] Draft PR opened first
- [ ] Only allowed files changed
- [ ] Alert API implemented
- [ ] Three scenarios handled correctly
- [ ] Required tests added
- [ ] `pytest` passes
- [ ] `ruff check .` passes
