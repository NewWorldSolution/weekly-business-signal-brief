# WBSB — Project Iterations
## Weekly Business Signal Brief — Full Roadmap

**MVP Definition:** Iterations I1–I7 + I9 complete. **MVP is now complete.**
**Post-MVP execution order:** I11 (security hardening) → I12 (server deployment) → I8 (dashboard polish) → I10 (multi-file data consolidation). I11 runs first to secure the feedback endpoint before any shared deployment. I12 deploys to a real server and establishes the operational stack reused by future projects.

---

## Iteration Status Overview

| # | Theme | Status | MVP |
|---|---|---|---|
| I1 | Pipeline Foundation | ✅ Complete | ✅ |
| I2 | Signal Architecture | ✅ Complete | ✅ |
| I3 | Business Reporting Layer | ✅ Complete | ✅ |
| I4 | LLM Integration | ✅ Complete | ✅ |
| I5 | Analytical Reasoning Upgrade | ✅ Complete | ✅ |
| I6 | Historical Memory & Trend Awareness | ✅ Complete | ✅ |
| I7 | Evaluation Framework & Feedback Loop | ✅ Complete | ✅ |
| I9 | Deployment & Delivery | ✅ Complete | ✅ |
| I11 | Security Hardening & Production Readiness | ✅ Complete | — |
| I12 | Server Deployment & Production Operations | 🔲 Planned | — |
| I8 | Dashboard & Visual Reporting | 🔲 Planned | — |
| I10 | Multi-File Data Consolidation | 🔲 Planned | — |

---

---

# COMPLETED ITERATIONS

---

## Iteration 1 — Pipeline Foundation
**Status:** ✅ Complete

### Goal
Build a deterministic, reproducible analytics pipeline that ingests weekly business data and produces structured output.

### What Was Built
- **CSV/XLSX ingestion** via `wbsb.ingest.loader` — handles both formats, emits `AuditEvent` on coercion
- **Schema validation** via `wbsb.validate.schema` — enforces required columns, coerces types, derives computed columns (`ad_spend_total`, `leads_total`, `new_clients_total`, `net_revenue`)
- **Metric calculations** via `wbsb.metrics.calculate` — 16 deterministic metrics using `safe_div` for all divisions
- **Delta computation** via `wbsb.compare.delta` — absolute and percentage week-over-week change per metric
- **Basic report output** — raw metric table with deltas; no signal interpretation yet
- **Run artifacts** — `findings.json`, `logs.jsonl` per run

### Architecture Established
The separation of concerns that all subsequent iterations depend on:
```
CSV → Loader → Validator → Metrics → Deltas → Findings → Renderer
```
All thresholds live in `config/rules.yaml`. No hardcoded values in code.

### Key Files
`src/wbsb/ingest/loader.py`, `src/wbsb/validate/schema.py`, `src/wbsb/metrics/calculate.py`, `src/wbsb/compare/delta.py`, `src/wbsb/pipeline.py`

---

## Iteration 2 — Signal Architecture
**Status:** ✅ Complete

### Goal
Introduce structured business signals — named, rule-based events that represent meaningful business conditions.

### What Was Built
- **Signal registry** — 12 rules defined in `config/rules.yaml` covering revenue, acquisition, operations, financial health
- **Rule-based signal detection** via `wbsb.rules.engine` — 5 condition types: `delta_pct_lte`, `delta_pct_gte`, `absolute_lt`, `absolute_gt`, `hybrid_delta_pct_lte`
- **Signal severity levels** — WARN and INFO with priority ordering
- **Guardrail system** — signals skipped when volume is too low to be statistically meaningful (e.g. `requires_min_prev_net_revenue`)
- **Render context preparation** via `wbsb.render.context` — `prepare_render_context()` assembles template-ready data from findings
- **Manifest artifact system** — `manifest.json` per run with SHA-256 hashes of input file and config

### Signals Defined
Revenue decline, CAC spike, conversion rate falling, new clients falling, cancellation rate rising, bookings volume falling, gross margin below threshold, marketing spend overweight, contribution margin declining.

### Key Files
`config/rules.yaml`, `src/wbsb/rules/engine.py`, `src/wbsb/render/context.py`, `src/wbsb/findings/build.py`

---

## Iteration 3 — Business Reporting Layer
**Status:** ✅ Complete

### Goal
Convert signals into a readable, structured Markdown business brief. Reports should be usable by a non-technical operator without interpretation help.

### What Was Built
- **Signal narratives** — deterministic one-sentence descriptions per signal, generated from evidence values
- **Grouped signal rendering** — signals grouped by business category (Revenue, Acquisition, Operations, Financial Health) in the Jinja2 template
- **Executive summary generation** — first LLM-adjacent feature: a simple summary block at the top of the report (template-driven at this stage)
- **Markdown report formatting** — `template.md.j2` with Weekly Priorities, Signals, Key Metrics table, Data Quality, Audit sections
- **Weekly Priorities section** — WARN/INFO counts, top issue, category breakdown

### Key Files
`src/wbsb/render/template.py`, `src/wbsb/render/template.md.j2`

---

## Iteration 4 — LLM Integration
**Status:** ✅ Complete

### Goal
Introduce optional AI interpretation safely. LLM must never be a single point of failure.

### What Was Built
- **LLM adapter architecture** — `AnthropicClient` implementing `LLMClientProtocol`; model overrideable via `WBSB_LLM_MODEL` env var
- **Prompt templates** — `system_full_v1.j2` and `user_full_v1.j2`; versioned and Jinja2-rendered
- **Three LLM modes** — `--llm-mode off | summary | full` via Typer CLI
- **Deterministic fallback** — `render_llm()` falls back to `render_template()` on any LLM failure (timeout, invalid JSON, API error)
- **Artifact capture** — `llm_response.json` per run stores raw response, rendered prompts, model, timestamp, prompt hash
- **JSON validation** — `validate_response()` with schema validation and markdown fence stripping
- **Manifest LLM observability** — model, fallback flag, fallback reason recorded in `manifest.json`

### Safety Guarantee
`--llm-mode off` produces output identical to a run with no LLM configured. LLM failure in any mode produces the same output as `--llm-mode off`.

### Key Files
`src/wbsb/render/llm_adapter.py`, `src/wbsb/render/llm.py`, `src/wbsb/cli.py`

---

## Iteration 5 — Analytical Reasoning Upgrade
**Status:** ✅ Complete

### Goal
Move the LLM from per-signal summarization to structured, section-based analysis. The report structure defines what the LLM must produce — not the reverse.

### What Was Built

**I5-1 — Report Architecture and Output Contract**
- Locked final Markdown report structure and JSON output schema
- Extended `LLMResult` and `AdapterLLMResult` with four new section fields: `situation`, `key_story`, `group_narratives`, `watch_signals`
- Defined `dominant_cluster_exists` as a deterministic boolean: `max(WARN signals per category) >= 2`

**I5-2 — Deterministic Input Structuring**
- Replaced flat signal list in LLM prompt with category-clustered evidence
- Added business mechanism chains (paid acquisition funnel, operational chain)
- Added category health summary and co-movement relationship hints (neutral verbs only — no causal language)

**I5-3 — Prompt and LLM Contract Redesign**
- New `system_full_v2.j2` and `user_full_v2.j2` — section responsibilities defined explicitly
- `validate_response()` extended: grounding checks for `watch_signals` IDs, null enforcement for `key_story` when no dominant cluster
- Prompt version bumped to `full_v2`

**I5-4 — Rendering, Fallback, and Evaluation**
- All new sections wired into `template.md.j2` with conditional logic
- Python extraction helpers in `template.py` — no `llm_result` attributes accessed inside Jinja2
- `_extract_group_narratives()` normalizes display-name keys (`"Financial Health"`) to internal keys (`"financial_health"`)
- Each section degrades independently — no section failure blocks another

