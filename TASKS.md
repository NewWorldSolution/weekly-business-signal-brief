# TASKS.md — Iteration Control

## Weekly Business Signal Brief (WBSB)

This document tracks the current active iteration tasks.
Full roadmap with all planned iterations: see `project-iterations.md`.

---

## Development Rules

- One task at a time. One task per PR.
- Plan Mode required for multi-file or behavioral changes.
- Only modify files explicitly allowed in each task.
- Always run before committing:
  - `pytest`
  - `ruff check .`
- No architectural rewrites unless explicitly defined.
- No silent error handling (`except: pass` is forbidden).
- No refactors outside allowed task scope.

---

## Iteration Status

| Iteration | Theme | Status |
|---|---|---|
| I1 | Pipeline Foundation | ✅ Complete |
| I2 | Signal Architecture | ✅ Complete |
| I3 | Business Reporting Layer | ✅ Complete |
| I4 | LLM Integration | ✅ Complete |
| I5 | Analytical Reasoning Upgrade | ✅ Complete |
| **I6** | **Historical Memory & Trend Awareness** | **🔲 Next** |
| I9 | Deployment & Delivery | 🔲 Planned |
| I7 | Evaluation Framework & Feedback Loop | 🔲 Planned |
| I8 | Dashboard & Visual Reporting | 🔲 Planned |
| I10 | Multi-File Data Consolidation | 🔲 Planned |

MVP = I1–I7 + I9 complete.

---

# Iteration 6 — Historical Memory & Trend Awareness

## Theme
Give the system memory across weeks. Every report today is stateless — it compares only the current week to the prior week. With historical context the system detects trajectories, consecutive signal patterns, and whether a metric is recovering or compounding.

## Goal
Pass multi-week trend facts to the LLM so it can produce situation summaries and key stories that reference trajectory — not just this-week delta.

---

## Task I6-1 — Findings Store and History Index

### Purpose
Build a lightweight index of historical runs so prior week metric values can be queried efficiently.

### What to Build
- On each pipeline run, after `findings.json` is written, register the run in a local index at `runs/index.json`
- Index record: `run_id`, `dataset_key`, `input_file`, `week_start`, `week_end`, `findings_path`
  - `dataset_key` is the primary isolation key — derived from the basename of the input file (without date suffix or extension). Example: `weekly_data_2026-03-03.csv` → `dataset_key: "weekly_data"`. This prevents trend queries from mixing runs from different businesses or data sources.
  - `input_file` is retained for full traceability but must not be used as the identity key on its own.
- `HistoryReader` class in `src/wbsb/history/store.py` — queries index **filtered by `dataset_key`** then by date range; returns ordered list of `(week_start, value)` tuples for any metric
- No external database — flat JSON file is sufficient for MVP

### Acceptance Criteria
- `runs/index.json` is created/updated after every pipeline run
- Each index entry contains `dataset_key` derived from the input filename
- `HistoryReader.get_metric_history(metric_id, dataset_key, n_weeks=4)` returns prior values in chronological order, scoped to that dataset only
- Runs from a different `dataset_key` never appear in query results
- First run (no index yet) creates the index gracefully
- All existing tests pass; new tests in `tests/test_history.py`
- Ruff clean

### Allowed Files
```
src/wbsb/history/store.py          ← new
src/wbsb/pipeline.py               ← register run in index after findings written
tests/test_history.py              ← new
```

---

## Task I6-2 — Deterministic Trend Classification

### Purpose
Classify each tracked metric's direction over the prior N weeks into a human-readable trend label. This is arithmetic over historical values — no interpretation.

### What to Build
- `src/wbsb/history/trends.py` — `compute_trends(history_reader, metric_ids, dataset_key, n_weeks=4)` returns a dict per metric:
  ```python
  {
    "cac_paid": {
      "trend_label": "rising",        # rising | falling | recovering | volatile | stable | insufficient_history
      "weeks_consecutive": 3,          # how many consecutive weeks in current direction
      "baseline_delta_pct": 0.47,      # vs N-week average
      "direction_sequence": ["up", "up", "up", "flat"]
    }
  }
  ```
