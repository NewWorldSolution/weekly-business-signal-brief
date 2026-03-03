# CLAUDE.md — Weekly Business Signal Brief (WBSB)

## Project Purpose

WBSB is a **deterministic** weekly analytics engine for appointment-based service businesses. It ingests weekly operational data (CSV/XLSX), validates it, computes standardised business metrics, compares current vs previous week, evaluates rule-based signals, and renders a structured business brief.

LLM is **optional** and used only for rendering. The core pipeline is always deterministic.

---

## Architecture

```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → Artifacts
```

| # | Module | Package | Responsibility |
|---|--------|---------|---------------|
| 1 | Ingestion | `wbsb.ingest.loader` | Load CSV/XLSX → pandas DataFrame |
| 2 | Validation | `wbsb.validate.schema` | Enforce required columns, coerce types, emit AuditEvents |
| 3 | Metrics | `wbsb.metrics.calculate` | Deterministic metric calculations via `safe_div` |
| 4 | Delta | `wbsb.compare.delta` | Absolute and percentage change per metric |
| 5 | Rules | `wbsb.rules.engine` | Evaluate config-driven YAML rules + guardrails |
| 6 | Findings | `wbsb.findings.build` | Assemble Pydantic `Findings` model |
| 7 | Rendering | `wbsb.render.template` / `.llm` | Jinja2 template (default) or LLM narrative |
| 8 | CLI | `wbsb.cli` | Typer CLI: `wbsb run`, `wbsb version` |

Rules are fully config-driven via `config/rules.yaml`. No hardcoded thresholds in code.

---

## Core Design Principles

- **Deterministic first** — pipeline output must be reproducible from the same inputs
- **Config-driven rules** — all thresholds live in `config/rules.yaml`
- **Auditability** — SHA-256 hashes on input file and config; structured AuditEvent trail throughout
- **No silent failure** — validation must surface every data quality issue explicitly
- **Separation of concerns** — metrics, rule evaluation, and rendering are strictly isolated
- **Test coverage** — pytest; all logic must be testable without side effects
- **Lint clean** — ruff; code must pass before commit

---

## What You Must NOT Do

- Do not rewrite the pipeline architecture without explicit instruction
- Do not hardcode thresholds — all thresholds belong in `config/rules.yaml`
- Do not remove or weaken validation guards in `wbsb.validate.schema`
- Do not mix rendering logic into rules or metrics modules
- Do not remove or bypass the audit trail (`AuditEvent`)
- Do not add silent data coercion without emitting a corresponding `AuditEvent`

---

## What You May Help With

- Writing new rules (add to `config/rules.yaml` + update `rules/engine.py` if needed)
- Improving validation robustness
- Improving hybrid rule logic
- Adding or improving tests (pytest)
- Refactoring for clarity within the existing module boundaries
- Improving dataset resilience
- Safe performance improvements

---

## Key Files

| File | Purpose |
|------|---------|
| `src/wbsb/validate/schema.py` | `REQUIRED_COLUMNS`, `FLOAT_COLUMNS`, `INT_COLUMNS`; derives `ad_spend_total`, `leads_total`, `new_clients_total`, `net_revenue` |
| `src/wbsb/metrics/calculate.py` | All 16 metric definitions; use `safe_div` for every division |
| `src/wbsb/rules/engine.py` | Rule condition types and guardrail logic |
| `config/rules.yaml` | All rule thresholds and guardrail values |
| `src/wbsb/domain/models.py` | `AuditEvent`, `Signal`, `Findings`, `MetricResult` Pydantic models |
| `src/wbsb/pipeline.py` | Orchestrator; generates `run_id`, calls every stage in order |
| `examples/datasets/` | 10 synthetic test datasets covering clean, edge-case, and anomaly scenarios |

---

## Rules Engine Reference

**Condition types:**

| Type | Meaning |
|------|---------|
| `delta_pct_lte` | Week-over-week % change ≤ threshold |
| `delta_pct_gte` | Week-over-week % change ≥ threshold |
| `absolute_lt` | Absolute metric value < threshold |
| `absolute_gt` | Absolute metric value > threshold |
| `hybrid_delta_pct_lte` | % change if volume ≥ min; else absolute change |

**Guardrail keys:**

| Key | Skips rule when … |
|-----|------------------|
| `requires_min_prev_net_revenue` | Previous week revenue below threshold |
| `requires_prev_leads_paid_gte` | Previous week paid leads below threshold |
| `requires_prev_new_clients_paid_gte` | Previous week new paid clients below threshold |
| `requires_prev_bookings_total_gte` | Previous week bookings below threshold |
| `requires_current_net_revenue_gt` | Current week revenue below threshold |

---

## Environment

- Python 3.11
- Key dependencies: `pandas`, `pydantic`, `typer`, `jinja2`, `PyYAML`
- Linter: `ruff`
- Tests: `pytest`

---

## Current State

- Deterministic pipeline: functional
- Tests: passing
- Ruff: clean
- GitHub Actions: configured (CI + Claude PR assistant)

---

## Execution Discipline (Non-Negotiable)

- Work is executed one task at a time (one task per PR unless explicitly approved).
- Use Plan Mode for any change that touches multiple files or changes behavior.
- Before editing: confirm which files will be modified.
- Only modify files explicitly allowed by the current task (see TASKS.md or the user prompt).
- If additional files seem necessary, STOP and ask before changing them.
- After implementing: run `pytest` and `ruff check .` and report results.

## Determinism & Stability Rules

- Do not introduce randomness (unless seeded and explicitly approved).
- Preserve stable ordering:
  - Signals must be sorted by `rule_id`.
  - Metrics must be emitted in a stable, deterministic order.
- “Current time” and run IDs may exist only in RunMeta/Manifest; they must not affect computed metrics or rule firing.

## Error Handling Policy

- Never use `except: pass`.
- Do not silently return empty structures for missing required data.
- For user-input/data issues: raise clear exceptions (ValueError) with actionable messages.
- For IO failures (export/logging): log and raise; never pretend success.

## Repo Workflow Conventions

- Avoid unrelated refactors or formatting-only changes unless requested.
- When changing behavior: add/adjust tests to cover the new behavior.
- Keep commits small and descriptive; do not mix unrelated changes.

## Task Source of Truth

- TASKS.md defines the current iteration tasks and allowed-file boundaries.
- CLAUDE.md defines permanent architecture and working rules.