**Bugs Fixed During Evaluation**
1. `LLMResult` was never extended with I5-1 fields — Codex worked around it with `Any` typing; fixed by adding fields to domain model
2. Double `---` separator — both conditional blocks ended with their own separator plus an unconditional one; fixed by removing separators from inside conditional blocks
3. Group narratives never rendered — LLM returns display-name keys that didn't match internal template lookup; fixed with key normalization

**Model Comparison (from stress test)**

| Model | Grounding | Specificity | Cost/run | Verdict |
|---|---|---|---|---|
| Haiku 4.5 | ✅ Always valid | Low — generic language, no numbers | ~$0.003 | Functional fallback |
| Sonnet 4.5 | ✅ Always valid | High — specific figures, relationships | ~$0.023 | **Recommended default** |
| Opus 4.5 | ✅ Always valid | Highest — paradox detection, severity framing | ~$0.089 | Use for complex multi-signal weeks |

**Final state at I5:** ruff clean, all I5 branches merged to main. Baseline grew to 324 tests by end of I7.

### Key Files
`src/wbsb/render/template.py`, `src/wbsb/render/template.md.j2`, `src/wbsb/render/llm.py`, `src/wbsb/domain/models.py`, `tests/test_render_template.py`

---

---

# PLANNED ITERATIONS

---

## Iteration 6 — Historical Memory & Trend Awareness
**Status:** ✅ Complete | **MVP:** ✅ Required

### Goal
Give the system memory across weeks. Today every report is stateless — the LLM sees only this week vs last week. With historical context, the system can detect trajectories ("CAC has risen for 3 consecutive weeks, now up 47% from 4 weeks ago") and the LLM can reason about whether a metric is recovering, compounding, or stable.

### Why This Matters
The difference between "CAC rose 15% this week" and "CAC has risen every week for 6 weeks and is now 52% above its baseline" is the difference between a data point and an insight. Historical context is what makes the report operator-grade rather than data-grade.

### What to Build

#### 6.1 — Findings Store
A lightweight store that indexes historical `findings.json` files so they can be queried efficiently.

- On each run, after `findings.json` is written, register the run in a local index (`runs/index.json` or SQLite)
- Index records: `run_id`, `dataset_key`, `input_file`, `week_start`, `week_end`, `signal_count`, `findings_path`
  - `dataset_key` is the primary isolation key, derived from the input filename stem (e.g. `weekly_data_2026-03-03.csv` → `"weekly_data"`). It prevents trend queries from mixing runs across different businesses or data sources.
  - `input_file` is retained for full path traceability but must not be used as the identity key alone.
- `HistoryReader` class in `wbsb.history.store` — queries index **filtered by `dataset_key`** then by metric_id and date range; never returns results from a different dataset
- No external database required for MVP — flat JSON index file is sufficient

#### 6.2 — Trend Computation
Deterministic trend classification computed from the findings store before the LLM call.

For each metric in the current findings:
- Query prior 4 weeks of values from the store
- Compute: `direction_sequence` (up/down/flat per week), `trend_label` (rising / falling / recovering / volatile / stable), `weeks_consecutive` (how many consecutive weeks in current direction), `baseline_delta_pct` (vs 4-week average)

```python
# Example output
{
  "cac_paid": {
    "trend_label": "rising",
    "weeks_consecutive": 3,
    "baseline_delta_pct": 0.47,
    "direction_sequence": ["up", "up", "up", "flat"]
  },
  "gross_margin": {
    "trend_label": "insufficient_history",
    "weeks_consecutive": 0,
    "baseline_delta_pct": None,
    "direction_sequence": ["up"]
  }
}
```

Trend labels:
- `rising` — consecutive up weeks ≥ `min_consecutive`
- `falling` — consecutive down weeks ≥ `min_consecutive`
- `recovering` — previously falling, now up for 1+ weeks
- `volatile` — alternating direction every week
- `stable` — all week-over-week changes within `stable_band_pct` for `stable_min_weeks` or more
- `insufficient_history` — fewer than 2 prior data points; returned in the internal dict for observability and test coverage, but **excluded from the LLM prompt**

**All numeric thresholds are config-driven.** A `history:` section is added to `config/rules.yaml` in this task:
```yaml
history:
  min_consecutive: 2        # weeks to classify rising or falling
  stable_band_pct: 0.02     # ±2% = stable
  stable_min_weeks: 3       # minimum stable weeks to label as stable
  n_weeks: 4                # default lookback window
```
No magic numbers in `trends.py`.

Trend computation is purely arithmetic — no interpretation, no causal claims. `dataset_key` is passed through from the pipeline so the trend engine only reads history for the active dataset.

#### 6.3 — Prompt Payload Extension
Include historical context in the LLM user prompt as stated facts.

New prompt section added above current signals:

```
TREND CONTEXT (prior 4 weeks)
cac_paid:        3 consecutive weeks rising | +47% vs 4-week average
paid_lead_to_client: 2 consecutive weeks falling | -18% vs 4-week average
gross_margin:    stable (within ±2% for 4 weeks)
```

This gives the LLM trajectory as ground truth — it does not need to infer it.

**Exclusion rule:** metrics with `trend_label: "insufficient_history"` are not included in this section. The section is omitted entirely when no metrics have a valid trend label (first run, or all metrics have insufficient history).

#### 6.4 — Updated Report Sections
- **Situation** — LLM now has permission to reference trajectory, not just this-week delta
- **Key Story** — can now explain whether a cluster is worsening, recovering, or newly emerged
- **Watch Next Week** — can now reference trajectory: "If CAC rises for a 4th consecutive week, review paid channel allocation"

#### Acceptance Criteria
- `HistoryReader` can query prior 4 weeks of metric values for any metric_id
- Trend labels are computed deterministically and unit-tested
- Trend context appears in rendered user prompt
- LLM outputs reference trajectory when relevant (manual evaluation)
- Pipeline works correctly for first run (no prior history) — trend context section omitted gracefully
- All existing tests pass; new tests for `HistoryReader` and trend computation
- Ruff clean

#### Allowed Files
```
src/wbsb/history/store.py          ← new: HistoryReader, index management (dataset_key scoped)
src/wbsb/history/trends.py         ← new: deterministic trend classification (config-driven thresholds)
src/wbsb/render/llm_adapter.py     ← extend build_prompt_inputs() with trend context
src/wbsb/render/prompts/           ← extend user_full_v2.j2 with trend section
src/wbsb/pipeline.py               ← register run in history index; compute trends; pass dataset_key
config/rules.yaml                  ← add history: section with trend thresholds
tests/test_history.py              ← new
tests/test_llm_adapter.py          ← extend for trend context in prompt
```

---

## Iteration 9 — Deployment & Delivery
**Status:** ✅ Complete | **MVP:** ✅ Required

### Goal
Get the system running automatically on a server and delivering reports to where the operator already is. This is what makes WBSB a product rather than a local script.

### Why This Matters
The system can produce excellent reports but currently requires the operator to manually run `wbsb run -i file.csv` and then open a markdown file. Iteration 9 closes both gaps: automated execution and push delivery.

### What to Build

#### 9.1 — Containerisation
Package the application as a Docker container for reproducible deployment.

- `Dockerfile` — Python 3.11 slim base, installs dependencies from `pyproject.toml`
- `docker-compose.yml` — for local testing of the full stack
- Environment variables for configuration: `ANTHROPIC_API_KEY`, `WBSB_LLM_MODEL`, `WBSB_LLM_MODE`, delivery webhook URLs
- `runs/` directory mounted as a volume so artifacts persist across container restarts

#### 9.2 — Scheduled Pipeline Execution
Automated weekly run without manual intervention.