- `trend_label` definitions:
  - `rising` — consecutive weeks up ≥ `min_consecutive` threshold
  - `falling` — consecutive weeks down ≥ `min_consecutive` threshold
  - `recovering` — was falling, now up for 1+ weeks
  - `volatile` — direction changes every week (alternating)
  - `stable` — all week-over-week changes within `stable_band_pct` for `stable_min_weeks` or more
  - `insufficient_history` — fewer than 2 prior data points available; computed but **excluded from LLM prompt**
- **Thresholds are config-driven** — all numeric trend thresholds must be read from `config/rules.yaml` under a `history:` key. No hardcoded numbers in `trends.py`.
  ```yaml
  # config/rules.yaml — to be added in this task
  history:
    min_consecutive: 2          # weeks needed to classify rising or falling
    stable_band_pct: 0.02       # ±2% week-over-week change = stable
    stable_min_weeks: 3         # minimum weeks of stability to label as stable
    n_weeks: 4                  # default lookback window
  ```
- Only tracks metrics that have signals in the current findings (not all 16 metrics)
- `dataset_key` is passed through to `HistoryReader` — trend engine never queries cross-dataset history

### Acceptance Criteria
- All six trend labels computed correctly and unit-tested (including `insufficient_history`)
- `insufficient_history` is returned in the dict when fewer than 2 prior weeks exist (not an empty dict)
- All thresholds read from `config/rules.yaml` — no magic numbers in `trends.py`
- Trend computation is scoped to `dataset_key` — cross-dataset contamination is tested and absent
- Ruff clean

### Allowed Files
```
src/wbsb/history/trends.py         ← new
config/rules.yaml                  ← add history: section
tests/test_history.py              ← extend
```

---

## Task I6-3 — Prompt Payload Extension

### Purpose
Include trend context in the LLM user prompt as stated facts. The LLM receives trajectory as ground truth — it does not infer it.

### What to Build
- Extend `build_prompt_inputs()` in `llm_adapter.py` to accept and include trend context
- Extend `user_full_v2.j2` with a TREND CONTEXT section:
  ```
  TREND CONTEXT (prior 4 weeks)
  cac_paid:              3 consecutive weeks rising | +47% vs 4-week average
  paid_lead_to_client:   2 consecutive weeks falling | -18% vs 4-week average
  gross_margin:          stable (within ±2% for 4 weeks)
  ```
- **Exclusion rule:** metrics with `trend_label: "insufficient_history"` are **not included** in the TREND CONTEXT section sent to the LLM. They exist in the internal trend dict for observability and testing, but provide no useful signal to the LLM.
- Section is omitted entirely when no metrics have a valid (non-`insufficient_history`) trend label
- `pipeline.py` calls `compute_trends()` and passes result to `render_llm()`; passes `dataset_key` through the call chain

### Acceptance Criteria
- Trend context appears in rendered user prompt when history exists
- `insufficient_history` metrics are present in `compute_trends()` output but absent from the rendered prompt
- Section absent entirely when no prior history (first run) or all metrics are `insufficient_history`
- Existing prompt structure and section order unchanged
- All existing tests pass; extend `tests/test_llm_adapter.py` for trend context
- Ruff clean

### Allowed Files
```
src/wbsb/render/llm_adapter.py          ← extend build_prompt_inputs()
src/wbsb/render/prompts/user_full_v2.j2 ← add TREND CONTEXT section
src/wbsb/pipeline.py                    ← compute trends, pass to render_llm()
tests/test_llm_adapter.py               ← extend
```

---

## Execution Workflow

For each task:

1. Create feature branch: `feature/i6-task-N-description`
2. Use Plan Mode if multi-file or behavioral change
3. Confirm allowed files before executing
4. Implement changes
5. Run: `pytest` and `ruff check .`
6. Commit with clear message
7. Push and open PR
8. Merge after review

Never combine multiple tasks in a single PR unless explicitly approved.

---

## Iteration 6 — Definition of Done

Iteration 6 is complete when:

- [ ] `runs/index.json` created and updated on every pipeline run (Task I6-1)
- [ ] `HistoryReader.get_metric_history()` returns correct historical values (Task I6-1)
- [ ] Trend labels computed correctly for all five trend types (Task I6-2)
- [ ] Trend context appears in LLM user prompt when history exists (Task I6-3)
- [ ] First run (no history) works gracefully — trend section omitted (Task I6-3)
- [ ] All existing 217+ tests pass
- [ ] Ruff clean
- [ ] `main` branch stable
