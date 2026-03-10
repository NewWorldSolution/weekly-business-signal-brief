# Iteration-2-Tasks.md — WBSB

## Iteration 2 — Output Clarity & Integration-Readiness

**Goal:** Transform WBSB output from developer-oriented to decision-ready while preserving
the deterministic core architecture.

**Theme:** Clarity · Prioritization · Explainability · Integration-Readiness

---

## Non-Negotiable Constraints

- Deterministic-first. Same input → same output, always.
- No cross-layer leakage. Rules engine must NOT import or depend on the metrics registry.
  All number formatting must occur in the render layer (template).
- No currency symbol hardcoding. Currency format = thousands-separated integer only.
- Canonical taxonomy must be consistent across metrics and signals (see below).
- `Findings.schema_version` must be bumped from `"1.0"` to `"1.1"`.
- All tests must pass after every task.
- Ruff must be clean after every task.
- One task per PR unless explicitly approved otherwise.

---

## Canonical Taxonomy

Use these identifiers everywhere (lowercase internally, Title Case in template display):

| Internal ID       | Display Label     |
|-------------------|-------------------|
| `acquisition`     | Acquisition       |
| `operations`      | Operations        |
| `revenue`         | Revenue           |
| `financial_health`| Financial Health  |

Do not introduce aliases or alternative names.

---

## Dependency Order

```
Task 1 (Signal Model & Rules)
    └── Task 3 (Rendering) depends on Task 1
Task 2 (Metric Registry)
    └── Task 3 (Rendering) depends on Task 2
Task 4 (Manifest) — independent, no upstream dependency
```

Task 1 and Task 2 may be worked in parallel.
Task 3 must wait for both Task 1 and Task 2 to be merged.
Task 4 may be worked at any point.

---

## Task 1 — Signal Model & Rules Enhancements

**Priority:** HIGH — other tasks depend on this

### Problem

- Signals expose raw `metric_id` literals, not human-readable names.
- All signals are equal in weight; sorted only alphabetically by `rule_id`.
- No domain grouping (acquisition / operations / revenue / financial_health).
- `schema_version` is stale at `"1.0"`.

### Required Changes

#### A. `config/rules.yaml`

Add three fields to every rule entry:

| Field      | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| `label`    | string  | Human-readable name for the signal                       |
| `category` | string  | Canonical taxonomy identifier (see table above)          |
| `priority` | integer | Urgency weight 1–10 (see rubric below)                   |

**Priority rubric:**

| Score | Meaning                                        |
|-------|------------------------------------------------|
| 10    | Threatens revenue or contribution margin       |
| 8     | Major efficiency collapse or volume loss       |
| 6     | Operational leakage                            |
| 4     | Early warning, watch signal                    |
| 2     | Informational, positive or context signal      |

**Assignments per rule:**

| Rule | Label                             | Category         | Priority |
|------|-----------------------------------|------------------|----------|
| A1   | Revenue Decline                   | revenue          | 10       |
| A2   | Revenue Surge                     | revenue          | 2        |
| B1   | Customer Acquisition Cost Rising  | acquisition      | 8        |
| C1   | Paid Lead Conversion Falling      | acquisition      | 6        |
| D1   | Show Rate Declining               | operations       | 6        |
| E1   | Cancellation Rate Rising          | operations       | 6        |
| F1   | Bookings Volume Falling           | operations       | 8        |
| G1   | New Client Acquisition Falling    | acquisition      | 8        |
| H1   | Gross Margin Below Threshold      | financial_health | 10       |
| H2   | Marketing Spend Overweight        | financial_health | 8        |
| H3   | Contribution Margin Declining     | financial_health | 10       |

#### B. `src/wbsb/domain/models.py`

Extend `Signal` with three new fields, all with defaults for backward compatibility:

```python
label: str = ""
category: str = ""
priority: int = 0
```

Add `threshold` to the evidence dict contract (doc comment only — evidence is already
`dict[str, Any]`; no type change needed).

Bump `Findings.schema_version` default from `"1.0"` to `"1.1"`.

#### C. `src/wbsb/rules/engine.py`

1. Propagate `label`, `category`, `priority` from each rule config dict to the fired
   `Signal`. If a rule in config omits any of these fields, fall back to `""`, `""`, `0`
   respectively — do not raise.

2. Add `threshold` (or `threshold_pct` / `threshold_abs` for hybrid) to the `evidence`
   dict so the render layer can display it without re-reading config.

