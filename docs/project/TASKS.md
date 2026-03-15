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
| **I6** | **Historical Memory & Trend Awareness** | **✅ Complete** |
| **I7** | **Evaluation Framework & Feedback Loop** | **✅ Complete** |
| **I9** | **Deployment & Delivery** | **✅ Complete** |
| **I11** | **Security Hardening & Production Readiness** | **🔲 In Progress** |
| I12 | Server Deployment & Production Operations | 🔲 Planned |
| I8 | Dashboard & Visual Reporting | 🔲 Planned |
| I10 | Multi-File Data Consolidation | 🔲 Planned |

MVP = I1–I7 + I9 complete.

---

# Iteration 6 — Historical Memory & Trend Awareness

## Theme
Give the system memory across weeks. Every report today is stateless — it compares only the current week to the prior week. With historical context the system detects trajectories, consecutive signal patterns, and whether a metric is recovering or compounding.

## Goal
Pass multi-week trend facts to the LLM so it can produce situation summaries and key stories that reference trajectory — not just this-week delta.

Full task detail: see `../iterations/i6/tasks.md`.

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
| I6-7 | You | Architecture review checklist | ✅ Done — passed (no issues) |
| I6-8 | Claude | Final cleanup + merge to main | ✅ Done — PR #32 |

---

## Branching Model