- Cron job or cloud scheduler triggers `wbsb run` each Monday morning (configurable)
- **Input source:** watches a configured folder (local path, mounted network share, or S3 bucket) for a new CSV/XLSX file matching a filename pattern (e.g. `weekly_data_*.csv`)
- If no new file is found since the last run, the scheduler logs a warning and skips — does not run on stale data
- Run result (success / fallback / error) logged and included in the delivery message

#### 9.3 — Teams / Slack Delivery
Push the report to a Teams channel or Slack workspace immediately after a successful run.

**Teams (Adaptive Card):**
- Formatted card with: run date, period, WARN signal count, top issue, situation paragraph
- Link to full `brief.md` artifact (if accessible) or full report pasted as text sections
- Action buttons for feedback (see I7 — Feedback Loop): "✅ Looks right", "⚠️ Unexpected", "❌ Something's wrong"

**Slack (Block Kit):**
- Header block with run metadata
- Situation and Key Story as text blocks
- Signal count and top signals as a compact list
- Action buttons for feedback

Both integrations use webhooks — no bot tokens required for delivery-only mode.

#### 9.4 — Failure Alerting
Notify the operator when the pipeline fails or degrades.

- LLM fallback triggered → delivery message includes a banner: "⚠️ AI analysis unavailable this week — showing deterministic report"
- Pipeline error (validation failure, missing columns, etc.) → alert message with error summary and the audit log
- No new data file found → reminder message: "No new weekly data detected. Upload a file to trigger the report."

#### 9.5 — Secrets & Security Hardening

Before I9 goes to any shared or hosted environment, confirm these controls are in place.

**Secrets management:**
- `.env.example` committed to the repo documenting every required env var (no real values, no defaults for secrets)
- `ANTHROPIC_API_KEY` and all webhook URLs sourced exclusively from environment variables — never from config files or code
- Docker image built with no secrets baked in; secrets injected at runtime via `--env-file` or orchestrator secrets
- `runs/index.json` and `runs/*/findings.json` must not contain the API key or webhook URLs (audit before first deployment)

**Webhook security:**
- Webhook URLs treated as credentials — rotation procedure documented in `config/delivery.yaml` comments
- Outbound webhook calls fail loudly (logged + alert) — never silently swallowed

**Logging hygiene:**
- No `os.environ` values printed in log output — confirm with a grep before release: `grep -r "environ" src/`
- `findings.json` and `llm_response.json` must not contain raw prompts that include secrets

**Input handling (scheduler):**
- File watcher validates that the input path is within the configured watch directory (no path traversal)
- Malformed or oversized input files rejected before pandas parsing

**Checklist (must be confirmed before I9 PR merge):**
- [ ] `.env.example` committed and up to date
- [ ] `grep -r "ANTHROPIC_API_KEY" src/` returns only env var reads, never hardcoded strings
- [ ] Docker image contains no `.env` file (`docker run --rm <image> ls -la | grep .env` returns nothing)
- [ ] Webhook URLs are not logged at INFO level

#### Acceptance Criteria
- `docker build` succeeds and `docker run` executes a pipeline run end-to-end
- Scheduler triggers a run on a configured cadence without manual intervention
- Report delivered to Teams or Slack within 5 minutes of pipeline completion
- LLM fallback state communicated clearly in the delivery message
- Failure states produce an alert, not silence
- All items in the 9.5 security checklist confirmed
- Ruff clean; Docker image builds on CI

#### Allowed Files
```
Dockerfile
docker-compose.yml
src/wbsb/delivery/teams.py         ← new: Adaptive Card builder and webhook sender
src/wbsb/delivery/slack.py         ← new: Block Kit builder and webhook sender
src/wbsb/scheduler/watcher.py      ← new: file watcher and run trigger
src/wbsb/cli.py                    ← add wbsb deliver command
config/delivery.yaml               ← new: webhook URLs, channel config, schedule
tests/test_delivery.py             ← new: card/block rendering tests (no live webhook calls)
```

---

## Iteration 7 — Evaluation Framework & Operator Feedback Loop
**Status:** ✅ Complete | **MVP:** ✅ Required

### Goal
Close the quality loop. By this point the system is live and delivering reports to real operators. Iteration 7 introduces two mechanisms: automated scoring that runs on every LLM output, and a structured feedback system that lets operators flag what's right, surprising, or wrong. Together, these create a compounding improvement cycle.

### What to Build

#### 7.1 — Automated Quality Scoring

Three dimensions scored on every LLM run, results appended to `llm_response.json`.

**Grounding Score** — are all cited numbers present in the payload?
- Extract numeric values from all LLM text fields using regex
- Build allowlist from findings evidence (current, previous, delta_abs, delta_pct, threshold values)
- Flag numbers not present in allowlist within ±0.5% rounding tolerance
- Score: `grounded_numbers / total_numbers_cited` → 0.0–1.0

**Signal Coverage Score** — did the LLM address all signals?
- Count `rule_ids` in `findings.signals`
- Count how many have a non-empty entry in `llm_result.signal_narratives`
- Check `group_narratives` covers all categories with signals
- Score: `signals_covered / signals_in_payload` → 0.0–1.0

**Hallucination Risk Count** — did the LLM reference anything that doesn't exist?
- `watch_signals` IDs verified against payload metric/rule IDs (already in `validate_response()` — now surfaced as a score)
- Category references in `situation` / `key_story` verified against payload categories
- `key_story` present when `dominant_cluster_exists=False` → hard violation
- Score: count of violations (0 = clean)

**Output format added to `llm_response.json`:**
```json
"eval_scores": {
  "grounding": 0.97,
  "signal_coverage": 1.0,
  "hallucination_risk": 0,
  "flagged_numbers": [],
  "flagged_references": [],
  "model": "claude-sonnet-4-5",
  "evaluated_at": "2026-04-07T09:00:00Z"
}
```

#### 7.2 — Operator Feedback Loop

Operators read the report in Teams or Slack (delivered by I9) and can label each section directly. This is the first human-in-the-loop quality signal.

**Feedback labels:**
- ✅ **Expected** — this accurately reflects what happened in the business this week
- ⚠️ **Unexpected** — surprising, may or may not be correct; worth investigating
- ❌ **Incorrect** — wrong data, fabricated numbers, or wrong interpretation

**How feedback is collected:**

*In Teams/Slack (primary path):*
The delivery card (built in I9) includes action buttons per major section. Operators click a label without leaving their messaging app. Feedback is sent to a webhook endpoint and stored.

*Fallback web form:*
A minimal HTML page linked from the delivery message — no login required, just run ID + section + label + optional comment. Stores to a local `feedback/` directory as JSON files.

**Security note for the feedback endpoint (`feedback/server.py`):**
- Validate that `run_id` in submitted feedback matches the format of a real run ID (regex: `^\d{8}T\d{6}Z_[a-f0-9]{6}$`) — reject anything that doesn't match before writing to disk
- `section` field must be one of a fixed allowlist (`situation`, `key_story`, `group_narratives`, `watch_signals`) — reject unknown values
- `comment` field: strip and cap at 1000 characters; no HTML rendering of this field anywhere
- Feedback files written only inside the `feedback/` directory — never allow `run_id` or `section` values to influence the file path
- No authentication required for MVP, but document this explicitly as a known limitation in `HOW_IT_WORKS.md`

**What feedback is stored:**
```json
{
  "run_id": "20260407T090000Z_abc123",
  "section": "situation",
  "label": "unexpected",
  "comment": "The situation says gross margin improved but we know costs went up this week",
  "operator": "optional free text name",
  "submitted_at": "2026-04-07T11:23:00Z"
}
```

#### 7.3 — Golden Dataset

