# WBSB — Project Iterations
## Weekly Business Signal Brief — Full Roadmap

**MVP Definition:** Iterations I1–I7 + I9 complete.
**Post-MVP:** I8 (dashboard polish), I10 (multi-file data consolidation).

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
| I9 | Deployment & Delivery | 🔲 Planned | ✅ |
| I7 | Evaluation Framework & Feedback Loop | ✅ Complete | ✅ |
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

**Final state:** 217 tests passing, ruff clean, all I5 branches merged to main.

### Key Files
`src/wbsb/render/template.py`, `src/wbsb/render/template.md.j2`, `src/wbsb/render/llm.py`, `src/wbsb/domain/models.py`, `tests/test_render_template.py`

---

---

# PLANNED ITERATIONS

---

## Iteration 6 — Historical Memory & Trend Awareness
**Status:** 🔲 Planned | **MVP:** ✅ Required

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
**Status:** 🔲 Planned | **MVP:** ✅ Required

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

### Why This Comes After I9
The feedback loop is only useful once real operators are reading real reports. The golden dataset for automated evaluation is built faster from real production runs (which start in I9) than from synthetic test cases. Starting I7 before I9 would mean evaluating against simulated scenarios; starting after means evaluating against reality.

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
- [ ] All tests passing (217 baseline + new per iteration)
- [ ] Ruff clean
- [ ] Docker image builds and runs end-to-end

---

*Document created: 2026-03-09*
*Reflects state after Iteration 5 completion.*
*Update this document at the start of each iteration with actual deliverables and any scope changes.*
