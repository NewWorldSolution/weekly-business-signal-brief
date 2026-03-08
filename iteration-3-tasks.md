# Iteration 3 Tasks — WBSB
## Output Quality & Render Context Architecture

**Goal:** Fix threshold formatting correctness, eliminate developer-facing language
from the brief, introduce a deterministic presentation preparation layer, and position
the system for clean LLM narrative integration in Iteration 4.

**Theme:** Readability · Correctness · Separation of Concerns · LLM Readiness

---

## Architectural Review Response

Before implementation begins, six architectural risks were raised by a second review.
Each risk was evaluated and resolved as follows. These decisions are binding for all
Iteration 3 tasks.

---

### Risk 1 — Metric Name Duplication · ACCEPTED — Plan Revised

**Original plan:** Add `metric_name` to every rule in `rules.yaml` so the engine can
use human-readable names in explanation strings.

**Problem with this approach:** It creates two sources of truth for metric display names:

```
Source A: src/wbsb/metrics/registry.py → MetricDef.name  (e.g. "Net Revenue")
Source B: config/rules.yaml → metric_name                (e.g. "Net Revenue" or "Revenue"?)
```

These will silently diverge over time, producing inconsistent output between
explanation strings and metric table headers with no compile-time or runtime error.

**Decision:** Do not add `metric_name` to `rules.yaml`. The context layer (`render/context.py`)
already has access to `findings.metrics`, which carries `MetricResult.name` derived from
the registry. The context layer uses `metric.name` to build narratives. Zero duplication.

**Impact:** `rules.yaml` requires no changes in Iteration 3.

---

### Risk 2 — Engine Producing Presentation Text · ACCEPTED — Plan Revised

**Original plan:** Rewrite all explanation f-strings in `engine.py` to produce
business-readable sentences ("Net Revenue declined 25.8% week-over-week.").