3. Update sorting key from `lambda s: s.rule_id` to:
   ```python
   lambda s: (0 if s.severity == "WARN" else 1, -s.priority, s.rule_id)
   ```
   WARN before INFO → higher priority first → rule_id as stable tiebreaker.

#### D. `tests/test_e2e_pipeline.py`

Update assertion:
```python
assert findings["schema_version"] == "1.1"   # was "1.0"
```

#### E. `tests/test_rules.py`

- Existing tests: do not break — `BASE_CONFIG` has no `label`/`category`/`priority`,
  so defaults apply. Signal construction must not raise with missing fields.
- Update `test_signals_sorted_by_rule_id`: rename to
  `test_signals_sorted_by_severity_priority_rule_id` and update the assertion to verify
  the complete sort semantics, not just alphabetical `rule_id`.
- Add one new test: construct two signals with different severities and priorities,
  assert WARN appears before INFO and higher priority WARN appears before lower priority WARN.

### Allowed Files

- `config/rules.yaml`
- `src/wbsb/domain/models.py`
- `src/wbsb/rules/engine.py`
- `tests/test_rules.py`
- `tests/test_e2e_pipeline.py`

### Backward Compatibility

All new `Signal` fields have defaults. Existing tests that construct `Signal` objects
without `label`, `category`, or `priority` will continue to work without modification.

### Acceptance Criteria

- All 11 rules in `rules.yaml` have `label`, `category`, `priority`.
- Fired signals carry `label`, `category`, `priority` from their rule config.
- Sort order is `(severity DESC, priority DESC, rule_id)`.
- `Findings.schema_version` is `"1.1"`.
- All existing tests pass; updated and new signal sort tests pass.
- Ruff clean.

---

## Task 2 — Metric Registry Enhancements (Bundled)

**Priority:** HIGH — Task 3 (rendering) depends on this

### Problem

- `MetricDef` carries no display metadata beyond `name` and `unit`.
- Metrics render as raw floats with no unit awareness.
- Metrics table is flat and alphabetical — no business grouping.
- `MetricResult` (the domain transfer object) does not carry formatting or grouping
  metadata, so the template cannot apply unit-aware formatting without re-importing
  the registry.

### Required Changes

#### A. `src/wbsb/metrics/registry.py`

Extend `MetricDef` dataclass with four new fields:

| Field           | Type  | Description                                           |
|-----------------|-------|-------------------------------------------------------|
| `format_hint`   | str   | `currency` / `percent` / `integer` / `decimal`        |
| `category`      | str   | Canonical taxonomy identifier                         |
| `category_order`| int   | Sort order for the category group (1 = first)         |
| `display_order` | int   | Sort order within the category                        |

**Assignments per metric:**

| Metric ID                    | format_hint | category         | category_order | display_order |
|------------------------------|-------------|------------------|----------------|---------------|
| `net_revenue`                | currency    | revenue          | 1              | 1             |
| `new_client_ratio`           | percent     | revenue          | 1              | 2             |
| `cac_paid`                   | currency    | acquisition      | 2              | 1             |
| `cost_per_paid_lead`         | currency    | acquisition      | 2              | 2             |
| `paid_lead_to_client`        | percent     | acquisition      | 2              | 3             |
| `paid_share_new_clients`     | percent     | acquisition      | 2              | 4             |
| `new_clients_total`          | integer     | acquisition      | 2              | 5             |
| `show_rate`                  | percent     | operations       | 3              | 1             |
| `cancel_rate`                | percent     | operations       | 3              | 2             |
| `rev_per_completed_appt`     | currency    | operations       | 3              | 3             |
| `bookings_total`             | integer     | operations       | 3              | 4             |
| `gross_margin`               | percent     | financial_health | 4              | 1             |
| `marketing_pct_revenue`      | percent     | financial_health | 4              | 2             |
| `contribution_after_marketing`| currency   | financial_health | 4              | 3             |

#### B. `src/wbsb/domain/models.py`

Extend `MetricResult` with four new fields, all with defaults:

```python
format_hint: str = "decimal"
category: str = ""
category_order: int = 0
display_order: int = 0
```

#### C. `src/wbsb/findings/build.py`

1. Propagate the four new fields from `MetricDef` when constructing each `MetricResult`.

2. Change the sort key for `metric_results` construction from:
   ```python
   sorted(METRIC_REGISTRY_BY_ID.values(), key=lambda m: m.id)
   ```
   to:
   ```python
   sorted(METRIC_REGISTRY_BY_ID.values(), key=lambda m: (m.category_order, m.display_order))
   ```