A curated set of `(findings, llm_result, expected_criteria)` tuples used for regression testing. Built from real production runs labeled by operators.

Each golden case captures:
- The `findings.json` from a real run
- The `llm_response.json` from that run
- Operator feedback labels for that run
- Explicit pass/fail criteria (which sections should be present, which signals should be covered)

Cases are selected to cover the evaluation matrix:
| Case | Description |
|---|---|
| Clean week (0 signals) | Situation present, no Key Story, no Watch signals |
| Single dominant cluster | Key Story present, references dominant category |
| Independent signals | Key Story absent, group narratives only |
| Multi-cluster compound | Key Story for dominant; group narratives for others |
| Trending signal | Situation references trajectory from I6 context |
| Fallback (LLM absent) | Deterministic report only, no LLM sections |

#### 7.4 — `wbsb eval` CLI Command

A new CLI command that runs the golden dataset through the current pipeline and reports quality scores.

```bash
wbsb eval                              # run full golden dataset
wbsb eval --case clean_week           # run a single case
wbsb eval --model claude-opus-4-5     # compare against a different model
```

Output: per-case pass/fail, per-dimension scores, summary table. Exit code non-zero if any case fails — allows CI integration.

#### 7.5 — Feedback Review in CLI

```bash
wbsb feedback list                    # show recent operator feedback entries
wbsb feedback summary                 # score breakdown: % expected / unexpected / incorrect
wbsb feedback export --run-id <id>    # export feedback for a specific run
```

#### Acceptance Criteria
- Grounding, coverage, and hallucination scores computed and stored on every LLM run
- Operator can label a report section from the Teams/Slack delivery card
- Feedback stored as structured JSON with run_id and section reference
- At least 6 golden cases assembled from real production runs (after I9)
- `wbsb eval` passes all golden cases against current model/prompt configuration
- `wbsb feedback summary` shows aggregate label breakdown
- All existing tests pass; new tests for scorer functions and feedback storage
- Ruff clean

#### Allowed Files
```
src/wbsb/eval/scorer.py              ← new: grounding, coverage, hallucination scoring
src/wbsb/eval/golden/               ← new: curated test cases
src/wbsb/eval/runner.py             ← new: golden dataset runner
src/wbsb/feedback/store.py          ← new: feedback storage and query
src/wbsb/feedback/server.py         ← new: minimal webhook endpoint for Teams/Slack buttons
src/wbsb/cli.py                     ← add wbsb eval and wbsb feedback commands
src/wbsb/render/llm_adapter.py      ← append eval_scores to llm_response.json
tests/test_eval.py                  ← new
tests/test_feedback.py              ← new
```

---

## Iteration 8 — Dashboard & Visual Reporting
**Status:** 🔲 Planned | **Post-MVP**

### Goal
A web-based report viewer with trend charts and run history. This is the upgrade from "report delivered as text in Teams" to "polished analytics product with a UI."

### Why This Is Post-MVP
The Teams/Slack delivery from I9 gives operators what they need to make decisions. The dashboard enhances the experience but is not required for the system to be useful. I7's feedback loop also creates data that makes the dashboard more valuable — trend charts and quality scores are more meaningful with several weeks of production history behind them.

### What to Build

#### 8.1 — Web Application
A lightweight read-only web app. Technology choice: FastAPI backend + Jinja2 HTML templates for the MVP UI (no JavaScript framework required). Can be upgraded to a React frontend later.

#### 8.2 — Run History View
- List of all past runs: date, dataset name, WARN signal count, LLM mode, fallback flag
- Click-through to full report for any run
- Filter by date range, signal count, LLM mode

#### 8.3 — Report Viewer
- Renders `brief.md` as formatted HTML
- Section navigation (jump to Situation, Key Story, Signals, etc.)
- Eval scores displayed per run (from I7): grounding, coverage, hallucination risk
- Operator feedback labels shown inline (from I7)

#### 8.4 — Trend Charts
Simple sparkline charts for key metrics over the last 8 weeks (from I6 history store):
- Revenue, CAC, conversion rate, gross margin, contribution after marketing
- Signal firing history: which rules fired each week
- Chart library: lightweight (Chart.js or Plotly) — no heavy BI dependencies

#### 8.5 — Feedback UI
Web form alternative to Teams/Slack buttons for operators who prefer browser-based labeling.

#### 8.6 — Web Application Security

The dashboard is the first component with a real browser-facing attack surface. These controls are required before any deployment beyond localhost.

**Authentication:**
- HTTP Basic Auth gate in front of all routes (username + password via env vars `WBSB_DASH_USER` / `WBSB_DASH_PASS`)
- No unauthenticated route exposes run data, findings, or feedback
- Document the auth model in `HOW_IT_WORKS.md` — acknowledge it is not production-grade for multi-tenant use

**Output encoding:**
- All user-controlled content rendered via Jinja2 with `autoescape=True` — no `| safe` filter on any field sourced from data files or LLM output
- `brief.md` rendered to HTML via a Markdown library (e.g. `mistune`) — not via raw string interpolation

**CORS & headers:**
- `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` on all responses
- No CORS headers added unless a specific cross-origin use case is identified

**Logging hygiene:**
- Access logs must not echo query parameters that might contain tokens
- Error pages must not expose stack traces to the browser

**Checklist (must be confirmed before I8 PR merge):**
- [ ] `autoescape=True` confirmed in Jinja2 environment for all HTML templates
- [ ] Auth gate tested: unauthenticated request to `/` returns 401
- [ ] No `| safe` filter used on any field sourced from data or LLM output

#### Acceptance Criteria
- Web app accessible at configured URL after `docker-compose up`
- Run history list loads within 2 seconds for 52 weeks of history
- Report viewer renders all report sections correctly
- Trend charts render for all tracked metrics
- Feedback can be submitted from the web UI
- All items in the 8.6 security checklist confirmed

---

## Iteration 10 — Multi-File Data Consolidation
**Status:** 🔲 Planned | **Post-MVP**

### Goal
Accept multiple input files from different source systems and produce a single clean dataset that the pipeline can process. This solves the real-world problem where business data lives in 3–5 separate exports (bookings system, POS, ad platform, CRM) with inconsistent column names and date formats.

### Why This Is Last
The pipeline itself does not change. I10 is purely a pre-processing layer that sits upstream. All value from I1–I9 is available without it; I10 makes the system accessible to operators who can't produce a single pre-merged CSV.

### What to Build

#### 10.1 — Column Mapping Config
A `column_map.yaml` that maps source column names to WBSB standard names.

```yaml
sources:
  bookings_export:
    week_start: "Week Starting"
    bookings_total: "Total Appointments"
    show_rate: "Show Rate %"
  revenue_export:
    week_start: "Period Start Date"
    net_revenue: "Net Revenue (USD)"
  ad_spend_export:
    week_start: "Date"
    ad_spend_total: "Total Spend"
```

#### 10.2 — Consolidator Pipeline
```
[File 1: bookings.xlsx]  ─┐
[File 2: revenue.csv]    ─┼──► Consolidator ──► clean_dataset.csv ──► Pipeline
[File 3: ad_spend.xlsx]  ─┘
```

- Reads each source file, applies column mapping, coerces types
- Merges on `week_start` date (inner join by default; emits AuditEvent for missing weeks)
- Validates completeness — warns if required WBSB columns are missing after merge
- Writes `clean_dataset.csv` to a temp directory and hands off to the existing pipeline

#### 10.3 — CLI Integration
```bash
wbsb consolidate \
  --source bookings.xlsx:bookings_export \
  --source revenue.csv:revenue_export \
  --source ad_spend.xlsx:ad_spend_export \
  --output clean_dataset.csv

wbsb run -i clean_dataset.csv --llm-mode full
```