**Problem with this approach:** The engine's responsibility is detection and evidence
collection, not presentation. If Iteration 4 introduces LLM narrative generation, the
engine's explanation strings will be bypassed — making the Iteration 3 rewriting work
wasted. Additionally, the engine cannot format thresholds correctly without registry
access (it doesn't know if a metric is `currency` or `percent`).

**Decision:**
- `signal.explanation` is retained as a **technical audit string** for `findings.json`.
  It is NOT the rendering surface for the brief.
- The context layer generates a `narrative` field per signal for template use.
- The template renders `sc.narrative`, never `signal.explanation` directly.
- Engine explanation strings are left structurally unchanged (only `condition`
  propagation is added — see Task 1).

**Impact:** Engine.py requires only one additive line. No explanation rewriting.

---

### Risk 3 — Schema Versioning · ACCEPTED

Adding `condition: str = ""` to `Signal` is an additive change, but it alters the
`findings.json` schema (Signal objects are serialised as part of Findings).

**Decision:** Bump `Findings.schema_version` from `"1.1"` to `"1.2"`.

This follows the same pattern as the `"1.0"→"1.1"` bump in Iteration 2, which was
triggered by additive field additions to Signal and MetricResult.

**Impact:** `models.py` version bump. `test_e2e_pipeline.py` assertion updated.

---

### Risk 4 — Hybrid Threshold Assumptions · NOTED — Documented in Code

The context layer will assume:
- `threshold_pct` → always `"percent"` format hint
- `threshold_abs` → always `"integer"` format hint

This is correct for the current rule set (F1, G1 — both measure integer counts).
It is an implicit policy, not a structural guarantee.

**Decision:** Document this assumption with named constants in `context.py`
(`_HYBRID_ABS_HINT = "integer"`) and note it explicitly in acceptance criteria.
If a future hybrid rule uses a non-integer absolute threshold, this constant is the
single place to update.

---

### Risk 5 — Template Responsibility Boundaries · CONFIRMED

**Principle (now explicit):**

> The template is responsible for **formatting and simple grouping only**.
> It must not compute business logic, perform lookups, determine threshold semantics,
> or assemble summaries. All such work belongs in the context layer.

After Iteration 3 changes, the template will:
- Format numbers via `format_value` macro ✓
- Group pre-built `signal_contexts` by category via `groupby` ✓
- Display pre-computed counts, narratives, and category lists ✓

It will not:
- Run `selectattr` to find metrics per signal ✗ (moved to context)
- Compute severity counts ✗ (moved to context)
- Determine threshold format hints ✗ (moved to context)

---

### Risk 6 — LLM Readiness for Iteration 4 · ACCEPTED — Plan Extended

The context layer will produce `narrative_inputs` per signal: a structured dict of
raw (unformatted) values an LLM can consume in Iteration 4.

In Iteration 4, `render_llm()` can receive `signal_contexts` with their `narrative_inputs`
and generate richer narratives without modifying the pipeline. The deterministic
template path continues to use `sc.narrative` (the pre-built human-readable string).

**Impact:** Each `signal_context` dict gains a `narrative_inputs` key. No pipeline changes.

---

## Part 1 — Repository Architecture Audit

### 1.1 Module Inventory

```
src/wbsb/
├── cli.py                    Typer CLI; wbsb run / wbsb version
├── pipeline.py               Top-level orchestrator; calls every stage in order
├── domain/
│   └── models.py             Pydantic models: AuditEvent, Signal, Findings, Manifest, …
├── ingest/
│   └── loader.py             CSV/XLSX → pandas DataFrame; normalises week_start_date
├── validate/
│   └── schema.py             Column validation, type coercion, derived columns; emits AuditEvents
├── metrics/
│   ├── calculate.py          Deterministic metric calculations; safe_div for all divisions
│   └── registry.py           MetricDef dataclass; METRIC_REGISTRY list; METRIC_REGISTRY_BY_ID
├── compare/
│   └── delta.py              compute_delta(current, previous) → (delta_abs, delta_pct)
├── rules/
│   └── engine.py             evaluate_rules(); constructs Signal objects with evidence + explanation
├── findings/
│   └── build.py              build_findings(); assembles Findings from metrics + signals + audit
├── render/
│   ├── template.py           render_template(findings) → Jinja2 render; passes raw Findings
│   ├── template.md.j2        Jinja2 template; ALL formatting logic lives here
│   └── llm.py                Stub for LLM rendering path (not implemented)
├── export/
│   └── write.py              write_artifacts(); writes findings.json, brief.md, manifest.json
├── observability/
│   └── logging.py            JsonlHandler + StructLogger; structured JSONL to logs.jsonl
└── utils/
    ├── dates.py              resolve_target_week(), week_end_date()
    ├── hash.py               file_sha256(), yaml_sha256(), git_commit_hash(), tool_versions()
    └── math.py               safe_div(numerator, denominator) → float | None
```

---

### 1.2 Pipeline Data Flow

```
CLI (cli.py)
  └── pipeline.execute(input_path, output_dir, llm_mode, config_path, target_week)
        │
        ├── file_sha256(input_path)                     # input audit hash
        ├── yaml.safe_load(config_path) → raw_config    # YAML parsed once
        ├── yaml_sha256(raw_config)                     # config audit hash
        │
        ├── load_data(input_path)          → DataFrame  # ingest/loader.py
        ├── validate_dataframe(df)         → (audit_events, df)   # validate/schema.py
        │     Derives: ad_spend_total, leads_total, new_clients_total, net_revenue
        │
        ├── resolve_target_week(df, target_week)  → (week_start, prev_week_start)
        │
        ├── build_findings(df, week_start, …, raw_config, run_config, audit_events)
        │     │   → Findings
        │     ├── _get_row(df, week_start)         → curr_row dict
        │     ├── _get_row(df, prev_week_start)    → prev_row dict
        │     ├── compute_metrics(curr_row)         → curr_metrics dict
        │     ├── compute_metrics(prev_row)         → prev_metrics dict
        │     ├── compute_delta(curr, prev)         → (delta_abs, delta_pct) per metric_id
        │     ├── reliability = "low" if prev_net_revenue < min_prev_net_revenue else "ok"
        │     ├── Build MetricResult list (sorted by category_order, display_order)
        │     ├── evaluate_rules(curr_metrics, prev_metrics, deltas, raw_config, …)
        │     │     → list[Signal] (sorted by severity DESC, priority DESC, rule_id)
        │     └── Assemble Findings(run=RunMeta, periods=Periods, metrics=…, signals=…, audit=…)
        │
        ├── render_template(findings)      → brief_md   # render/template.py
        │     └── Jinja2 env.get_template("template.md.j2")
        │           template.render(findings=findings)
        │           [template does groupby, selectattr, format_value inline]
        │
        └── write_artifacts(run_dir, findings, brief_md, …)
              Writes: findings.json, brief.md, manifest.json
```

---

### 1.3 Signal Creation Flow

`evaluate_rules()` in `rules/engine.py`:

1. Iterates over every rule in `raw_config["rules"]`.
2. Applies guard checks (min_prev_net_revenue, prev_leads_paid, volume, etc.).
3. Evaluates one of five condition types:
   - `delta_pct_lte` — fires when `delta_pct ≤ threshold`
   - `delta_pct_gte` — fires when `delta_pct ≥ threshold`
   - `absolute_lt`   — fires when `current_val < threshold`
   - `absolute_gt`   — fires when `current_val > threshold`
   - `hybrid_delta_pct_lte` — pct mode if volume ≥ volume_threshold; abs mode otherwise
4. Constructs `Signal` with `evidence`, `explanation` (technical string), `label`,
   `category`, `priority` from rule config.
5. Returns signals sorted by `(0 if WARN else 1, -priority, rule_id)`.

**Critical observation:** The engine does NOT persist the `condition` type on the Signal.
It is consumed at evaluation time and discarded. Task 1 fixes this.

---

### 1.4 Findings Assembly

`build_findings()` in `findings/build.py`:

- Imports `METRIC_REGISTRY_BY_ID` from `metrics/registry.py`.
- Builds `MetricResult` objects joining computed values with registry metadata.
- Calls `evaluate_rules()` — the engine receives raw dicts only, no registry access.
- Wraps everything in a `Findings` Pydantic model.

**Non-negotiable constraint:** The engine (`rules/engine.py`) must never import
from `wbsb.metrics.registry`. The context layer may import it freely.

---

### 1.5 Rendering Context (Current State)

`render_template()` passes the raw `Findings` object directly to Jinja2 as a single
variable. The template performs all data transformation inline:

| Concern | Current implementation | Classification |
|---|---|---|
| Metric format lookup per signal | `selectattr('id', '==', metric_id) \| first` | Business logic — wrong layer |
| Signal filtering by severity | `selectattr('severity', '==', 'WARN') \| list` | Business logic — wrong layer |
| Category display label mapping | Hardcoded dict inside the template | Config — wrong layer |
| Executive summary computation | `warn_signals[0]`, length counts | Business logic — wrong layer |
| Number formatting | `format_value(value, hint)` macro | Formatting — correct layer |
| Category grouping | `groupby('category')` | Simple grouping — acceptable |

---

## Part 2 — Identified Problems

### 2.1 Metric ID Leakage in Rendered Brief

**Location:** `template.md.j2`, line 34: `{{ signal.explanation }}`

The template renders `signal.explanation` as the primary signal narrative. These strings
are built in the engine with raw `metric_id` identifiers:

```
"net_revenue changed -25.8% (threshold: ≤-15.0%)"
"gross_margin is 0.4750 (threshold: <0.5)"
"bookings_total dropped by 20 (absolute threshold: ≤-3, low-volume mode)"
```

The `explanation` field in `Signal` was designed as an audit string for `findings.json`.
It was never intended to be the rendering surface for a business brief.

**Root cause:** There is no separation between the technical audit record and the
human-facing narrative. The template uses them interchangeably.

---

### 2.2 Threshold Formatting Inconsistency (Bug)

**Location:** `template.md.j2`, evidence block.

The template formats the `threshold` evidence value using the metric's `format_hint`:

```jinja2
{%- set hint = metric.format_hint if metric is defined else 'decimal' %}
- Threshold: {{ format_value(signal.evidence.threshold, hint) }}
```

**The bug:** For `delta_pct_lte`/`delta_pct_gte` conditions, `threshold` is a fractional
percentage change (e.g., `-0.15` means −15%). But `hint` is the metric's own unit —
which may be `currency` or `integer`.

| Rule | Condition | Metric | format_hint | threshold | Rendered | Correct |
|---|---|---|---|---|---|---|
| A1 | delta_pct_lte | net_revenue | currency | -0.15 | `0` | `-15.0%` |
| B1 | delta_pct_gte | cac_paid | currency | 0.20 | `0` | `20.0%` |
| F1 | hybrid | bookings_total | integer | threshold_pct: -0.20 | `0` | `-20.0%` |
| H1 | absolute_lt | gross_margin | percent | 0.50 | `50.0%` | `50.0%` ✓ |
| E1 | delta_pct_gte | cancel_rate | percent | 0.15 | `15.0%` | `15.0%` ✓ |

The threshold renders correctly only when the metric's format_hint happens to be
`percent` — correct by accident, not by design.

**Root cause:** `signal.condition` is not persisted, so the template cannot distinguish
a delta-percentage threshold from an absolute threshold.

---

### 2.3 O(n) Metric Lookup Per Signal in Template

Per signal, the template performs a linear scan over the metrics list:

```jinja2
{%- set metric = findings.metrics | selectattr('id', 'equalto', signal.metric_id) | first -%}
```

With 9 signals and 14 metrics: 126 comparisons per render. This is avoidable.
The metric lookup should be O(1) via a pre-built Python dict.

---

### 2.4 Presentation Logic in the Templating Layer

The `category_labels` dict, severity counts, `top_warn` selection, and `first_warn`
are all defined inside the Jinja2 template. These are deterministic data transformations
that belong in Python, not in a templating language.

---

### 2.5 Executive Summary Lacks Business Context

The current "Weekly Priorities" section:

```
- 9 WARN signals
- 0 INFO signals
- Top issue: Revenue Decline
```

Missing: which categories are affected, a multi-signal view, per-category severity
breakdown. A business reader cannot tell which domain is under stress without reading
all 9 signals.

---

## Part 3 — Proposed Iteration 3 Architecture

### 3.1 Data Flow After Changes

```
Findings Builder
    ↓  Findings (domain model — unchanged)
Render Context Preparation                       ← NEW: render/context.py
    ↓  dict (presentation-ready context)
    │
    ├── [deterministic template path]
    │     Jinja2 Template → brief.md             uses sc.narrative (not signal.explanation)
    │
    └── [future LLM path — Iteration 4]
          render_llm(ctx) → brief.md             uses sc.narrative_inputs
```

The context layer is the **single transformation boundary** between the domain
and any rendering path (template or LLM). It is:
- **Deterministic:** same Findings → same context dict
- **Registry-aware:** may import `METRIC_REGISTRY_BY_ID` (unlike the engine)
- **Presentation-only:** no metric computation, no rule evaluation
- **Testable in isolation:** unit tests against synthetic Findings objects

---

### 3.2 Signal Context Design

Each signal produces a `signal_context` dict containing:

```python
{
    # Access
    "signal":           Signal,         # original domain object
    "category":         str,            # signal.category (flat key for groupby)
    "metric":           MetricResult | None,

    # Formatting
    "format_hint":      str,            # metric's own format hint (for current/prev/delta_abs)
    "threshold_hint":   str,            # CORRECT hint for threshold display (condition-aware)

    # Rendering surface (for template)
    "narrative":        str,            # human-readable narrative sentence for the brief

    # Structured inputs (for Iteration 4 LLM)
    "narrative_inputs": dict,           # raw structured data an LLM can consume
}
```

**`narrative`** is what the template renders in place of `signal.explanation`.
It is built from `metric.name` + `signal.condition` + `signal.evidence`, with no
registry import at the engine level.

**`narrative_inputs`** is a structured dict of raw (unformatted) values for future
LLM consumption. Example structure:

```python
{
    "metric_name":     "Net Revenue",
    "metric_id":       "net_revenue",
    "condition":       "delta_pct_lte",
    "direction":       "declined",          # declined | rose | below_threshold | above_threshold
    "current_value":   8000.0,              # raw float, LLM formats its own way
    "previous_value":  10780.0,
    "delta_pct":       -0.258,
    "delta_abs":       -2780.0,
    "threshold":       -0.15,              # None if not applicable
    "threshold_pct":   None,
    "threshold_abs":   None,
    "category":        "revenue",
    "category_display":"Revenue",
    "severity":        "WARN",
    "priority":        10,
    "label":           "Revenue Decline",
    "rule_id":         "A1",
}
```

This structure makes Iteration 4 a clean addition: `render_llm()` receives
`ctx["signal_contexts"]`, iterates `sc["narrative_inputs"]`, and generates richer text
without touching the pipeline, domain models, or engine.

---

### 3.3 Engine Explanation as Audit Record

`signal.explanation` is retained as a **technical audit string** stored in `findings.json`.
It is intentionally NOT used as the rendering surface for the brief.

The brief renders `sc["narrative"]` (from the context layer).
`findings.json` contains `signal.explanation` (from the engine) for auditability.

These serve different audiences:
- `signal.explanation` → developers, debugging, audit trail
- `sc.narrative` → business stakeholders, the brief

The engine explanation strings are not changed in Iteration 3. They may be improved
in a future iteration if `findings.json` is exposed directly to stakeholders.

---

### 3.4 Threshold Hint Resolution

The context layer resolves the correct `threshold_hint` per signal based on
`signal.condition`, which is now persisted on the domain model:

```
condition = "delta_pct_lte" | "delta_pct_gte"   →  threshold_hint = "percent"
condition = "absolute_lt"   | "absolute_gt"     →  threshold_hint = metric.format_hint
condition = "hybrid_delta_pct_lte"              →  threshold_pct_hint = "percent"  (constant)
                                                    threshold_abs_hint = "integer"  (constant)
```

The hybrid constants are named in code (`_HYBRID_ABS_HINT = "integer"`) to make
the policy explicit and provide a single location to update if future hybrid rules
use non-integer absolute thresholds.

---

## Part 4 — Task Breakdown

### Dependency Order

```
Task 1 (Signal model + schema version)  ← independent, no upstream dependency
    └── Task 2 (Render context layer)   ← depends on Task 1 (uses signal.condition)
            └── Task 3 (Executive summary) ← depends on Task 2
```

---

## Task 1 — Signal Model Extension & Schema Version Bump

**Priority:** HIGH — Task 2 depends on this

**Branch:** `feat/i3-task-1-signal-condition`

**Scope:** Minimal. This task makes one additive model change and bumps the schema
version. No config changes. No engine logic changes beyond the one-line propagation.

---

### Required Changes

#### A. `src/wbsb/domain/models.py`

Add `condition: str = ""` to `Signal`, between `priority` and `explanation`:

```python
class Signal(BaseModel):
    """A fired rule/signal."""

    rule_id: str
    severity: str  # WARN | INFO
    metric_id: str
    label: str = ""
    category: str = ""
    priority: int = 0
    condition: str = ""          # ← ADD: "delta_pct_lte" | "delta_pct_gte" |
                                 #         "absolute_lt" | "absolute_gt" |
                                 #         "hybrid_delta_pct_lte"
    explanation: str
    # evidence may include: threshold, threshold_pct, threshold_abs
    evidence: dict[str, Any]
    guardrails: list[str] = Field(default_factory=list)
    reliability: str = "ok"  # ok | low
```

Bump `Findings.schema_version` default from `"1.1"` to `"1.2"`:

```python
class Findings(BaseModel):
    """Full findings document."""

    schema_version: str = "1.2"    # ← was "1.1"
    ...
```

Both changes are additive. Existing code that constructs `Signal` without `condition`
continues to work (default `""`).

---

#### B. `src/wbsb/rules/engine.py`

One change: propagate `condition` when constructing the `Signal`:

```python
fired.append(
    Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id=metric_id,
        label=rule.get("label", ""),
        category=rule.get("category", ""),
        priority=rule.get("priority", 0),
        condition=condition,              # ← ADD THIS LINE
        explanation=explanation,
        evidence=evidence,
        guardrails=guardrails,
        reliability=reliability,
    )
)
```

No other changes to `engine.py`. Explanation strings are left unchanged — they
are technical audit strings for `findings.json`, not the rendering surface.

---

#### C. `tests/test_e2e_pipeline.py`

Update the schema version assertion:

```python
assert findings["schema_version"] == "1.2"   # was "1.1"
```

---

#### D. `tests/test_rules.py`

Add `test_signal_condition_is_propagated`:

```python
def test_signal_condition_is_propagated():
    """Every fired signal carries the condition type that triggered it."""
    curr = {"net_revenue": 7000.0, "bookings_total": 1.0, "gross_margin": 0.45}
    prev = {"net_revenue": 9000.0, "bookings_total": 4.0,
            "leads_paid": 10.0, "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (-2000.0, -0.2222),
        "bookings_total": (-3.0, -0.75),
        "gross_margin": (-0.05, -0.10),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    for s in signals:
        assert s.condition != "", f"Signal {s.rule_id} has empty condition"

    a1 = next((s for s in signals if s.rule_id == "A1"), None)
    if a1:
        assert a1.condition == "delta_pct_lte"

    h1 = next((s for s in signals if s.rule_id == "H1"), None)
    if h1:
        assert h1.condition == "absolute_lt"

    f1 = next((s for s in signals if s.rule_id == "F1"), None)
    if f1:
        assert f1.condition == "hybrid_delta_pct_lte"
```

No other test changes in this task. The existing `test_signals_sorted_by_severity_priority_rule_id`
and all other tests remain unchanged — adding `condition` does not break them.

---

### Allowed Files (Task 1)

- `src/wbsb/domain/models.py`
- `src/wbsb/rules/engine.py`
- `tests/test_e2e_pipeline.py`
- `tests/test_rules.py`

### Acceptance Criteria (Task 1)

- `signal.condition` is non-empty for every fired signal.
- `signal.condition` matches the rule's `condition` field exactly.
- `Findings.schema_version` is `"1.2"`.
- `test_e2e_pipeline.py` assertion passes with `"1.2"`.
- All 43 existing tests pass; new test passes.
- `config/rules.yaml` is untouched.
- Ruff clean.

---

## Task 2 — Render Context Preparation Layer

**Priority:** HIGH — Task 3 depends on this

**Branch:** `feat/i3-task-2-render-context`

**Depends on:** Task 1 merged (uses `signal.condition` for threshold hints and narratives)

---

### Problem Summary

- `render_template()` passes raw `Findings` to Jinja2; all data transformation
  is deferred to the template.
- Template renders `signal.explanation` (technical audit string) as the primary
  business narrative — wrong layer, wrong audience.
- Threshold formatting is incorrect for currency/integer metrics on delta conditions.
- O(n) metric lookup per signal in the template.
- Presentation constants (`category_labels`) live in the templating language.

---

### Required Changes

#### A. `src/wbsb/render/context.py` (NEW FILE)

```python
"""Render context preparation — presentation layer between Findings and Jinja2.

This module is the single transformation boundary between the Findings domain object
and any rendering path (Jinja2 template or future LLM). It:
  - builds O(1) metric lookups
  - computes threshold format hints based on signal.condition
  - generates human-readable narratives for the template
  - generates structured narrative_inputs for future LLM consumption

It may import from wbsb.metrics.registry (unlike the rules engine).
It must remain deterministic: same Findings → same context dict.
"""
from __future__ import annotations

from typing import Any

from wbsb.domain.models import Findings, MetricResult, Signal

# Canonical category display labels. Single source of truth in Python.
CATEGORY_LABELS: dict[str, str] = {
    "acquisition": "Acquisition",
    "operations": "Operations",
    "revenue": "Revenue",
    "financial_health": "Financial Health",
}

# Condition sets for threshold hint resolution.
_DELTA_CONDITIONS = frozenset({"delta_pct_lte", "delta_pct_gte"})
_ABSOLUTE_CONDITIONS = frozenset({"absolute_lt", "absolute_gt"})

# Hybrid threshold format policy.
# threshold_pct in hybrid rules is always a fractional percentage change.
# threshold_abs in hybrid rules is always an integer count (bookings, clients).
# If a future hybrid rule uses a non-integer absolute threshold, update this constant.
_HYBRID_ABS_HINT = "integer"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _threshold_hint(signal: Signal, metric: MetricResult | None) -> str:
    """Return the format_hint to use when rendering the 'threshold' evidence value.

    For delta-percentage conditions, threshold is a fractional change that must
    always render as percent, regardless of the underlying metric's unit.
    For absolute conditions, threshold is in the metric's own unit.
    """
    if signal.condition in _DELTA_CONDITIONS:
        return "percent"
    if signal.condition in _ABSOLUTE_CONDITIONS:
        return metric.format_hint if metric is not None else "decimal"
    # hybrid_delta_pct_lte: template handles threshold_pct and threshold_abs
    # separately using "percent" and _HYBRID_ABS_HINT respectively.
    return "percent"


def _infer_direction(condition: str, delta_pct: float | None) -> str:
    """Return a direction word for narrative_inputs."""
    if condition in ("delta_pct_lte", "hybrid_delta_pct_lte"):
        return "declined"
    if condition == "delta_pct_gte":
        return "rose"
    if condition == "absolute_lt":
        return "below_threshold"
    if condition == "absolute_gt":
        return "above_threshold"
    return "changed"


def _build_narrative(signal: Signal, metric_name: str) -> str:
    """Build a human-readable narrative sentence for the brief.

    This is the rendering surface used by the Jinja2 template. It uses
    metric.name (from findings.metrics, derived from the registry) so metric
    display names have a single source of truth.

    Note: signal.explanation is the technical audit string stored in findings.json.
    It is NOT used here. These serve different audiences.
    """
    condition = signal.condition
    ev = signal.evidence
    delta_pct = ev.get("delta_pct")
    delta_abs = ev.get("delta_abs")

    if condition == "delta_pct_lte":
        if delta_pct is not None:
            return f"{metric_name} declined {abs(delta_pct):.1%} week-over-week."
        return f"{metric_name} declined week-over-week."

    if condition == "delta_pct_gte":
        if delta_pct is not None:
            return f"{metric_name} rose {delta_pct:.1%} week-over-week."
        return f"{metric_name} increased week-over-week."

    if condition == "absolute_lt":
        return f"{metric_name} has fallen below the minimum threshold."

    if condition == "absolute_gt":
        return f"{metric_name} has exceeded the maximum threshold."

    if condition == "hybrid_delta_pct_lte":
        # Determine which mode fired based on which evidence keys are populated
        # relative to the evidence values.
        if delta_pct is not None and ev.get("threshold_pct") is not None:
            # Percentage mode fired
            return f"{metric_name} declined {abs(delta_pct):.1%} week-over-week."
        if delta_abs is not None:
            # Absolute (low-volume) mode fired
            return f"{metric_name} fell by {abs(int(delta_abs))} (low-volume mode)."
        return f"{metric_name} declined week-over-week."

    # Fallback: condition unknown (empty string for old Signal objects)
    return signal.label + "." if signal.label else signal.explanation


def _build_narrative_inputs(signal: Signal, metric: MetricResult | None) -> dict[str, Any]:
    """Build a structured dict of raw values for LLM consumption in Iteration 4.

    All values are raw (unformatted). The LLM render path applies its own formatting.
    This dict is deterministic: same signal + metric → same inputs.
    """
    ev = signal.evidence
    metric_name = metric.name if metric is not None else signal.metric_id
    category_display = CATEGORY_LABELS.get(signal.category, signal.category)
    return {
        "metric_name":      metric_name,
        "metric_id":        signal.metric_id,
        "condition":        signal.condition,
        "direction":        _infer_direction(signal.condition, ev.get("delta_pct")),
        "current_value":    ev.get("current"),
        "previous_value":   ev.get("previous"),
        "delta_pct":        ev.get("delta_pct"),
        "delta_abs":        ev.get("delta_abs"),
        "threshold":        ev.get("threshold"),
        "threshold_pct":    ev.get("threshold_pct"),
        "threshold_abs":    ev.get("threshold_abs"),
        "category":         signal.category,
        "category_display": category_display,
        "severity":         signal.severity,
        "priority":         signal.priority,
        "label":            signal.label,
        "rule_id":          signal.rule_id,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_render_context(findings: Findings) -> dict[str, Any]:
    """Prepare a presentation-ready context dict for the Jinja2 template.

    This is the single entry point for the presentation preparation layer.
    Call it from render_template() before passing context to Jinja2.

    Template responsibility boundary: the context layer computes; the template
    formats and groups. The template must not perform business logic lookups or
    assemble summaries.

    Args:
        findings: Fully populated Findings document from build_findings().

    Returns:
        Context dict. Keys:

        findings            Original Findings (for run/periods metadata and raw access)
        warn_count          int
        info_count          int
        top_warn            Signal | None — highest-priority WARN signal
        affected_categories list[str] — display labels of categories with WARN signals,
                            in order of first WARN signal appearance (priority-sorted)
        category_labels     dict[str, str] — CATEGORY_LABELS constant
        metric_by_id        dict[str, MetricResult] — O(1) lookup by metric_id
        signal_contexts     list[dict] — per-signal presentation metadata (see below)

        Each signal_context dict contains:
          signal            Signal object (original domain object)
          category          str — signal.category (flat key for Jinja2 groupby)
          metric            MetricResult | None
          format_hint       str — metric format hint for current/previous/delta_abs
          threshold_hint    str — CORRECT hint for the 'threshold' evidence key
          narrative         str — human-readable sentence for the brief (use this, not signal.explanation)
          narrative_inputs  dict — structured raw values for Iteration 4 LLM consumption
    """
    # O(1) metric lookup
    metric_by_id: dict[str, MetricResult] = {m.id: m for m in findings.metrics}

    warn_signals = [s for s in findings.signals if s.severity == "WARN"]
    info_signals = [s for s in findings.signals if s.severity == "INFO"]
    top_warn = warn_signals[0] if warn_signals else None

    # Unique affected categories in WARN-priority order (signals already sorted by engine)
    seen: set[str] = set()
    affected_categories: list[str] = []
    for s in warn_signals:
        if s.category and s.category not in seen:
            seen.add(s.category)
            affected_categories.append(CATEGORY_LABELS.get(s.category, s.category))

    # Per-signal presentation metadata
    signal_contexts: list[dict[str, Any]] = []
    for signal in findings.signals:
        metric = metric_by_id.get(signal.metric_id)
        metric_name = metric.name if metric is not None else signal.metric_id
        format_hint = metric.format_hint if metric is not None else "decimal"
        threshold_hint = _threshold_hint(signal, metric)
        narrative = _build_narrative(signal, metric_name)
        narrative_inputs = _build_narrative_inputs(signal, metric)
        signal_contexts.append({
            "signal":           signal,
            "category":         signal.category,    # flat key for Jinja2 groupby
            "metric":           metric,
            "format_hint":      format_hint,
            "threshold_hint":   threshold_hint,
            "narrative":        narrative,
            "narrative_inputs": narrative_inputs,
        })

    return {
        "findings":             findings,
        "warn_count":           len(warn_signals),
        "info_count":           len(info_signals),
        "top_warn":             top_warn,
        "affected_categories":  affected_categories,
        "category_labels":      CATEGORY_LABELS,
        "metric_by_id":         metric_by_id,
        "signal_contexts":      signal_contexts,
    }
```

---

#### B. `src/wbsb/render/template.py`

Update `render_template()` to call `prepare_render_context()`. The public signature
is unchanged — `pipeline.py` requires no modification.

```python
"""Template-based brief renderer using Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from wbsb.domain.models import Findings
from wbsb.render.context import prepare_render_context

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "template.md.j2"


def render_template(findings: Findings) -> str:
    """Render brief.md from findings using Jinja2 template.

    Args:
        findings: Pre-computed Findings document.

    Returns:
        Markdown string for brief.md.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(_TEMPLATE_NAME)
    ctx = prepare_render_context(findings)
    return template.render(**ctx)
```

---

#### C. `src/wbsb/render/template.md.j2`

Key changes to the template (all other sections unchanged):

**1. Remove** the `{%- set category_labels = {...} -%}` block — now a context variable.

**2. Weekly Priorities** — replace `selectattr` severity computations:

```jinja2
## Weekly Priorities
- {{ warn_count }} WARN signal{{ 's' if warn_count != 1 else '' }}
- {{ info_count }} INFO signal{{ 's' if info_count != 1 else '' }}
- Top issue: {% if top_warn %}{{ top_warn.label }}{% else %}No critical alerts this week{% endif %}
```

**3. Signals section** — replace `findings.signals | groupby('category')` and the
per-signal O(n) metric lookup with the pre-built `signal_contexts`:

```jinja2
{% if findings.signals %}
{% for category, cat_ctxs in signal_contexts | groupby('category') %}

**{{ category_labels.get(category, category) }}**

{% for sc in cat_ctxs %}
{% set signal = sc.signal %}
{% set hint = sc.format_hint %}
{% set t_hint = sc.threshold_hint %}
### {{ signal.severity }} — {{ signal.label }} (Rule {{ signal.rule_id }})

{{ sc.narrative }}

**Evidence:**
- Current: {{ format_value(signal.evidence.current, hint) }}
- Previous: {{ format_value(signal.evidence.previous, hint) }}
- Δ absolute: {{ format_value(signal.evidence.delta_abs, hint) }}
- Δ %: {{ format_value(signal.evidence.delta_pct, 'percent') }}
{% if 'threshold' in signal.evidence %}- Threshold: {{ format_value(signal.evidence.threshold, t_hint) }}
{% endif %}{% if 'threshold_pct' in signal.evidence %}- Threshold (% change): {{ format_value(signal.evidence.threshold_pct, 'percent') }}
{% endif %}{% if 'threshold_abs' in signal.evidence %}- Threshold (absolute): {{ format_value(signal.evidence.threshold_abs, 'integer') }}
{% endif %}
{% if signal.guardrails %}
**Guardrails:** {{ signal.guardrails | join('; ') }}
{% endif %}
{% if signal.reliability == "low" %}
> ⚠️ Low-reliability signal: previous period data below minimum threshold.
{% endif %}

---
{% endfor %}
{% endfor %}
{% else %}
No signals fired this week. All metrics within thresholds.

---
{% endif %}
```

Key changes:
- `{{ sc.narrative }}` replaces `{{ signal.explanation }}` (correct rendering surface)
- `{{ t_hint }}` (from context) replaces `{{ hint }}` for threshold display (fixes bug §2.2)
- `'integer'` hardcoded for `threshold_abs` (consistent with `_HYBRID_ABS_HINT` policy)
- No `selectattr` lookup per signal (eliminated)
- No `{% set metric = ... %}` per signal (eliminated)

**4. Remove** the `{% set warn_signals %}`, `{% set info_signals %}`,
`{% set first_warn %}` lines from the Weekly Priorities section —
these are now `warn_count`, `info_count`, `top_warn` from context.

---

#### D. `tests/test_render_context.py` (NEW FILE)

```python
"""Tests for the render context preparation layer."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from wbsb.domain.models import (
    AuditEvent, Findings, MetricResult, Periods, RunMeta, Signal,
)
from wbsb.render.context import (
    CATEGORY_LABELS,
    _HYBRID_ABS_HINT,
    _build_narrative,
    _build_narrative_inputs,
    _threshold_hint,
    prepare_render_context,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_metric(
    metric_id: str,
    name: str = "",
    format_hint: str = "decimal",
    category: str = "revenue",
    category_order: int = 1,
    display_order: int = 1,
) -> MetricResult:
    return MetricResult(
        id=metric_id,
        name=name or metric_id,
        unit="decimal",
        format_hint=format_hint,
        category=category,
        category_order=category_order,
        display_order=display_order,
        current=100.0,
        previous=90.0,
        delta_abs=10.0,
        delta_pct=0.111,
    )


def _make_signal(
    rule_id: str,
    metric_id: str,
    severity: str = "WARN",
    condition: str = "delta_pct_lte",
    category: str = "revenue",
    priority: int = 5,
    label: str = "",
    evidence: dict | None = None,
) -> Signal:
    if evidence is None:
        evidence = {
            "current": 100.0,
            "previous": 90.0,
            "delta_abs": -10.0,
            "delta_pct": -0.10,
            "threshold": -0.15,
        }
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id=metric_id,
        condition=condition,
        category=category,
        priority=priority,
        label=label or f"Label {rule_id}",
        explanation=f"{metric_id} technical explanation",
        evidence=evidence,
    )


def _make_findings(
    signals: list[Signal],
    metrics: list[MetricResult] | None = None,
    audit: list[AuditEvent] | None = None,
) -> Findings:
    run = RunMeta(
        run_id="test_run",
        generated_at=datetime(2024, 12, 1, 12, 0, tzinfo=timezone.utc),
        input_file="test.csv",
        input_sha256="abc",
        config_sha256="def",
    )
    periods = Periods(
        current_week_start=date(2024, 11, 25),
        current_week_end=date(2024, 12, 1),
        previous_week_start=date(2024, 11, 18),
        previous_week_end=date(2024, 11, 24),
    )
    if metrics is None:
        metrics = [_make_metric("net_revenue", "Net Revenue", "currency")]
    return Findings(
        run=run, periods=periods, metrics=metrics,
        signals=signals, audit=audit or [],
    )


# ---------------------------------------------------------------------------
# CATEGORY_LABELS
# ---------------------------------------------------------------------------

def test_category_labels_covers_all_canonical_ids():
    for cat_id in ("acquisition", "operations", "revenue", "financial_health"):
        assert cat_id in CATEGORY_LABELS
        label = CATEGORY_LABELS[cat_id]
        assert label and label[0].isupper()


def test_category_labels_financial_health_has_space():
    assert CATEGORY_LABELS["financial_health"] == "Financial Health"


# ---------------------------------------------------------------------------
# _threshold_hint
# ---------------------------------------------------------------------------

def test_threshold_hint_delta_pct_lte_is_percent():
    m = _make_metric("net_revenue", format_hint="currency")
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte")
    assert _threshold_hint(s, m) == "percent"


def test_threshold_hint_delta_pct_gte_is_percent():
    m = _make_metric("cac_paid", format_hint="currency")
    s = _make_signal("B1", "cac_paid", condition="delta_pct_gte")
    assert _threshold_hint(s, m) == "percent"


def test_threshold_hint_absolute_lt_uses_metric_hint():
    m = _make_metric("gross_margin", format_hint="percent")
    s = _make_signal("H1", "gross_margin", condition="absolute_lt")
    assert _threshold_hint(s, m) == "percent"


def test_threshold_hint_absolute_gt_uses_metric_hint():
    m = _make_metric("marketing_pct_revenue", format_hint="percent")
    s = _make_signal("H2", "marketing_pct_revenue", condition="absolute_gt")
    assert _threshold_hint(s, m) == "percent"


def test_threshold_hint_absolute_with_currency_metric():
    """An absolute threshold on a hypothetical currency metric uses currency hint."""
    m = _make_metric("net_revenue", format_hint="currency")
    s = _make_signal("X1", "net_revenue", condition="absolute_lt")
    assert _threshold_hint(s, m) == "currency"


def test_threshold_hint_no_metric_fallback():
    s = _make_signal("X1", "unknown", condition="absolute_lt")
    assert _threshold_hint(s, None) == "decimal"


def test_hybrid_abs_hint_constant_is_integer():
    """_HYBRID_ABS_HINT must be 'integer' — the assumed unit for hybrid absolute thresholds."""
    assert _HYBRID_ABS_HINT == "integer"


# ---------------------------------------------------------------------------
# _build_narrative
# ---------------------------------------------------------------------------

def test_narrative_delta_pct_lte_declined():
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte",
                     evidence={"current": 8000.0, "previous": 10780.0,
                               "delta_abs": -2780.0, "delta_pct": -0.258, "threshold": -0.15})
    n = _build_narrative(s, "Net Revenue")
    assert "Net Revenue" in n
    assert "declined" in n
    assert "25.8%" in n
    assert "net_revenue" not in n


def test_narrative_delta_pct_gte_rose():
    s = _make_signal("B1", "cac_paid", condition="delta_pct_gte",
                     evidence={"current": 236.0, "previous": 146.0,
                               "delta_abs": 90.0, "delta_pct": 0.616, "threshold": 0.20})
    n = _build_narrative(s, "CAC (Paid)")
    assert "CAC (Paid)" in n
    assert "rose" in n
    assert "cac_paid" not in n


def test_narrative_absolute_lt_below_threshold():
    s = _make_signal("H1", "gross_margin", condition="absolute_lt",
                     evidence={"current": 0.475, "previous": 0.657,
                               "delta_abs": -0.182, "delta_pct": -0.277, "threshold": 0.50})
    n = _build_narrative(s, "Gross Margin")
    assert "Gross Margin" in n
    assert "below" in n
    assert "gross_margin" not in n


def test_narrative_absolute_gt_above_threshold():
    s = _make_signal("H2", "marketing_pct_revenue", condition="absolute_gt",
                     evidence={"current": 0.531, "previous": 0.353,
                               "delta_abs": 0.178, "delta_pct": 0.504, "threshold": 0.40})
    n = _build_narrative(s, "Marketing % of Revenue")
    assert "Marketing % of Revenue" in n
    assert "exceeded" in n


def test_narrative_hybrid_pct_mode():
    s = _make_signal("F1", "bookings_total", condition="hybrid_delta_pct_lte",
                     evidence={"current": 42.0, "previous": 62.0,
                               "delta_abs": -20.0, "delta_pct": -0.323,
                               "threshold_pct": -0.20, "threshold_abs": -3})
    n = _build_narrative(s, "Total Bookings")
    assert "Total Bookings" in n
    assert "declined" in n
    assert "32.3%" in n


def test_narrative_hybrid_abs_mode():
    s = _make_signal("F1", "bookings_total", condition="hybrid_delta_pct_lte",
                     evidence={"current": 1.0, "previous": 4.0,
                               "delta_abs": -3.0, "delta_pct": -0.75,
                               "threshold_pct": -0.20, "threshold_abs": -3})
    # Simulate abs mode: delta_pct is present but so is threshold_pct
    # In abs mode, delta_pct was computed but pct threshold was NOT the trigger.
    # We detect abs mode when threshold_pct is None in evidence (set only if pct mode fired)
    # For this test, build evidence without threshold_pct to simulate abs mode evidence path:
    s2 = _make_signal("F1", "bookings_total", condition="hybrid_delta_pct_lte",
                      evidence={"current": 1.0, "previous": 4.0,
                                "delta_abs": -3.0, "delta_pct": None,
                                "threshold_abs": -3})
    n = _build_narrative(s2, "Total Bookings")
    assert "Total Bookings" in n
    assert "low-volume" in n


def test_narrative_no_raw_metric_id():
    """Narrative must never contain the raw snake_case metric_id."""
    import re
    metrics_to_test = [
        ("net_revenue", "Net Revenue", "delta_pct_lte"),
        ("cac_paid", "CAC (Paid)", "delta_pct_gte"),
        ("gross_margin", "Gross Margin", "absolute_lt"),
        ("bookings_total", "Total Bookings", "hybrid_delta_pct_lte"),
    ]
    for metric_id, metric_name, condition in metrics_to_test:
        s = _make_signal("X1", metric_id, condition=condition)
        n = _build_narrative(s, metric_name)
        assert metric_id not in n, (
            f"Narrative for {metric_id} contains raw metric_id: {n!r}"
        )


# ---------------------------------------------------------------------------
# _build_narrative_inputs
# ---------------------------------------------------------------------------

def test_narrative_inputs_contains_required_keys():
    m = _make_metric("net_revenue", "Net Revenue", "currency")
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte")
    ni = _build_narrative_inputs(s, m)
    required = {
        "metric_name", "metric_id", "condition", "direction",
        "current_value", "previous_value", "delta_pct", "delta_abs",
        "threshold", "threshold_pct", "threshold_abs",
        "category", "category_display", "severity", "priority", "label", "rule_id",
    }
    for key in required:
        assert key in ni, f"Missing key in narrative_inputs: {key}"


def test_narrative_inputs_metric_name_from_registry():
    m = _make_metric("net_revenue", "Net Revenue", "currency")
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte")
    ni = _build_narrative_inputs(s, m)
    assert ni["metric_name"] == "Net Revenue"


def test_narrative_inputs_metric_name_fallback_to_id():
    s = _make_signal("X1", "unknown_metric", condition="delta_pct_lte")
    ni = _build_narrative_inputs(s, None)
    assert ni["metric_name"] == "unknown_metric"


def test_narrative_inputs_direction_declined():
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte")
    ni = _build_narrative_inputs(s, None)
    assert ni["direction"] == "declined"


def test_narrative_inputs_direction_rose():
    s = _make_signal("B1", "cac_paid", condition="delta_pct_gte")
    ni = _build_narrative_inputs(s, None)
    assert ni["direction"] == "rose"


def test_narrative_inputs_category_display():
    s = _make_signal("H1", "gross_margin", condition="absolute_lt",
                     category="financial_health")
    ni = _build_narrative_inputs(s, None)
    assert ni["category"] == "financial_health"
    assert ni["category_display"] == "Financial Health"


def test_narrative_inputs_values_are_raw():
    """narrative_inputs must contain raw floats, not formatted strings."""
    m = _make_metric("net_revenue", "Net Revenue", "currency")
    ev = {"current": 8000.0, "previous": 10780.0, "delta_abs": -2780.0,
          "delta_pct": -0.258, "threshold": -0.15}
    s = _make_signal("A1", "net_revenue", condition="delta_pct_lte", evidence=ev)
    ni = _build_narrative_inputs(s, m)
    assert ni["current_value"] == 8000.0
    assert ni["delta_pct"] == -0.258
    assert ni["threshold"] == -0.15
    assert isinstance(ni["current_value"], float)


# ---------------------------------------------------------------------------
# prepare_render_context
# ---------------------------------------------------------------------------

def test_metric_by_id_contains_all_metrics():
    metrics = [
        _make_metric("net_revenue", "Net Revenue", "currency"),
        _make_metric("gross_margin", "Gross Margin", "percent",
                     category="financial_health", category_order=4, display_order=1),
    ]
    ctx = prepare_render_context(_make_findings([], metrics=metrics))
    assert "net_revenue" in ctx["metric_by_id"]
    assert "gross_margin" in ctx["metric_by_id"]
    assert ctx["metric_by_id"]["net_revenue"].format_hint == "currency"


def test_warn_info_counts():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN"),
        _make_signal("A2", "net_revenue", severity="INFO"),
        _make_signal("B1", "cac_paid", severity="WARN"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["warn_count"] == 2
    assert ctx["info_count"] == 1


def test_top_warn_is_first_signal():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN", priority=10),
        _make_signal("B1", "cac_paid", severity="WARN", priority=8),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["top_warn"] is signals[0]


def test_top_warn_none_when_no_warn_signals():
    signals = [_make_signal("A2", "net_revenue", severity="INFO")]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["top_warn"] is None


def test_affected_categories_ordered_by_first_warn():
    signals = [
        _make_signal("H1", "gross_margin", severity="WARN", category="financial_health"),
        _make_signal("A1", "net_revenue", severity="WARN", category="revenue"),
        _make_signal("B1", "cac_paid", severity="WARN", category="acquisition"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["affected_categories"] == ["Financial Health", "Revenue", "Acquisition"]


def test_affected_categories_unique():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN", category="revenue"),
        _make_signal("A3", "net_revenue", severity="WARN", category="revenue"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["affected_categories"].count("Revenue") == 1


def test_affected_categories_empty_when_no_warn():
    signals = [_make_signal("A2", "net_revenue", severity="INFO", category="revenue")]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["affected_categories"] == []


def test_signal_contexts_length():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN"),
        _make_signal("A2", "net_revenue", severity="INFO"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert len(ctx["signal_contexts"]) == len(signals)


def test_signal_context_required_keys():
    signals = [_make_signal("A1", "net_revenue")]
    ctx = prepare_render_context(_make_findings(signals))
    sc = ctx["signal_contexts"][0]
    for key in ("signal", "category", "metric", "format_hint", "threshold_hint",
                "narrative", "narrative_inputs"):
        assert key in sc, f"Missing key in signal_context: {key}"


def test_signal_context_category_matches_signal():
    signals = [_make_signal("A1", "net_revenue", category="revenue")]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["signal_contexts"][0]["category"] == "revenue"


def test_signal_context_threshold_hint_correct_for_delta():
    metrics = [_make_metric("net_revenue", "Net Revenue", "currency")]
    signals = [_make_signal("A1", "net_revenue", condition="delta_pct_lte")]
    ctx = prepare_render_context(_make_findings(signals, metrics=metrics))
    assert ctx["signal_contexts"][0]["threshold_hint"] == "percent"


def test_signal_context_narrative_not_explanation():
    """Template rendering surface (narrative) must differ from technical explanation."""
    metrics = [_make_metric("net_revenue", "Net Revenue", "currency")]
    signals = [_make_signal("A1", "net_revenue", condition="delta_pct_lte",
                            evidence={"current": 8000.0, "previous": 10780.0,
                                      "delta_abs": -2780.0, "delta_pct": -0.258,
                                      "threshold": -0.15})]
    ctx = prepare_render_context(_make_findings(signals, metrics=metrics))
    sc = ctx["signal_contexts"][0]
    # Narrative must use metric display name, not raw metric_id
    assert "net_revenue" not in sc["narrative"]
    assert "Net Revenue" in sc["narrative"]


def test_signal_context_narrative_inputs_present():
    metrics = [_make_metric("net_revenue", "Net Revenue", "currency")]
    signals = [_make_signal("A1", "net_revenue", condition="delta_pct_lte")]
    ctx = prepare_render_context(_make_findings(signals, metrics=metrics))
    ni = ctx["signal_contexts"][0]["narrative_inputs"]
    assert ni["metric_name"] == "Net Revenue"
    assert ni["condition"] == "delta_pct_lte"
    assert ni["direction"] == "declined"


def test_findings_passthrough():
    findings = _make_findings([])
    ctx = prepare_render_context(findings)
    assert ctx["findings"] is findings


def test_category_labels_in_context():
    ctx = prepare_render_context(_make_findings([]))
    assert ctx["category_labels"] == CATEGORY_LABELS
```

---

### Allowed Files (Task 2)

- `src/wbsb/render/context.py` (new)
- `src/wbsb/render/template.py`
- `src/wbsb/render/template.md.j2`
- `tests/test_render_context.py` (new)

### Acceptance Criteria (Task 2)

- `prepare_render_context(findings)` returns a dict with all documented keys.
- Every `signal_context` contains `narrative`, `narrative_inputs`, `threshold_hint`,
  `format_hint`, `category`, `metric`.
- `narrative` does not contain raw `snake_case` metric IDs.
- `threshold_hint` is `"percent"` for all delta-percentage conditions.
- `threshold_hint` matches the metric's `format_hint` for absolute conditions.
- Template uses `{{ sc.narrative }}`, not `{{ signal.explanation }}`.
- Template uses `{{ t_hint }}` (from context), not `{{ hint }}`, for threshold display.
- Template contains no `selectattr` for per-signal metric lookup.
- Template contains no `category_labels` dict literal.
- `narrative_inputs` contains raw float values (not formatted strings).
- `_HYBRID_ABS_HINT = "integer"` constant exists in `context.py`.
- All existing tests pass; all `test_render_context.py` tests pass.
- Ruff clean.

**Threshold formatting verification (manual):**
After Task 2, run `wbsb run --input examples/sample_weekly.csv` and verify in `brief.md`:
- Rule A1 (Revenue Decline): `- Threshold: -15.0%` (was `0`)
- Rule B1 (CAC Rising): `- Threshold: 20.0%` (was `0`)
- Rule H1 (Gross Margin): `- Threshold: 50.0%` (unchanged, was correct)
- Rule F1 threshold_pct: `-20.0%` (was `0`)

---

## Task 3 — Improved Executive Summary

**Priority:** MEDIUM

**Branch:** `feat/i3-task-3-executive-summary`

**Depends on:** Task 2 merged

---

### Required Changes

#### A. `src/wbsb/render/context.py`

Add two new outputs to `prepare_render_context()`.

**`top_signals`**: First 3 WARN signals (already priority-sorted by engine):

```python
top_signals = warn_signals[:3]
```

**`severity_by_category`**: WARN count per category display label. Preserves insertion
order (same as `affected_categories` order):

```python
severity_by_category: dict[str, int] = {}
for s in warn_signals:
    label = CATEGORY_LABELS.get(s.category, s.category)
    severity_by_category[label] = severity_by_category.get(label, 0) + 1
```

Add both to the returned dict.

---

#### B. `src/wbsb/render/template.md.j2`

Replace the current "Weekly Priorities" block:

```jinja2
## Weekly Priorities

- **{{ warn_count }} WARN** · **{{ info_count }} INFO**
{% if affected_categories %}
- Categories affected: {{ affected_categories | join(" · ") }}
{% endif %}
- Top issue: {% if top_warn %}{{ top_warn.label }} ({{ category_labels.get(top_warn.category, top_warn.category) }}){% else %}No critical alerts this week{% endif %}
{% if top_signals | length > 1 %}

**Priority signals:**
{% for s in top_signals %}
- {{ s.severity }}: {{ s.label }} — {{ category_labels.get(s.category, s.category) }}
{% endfor %}
{% endif %}
{% if severity_by_category %}

**By category:**
{% for cat_label, count in severity_by_category.items() %}
- {{ cat_label }}: {{ count }} WARN
{% endfor %}
{% endif %}
```

Target output for a run with 9 WARN signals across 4 categories:

```markdown
## Weekly Priorities

- **9 WARN** · **0 INFO**
- Categories affected: Revenue · Financial Health · Acquisition · Operations
- Top issue: Revenue Decline (Revenue)

**Priority signals:**
- WARN: Revenue Decline — Revenue
- WARN: Gross Margin Below Threshold — Financial Health
- WARN: Contribution Margin Declining — Financial Health

**By category:**
- Revenue: 1 WARN
- Financial Health: 3 WARN
- Acquisition: 3 WARN
- Operations: 2 WARN
```

---

#### C. `tests/test_render_context.py`

Add:

```python
def test_top_signals_capped_at_three():
    signals = [
        _make_signal(f"W{i}", "net_revenue", severity="WARN", priority=10 - i)
        for i in range(5)
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert len(ctx["top_signals"]) == 3
    assert ctx["top_signals"][0] is signals[0]


def test_top_signals_warn_only():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN"),
        _make_signal("A2", "net_revenue", severity="INFO"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    assert all(s.severity == "WARN" for s in ctx["top_signals"])


def test_top_signals_empty_when_no_warn():
    signals = [_make_signal("A2", "net_revenue", severity="INFO")]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["top_signals"] == []


def test_severity_by_category_counts():
    signals = [
        _make_signal("A1", "net_revenue", severity="WARN", category="revenue"),
        _make_signal("H1", "gross_margin", severity="WARN", category="financial_health"),
        _make_signal("H3", "contribution_after_marketing", severity="WARN",
                     category="financial_health"),
        _make_signal("A2", "net_revenue", severity="INFO", category="revenue"),
    ]
    ctx = prepare_render_context(_make_findings(signals))
    sbc = ctx["severity_by_category"]
    assert sbc.get("Revenue") == 1
    assert sbc.get("Financial Health") == 2
    assert "INFO" not in str(sbc)


def test_severity_by_category_empty_when_no_warn():
    signals = [_make_signal("A2", "net_revenue", severity="INFO")]
    ctx = prepare_render_context(_make_findings(signals))
    assert ctx["severity_by_category"] == {}
```

#### D. `tests/test_e2e_pipeline.py`

Add smoke assertions for the new executive summary:

```python
if manifest["signals_warn_count"] > 0:
    assert "Categories affected:" in brief_md
if manifest["signals_warn_count"] > 1:
    assert "Priority signals:" in brief_md
```

---

### Allowed Files (Task 3)

- `src/wbsb/render/context.py`
- `src/wbsb/render/template.md.j2`
- `tests/test_render_context.py`
- `tests/test_e2e_pipeline.py`

### Acceptance Criteria (Task 3)

- `top_signals` is a list of WARN signals, maximum length 3, in priority order.
- `severity_by_category` is a dict of display_label → WARN count, in category order.
- Brief shows "Categories affected:" when WARN signals are present.
- Brief shows "Priority signals:" section when more than 1 WARN signal fires.
- Brief shows per-category WARN counts.
- "No critical alerts this week" renders correctly when no WARN signals fire.
- All existing tests pass; updated context tests pass; e2e smoke assertions pass.
- Ruff clean.

---

## Part 5 — File-Level Change Plan

| Task | File | Change Type | Notes |
|---|---|---|---|
| 1 | `src/wbsb/domain/models.py` | Edit | Add `condition: str = ""` to Signal; bump schema to `"1.2"` |
| 1 | `src/wbsb/rules/engine.py` | Edit | One line: `condition=condition` in Signal constructor |
| 1 | `tests/test_e2e_pipeline.py` | Edit | Update `"1.1"` → `"1.2"` assertion |
| 1 | `tests/test_rules.py` | Edit | Add `test_signal_condition_is_propagated` |
| 2 | `src/wbsb/render/context.py` | **New** | Full context preparation layer |
| 2 | `src/wbsb/render/template.py` | Edit | Call `prepare_render_context()`; pass `**ctx` |
| 2 | `src/wbsb/render/template.md.j2` | Edit | Use `sc.narrative`; use `t_hint`; remove inline transforms |
| 2 | `tests/test_render_context.py` | **New** | 35+ unit tests for context layer |
| 3 | `src/wbsb/render/context.py` | Edit | Add `top_signals`, `severity_by_category` |
| 3 | `src/wbsb/render/template.md.j2` | Edit | Expand Weekly Priorities section |
| 3 | `tests/test_render_context.py` | Edit | Add 5 tests for new context fields |
| 3 | `tests/test_e2e_pipeline.py` | Edit | Add executive summary smoke assertions |

**Files that must NOT change in Iteration 3:**

- `config/rules.yaml` — no changes required
- `src/wbsb/pipeline.py` — orchestrator unchanged; `render_template()` signature unchanged
- `src/wbsb/findings/build.py` — findings assembly unchanged
- `src/wbsb/metrics/calculate.py` — no metric logic changes
- `src/wbsb/metrics/registry.py` — no registry changes
- `src/wbsb/compare/delta.py` — no delta logic changes
- `src/wbsb/validate/schema.py` — no validation changes
- `src/wbsb/export/write.py` — no artifact writing changes
- `src/wbsb/ingest/loader.py` — no ingestion changes

---

## Part 6 — New Modules

### `src/wbsb/render/context.py`

**Purpose:** Presentation preparation layer. Single transformation boundary between
domain objects and any rendering path.

**Public API:**

```python
CATEGORY_LABELS: dict[str, str]

def prepare_render_context(findings: Findings) -> dict[str, Any]: ...

# Internal but testable:
def _threshold_hint(signal: Signal, metric: MetricResult | None) -> str: ...
def _build_narrative(signal: Signal, metric_name: str) -> str: ...
def _build_narrative_inputs(signal: Signal, metric: MetricResult | None) -> dict: ...
```

**Permitted imports:** `wbsb.domain.models`, standard library only.
The context module receives `MetricResult` objects (which carry `name` and `format_hint`
already derived from the registry) from `findings.metrics`. It does NOT need to import
`wbsb.metrics.registry` directly.

**Invariants:**
- Deterministic: same Findings → same context dict.
- Does not modify Findings or any domain object.
- Does not compute metrics, fire rules, or perform I/O.
- Does not format numbers (formatting stays in the template).

### `tests/test_render_context.py`

**Purpose:** Isolated unit tests for the context layer. Uses synthetic `Findings`;
does not require the full pipeline, filesystem, or sample data.

---

## Part 7 — Non-Negotiable Constraints

| Constraint | Enforced by |
|---|---|
| Deterministic: same input → same output | Context preparation is a pure function |
| Engine must NOT import metric registry | `engine.py` imports only `wbsb.domain.models` |
| Formatting stays in the rendering layer (template) | Context computes hints; `format_value` macro applies them |
| Schema changes additive only | `Signal.condition = ""` default; no removals |
| `rules.yaml` unchanged | No `metric_name` field added (single source of truth preserved) |
| Engine explanations unchanged | `signal.explanation` is audit record; template uses `sc.narrative` |
| Existing tests must pass | Run `pytest` after every task |
| Ruff must be clean | Run `ruff check .` after every task |
| One task per PR | Three PRs total for Iteration 3 |

---

## Part 8 — Testing Strategy

### Unit Tests

| Test File | What It Covers | New in Iteration 3 |
|---|---|---|
| `tests/test_rules.py` | Engine condition propagation | 1 new test |
| `tests/test_render_context.py` | Context layer: threshold hints, narrative generation, narrative_inputs, grouping, executive summary inputs | NEW FILE (~40 tests) |
| `tests/test_e2e_pipeline.py` | Full pipeline + brief content smoke assertions | 3–4 updated/new assertions |

### Manual Verification Checklist

After Task 2 is merged:

```
wbsb run --input examples/sample_weekly.csv
```

Open `runs/<run_id>/brief.md` and verify:

- [ ] Signal narratives use human-readable metric names ("Net Revenue", not "net_revenue")
- [ ] Signal narratives do not contain threshold values inline
- [ ] Rule A1 evidence block: `- Threshold: -15.0%` (not `0`)
- [ ] Rule B1 evidence block: `- Threshold: 20.0%` (not `0`)
- [ ] Rule H1 evidence block: `- Threshold: 50.0%` (unchanged, was correct)
- [ ] Rule F1 evidence block: `- Threshold (% change): -20.0%` (not `0`)
- [ ] `findings.json`: `signal.explanation` still contains technical strings (audit)
- [ ] `findings.json`: `signal.condition` is populated for every signal

After Task 3 is merged:

- [ ] Weekly Priorities shows "Categories affected:" with category names
- [ ] Weekly Priorities shows "Priority signals:" with top 3
- [ ] Weekly Priorities shows per-category WARN counts
- [ ] "No critical alerts this week" renders when no WARN signals fire

---

## Part 9 — Iteration 4 Compatibility

Iteration 4 may introduce LLM-based narrative generation. The architecture established
in Iteration 3 supports this without pipeline changes:

```python
# Iteration 4: render_llm() receives the context dict
def render_llm(findings: Findings, mode: str) -> str:
    ctx = prepare_render_context(findings)
    # Each sc["narrative_inputs"] is a structured dict ready for LLM prompt assembly
    for sc in ctx["signal_contexts"]:
        inputs = sc["narrative_inputs"]
        # inputs["metric_name"], inputs["direction"], inputs["current_value"], …
        # → assemble LLM prompt, call API, collect narrative
    ...
```

The deterministic template path (`render_template`) and the LLM path (`render_llm`)
both start from `prepare_render_context(findings)`. The context layer is the shared
foundation. Neither path modifies the other.

---

## Part 10 — Definition of Done

Iteration 3 is complete when:

1. **`signal.condition`** is populated for every fired signal in `findings.json`.

2. **`Findings.schema_version` is `"1.2"`.**

3. **Signal narratives in `brief.md` use human-readable metric names** — no
   `snake_case` identifiers appear in the rendered brief.

4. **Threshold formatting is correct** — delta-percentage thresholds render as `%`
   in the evidence block for all condition types, including currency and integer metrics.
   (Rules A1, B1 thresholds previously rendered as `0`; now render as `-15.0%`, `20.0%`.)

5. **`render_template()` uses `prepare_render_context()`** internally. The template
   receives `**ctx` and uses `sc.narrative` as the signal narrative surface.

6. **`narrative_inputs` is populated** per signal for Iteration 4 LLM consumption.

7. **Template responsibility boundary is respected:**
   - No `selectattr` for metric lookup per signal
   - No `category_labels` dict literal
   - No severity counts computed in template

8. **Executive summary shows category breakdown** when WARN signals are present.

9. **All tests pass (existing + new).** `pytest` exit code 0 on `main`.

10. **Ruff is clean** on `main` after all three PRs are merged.

---

## Execution Workflow

For each task:

1. `git checkout -b feat/i3-task-N-<description>`
2. Read all allowed files before writing any code.
3. Implement changes.
4. `pytest` — fix any failures within allowed files only.
5. `ruff check .` — fix any issues within allowed files only.
6. `git diff --name-only` — confirm only allowed files changed.
7. Commit: `feat(iteration-3): implement Task N <description>`
8. Push and open PR.
9. Merge after review; run full test suite on main.

Never combine multiple tasks in a single PR unless explicitly approved.
