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
| **I6** | **Historical Memory & Trend Awareness** | **🔄 In Progress** |
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

Full task detail: see `iteration-6-tasks.md`.

---

## Task Overview

| Task | Owner | Description | Status |
|------|-------|-------------|--------|
| I6-0 | Claude | Architecture/docs update | ✅ Done — merged to main |
| I6-1 | Codex | Add `history:` section to `config/rules.yaml` | ✅ Done — merged to `feature/iteration-6` |
| I6-2 | Claude | History store + dataset-scoped HistoryReader | ✅ Done — PR #27 ready |
| I6-3 | Claude | Register completed runs in pipeline | ✅ Done — PR #28 ready |
| I6-4 | Claude | Deterministic trend engine (6 labels) | 🔲 Next — depends on I6-2 |
| I6-5 | Claude | Extend LLM adapter with trend context | 🔲 Blocked on I6-3 + I6-4 |
| I6-6 | Codex | Update prompt template for trend context | 🔲 Blocked on I6-5 |
| I6-7 | You | Architecture review checklist | 🔲 Blocked on I6-6 |
| I6-8 | Claude | Final cleanup + merge to main | 🔲 Blocked on I6-7 |

---

## Branching Model

```
main
 └── feature/iteration-6                      ← integration branch (never PR to main directly)
      ├── feature/i6-1-history-config         (merged ✅)
      ├── feature/i6-2-history-store          (PR #27 ready ✅)
      ├── feature/i6-3-pipeline-integration   (PR #28 ready ✅)
      ├── feature/i6-4-trend-engine           ← next task branch
      ├── feature/i6-5-llm-trend-context
      └── feature/i6-6-prompt-template
```

`feature/iteration-6` → `main` via single PR after I6-7 architecture review passes.

---

## Completed Tasks

### I6-2 — History Store (PR #27)
- `src/wbsb/history/__init__.py` — package marker
- `src/wbsb/history/store.py` — `RunRecord`, `derive_dataset_key()`, `register_run()`, `HistoryReader`
- `tests/test_history.py` — 18 tests
- Tests: 217 → 235

### I6-3 — Pipeline Integration (PR #28)
- `src/wbsb/pipeline.py` — `derive_dataset_key()`, `week_end`, `RunRecord`, `register_run()` after `write_artifacts()`
- `tests/test_pipeline_history.py` — 7 integration tests
- Tests: 235 → 242

---

## Next: I6-4 — Deterministic Trend Engine

### Purpose
Classify each signal metric's direction over prior N weeks into one of six deterministic labels. Pure arithmetic — no interpretation, no LLM.

### What to Build
- `src/wbsb/history/trends.py` — `compute_trends(history_reader, metric_ids, n_weeks=None) -> dict[str, TrendResult]`
- Six labels: `rising` | `falling` | `recovering` | `volatile` | `stable` | `insufficient_history`
- All thresholds from `config/rules.yaml` → `history:` section (already added in I6-1)
- `insufficient_history` returned as explicit label when fewer than 2 prior data points

### Allowed Files
```
src/wbsb/history/trends.py         ← new
tests/test_trends.py               ← new
```

---

## Iteration 6 — Definition of Done

- [ ] `runs/index.json` created/updated after every successful pipeline run — I6-2, I6-3
- [ ] Each entry has all `RunRecord` fields with correct types — I6-2, I6-3
- [ ] Failed runs never produce index entries — I6-3
- [ ] Dataset isolation enforced — I6-2
- [ ] All six trend labels computed correctly — I6-4
- [ ] Zero hardcoded thresholds in `trends.py` — I6-4
- [ ] Trend context in LLM prompt when valid history exists — I6-5, I6-6
- [ ] TREND CONTEXT absent on first run and when all `insufficient_history` — I6-5, I6-6
- [ ] `direction_sequence` never sent to LLM — I6-5
- [ ] All 242+ tests passing — ongoing
- [ ] Ruff clean — ongoing
- [ ] `runs/index.json` in `.gitignore` — I6-8
- [ ] `main` branch stable — I6-8