Or as a combined command:
```bash
wbsb run \
  --source bookings.xlsx:bookings_export \
  --source revenue.csv:revenue_export \
  --llm-mode full
```

#### Acceptance Criteria
- `wbsb consolidate` produces a valid WBSB input CSV from 2+ source files
- Column mapping is config-driven — no code changes needed to add a new source
- Missing columns after merge produce AuditEvents, not silent failures
- Existing `wbsb run -i file.csv` interface unchanged
- All existing tests pass; new tests for consolidation logic

---

## Iteration 11 — Security Hardening & Production Readiness
**Status:** ✅ Complete | **Post-MVP**

### Goal
Move WBSB from "deployable MVP" to "defensible for shared or hosted use." I9 introduces the first inbound HTTP surface (`POST /feedback`) and outbound delivery credentials (Slack/Teams webhooks). That is sufficient for an internal MVP but not for any deployment reachable by untrusted parties. I11 adds deliberate security controls across authentication, transport security, abuse prevention, secrets lifecycle, runtime hardening, supply chain, and observability.

---

### Threat Model

Before building controls, the threats must be named:

| Threat | Attack Vector | Impact |
|---|---|---|
| Unauthenticated feedback injection | Direct POST to `/feedback` from internet | Pollutes feedback store; disk fill |
| Replay attack | Re-sending a captured valid POST | Duplicate/forged feedback records |
| Credential exposure | Webhook URLs or API keys in logs/artifacts | Account takeover on Teams/Slack/Anthropic |
| Disk fill / DoS | Flood of large valid or invalid POSTs | Service unavailability |
| Container escape / lateral movement | Compromised process running as root | Host-level damage beyond feedback dir |
| Dependency supply chain | Vulnerable transitive Python package | RCE, credential theft |
| Information disclosure | Stack traces or paths in error responses | Reconnaissance for further attacks |
| Path traversal | Crafted file paths via user input | File read/write outside permitted dirs |
| TLS stripping | Plaintext HTTP in transit | Credential interception (auth header, payload) |

The MVP already mitigates path traversal (UUID-only file paths) and partial information disclosure (comment not logged). I11 closes the remaining gaps.

---

### What to Build

#### 11.1 — Transport Security (TLS Enforcement)

All traffic to `/feedback` must be encrypted. Plaintext HTTP exposes the `X-WBSB-Feedback-Secret` header and payload content to network-level interception.

**Requirements:**
- The server MUST be deployed behind a TLS-terminating reverse proxy (nginx, Caddy, Azure App Gateway, or equivalent). The Python HTTP server does not handle TLS directly — this is correct and intentional.
- If the request arrives without TLS evidence, the application SHOULD reject or warn based on a configurable `WBSB_REQUIRE_HTTPS=true` environment variable checked at startup.
- The `X-Forwarded-Proto` header MUST be validated when behind a proxy: requests arriving with `X-Forwarded-Proto: http` are rejected with HTTP 400.
- Document the required reverse proxy TLS configuration in `docs/deployment/tls.md`.
- Self-signed certificates are not acceptable for production; document minimum: Let's Encrypt (Certbot) or a CA-issued cert.

#### 11.2 — Feedback Endpoint Authentication (HMAC Shared Secret)

Add real, cryptographically verifiable authentication to `POST /feedback`.

**Mechanism: HMAC-SHA256 request signing**

Every request must include:
- `X-WBSB-Timestamp`: Unix timestamp (seconds) of request creation
- `X-WBSB-Signature`: `HMAC-SHA256(secret, f"{timestamp}.{body_bytes}")`

The server verifies:
1. `X-WBSB-Timestamp` is within ±300 seconds of server time (timestamp freshness window — this also serves as replay protection, see 11.3)
2. HMAC verification using `hmac.compare_digest()` — constant-time comparison, prevents timing attacks
3. Reject with HTTP 401 if the header is absent or fails verification
4. Reject with HTTP 400 if the timestamp is malformed

**Implementation notes:**
- Secret sourced exclusively from `WBSB_FEEDBACK_SECRET` environment variable; server refuses to start if unset in non-dev mode
- Use Python stdlib `hmac` and `hashlib` — no new dependencies
- Never log the raw secret or signature value
- Do not use a static "dev bypass" in production builds; use a `WBSB_ENV=development` guard that requires explicit opt-in

**Why HMAC over a plain shared secret header:**
A plain header check (`X-WBSB-Feedback-Secret: mytoken`) is vulnerable to replay (captured token reused indefinitely). HMAC-SHA256 with a timestamp binds the signature to the exact request and time window, making captured requests useless after 5 minutes.

#### 11.3 — Replay Attack Prevention

Replay protection is built into the HMAC scheme (11.2) via timestamp freshness. However, within the 5-minute window, the same signed payload can still be replayed.

**Additional nonce-based deduplication:**
- Require a `X-WBSB-Nonce` header (UUID4 or random 128-bit hex)
- Server maintains an in-memory nonce store (TTL = 10 minutes, 2× the timestamp window)
- Any nonce seen more than once within the TTL is rejected with HTTP 409 Conflict
- Nonce store is bounded: maximum 10,000 entries; oldest entries evicted when full (LRU or FIFO)

**Limitations to document:**
- The nonce store is in-process and does not survive restart. On restart, the freshness window is the only protection for the first 5 minutes.
- For multi-instance deployments, a shared store (Redis or equivalent) is required. Document this explicitly as an upgrade path.

#### 11.4 — Rate Limiting and Abuse Controls

Prevent disk fill and denial-of-service from flood traffic.

**Per-IP rate limiting:**
- Maximum 10 requests per 60-second sliding window per source IP
- Burst allowance: 3 additional requests above limit before backpressure
- Return HTTP 429 with `Retry-After` header when limit exceeded
- Implemented in-process using a sliding window counter (token bucket acceptable)

**Global rate limiting:**
- Maximum 100 requests per 60 seconds across all IPs (circuit breaker for coordinated floods)
- Return HTTP 503 with `Retry-After` when global limit exceeded

**Implementation constraints:**
- Use Python stdlib only; no external rate-limiting libraries
- In-memory only; state does not persist across restarts (document this limitation)
- For multi-instance or persistent rate limiting, document Redis upgrade path

**Structured rejection logging:**
- Log `rate_limit_exceeded` event with: source IP (pseudonymized — last octet zeroed), rate_window, request_count
- Never log request body or headers in rejection log entry

#### 11.5 — Secrets Lifecycle Management

Standardize how every secret is sourced, rotated, and audited across all deployment environments.

**Required secrets:**
| Variable | Purpose | Required for |
|---|---|---|
| `WBSB_FEEDBACK_SECRET` | HMAC signing key for `/feedback` | Production deployment |
| `TEAMS_WEBHOOK_URL` | Outbound Teams delivery | Teams delivery |
| `SLACK_WEBHOOK_URL` | Outbound Slack delivery | Slack delivery |
| `ANTHROPIC_API_KEY` | LLM narrative generation | `--llm-mode full` |

**Requirements:**
- Document all secrets in `.env.example` with placeholder values and descriptions — never real values
- Secrets are injected at runtime only: environment variables, Docker secrets (`--secret`), or a secrets manager
- No secrets in Docker image layers; verify with `docker history --no-trunc wbsb` and image scan
- Rotation: webhook URLs and the HMAC secret must be rotatable without code changes (env var only)
- Add a pre-flight check: server logs a startup warning (not error) for each optional secret that is absent; fails hard for required secrets
- Add `pip-audit` to CI to catch known CVEs in Python dependencies before merge

**What is out of scope for I11:**
- Automatic secret rotation (e.g., Azure Key Vault rotation triggers)
- Vault agent sidecar patterns
These are documented as upgrade paths, not implemented.

#### 11.6 — Dependency and Supply Chain Security