### Tests

Add `tests/test_registry.py`:

- Assert every `MetricDef` in `METRIC_REGISTRY` has a non-empty `format_hint` from
  the valid set `{"currency", "percent", "integer", "decimal"}`.
- Assert every `MetricDef` has a non-empty `category` matching the canonical taxonomy.
- Assert `category_order` and `display_order` are positive integers.
- Assert no two metrics share the same `(category, display_order)` pair.

### Allowed Files

- `src/wbsb/metrics/registry.py`
- `src/wbsb/domain/models.py`
- `src/wbsb/findings/build.py`
- `tests/test_registry.py`

### Backward Compatibility

All new `MetricResult` fields have defaults. Existing tests that construct `MetricResult`
objects directly will not require changes.

### Acceptance Criteria

- All 14 `MetricDef` entries have correct `format_hint`, `category`, `category_order`,
  `display_order`.
- `MetricResult` objects carry the four new fields when built via `build_findings`.
- Metrics are ordered by `(category_order, display_order)` in `findings.metrics`.
- New registry tests pass.
- All existing tests pass.
- Ruff clean.

---

## Task 3 — Rendering Layer Upgrades

**Priority:** HIGH (depends on Task 1 and Task 2 being merged)

### Problem

- Brief has no at-a-glance summary — opens directly into a flat signal list.
- All numeric values render as raw floats regardless of unit.
- Metrics table is unsorted and unrouped.
- Audit events are buried at the bottom with no callout.
- Signal headings expose `metric_id` literals.

### Required Changes

All changes are confined to `src/wbsb/render/template.md.j2`.
No Python logic changes. No new Jinja2 filters requiring Python code.
Standard Jinja2 constructs only (`if`, `for`, `groupby`, `namespace`, arithmetic).

#### A. Executive Summary Block (top of brief)

Replace the current plain header with a structured "Weekly Priorities" section:

```
## Weekly Priorities

- N WARN signals
- N INFO signals
- Top issue: <label of first WARN by sort order, or "No critical alerts this week">
```

Derive counts and top signal from `findings.signals` (already sorted by the engine).

#### B. Unit-Aware Formatting

Implement a Jinja2 macro `format_value(value, hint)` in the template:

| `hint`      | Format rule                                       | Example     |
|-------------|---------------------------------------------------|-------------|
| `currency`  | Thousands-separated integer, no symbol            | `12,450`    |
| `percent`   | 1 decimal place + `%`                             | `68.3%`     |
| `integer`   | Integer with no decimals                          | `124`       |
| `decimal`   | 1 decimal place                                   | `142.3`     |
| `None`      | Render as `—`                                     | `—`         |

Use this macro everywhere a metric value, delta, or threshold is displayed.
Delta % values come from `signal.evidence.delta_pct` and metric `delta_pct` fields
(already stored as decimals, e.g. `-0.185` for −18.5%).

#### C. Signal Section Restructure

- Group signals by `signal.category` using Jinja2 `groupby`.
- Display category heading in Title Case using the canonical display label mapping.
- Within each group, signals are already sorted by the engine; preserve that order.
- Signal heading format: `### <severity> — <signal.label> (Rule <signal.rule_id>)`
  Do not expose `metric_id` in the heading.
- Evidence block: use `format_value` macro with the metric's `format_hint` for
  current, previous, delta_abs, delta_pct, and threshold values.

To look up `format_hint` for formatting evidence values in a signal, iterate
`findings.metrics` to find the matching `metric_id`. The `format_hint` is available
on each `MetricResult`.

#### D. Data Quality Callout

Add a "Data Quality" section immediately above the Key Metrics table:

- If `findings.audit` is empty: `No data quality issues detected.`
- If non-empty: `⚠️ N validation/coercion events detected.` followed by a count
  breakdown by `event_type`.

Keep the existing raw audit list at the bottom of the brief unchanged.

#### E. Metric Table Restructure

- Group the metric table by category using Jinja2 `groupby` on `m.category`.
- Sort within groups by `m.display_order` (already set on `MetricResult`).
- Render a sub-header row for each category group (Title Case display label).
- Apply `format_value` macro for `current`, `previous`, and `delta_pct` columns.
- `delta_pct` hint is always `percent` regardless of metric type.

### Allowed Files

