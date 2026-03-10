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

Full task detail: see `../iterations/iteration-6-tasks.md`.

---

## Task Overview

| Task | Owner | Description | Status |
|------|-------|-------------|--------|
| I6-0 | Claude | Architecture/docs update | ✅ Done — merged to main |
| I6-1 | Codex | Add `history:` section to `config/rules.yaml` | ✅ Done — merged to `feature/iteration-6` |
| I6-2 | Claude | History store + dataset-scoped HistoryReader | ✅ Done — PR #27 ready |
| I6-3 | Claude | Register completed runs in pipeline | ✅ Done — PR #28 ready |
| I6-4 | Claude | Deterministic trend engine (6 labels) | ✅ Done — PR #29 merged |
| I6-5 | Claude | Extend LLM adapter with trend context | ✅ Done — PR #30 merged |
| I6-6 | Codex | Update prompt template for trend context | ✅ Done — PR #31 merged |
| I6-7 | You | Architecture review checklist | 🔲 Next — depends on I6-6 |
| I6-8 | Claude | Final cleanup + merge to main | 🔲 Blocked on I6-7 |

---

## Branching Model

```
main
 └── feature/iteration-6                      ← integration branch (never PR to main directly)
      ├── feature/i6-1-history-config         (merged ✅)
      ├── feature/i6-2-history-store          (PR #27 ready ✅)
      ├── feature/i6-3-pipeline-integration   (PR #28 ready ✅)
      ├── feature/i6-4-trend-engine           (merged ✅)
      ├── feature/i6-5-llm-trend-context      (PR #30 ready ✅)
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

## Completed Tasks (continued)

### I6-4 — Trend Engine (PR #29)
- `src/wbsb/history/trends.py` — `compute_trends()`, `TrendResult`, 6 deterministic labels
- `tests/test_history.py` — 20 new trend classification tests (moved from test_trends.py after scope review)
- Tests: 242 → 262

### I6-5 — LLM Adapter Extension (PR #30)
- `src/wbsb/pipeline.py` — `HistoryReader`, `compute_trends()` call, `trend_context` → `render_llm()`
- `src/wbsb/render/llm.py` — `trend_context` param threaded to `build_prompt_inputs()` and `generate()`
- `src/wbsb/render/llm_adapter.py` — `build_prompt_inputs(ctx, trend_context)`, `_build_trend_context_for_prompt()`, `generate(ctx, ..., trend_context)`
- `tests/test_llm_adapter.py` — 6 unit tests for trend context filtering
- `tests/test_pipeline_history.py` — 1 pipeline integration test
- Tests: 262 → 269

---

## Next: I6-6 — Prompt Template Update (Codex)

Add TREND CONTEXT block to `src/wbsb/render/prompts/user_full_v2.j2`.
Receives `trend_context_for_prompt` list from `build_prompt_inputs()`.
Omit block entirely when list is empty.

---

## Iteration 6 — Definition of Done

- [x] `runs/index.json` created/updated after every successful pipeline run — I6-2, I6-3
- [x] Each entry has all `RunRecord` fields with correct types — I6-2, I6-3
- [x] Failed runs never produce index entries — I6-3
- [x] Dataset isolation enforced — I6-2
- [x] All six trend labels computed correctly — I6-4
- [x] Zero hardcoded thresholds in `trends.py` — I6-4
- [x] `direction_sequence` never sent to LLM — I6-5
- [ ] Trend context in LLM prompt when valid history exists — I6-5 ✅ wired, I6-6 template pending
- [ ] TREND CONTEXT absent on first run and when all `insufficient_history` — I6-5 ✅ filtered, I6-6 template pending
- [ ] All 269+ tests passing — ongoing
- [ ] Ruff clean — ongoing
- [ ] `runs/index.json` in `.gitignore` — I6-8
- [ ] `main` branch stable — I6-8