Vulnerable transitive dependencies are a real attack vector. I11 adds automated controls.

**Requirements:**
- Add `pip-audit` to the CI pipeline; build fails on any HIGH or CRITICAL CVE
- Pin all direct dependencies to exact versions in `pyproject.toml` (`==` not `>=`)
- Generate and commit `requirements.lock` (or use `pip-compile`) for reproducible builds
- Docker image: add `trivy` image scan step to CI; fail on CRITICAL severity
- Do not install build tools (`gcc`, `build-essential`) in the final production image; use multi-stage Docker build

#### 11.7 — File and Runtime Hardening

Reduce blast radius if the process is compromised.

**Container hardening:**
- Run as a dedicated non-root user (`USER wbsb`, UID 1000) in Dockerfile
- Set `read_only: true` on all container mounts except `runs/`, `feedback/`, and temp dirs
- Use `--cap-drop=ALL` in Docker / compose; add back only what is explicitly required (none expected)
- Avoid `privileged: true` in any compose configuration
- Use distroless or slim base image; document justification for any added packages

**File permission hardening:**
- Feedback JSON artifacts created with mode `0o600` (owner-read-only)
- Log files created with mode `0o640` (owner-read-write, group-read)
- The `feedback/` directory created with mode `0o700`

**Error response hardening:**
- All HTTP error responses return only: `{"status": "error", "message": "<user-safe string>"}`
- Stack traces, file paths, module names, and Python version must never appear in HTTP responses
- Verify with test: inject invalid JSON, oversized body, bad signature — assert no stack trace in response body

#### 11.8 — Security Observability

Provide enough visibility to detect and investigate misuse without leaking sensitive data.

**Required structured log events:**

| Event | Fields | Never log |
|---|---|---|
| `auth_failure` | source_ip (pseudonymized), reason, timestamp | secret, signature, request body |
| `rate_limit_exceeded` | source_ip (pseudonymized), window, count | request body, headers |
| `replay_detected` | nonce (truncated), timestamp_delta | request body, secret |
| `feedback_received` | run_id, section, label | comment, feedback_id, operator |
| `invalid_input` | field, reason | field value |

**Pseudonymization:** Source IP last octet zeroed before logging (e.g., `192.168.1.0` not `192.168.1.47`). Document that full IPs may be available in reverse proxy access logs, not application logs.

**Alerting guidance (operational, not code):**
- Document thresholds that suggest active attack: >50 auth failures in 5 minutes, >200 rate limit rejections in 1 minute
- Document how to connect structured logs to an alerting tool (Grafana Loki, Datadog, Azure Monitor) — integration itself is out of scope

---

### Acceptance Criteria

**Authentication:**
- `POST /feedback` with missing `X-WBSB-Signature` returns HTTP 401
- `POST /feedback` with invalid HMAC returns HTTP 401
- `POST /feedback` with expired timestamp (>300s) returns HTTP 401
- `POST /feedback` with replayed nonce returns HTTP 409
- `POST /feedback` with valid HMAC and fresh nonce returns HTTP 200

**Transport:**
- `X-Forwarded-Proto: http` request rejected with HTTP 400 when `WBSB_REQUIRE_HTTPS=true`
- TLS deployment documented in `docs/deployment/tls.md`

**Rate limiting:**
- 11th request in 60-second window from same IP returns HTTP 429 with `Retry-After` header
- Global circuit breaker triggers at 100 req/60s and returns HTTP 503

**Secrets:**
- Server refuses to start without `WBSB_FEEDBACK_SECRET` in non-dev mode
- No secrets appear in `docker history --no-trunc wbsb` output
- `.env.example` documents all four required variables with descriptions
- `pip-audit` passes with no HIGH or CRITICAL CVEs

**Runtime hardening:**
- Container process runs as UID 1000 (non-root); `docker inspect` confirms
- Feedback artifacts created with permissions `0o600`
- HTTP error responses contain no stack traces, paths, or module names

**Observability:**
- `auth_failure` event logged on every rejected request; no secret in log entry
- `rate_limit_exceeded` event logged with pseudonymized IP
- `comment` field never appears in any log event

**Regression:**
- All existing tests pass; ruff clean
- `wbsb eval` golden cases all pass
- Valid authenticated requests behave identically to current behaviour

---

### Suggested Files
```text
src/wbsb/feedback/server.py         ← auth, replay, rate limiting middleware
src/wbsb/feedback/auth.py           ← HMAC verification, nonce store (new)
src/wbsb/feedback/ratelimit.py      ← rate limiter (new)
src/wbsb/cli.py                     ← WBSB_REQUIRE_HTTPS startup check
src/wbsb/observability/logging.py   ← pseudonymization helper
Dockerfile                          ← non-root user, multi-stage, distroless
docker-compose.yml                  ← cap-drop, read-only mounts
.env.example                        ← all secrets documented
docs/deployment/tls.md             ← TLS and reverse proxy setup (new)
docs/deployment/security.md        ← threat model, controls summary (new)
tests/test_feedback_auth.py         ← HMAC, nonce, timestamp tests (new)
tests/test_feedback_ratelimit.py    ← rate limit and 429/503 tests (new)
tests/test_security_hardening.py    ← error response hygiene, non-root (new)
.github/workflows/security.yml      ← pip-audit + trivy CI step (new)
```

### Out of Scope
- OAuth 2.0 / OpenID Connect / SSO
- Multi-tenant RBAC or per-operator access control
- Automatic secret rotation (Azure Key Vault rotation triggers, Vault agent)
- SIEM integration or log forwarding configuration
- Formal penetration testing or third-party security audit
- Web Application Firewall (WAF) configuration
- DDoS mitigation beyond in-process rate limiting (use hosting-layer controls for volumetric attacks)

### Definition of Done
WBSB can be deployed to a shared or hosted environment with:
- every inbound request cryptographically authenticated and replay-protected
- abuse controls that prevent disk fill and service exhaustion
- all secrets injected at runtime with no baked-in values
- TLS enforced at the transport layer and validated at the application layer
- container running as non-root with minimal writable surface
- supply chain protected by CVE scanning and pinned dependencies
- security-relevant events observable in structured logs without sensitive data leakage
- a written threat model, controls summary, and deployment security guide

At the end of I11, WBSB's security posture rests on deliberate, testable controls — not perimeter assumptions.

---

## Iteration 12 — Server Deployment & Production Operations
**Status:** 🔲 Planned | **Post-MVP**
**Prerequisites:** I11 (Security Hardening) must be complete before deploying to any server reachable from outside localhost.

### Goal
Deploy WBSB to a real Linux server so it runs autonomously: the scheduler fires on schedule, reports are delivered to Teams/Slack without manual intervention, and the feedback endpoint is reachable over HTTPS. This iteration also establishes the operational knowledge and server stack that will be reused for future projects (cash flow bot and others).

### Why This Is Needed
After I9 and I11, WBSB is fully packaged and secured. But it still requires a developer to start it manually on a local machine. I12 makes it run autonomously on a real server, establishes operational discipline (deployment workflow, secrets management, health checks), and gives the operator direct experience with Linux server management — a transferable skill across all future projects.

---

### Task Overview

| Task | Owner | Description |
|---|---|---|
| I12-0 | Claude | Docs update, deployment target decision, `docs/deployment/` structure |
| I12-1 | You | VPS provisioning + initial server setup (runbook only, no code) |
| I12-2 | Codex | `docker-compose.prod.yml` — restart policies, named volumes, data bind mount, health checks |
| I12-3 | Codex | `Caddyfile` + TLS docs (`docs/deployment/tls.md`) |
| I12-4 | Claude | `Makefile` with all standard targets; backup implementation; smoke test script |
| I12-5 | Codex | `GET /health` endpoint in `src/wbsb/feedback/server.py` |
| I12-6 | Claude | Scheduler production config + `docs/deployment/scheduler.md` |
| I12-7 | Claude | `docs/deployment/env-management.md` + `docs/deployment/operations.md` |
| I12-8 | You | Architecture review |
| I12-9 | Claude | Final cleanup + merge to main |