- `src/wbsb/render/template.md.j2`

### Tests

No new unit tests required for this task. The e2e test already asserts `brief.md`
exists and the pipeline completes. Manual verification of brief output against a
synthetic dataset is sufficient for this task.

Optionally add a smoke assertion to `tests/test_e2e_pipeline.py`:
- Assert `brief.md` contains the string `"Weekly Priorities"`.
- Assert `brief.md` contains the string `"Revenue"` (category heading).

### Acceptance Criteria

- Brief opens with a "Weekly Priorities" block showing warn/info counts and top issue.
- All numeric values are unit-aware formatted (no raw `0.6832` or `12450.0`).
- Signals are grouped by category with Title Case headings.
- Signal headings show human-readable label, not `metric_id`.
- Evidence values include formatted threshold.
- "Data Quality" callout appears above metrics when audit events exist.
- Metrics table is grouped by category and sorted by `display_order`.
- All existing tests pass.
- Ruff clean.

---

## Task 4 — Manifest Enrichment

**Priority:** MEDIUM — independent, no upstream dependency

### Problem

The manifest captures hashes and timing but no summary statistics. A dashboard or
monitoring tool consuming `manifest.json` must parse the full `findings.json` to
retrieve signal counts or render mode — defeating the purpose of a lightweight manifest.

### Required Changes

#### A. `src/wbsb/domain/models.py`

Extend `Manifest` with five new fields, all with defaults:

```python
signals_warn_count: int = 0
signals_info_count: int = 0
audit_events_count: int = 0
render_mode: str = "off"
config_version: str = ""
```

#### B. `src/wbsb/export/write.py`

Update `write_artifacts` signature to accept:

```python
signals_warn_count: int
signals_info_count: int
audit_events_count: int
render_mode: str
config_version: str
```

Populate the five new `Manifest` fields from these arguments.

#### C. `src/wbsb/pipeline.py`

Compute and pass the five values to `write_artifacts`:

- `signals_warn_count` = `len([s for s in findings.signals if s.severity == "WARN"])`
- `signals_info_count` = `len([s for s in findings.signals if s.severity == "INFO"])`
- `audit_events_count` = `len(findings.audit)`
- `render_mode` = `llm_mode` (already in scope)
- `config_version` = `raw_config.get("config_version", "")` (already in scope)

### Tests

Update `tests/test_e2e_pipeline.py`:

```python
manifest = json.loads((run_dir / "manifest.json").read_text())
assert "signals_warn_count" in manifest
assert "signals_info_count" in manifest
assert "audit_events_count" in manifest
assert manifest["render_mode"] == "off"
assert isinstance(manifest["config_version"], str)
```

### Allowed Files

- `src/wbsb/domain/models.py`
- `src/wbsb/export/write.py`
- `src/wbsb/pipeline.py`
- `tests/test_e2e_pipeline.py`

### Backward Compatibility

All new `Manifest` fields have defaults. No breaking change to `findings.json`.
`manifest.json` gains new fields — additive only.

### Acceptance Criteria

- `manifest.json` contains all five new fields.
- `signals_warn_count` + `signals_info_count` equals total signal count in findings.
- `render_mode` matches the `--llm-mode` flag used for the run.
- `config_version` matches the value in `rules.yaml`.
- Updated e2e test assertions pass.
- All existing tests pass.
- Ruff clean.

---

## Execution Workflow

For each task:

1. Create feature branch: `feat/iteration-2-task-N-<short-description>`
2. Use Plan Mode — all tasks touch multiple files.
3. Confirm allowed files match the list above before writing any code.
4. Implement changes.
5. Run:
   ```
   pytest
   ruff check .
   ```
6. Commit with a clear, scoped message.
7. Push and open PR.
8. Merge after review.

Never combine multiple tasks in a single PR unless explicitly approved.

---

## Iteration 2 — Definition of Done

Iteration 2 is complete when:

1. Signals are grouped by category and sorted by `(severity DESC, priority DESC, rule_id)`.
2. All numeric values in the brief are unit-aware formatted.
3. Brief opens with an Executive Summary showing warn/info counts and top issue.
4. Data quality issues are visible before the metrics section.
5. Manifest exposes `signals_warn_count`, `signals_info_count`, `audit_events_count`,
   `render_mode`, `config_version`.
6. `Findings.schema_version` is `"1.1"`.
7. All tests pass.
8. Ruff is clean.
9. `main` branch is stable and CI is passing.
