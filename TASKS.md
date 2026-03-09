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
- Index record: `run_id`, `input_file`, `week_start`, `week_end`, `findings_path`
- `HistoryReader` class in `src/wbsb/history/store.py` — queries index by metric_id and date range, returns ordered list of `(week_start, value)` tuples for any metric
- No external database — flat JSON file is sufficient for MVP

### Acceptance Criteria
- `runs/index.json` is created/updated after every pipeline run
- `HistoryReader.get_metric_history(metric_id, n_weeks=4)` returns prior values in chronological order
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
- `src/wbsb/history/trends.py` — `compute_trends(history_reader, metric_ids, n_weeks=4)` returns a dict per metric:
  ```python
  {
    "cac_paid": {
      "trend_label": "rising",        # rising | falling | recovering | volatile | stable
      "weeks_consecutive": 3,          # how many consecutive weeks in current direction
      "baseline_delta_pct": 0.47,      # vs N-week average
      "direction_sequence": ["up", "up", "up", "flat"]
    }
  }
  ```
- `trend_label` definitions:
  - `rising` — 2+ consecutive weeks up
  - `falling` — 2+ consecutive weeks down
  - `recovering` — was falling, now up for 1+ weeks
  - `volatile` — direction changes every week
  - `stable` — all weeks within ±2%
- Only tracks metrics that have signals in the current findings (not all 16 metrics)

### Acceptance Criteria
- All five trend labels computed correctly and unit-tested
- `compute_trends()` returns empty dict gracefully when fewer than 2 prior weeks exist
- Ruff clean

### Allowed Files
```
src/wbsb/history/trends.py         ← new
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
- Section is omitted entirely when fewer than 2 prior weeks exist (first run graceful)
- `pipeline.py` calls `compute_trends()` and passes result to `render_llm()`

### Acceptance Criteria
- Trend context appears in rendered user prompt when history exists
- Section absent when no prior history (first run)
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