---

### Branching Model

```
main
 └── feature/iteration-12                    ← integration branch
      ├── feature/i12-0-pre-work             ← docs structure + deployment decision
      ├── feature/i12-2-prod-compose         ← docker-compose.prod.yml
      ├── feature/i12-3-caddy-tls            ← Caddyfile + tls.md
      ├── feature/i12-4-makefile             ← Makefile + smoke_test.sh
      ├── feature/i12-5-health-endpoint      ← GET /health
      ├── feature/i12-6-scheduler            ← scheduler config + docs
      └── feature/i12-7-runbooks             ← env-management.md + operations.md
```

`feature/iteration-12` → `main` via single PR after I12-8 architecture review passes.

---

### Deployment Target Decision

I12 supports two deployment paths. Choose one before starting. The tasks below are written for **Path A (VPS)**. Path B differences are noted per task.

| | Path A — VPS (Hetzner/DigitalOcean) | Path B — Azure Container Apps |
|---|---|---|
| **Cost** | €4–$6/month | $0–5/month (free tier likely sufficient) |
| **Learning value** | High — Linux, Docker, SSH, cron, firewall | High — Azure CLI, container registry, managed infra |
| **Complexity** | You manage the OS and Docker | Azure manages the OS; you manage the app |
| **TLS** | Caddy handles automatically | Azure handles automatically |
| **Scheduler** | Host cron | Azure Container Apps Jobs (scheduled) |
| **Teams integration** | Natural (outbound HTTP) | Natural (outbound HTTP) |
| **Portfolio signal** | DevOps fundamentals | Enterprise cloud (relevant for Polish market) |
| **Recommended if** | You want to understand how servers work | You want to leverage existing M365 subscription |

Both paths produce the same end result. Path B is documented as an alternative in `docs/deployment/azure.md`. The runbook tasks below follow Path A; Path B equivalents are noted where they diverge significantly.

---

### What to Build

#### 12.1 — Server Provisioning and Initial Setup

**Path A — VPS:**

Recommended providers:

| Provider | Spec | Cost | Notes |
|---|---|---|---|
| **Hetzner CX22** | 2 vCPU, 4 GB RAM | ~€4/month | Best value, Helsinki or Warsaw DC |
| DigitalOcean Droplet | 1 vCPU, 1 GB RAM | $6/month | More documentation available |

**Server setup steps (all documented in `docs/deployment/server-setup.md`):**
- Provision Ubuntu 24.04 LTS
- Install Docker and Docker Compose
- Create non-root deploy user (`wbsb`) with sudo
- SSH key authentication only — password auth disabled
- UFW firewall: ports 22 (SSH), 80 (HTTP), 443 (HTTPS) allowed; all others denied
- System timezone set to match business location
- Clone the repo: `git clone <repo> /opt/wbsb` — required for `make deploy` (git pull model)
- Create `/opt/wbsb/data/` for weekly input files

**Path B — Azure Container Apps:**
- Create Azure free account
- Install Azure CLI
- Create Container Apps environment via `az containerapp env create`
- Push Docker image to Azure Container Registry
- Documented in `docs/deployment/azure.md`; Makefile targets adapted accordingly

No code changes in either path.

#### 12.2 — Production Docker Compose Configuration

Create `docker-compose.prod.yml` separate from the development compose file.

Production-specific differences from the dev compose:
- `restart: unless-stopped` on all services — containers restart after server reboot
- Environment variables sourced from `.env` file on server (not committed to repo)
- Named Docker volumes for `runs/`, `feedback/`, `logs/` — data survives container recreation
- A `data` bind mount mapping `/opt/wbsb/data` on the host to `/data` in the pipeline container — this is the production input-ingest path where the operator drops weekly source files
- No development bind mounts (`./src:/app/src` etc.) in production
- Health check defined for the feedback server container
- Resource limits: `mem_limit: 512m` on pipeline container; `mem_limit: 128m` on feedback server

#### 12.3 — Reverse Proxy with TLS (Caddy)

Caddy is recommended over nginx for first-time server operators: automatic Let's Encrypt certificate management with zero manual renewal.

**Pre-condition:** The operator must purchase a domain and point a DNS A record to the server IP before Caddy can obtain a Let's Encrypt certificate. DNS propagation (typically 5–60 minutes) must complete before the TLS acceptance criteria can be evaluated. Domain purchase and DNS configuration are operator responsibilities, but they are a required pre-condition for this task — not optional.

**Deliverables:**
- `Caddyfile` committed to repo with placeholder domain (`feedback.yourdomain.com`)
- TLS configuration documented in `docs/deployment/tls.md` (referenced in I11), including DNS pre-condition and A record setup
- Caddy runs as a separate container in the compose stack
- WBSB feedback server is not exposed directly — all inbound traffic goes through Caddy

**Config pattern:**
```
feedback.yourdomain.com {
    reverse_proxy feedback-server:8000
}
```

**Why Caddy over nginx:** Caddy handles Let's Encrypt certificate issuance and renewal automatically. Nginx requires manual `certbot` setup and cron jobs. For a single-server deployment operated by one person, Caddy reduces operational overhead significantly.

#### 12.4 — Environment and Secrets Management on Server

Establish a consistent, safe pattern for managing secrets on the server.

**Requirements:**
- `.env` file on server at `/opt/wbsb/.env`, owned by deploy user, permissions `0o600`
- Documented process for adding or rotating a secret (edit `.env`, restart affected container)
- Rotation of any single secret requires only one command: `make restart-feedback` or equivalent
- Never `git pull` secrets — they live only on the server, never in the repo

**Deliverable:** `docs/deployment/env-management.md` — covers initial setup, rotation procedure, and what to do if a secret is compromised.

#### 12.5 — Deployment Workflow (Makefile)

A `Makefile` with standard targets that wrap Docker Compose commands. Reduces operator error by making all common operations one-liners.

```makefile
deploy:       ## git pull + docker compose up --build -d (brief restart, typically <30s)
logs:         ## Tail logs from all containers
status:       ## Show container health, uptime; reads last entry from runs/index.json
restart:      ## Restart all containers
backup:       ## Archive runs/, feedback/, and data/ to dated tarball in /opt/wbsb/backups/
smoke-test:   ## Send HMAC-signed POST /feedback and assert HTTP 200 (requires WBSB_FEEDBACK_SECRET in env)
```

**Deployment model:** `make deploy` runs `git pull` on the server (repo cloned at `/opt/wbsb` in 12.1) then `docker compose up --build -d`. Containers are rebuilt from the updated source and recreated. There is a brief interruption (<30 seconds typically) while the feedback server restarts. This is acceptable for a low-traffic internal tool. Zero-downtime blue-green deployment is documented as an upgrade path, not implemented in I12.

**Backup implementation note:** Named Docker volume backup uses `docker run --rm -v wbsb_runs:/runs -v /opt/wbsb/backups:/backup alpine tar czf /backup/wbsb-$(date +%Y%m%d).tar.gz /runs /feedback /data`. This pattern is documented in the Makefile comments.

**`smoke_test.sh` note:** The script reads `WBSB_FEEDBACK_SECRET` from the environment (sourced from `.env` before running). Never hardcode the secret in the script.

#### 12.6 — Health Check Endpoint

Add a minimal `GET /health` route to the feedback server.

**Response:** `{"status": "ok", "timestamp": "<ISO8601>"}` — HTTP 200 always (no auth required).