```
main
 └── feature/iteration-6                      ← integration branch (never PR to main directly)
      ├── feature/i6-1-history-config         (merged ✅)
      ├── feature/i6-2-history-store          (PR #27 ready ✅)
      ├── feature/i6-3-pipeline-integration   (PR #28 ready ✅)
      ├── feature/i6-4-trend-engine           (merged ✅)
      ├── feature/i6-5-llm-trend-context      (PR #30 merged ✅)
      ├── feature/i6-6-prompt-template        (PR #31 merged ✅)
      └── feature/i6-8-final-cleanup          (PR #32 ✅)
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

## Iteration 6 — Definition of Done

- [x] `runs/index.json` created/updated after every successful pipeline run — I6-2, I6-3
- [x] Each entry has all `RunRecord` fields with correct types — I6-2, I6-3
- [x] Failed runs never produce index entries — I6-3
- [x] Dataset isolation enforced — I6-2
- [x] All six trend labels computed correctly — I6-4
- [x] Zero hardcoded thresholds in `trends.py` — I6-4
- [x] `direction_sequence` never sent to LLM — I6-5
- [x] Trend context in LLM prompt when valid history exists — I6-5, I6-6
- [x] TREND CONTEXT absent on first run and when all `insufficient_history` — I6-5, I6-6
- [x] All 271 tests passing — I6-8
- [x] Ruff clean — I6-8
- [x] `runs/index.json` in `.gitignore` — I6-8
- [x] `main` branch stable — I6-8

---

# Iteration 7 — Evaluation Framework & Operator Feedback Loop

## Theme
Add a quality control layer around LLM output and a lightweight operator feedback loop. Every LLM run is automatically scored for grounding, signal coverage, and hallucination risk. Operators can label report sections; feedback is stored and queryable via CLI.

Full task detail: see `../iterations/i7/tasks.md`.

---

## Task Overview

| Task | Owner | Description | Status |
|------|-------|-------------|--------|
| I7-0 | Claude | Domain models, JSON schemas, eval config | ✅ Done — PR #34 merged |
| I7-1 | Codex | Numeric extraction utility | ✅ Done — PR #35 merged |
| I7-2 | Codex | Grounding scorer | ✅ Done — PR #39 merged |
| I7-3 | Codex | Signal coverage scorer | ✅ Done — PR #37 merged |
| I7-4 | Codex | Hallucination detector | ✅ Done — PR #38 merged |
| I7-5 | Claude | build_eval_scores() + pipeline integration | ✅ Done — PR #40 merged |
| I7-6 | Claude | Golden dataset runner + wbsb eval CLI | ✅ Done — PR #41 merged |
| I7-7 | Claude | Feedback storage + wbsb feedback CLI | ✅ Done — PR #36 merged |
| I7-8 | You | Architecture review | ✅ Done — PASS (all 16 checks) |
| I7-9 | Claude | Final cleanup + merge to main | ✅ Done |

---

## Iteration 7 — Definition of Done

**Evaluation Engine**
- [x] `eval_scores` written to `llm_response.json` on every successful LLM run
- [x] `eval_skipped_reason` set correctly on LLM fallback and scorer error
- [x] Grounding score computable (or null with reason when no numbers cited)
- [x] Signal coverage counts both WARN and INFO signals
- [x] Hallucination violations classified by type and severity
- [x] No hardcoded tolerance values — all read from `config/rules.yaml`
- [x] Scorer never breaks report generation

**Golden Dataset**
- [x] At least 6 cases present in `src/wbsb/eval/golden/`
- [x] `wbsb eval` runs all cases and exits 0 when all pass
- [x] `fallback_no_llm` case always present and always passing
- [x] Governance rules documented in `eval/golden/README.md`

**Feedback System**
- [x] `save_feedback()` validates run_id, section, label — raises ValueError on violation
- [x] Comment truncated to 1000 chars silently
- [x] `wbsb feedback list/summary/export` commands operational
- [x] `feedback/` directory gitignored, `.gitkeep` committed
- [x] No webhook server built in I7

**Quality**
- [x] 324 tests passing (271 baseline + 53 from I7)
- [x] Ruff clean
- [x] `domain/models.py` unchanged
- [x] `main` branch stable

---

# Iteration 9 — Deployment & Delivery

## Theme
Take WBSB from a local CLI tool to a deployed product: push delivery to Teams/Slack, automated scheduling, feedback webhook, Docker packaging, and secrets hardening.

Full task detail: see `../iterations/i9/tasks.md`.

---

## Task Overview

| Task | Owner | Description | Status |
|------|-------|-------------|--------|
| I9-0 | Claude | Docs update + package scaffolding | ✅ Done — merged |
| I9-1 | Codex | Delivery config schema (`config/delivery.yaml`) | ✅ Done — merged |
| I9-2 | Codex | Teams adaptive card builder + sender | ✅ Done — merged |
| I9-3 | Codex | Slack block kit builder + sender | ✅ Done — merged |
| I9-4 | Codex | Scheduler / file watcher (`wbsb run --auto`) | ✅ Done — merged |
| I9-5 | Claude | Delivery orchestrator (`wbsb deliver`) | ✅ Done — merged |
| I9-6 | Codex | Failure alerting (LLM fallback + pipeline error) | ✅ Done — merged |
| I9-7 | Codex | Feedback webhook server (`feedback/server.py`) | ✅ Done — merged |
| I9-8 | Claude | Docker + `.env.example` + security hardening | ✅ Done — merged |
| I9-9 | You | Architecture review | ✅ Done — PASS (2 findings fixed) |
| I9-10 | Claude | Final cleanup + merge to main | ✅ Done — this PR |

---

## Definition of Done — I9

All acceptance criteria met:

- **Delivery layer:** `wbsb deliver --run-id` and `wbsb run --deliver` dispatch to Teams/Slack via config-driven orchestrator; all delivery failures captured as `DeliveryResult` (never raises)
- **Scheduler:** `wbsb run --auto --watch-dir` discovers and processes the latest unprocessed file; path traversal guard and oversized file guard in place; scheduler boundary enforced (auto mode does not trigger delivery)
- **Feedback webhook:** `POST /feedback` validates run_id (regex), section, label (allowlists); body capped at 4096 bytes; UUID-only file paths; comment never logged; audit log limited to run_id/section/label
- **Docker:** image builds cleanly; `.env` excluded from image; runtime directories created; secrets injected at runtime only
- **CLI:** `wbsb feedback serve`, `wbsb feedback list/summary/export` all operational
- **Failure alerting:** LLM fallback and pipeline error alerts dispatched via delivery config; no silent failures — all alert dispatch failures emit visible warnings
- **Security:** no hardcoded secrets; no webhook URLs logged at INFO; no stack traces in HTTP error responses
- **Tests:** 391 passing (up from 324 baseline); ruff clean; all 6 golden eval cases pass
- **I9-9 findings resolved:** scheduler delivery boundary enforced; silent `except: pass` replaced with warnings; `RUN_ID_PATTERN` consolidated to single source of truth in `store.py`

---

## Branching Model

```
main
 └── feature/iteration-9                   ← integration branch
      ├── feature/i9-0-pre-work            ← docs + scaffolding (PR #44 — in progress)
      ├── feature/i9-1-delivery-config     ← delivery config schema
      ├── feature/i9-2-teams-adapter       ← Teams card builder
      ├── feature/i9-3-slack-adapter       ← Slack block builder
      ├── feature/i9-4-scheduler           ← file watcher + auto-run
      ├── feature/i9-5-delivery-orchestrator ← wbsb deliver command
      ├── feature/i9-6-failure-alerting    ← alerting banners
      ├── feature/i9-7-feedback-webhook    ← feedback HTTP endpoint
      └── feature/i9-8-docker             ← Docker + security
```

---

# Iteration 11 — Security Hardening & Production Readiness

## Theme
Move WBSB from a secured MVP to a defensible system for shared or hosted use. Add cryptographic authentication, replay protection, abuse controls, runtime hardening, supply chain scanning, and structured security observability to the feedback webhook.

Full task detail: see `../iterations/i11/tasks.md`.

---

## Task Overview

| Task | Owner | Description | Status |
|---|---|---|---|
| I11-0 | Claude | Pre-work: docs, frozen contract scaffolding | 🔲 In Progress |
| I11-1 | Codex | HMAC verification + timestamp freshness (`auth.py`) | 🔲 Blocked on I11-0 |
| I11-2 | Codex | Nonce store — replay prevention (`auth.py`) | 🔲 Blocked on I11-1 |
| I11-3 | Codex | Rate limiter (`ratelimit.py`) | 🔲 Blocked on I11-0 |
| I11-4 | Codex | Security observability (`observability/logging.py`) | 🔲 Blocked on I11-0 |
| I11-5 | Claude | Wire all guards into `server.py` + `cli.py` | 🔲 Blocked on I11-2, I11-3, I11-4 |
| I11-6 | Codex | Runtime hardening: Dockerfile non-root, file permissions | 🔲 Blocked on I11-0 |
| I11-7 | Codex | Supply chain: pip-audit, trivy, multi-stage Docker | 🔲 Blocked on I11-6 |
| I11-8 | You | Architecture review | 🔲 Blocked on I11-5, I11-6, I11-7 |
| I11-9 | Claude | Final cleanup + merge to main | 🔲 Blocked on I11-8 |

---

## Branching Model

```
main
 └── feature/iteration-11
      ├── feature/i11-0-pre-work
      ├── feature/i11-1-hmac-auth
      ├── feature/i11-2-nonce-store
      ├── feature/i11-3-rate-limiter
      ├── feature/i11-4-observability
      ├── feature/i11-5-server-integration
      ├── feature/i11-6-runtime-hardening
      └── feature/i11-7-supply-chain
```