Used by:
- Docker health check in `docker-compose.prod.yml`
- Caddy upstream health probing
- `make smoke-test` script
- Any external uptime monitor (UptimeRobot free tier is sufficient)

**Allowed files:** `src/wbsb/feedback/server.py`

#### 12.7 — Scheduler Production Configuration

Configure `wbsb run --auto` to run on a production schedule.

Two options (both documented; implement whichever fits the chosen hosting):

**Production input-ingest path:** Weekly source files are placed by the operator into `/opt/wbsb/data/` on the server. This directory is bind-mounted to `/data` inside the pipeline container (defined in 12.2). The operator (or assistant) transfers the file to the server via SCP (`scp weekly_data.csv wbsb@server:/opt/wbsb/data/`) or SFTP. This step is documented in `docs/deployment/scheduler.md` and in the operations runbook (12.8). The scheduler then picks up the latest unprocessed file automatically.

**Option A — Host cron (recommended for VPS):**
```cron
0 6 * * 1 docker compose -f /opt/wbsb/docker-compose.prod.yml run --rm pipeline wbsb run --auto --watch-dir /data
```

**Option B — Docker restart-on-completion pattern:**
A separate `pipeline` service in `docker-compose.prod.yml` that runs, exits, and is restarted by a cron-based Docker trigger.

**No-file behaviour:** If no new file is present in `/data` when the scheduler fires, `wbsb run --auto` exits gracefully with no run artifact (I9 behaviour). This is expected every week until the operator uploads the file. The operations runbook documents: "if no report arrives by 7am Monday, check that the data file was uploaded to `/opt/wbsb/data/` before 6am."

**Deliverable:** `docs/deployment/scheduler.md` — production schedule configuration, input file transfer procedure, how to verify a run fired, how to manually trigger a run, what to do if no file was present.

#### 12.8 — Basic Operational Runbook

Document how to operate the system day-to-day without a developer present. Intended audience: the business owner or a non-technical assistant.

**Contents of `docs/deployment/operations.md`:**
- How to tell if the Monday report ran successfully
- How to re-trigger a run manually
- What to do if the report was not delivered
- How to check container logs
- How to rotate an API key or webhook URL
- How to restore from backup

**`scripts/smoke_test.sh`:** A shell script that sends a valid HMAC-signed `POST /feedback` request and asserts HTTP 200. Run after every deployment to confirm the system is operational.

---

### Acceptance Criteria

**Deployment:**
- `docker compose -f docker-compose.prod.yml up -d` starts all services on a fresh VPS from the documented setup runbook
- All containers show `healthy` status after startup

**TLS and network** *(evaluated after DNS A record is pointed to the server IP):*
- `https://feedback.yourdomain.com/health` returns `{"status": "ok"}` with a valid Let's Encrypt certificate
- `http://` request redirects to `https://` (Caddy default behaviour)
- `POST /feedback` with `X-Forwarded-Proto: http` returns HTTP 400 (I11 requirement verified in production)
- If DNS is not yet configured, TLS acceptance is deferred; all other criteria must still pass using the server IP directly on HTTP (Caddy self-signed or HTTP-only mode for local validation)

**Scheduler:**
- Scheduler fires at configured time; run artifact written to named volume without manual intervention
- Delivery dispatched to Teams or Slack within 5 minutes of pipeline completion
- `make status` shows timestamp of last successful run

**Security (verify I11 controls are active in production):**
- `POST /feedback` without valid HMAC returns HTTP 401
- `POST /feedback` with valid HMAC and fresh nonce returns HTTP 200 over HTTPS
- `docker inspect` confirms containers run as UID 1000 (non-root)
- No secrets appear in `docker history --no-trunc wbsb` output

**Operations:**
- `make deploy` completes without manual steps; containers restart cleanly
- `make backup` produces a dated archive of `runs/` and `feedback/` volumes
- `make smoke-test` passes end-to-end after a clean deploy
- `docs/deployment/` contains: `server-setup.md`, `tls.md`, `env-management.md`, `scheduler.md`, `operations.md`

**Regression:**
- All existing tests pass locally; ruff clean
- `wbsb eval` golden cases all pass

---

### Suggested Files
```text
docker-compose.prod.yml                ← production compose (new)
Caddyfile                              ← reverse proxy config (new)
Makefile                               ← operational commands (new or extended)
scripts/smoke_test.sh                  ← deployment smoke test (new)
src/wbsb/feedback/server.py            ← add GET /health route
docs/deployment/server-setup.md        ← VPS provisioning runbook (new)
docs/deployment/azure.md               ← Azure Container Apps alternative path (new)
docs/deployment/tls.md                 ← TLS setup guide (new; referenced by I11)
docs/deployment/env-management.md      ← secrets management guide (new)
docs/deployment/scheduler.md           ← scheduler production config + input ingest (new)
docs/deployment/operations.md          ← day-to-day operations runbook (new)
```

### Out of Scope
- Multi-server or high-availability deployment
- CI/CD pipeline that auto-deploys on push to main (documented as upgrade path)
- External monitoring services (Grafana, Datadog) — documented as upgrade path
- Database migration (WBSB uses file-based storage; no database setup required in I12)
- Custom domain purchase and DNS A record configuration — operator pre-condition (must be done before TLS acceptance is evaluated; not a deliverable of this iteration)

### Definition of Done
WBSB runs autonomously on a real Linux server with:
- weekly reports triggered and delivered without any manual action
- feedback endpoint reachable over HTTPS with I11 security controls active
- deployment, secrets rotation, and basic troubleshooting achievable by following the documented runbooks
- the server stack documented clearly enough to reuse for the next project

---

---

# Architecture Principles (Permanent)

These apply to every iteration. No change to any iteration is approved if it violates these.

1. **Deterministic first** — pipeline output must be reproducible from the same inputs
2. **Config-driven rules** — all thresholds live in `config/rules.yaml`; none hardcoded
3. **Auditability** — SHA-256 hashes on input and config; structured AuditEvent trail throughout
4. **No silent failure** — every data quality issue must surface explicitly
5. **Separation of concerns** — metrics, rule evaluation, and rendering are strictly isolated
6. **LLM is optional** — every mode must produce a valid, complete report without LLM
7. **Section-level degradation** — no section failure blocks another section from rendering
8. **No recommendation engine** — the system observes and explains; it never advises
9. **Secrets never in code or logs** — all credentials and tokens sourced from environment variables only; `.env` is gitignored; no secret value may appear in log output, artifact files, or error messages

---

# MVP Completion Criteria

MVP is complete when all of the following are true:

**Data & Analysis**
- [ ] Multi-week trend context included in LLM prompt (I6)
- [ ] Trend labels computed deterministically for all tracked metrics (I6)

**Delivery**
- [ ] Pipeline runs on a schedule without manual intervention (I9)
- [ ] Report delivered to Teams or Slack within 5 minutes of run completion (I9)
- [ ] LLM fallback state communicated clearly in delivery (I9)
- [ ] Pipeline failure produces an alert, not silence (I9)

**Quality & Feedback**
- [ ] Grounding, coverage, and hallucination scores stored per run (I7)
- [ ] Operator can label any report section as Expected / Unexpected / Incorrect (I7)
- [ ] Feedback stored with run_id reference for later analysis (I7)
- [ ] Golden dataset assembled from real production runs (I7)
- [ ] `wbsb eval` passes all golden cases (I7)

**Ongoing**
- [ ] All tests passing (324 baseline + new per iteration)
- [ ] Ruff clean
- [ ] Docker image builds and runs end-to-end

---

*Document created: 2026-03-09*
*Updated: 2026-03-14 — reflects state after Iteration 9 completion. MVP (I1–I7 + I9) is complete.*
*Update this document at the start of each iteration with actual deliverables and any scope changes.*
