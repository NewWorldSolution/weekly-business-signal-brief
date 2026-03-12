# Iteration 9 — Deployment & Delivery
## Detailed Task Plan

**Status:** Planning complete. Ready to start.
**Baseline:** 324 tests passing, ruff clean, main stable.

---

## Purpose

Iteration 9 takes WBSB from a local CLI tool to a deployed product. Three distinct systems are built:

1. **Delivery layer** — push the report to Teams and Slack immediately after a successful run, including operator feedback action buttons
2. **Scheduler / file watcher** — trigger the pipeline automatically when a new data file arrives, without manual `wbsb run`
3. **Container + security hardening** — Docker packaging and secrets hygiene before any shared or hosted deployment

I9 also completes one explicit I7 deferral: the feedback webhook server. The `feedback/server.py` HTTP endpoint — which Teams/Slack action buttons POST to — was intentionally moved from I7 to I9 because it depends on the delivery infrastructure being in place first.

I9 also begins with a docs normalisation task. Several project docs (`project-iterations.md`, `HOW_IT_WORKS.md`, `PROJECT_BRIEF.md`) still reference outdated baselines and describe I9 as future work. These are updated before any code is written.

---

## Critical Architecture Rules

These rules apply to every I9 task. Any implementation that violates them is wrong regardless of whether tests pass.

**Rule 1 — Pipeline produces artifacts; delivery reads artifacts**
The pipeline must not import from `wbsb.delivery`. After a run completes, `runs/{run_id}/` contains `brief.md`, `findings.json`, `manifest.json`, and optionally `llm_response.json`. The delivery orchestrator reads these files from disk. Pipeline objects are never passed directly to delivery code. This ensures re-delivery is always possible (`wbsb deliver --run-id`) and the pipeline stays deterministic and testable in isolation.

**Rule 2 — Delivery must be idempotent**
Running `wbsb deliver --run-id 20260415T080000Z_abc123` must produce the same result regardless of whether it is the first or tenth invocation. Delivery reads from immutable artifacts. No delivery state is written back to `runs/`.

**Rule 3 — Scheduler never calls Slack or Teams directly**
The scheduler's only job is to decide whether to trigger a run. It calls `wbsb run --auto`. The pipeline produces artifacts. The delivery orchestrator (called post-run) dispatches to Slack/Teams. These three stages are strictly isolated. A scheduler failure cannot cause a delivery. A delivery failure cannot cause a re-run.

---

## Scope Boundaries

| In scope (I9) | Out of scope |
|---|---|
| Adaptive Card builder + webhook sender (Teams) | Web dashboard (I8) |
| Block Kit builder + webhook sender (Slack) | Bot token authentication |
| `config/delivery.yaml` + validation model | Multi-tenant webhook routing |
| `feedback/server.py` HTTP webhook endpoint | OAuth / SSO for feedback |
| `wbsb run --auto` (scheduled run via existing I6 index) | Complex file watcher daemon |
| `wbsb deliver` CLI command | SMS / email delivery |
| Delivery orchestrator reading artifacts from `runs/` | Dashboard run history view (I8) |
| Failure alerting (LLM fallback, pipeline error, no-new-file) | Kubernetes / cloud orchestration |
| Dockerfile + docker-compose + `.env.example` | CI/CD pipeline deployment |
| 9.5 security hardening checklist | Multi-file data consolidation (I10) |
| Docs normalisation (project-iterations.md, HOW_IT_WORKS.md, PROJECT_BRIEF.md) | |

---

## Branching Strategy

```
main
 └── feature/iteration-9
      ├── feature/i9-0-pre-work
      ├── feature/i9-1-delivery-config
      ├── feature/i9-2-teams-adapter
      ├── feature/i9-3-slack-adapter
      ├── feature/i9-4-scheduler
      ├── feature/i9-5-cli-integration
      ├── feature/i9-6-failure-alerting
      ├── feature/i9-7-feedback-webhook
      └── feature/i9-8-containerization
```

**Rules (same as all iterations):**
- Every task branch is created from `feature/iteration-9` — never from `main`
- Every task PR targets `feature/iteration-9` — never `main`
- `main` stays stable throughout the entire iteration
- `feature/iteration-9` → `main` via one final PR after I9-10 review passes

---

## Execution Order

```
I9-0  [Claude]   Pre-work: docs normalisation + package init + .env.example    → no dependencies
I9-1  [Codex]    Delivery config schema (config/delivery.yaml + model)         → I9-0
I9-2  [Codex]    Teams Adaptive Card builder + webhook sender                  → I9-1
I9-3  [Codex]    Slack Block Kit builder + webhook sender                      → I9-1
I9-4  [Claude]   Scheduler: wbsb run --auto + cron wrapper (uses I6 index)    → I9-0
I9-5  [Claude]   Delivery orchestrator + wbsb deliver CLI (reads artifacts)   → I9-2, I9-3, I9-4
I9-6  [Claude]   Failure alerting path                                         → I9-5
I9-7  [Claude]   Feedback webhook server (Teams/Slack button handler)          → I9-5
I9-8  [Claude]   Containerisation + security hardening checklist               → I9-6, I9-7
I9-9  [You]      Architecture review                                            → I9-8
I9-10 [Claude]   Final cleanup + merge to main                                 → I9-9
```

**Parallelism opportunities:**
- I9-2 and I9-3 can run in parallel (both depend only on I9-1)
- I9-4 can start as soon as I9-0 merges, independent of I9-1 through I9-3
- I9-6 and I9-7 can run in parallel once I9-5 merges
- I9-8 starts only after I9-6 and I9-7 both merge (Docker wraps the full app)

---

## Per-Task Workflow

```bash
# 1. Start from the iteration branch
git checkout feature/iteration-9
git pull origin feature/iteration-9

# 2. Create and push the task branch
git checkout -b feature/i9-N-description
git push -u origin feature/i9-N-description

# 3. Open a DRAFT PR immediately — before writing any code
gh pr create \
  --base feature/iteration-9 \
  --head feature/i9-N-description \
  --title "I9-N: Task title" \
  --body "Work in progress." \
  --draft

# 4. Verify baseline before touching anything
pytest && ruff check .

# 5. Implement, then verify
pytest && ruff check .
git diff --name-only feature/iteration-9    # only allowed files

# 6. Push and mark ready
git push origin feature/i9-N-description
gh pr ready
```

---

## Task Summary

| Task | Owner | Description | Depends on |
|------|-------|-------------|------------|
| I9-0 | Claude | Pre-work: docs normalisation, package scaffolding, `.env.example` | — |
| I9-1 | Codex | `config/delivery.yaml` schema + `DeliveryConfig` validation model | I9-0 |
| I9-2 | Codex | Teams Adaptive Card builder + webhook sender + tests | I9-1 |
| I9-3 | Codex | Slack Block Kit builder + webhook sender + tests | I9-1 |
| I9-4 | Claude | `wbsb run --auto`: scan dir + check I6 index + trigger run (no daemon) | I9-0 |
| I9-5 | Claude | Delivery orchestrator (reads artifacts) + `wbsb deliver` CLI | I9-2, I9-3, I9-4 |
| I9-6 | Claude | Failure alerting: LLM fallback, pipeline error, no-new-file notices | I9-5 |
| I9-7 | Claude | Feedback webhook server (I7 deferral) | I9-5 |
| I9-8 | Claude | Dockerfile + docker-compose + 9.5 security hardening | I9-6, I9-7 |
| I9-9 | You | Architecture review | I9-8 |
| I9-10 | Claude | Final cleanup + merge to main | I9-9 |

---

---

## Delivery Config Schema (Frozen — Defined in I9-1)

All delivery config lives in `config/delivery.yaml`. Never hardcoded. The schema below is frozen after I9-1 and must not drift across tasks.

```yaml
delivery:
  teams:
    enabled: false
    webhook_url: "${TEAMS_WEBHOOK_URL}"   # sourced from environment at runtime
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"   # sourced from environment at runtime

scheduler:
  trigger: "manual"          # "manual" | "cron"
  cron: "0 8 * * 1"          # Monday 8am — only used when trigger = cron
  watch_directory: "data/incoming"
  filename_pattern: "weekly_data_*.csv"
  llm_mode: "off"             # passed to pipeline on scheduled run

alerts:
  on_llm_fallback: true
  on_pipeline_error: true
  on_no_new_file: true
```

**Environment variable contract:**
- `TEAMS_WEBHOOK_URL` — Teams incoming webhook URL
- `SLACK_WEBHOOK_URL` — Slack incoming webhook URL
- `ANTHROPIC_API_KEY` — existing (unchanged)
- `WBSB_LLM_MODEL` — existing (unchanged)
- `WBSB_LLM_MODE` — existing (unchanged)

**Webhook URL security rule:** webhook URLs are credentials. They must never appear in log output at INFO level or above. They must never be baked into the Docker image.

---

## Delivery Domain Models (I9-0)

```python
# src/wbsb/delivery/models.py

class DeliveryTarget(str, Enum):
    teams = "teams"
    slack = "slack"

class DeliveryStatus(str, Enum):
    success = "success"
    skipped = "skipped"    # target disabled in config
    failed = "failed"

class DeliveryResult(BaseModel):
    target: DeliveryTarget
    status: DeliveryStatus
    http_status_code: int | None     # None on skipped
    error: str | None                # None on success/skipped
    delivered_at: str | None         # ISO 8601 — None on skipped/failed
```

---

## Teams Card Structure (I9-2)

The Adaptive Card sent to Teams must contain exactly these sections:

```
[Header]       "Weekly Business Signal Brief — {period}"
[Metadata]     Run ID | {week_start} to {week_end} | {warn_count} warnings
[Situation]    {situation paragraph} — omitted if LLM fallback
[Top Signals]  Bullet list of WARN signals (rule_id + label + one-line narrative)
               "No warnings this week." if warn_count == 0
[Feedback]     Action buttons: "✅ Looks right"  "⚠️ Unexpected"  "❌ Something's wrong"
               Each button POSTs to: {feedback_webhook_url}/feedback with run_id + label
```

**LLM fallback banner** (replaces Situation when llm_result is None or llm_fallback=True):
```
⚠️ AI analysis unavailable this week — showing deterministic report
```

**Card format rules:**
- Adaptive Card schema version: `1.4`
- All text content is escaped — no raw HTML
- `feedback_webhook_url` read from `config/delivery.yaml` — never hardcoded
- Card rendered as a Python dict; actual HTTP POST is handled by a separate `send_teams_card(card: dict, webhook_url: str)` function
- Tests cover card dict rendering only — no live webhook calls in tests

---

## Slack Block Structure (I9-3)

The Block Kit message sent to Slack must contain:

```
[Header block]    "Weekly Business Signal Brief"
[Context block]   "{week_start} to {week_end} | Run {run_id}"
[Divider]
[Section block]   Situation paragraph — or fallback banner if LLM absent
[Section block]   "{warn_count} warning(s)" + top 3 signal labels as bullet list
[Divider]
[Actions block]   Buttons: "✅ Looks right"  "⚠️ Unexpected"  "❌ Something's wrong"
                  value field: JSON-encoded {run_id, label}
```

**LLM fallback banner:** same text as Teams — `⚠️ AI analysis unavailable this week — showing deterministic report`

**Block format rules:**
- Block Kit blocks rendered as a Python list of dicts
- HTTP POST handled by a separate `send_slack_message(blocks: list, webhook_url: str)` function
- Tests cover block rendering only — no live webhook calls in tests

---

## Scheduler Contract (I9-4)

The scheduler is not a file watcher daemon. It is a thin decision layer that uses the I6 run index that already exists.

```python
# src/wbsb/scheduler/auto.py

def find_latest_input(watch_dir: Path, pattern: str) -> Path | None:
    """
    Scan watch_dir for files matching pattern.
    Return the most recently modified matching file, or None if none found.
    Validates resolved path is within watch_dir — raises ValueError on traversal.
    """

def already_processed(input_path: Path, index_path: Path) -> bool:
    """
    Check runs/index.json (built by I6) to see if input_path was already
    successfully processed this week.
    Uses derive_dataset_key(input_path) to scope the lookup — same function
    used by the pipeline. Returns False if index is absent or has no matching entry.
    """
```

**Auto-run flow:**
```
wbsb run --auto
  ↓
find_latest_input(watch_dir, pattern)        ← scan directory
  ↓ None → log + alert "no new file" → exit 0
already_processed(path, index_path)          ← check I6 index
  ↓ True → log "already processed" → exit 0
run_pipeline(path, ...)                      ← normal pipeline run
  ↓
artifacts written to runs/{run_id}/
```

**Why this is simpler than a watcher daemon:**
- No `scheduler_state.json` — the I6 `runs/index.json` already tracks what ran
- No filesystem events — polling on cron trigger is sufficient for weekly data
- No race conditions — `already_processed` is a read-only check on an append-only index
- Idempotency falls out naturally: running `--auto` twice in a row never double-processes

---

---

## I9-0 — Pre-Work: Docs Normalisation + Package Scaffolding

**Owner:** Claude
**Branch:** `feature/i9-0-pre-work`
**Depends on:** nothing — starts immediately

### Why First

All downstream tasks need two things before they can start:
1. Correct project state reflected in docs (stale baselines cause confusion during review)
2. Empty package directories and `.env.example` so Codex tasks can import from the right paths without guessing

### What to Build

#### Docs updates

`docs/project/project-iterations.md`:
- Update I9 status from `🔲 Planned` to `🔲 In Progress`
- Fix test baseline references: replace any `217`, `271` counts with `324`
- Fix historical ordering text — remove any suggestion that I7 comes after I9 in execution
- Mark I7 completion details accurately

`docs/project/HOW_IT_WORKS.md`:
- Update test count to 324
- Update project structure section to reflect `src/wbsb/eval/`, `src/wbsb/feedback/`, `src/wbsb/history/` modules added in I6 and I7
- Update roadmap paragraph to reflect I6 and I7 complete; I9 in progress
- CLI options table: add `wbsb eval` and `wbsb feedback` commands added in I7

`docs/project/PROJECT_BRIEF.md`:
- Update "The Road Ahead" section: mark I6 and I7 complete; I9 in progress
- Update iteration ordering paragraph (currently describes I9 as future; it is now active)

`docs/project/TASKS.md`:
- Add I9 as current active iteration (brief summary, link to this file)

#### New package scaffolding

```
src/wbsb/delivery/__init__.py       ← empty package marker
src/wbsb/delivery/models.py         ← DeliveryTarget, DeliveryStatus, DeliveryResult (see schema above)
src/wbsb/scheduler/__init__.py      ← empty package marker
```

#### `.env.example`

Committed to repo root. Documents every required environment variable with no real values and no defaults for secrets:

```bash
# WBSB — Environment Variables
# Copy to .env and fill in values. Never commit .env.

# Required for AI-enhanced reports
ANTHROPIC_API_KEY=

# Optional: override the default LLM model
# Default: claude-haiku-4-5-20251001
WBSB_LLM_MODEL=

# Optional: override LLM mode (off | full)
# Default: off
WBSB_LLM_MODE=

# Teams delivery (required if delivery.teams.enabled = true)
TEAMS_WEBHOOK_URL=

# Slack delivery (required if delivery.slack.enabled = true)
SLACK_WEBHOOK_URL=
```

### Acceptance Criteria
- `docs/project/project-iterations.md` test baseline is 324 everywhere; I9 marked In Progress
- `docs/project/HOW_IT_WORKS.md` project structure section includes I6/I7 modules
- `docs/project/PROJECT_BRIEF.md` roadmap marks I6 and I7 complete
- `src/wbsb/delivery/models.py` instantiates `DeliveryResult` without error
- `.env.example` committed at repo root with all five env vars documented
- No existing tests broken
- Ruff clean

### Allowed Files
```
docs/project/project-iterations.md
docs/project/HOW_IT_WORKS.md
docs/project/PROJECT_BRIEF.md
docs/project/TASKS.md
src/wbsb/delivery/__init__.py       ← create (empty)
src/wbsb/delivery/models.py         ← create
src/wbsb/scheduler/__init__.py      ← create (empty)
.env.example                        ← create
```

### Files Not to Touch
```
src/wbsb/pipeline.py
src/wbsb/cli.py
src/wbsb/domain/models.py
config/rules.yaml
Any test file
```

---

---

## I9-1 — Delivery Config Schema

**Owner:** Codex
**Branch:** `feature/i9-1-delivery-config`
**Depends on:** I9-0 merged

### Why Codex

Bounded config validation module. The schema is fully specified above. No pipeline edits, no architectural judgment. Same pattern as I7-0 (frozen schemas for downstream tasks to import).

### What to Build

#### `config/delivery.yaml`

Create with the full schema from the "Delivery Config Schema" section above. All secrets reference environment variable placeholders (e.g. `${TEAMS_WEBHOOK_URL}`), never real values.

#### `src/wbsb/delivery/config.py`

```python
def load_delivery_config(path: Path = Path("config/delivery.yaml")) -> dict:
    """Load and parse delivery.yaml. Raise ValueError if required keys are missing."""

def resolve_webhook_url(template: str) -> str | None:
    """
    Resolve ${ENV_VAR} placeholders from environment.
    Returns None if the env var is not set.
    Does NOT raise — callers decide whether a missing URL is an error.
    """

def teams_enabled(cfg: dict) -> bool:
    """True if delivery.teams.enabled = true AND TEAMS_WEBHOOK_URL is set."""

def slack_enabled(cfg: dict) -> bool:
    """True if delivery.slack.enabled = true AND SLACK_WEBHOOK_URL is set."""
```

**Security rule:** `resolve_webhook_url` reads from `os.environ` only. The raw URL must never be logged. The function returns the resolved string (or None) — logging at the call site is the caller's responsibility, and callers must not log the URL.

### Tests Required (`tests/test_delivery_config.py`)
- `test_load_delivery_config_valid` — loads correctly from a temp config file
- `test_load_delivery_config_missing_required_key` — raises ValueError
- `test_resolve_webhook_url_set` — returns value when env var is set
- `test_resolve_webhook_url_missing` — returns None when env var absent
- `test_teams_enabled_true` — both flag and env var set → True
- `test_teams_enabled_flag_false` — flag false → False even if env var set
- `test_teams_enabled_no_url` — flag true but env var absent → False
- `test_slack_enabled_same_logic` — mirrors Teams tests

### Allowed Files
```
config/delivery.yaml               ← create
src/wbsb/delivery/config.py        ← create
tests/test_delivery_config.py      ← create
```

### Files Not to Touch
```
src/wbsb/delivery/models.py        ← frozen after I9-0
src/wbsb/pipeline.py
src/wbsb/cli.py
config/rules.yaml
```

---

---

## I9-2 — Teams Adaptive Card Builder

**Owner:** Codex
**Branch:** `feature/i9-2-teams-adapter`
**Depends on:** I9-1 merged

### Why Codex

Pure builder module: given structured findings data, produce a valid Adaptive Card dict. The card structure is fully specified above. Webhook sending is a thin wrapper around `requests.post`. No existing pipeline code is touched.

### What to Build

#### `src/wbsb/delivery/teams.py`

```python
def build_teams_card(
    findings: Findings,
    llm_result: LLMResult | None,
    feedback_webhook_url: str | None,
) -> dict:
    """
    Build an Adaptive Card dict for Teams delivery.
    Structure: header, metadata, situation (or fallback banner), top signals, feedback buttons.
    feedback_webhook_url: if None, feedback buttons are omitted from the card.
    Returns a dict that is JSON-serialisable.
    """

def send_teams_card(card: dict, webhook_url: str) -> DeliveryResult:
    """
    POST card to webhook_url as JSON.
    Returns DeliveryResult with status=success or status=failed.
    Raises nothing — all errors captured in DeliveryResult.
    """
```

**Card rules:**
- Adaptive Card schema version: `1.4`
- Period string: `"{week_start} – {week_end}"` (em dash, not hyphen)
- Warn count sourced from `len([s for s in findings.signals if s.severity == "WARN"])`
- Situation text: `llm_result.situation` if present and non-empty, else fallback banner
- Fallback banner text: `"⚠️ AI analysis unavailable this week — showing deterministic report"`
- Top signals: all WARN signals sorted by `rule_id`, formatted as `"⚠️ {rule_id} — {label}"`
- If no WARN signals: one text block: `"No warnings this week. All metrics within thresholds."`
- Feedback buttons: three `Action.Submit` elements with `data = {"run_id": ..., "label": "expected"|"unexpected"|"incorrect"}`
- HTTP timeout: 10 seconds
- Non-2xx response → `DeliveryResult(status=failed, http_status_code=response.status_code, ...)`

### Tests Required (`tests/test_delivery_teams.py`)
- `test_build_card_with_llm` — situation present; card includes situation text
- `test_build_card_llm_fallback` — llm_result is None; fallback banner present
- `test_build_card_warn_signals` — WARN signals appear in card; INFO signals do not
- `test_build_card_no_signals` — "No warnings" text present
- `test_build_card_no_feedback_url` — feedback buttons omitted when url is None
- `test_build_card_feedback_buttons` — three buttons with correct labels and data
- `test_send_card_success` — mock requests.post returns 200 → DeliveryResult(status=success)
- `test_send_card_failure` — mock returns 500 → DeliveryResult(status=failed)
- `test_send_card_timeout` — mock raises Timeout → DeliveryResult(status=failed)

No live webhook calls in any test. Use `unittest.mock.patch` for all HTTP.

### Allowed Files
```
src/wbsb/delivery/teams.py         ← create
tests/test_delivery_teams.py       ← create
```

---

---

## I9-3 — Slack Block Kit Builder

**Owner:** Codex
**Branch:** `feature/i9-3-slack-adapter`
**Depends on:** I9-1 merged (can run in parallel with I9-2)

### Why Codex

Same pattern as I9-2 — pure builder, specified structure, no pipeline edits.

### What to Build

#### `src/wbsb/delivery/slack.py`

```python
def build_slack_blocks(
    findings: Findings,
    llm_result: LLMResult | None,
    feedback_webhook_url: str | None,
) -> list[dict]:
    """
    Build a Block Kit block list for Slack delivery.
    Structure: header, context, divider, situation (or fallback), signals summary, divider, actions.
    feedback_webhook_url: if None, actions block is omitted.
    Returns a list of block dicts that is JSON-serialisable.
    """

def send_slack_message(blocks: list[dict], webhook_url: str) -> DeliveryResult:
    """
    POST {"blocks": blocks} to webhook_url.
    Returns DeliveryResult with status=success or status=failed.
    Raises nothing.
    """
```

**Block rules:**
- Header: `type: header`, `text: "Weekly Business Signal Brief"`
- Context: `type: context`, elements include week range and run ID
- Situation: `type: section`, text is situation or fallback banner
- Signals summary: `type: section` with `{warn_count} warning(s)` + mrkdwn bullet list of top 3 WARN signal labels (by rule_id). If more than 3: `"+ {N} more"`. If zero: "No warnings this week."
- Actions block: three `button` elements with `value: json.dumps({"run_id": ..., "label": ...})`
- HTTP timeout: 10 seconds
- Non-2xx → `DeliveryResult(status=failed, ...)`

### Tests Required (`tests/test_delivery_slack.py`)
- Mirror of I9-2 tests, adapted for Slack block structure
- `test_build_blocks_with_llm`
- `test_build_blocks_llm_fallback`
- `test_build_blocks_warn_signals` — top 3 appear; extras summarised
- `test_build_blocks_no_signals`
- `test_build_blocks_no_feedback_url`
- `test_build_blocks_feedback_actions`
- `test_send_message_success`
- `test_send_message_failure`
- `test_send_message_timeout`

### Allowed Files
```
src/wbsb/delivery/slack.py         ← create
tests/test_delivery_slack.py       ← create
```

---

---

## I9-4 — Scheduler: wbsb run --auto

**Owner:** Claude
**Branch:** `feature/i9-4-scheduler`
**Depends on:** I9-0 merged (independent of I9-1 through I9-3)

### Why Claude

The scheduler leverages the I6 history index, which requires understanding of `HistoryReader`, `derive_dataset_key`, and how the index is scoped. Also requires judgment about the `--auto` flag integration into the CLI layer without touching pipeline internals.

### What to Build

#### `src/wbsb/scheduler/auto.py`

Full public API specified in the "Scheduler Contract" section above. No daemon, no separate state file.

**Path traversal guard** (same principle as before, but simpler):
```python
resolved = file.resolve()
watch_resolved = watch_dir.resolve()
if not str(resolved).startswith(str(watch_resolved)):
    raise ValueError(f"Path outside watch directory: {resolved}")
```

**`already_processed` implementation:**
Uses `derive_dataset_key(input_path)` (from `wbsb.history.store` — already exists) to scope the lookup, then reads `runs/index.json` and checks whether any entry with that dataset_key has `input_file` matching the candidate path's name AND `week_start` in the current ISO week. Returns `True` if such an entry exists.

#### `src/wbsb/cli.py` — extend `wbsb run`

Add `--auto` flag:

```
wbsb run --auto [--config config/delivery.yaml]
```

- Loads `scheduler` section from `config/delivery.yaml`
- Calls `find_latest_input(watch_dir, pattern)`
- If None: logs "No new file found in {watch_dir}" at INFO; exits 0 (no error)
- Calls `already_processed(path, index_path)`
- If True: logs "Input already processed this week: {path.name}" at INFO; exits 0
- Otherwise: runs normal pipeline with `llm_mode` from scheduler config
- After successful run: if `--deliver` flag is set (or delivery auto-enabled in config), calls orchestrator

**Cron usage:**
```bash
# crontab — every Monday 8am
0 8 * * 1 cd /app && wbsb run --auto
```

No WBSB-managed cron daemon. The cron line is documented in `config/delivery.yaml` comments as a copy-paste example.

### Tests Required (`tests/test_scheduler.py`)
- `test_find_latest_input_found` — matching file present → returns Path
- `test_find_latest_input_no_match` — no matching files → returns None
- `test_find_latest_input_empty_dir` — empty directory → returns None
- `test_find_latest_input_path_traversal` — symlink outside watch_dir → raises ValueError
- `test_already_processed_true` — index has matching dataset_key + same filename → True
- `test_already_processed_false_new_file` — different filename → False
- `test_already_processed_index_absent` — no index.json → False

### Allowed Files
```
src/wbsb/scheduler/auto.py         ← create
src/wbsb/cli.py                    ← extend (add --auto flag to wbsb run)
tests/test_scheduler.py            ← create
```

### Files Not to Touch
```
src/wbsb/pipeline.py               ← the scheduler calls CLI, not pipeline directly
src/wbsb/history/store.py          ← read-only use of existing derive_dataset_key
```

---

---

## I9-5 — Delivery Orchestrator + wbsb deliver CLI

**Owner:** Claude
**Branch:** `feature/i9-5-cli-integration`
**Depends on:** I9-2, I9-3, I9-4 all merged

### Why Claude

Architectural task: wiring the delivery adapters together without touching the pipeline. Requires judgment about the artifact-reading contract, the fallback banner logic, and clean error isolation per delivery target.

### What to Build

#### `src/wbsb/delivery/orchestrator.py`

The orchestrator is the only module that coordinates delivery. It reads artifacts from disk and calls the channel-specific senders. The pipeline never imports this module.

```python
def load_run_artifacts(run_id: str, output_dir: Path = Path("runs")) -> dict:
    """
    Load findings.json, manifest.json, and llm_response.json (if present)
    from runs/{run_id}/.
    Returns dict with keys: findings, manifest, llm_result (may be None).
    Raises FileNotFoundError with clear message if findings.json or manifest.json absent.
    """

def deliver_run(run_id: str, delivery_cfg: dict) -> list[DeliveryResult]:
    """
    Load artifacts for run_id, then dispatch to all enabled delivery targets.
    Returns one DeliveryResult per attempted target.
    Never raises — all errors captured in DeliveryResult.
    """
```

**Fallback banner logic lives here**, not in the card builders:
- Check `manifest["llm_fallback"]` after loading artifacts
- If True (or if `llm_result` is None): pass `llm_result=None` to card builders
- Card builders already handle `None` by rendering the fallback banner

**Both targets can fire simultaneously:**
```python
results = []
if teams_enabled(delivery_cfg):
    results.append(send_teams_card(...))
if slack_enabled(delivery_cfg):
    results.append(send_slack_message(...))
return results
```

#### `src/wbsb/cli.py` — new `wbsb deliver` command

```
wbsb deliver --run-id RUN_ID [--config config/delivery.yaml]
```

- Calls `deliver_run(run_id, delivery_cfg)`
- Prints per-target: `✅ teams: delivered` or `❌ slack: failed — {error}`
- Exit code 0 if all succeed or were skipped; 1 if any failed

#### `wbsb run` — extend with `--deliver` flag

```
wbsb run -i data.csv [--deliver]
```

`--deliver` flag: after the run completes and the run_id is known, calls `deliver_run(run_id, delivery_cfg)` **in the CLI layer, not inside `run_pipeline()`**. Pipeline stays unchanged.

```python
# In cli.py, after run_pipeline() returns:
if deliver:
    results = deliver_run(run_id, delivery_cfg)
    for r in results:
        if r.status == DeliveryStatus.failed:
            typer.echo(f"⚠️  Delivery failed ({r.target}): {r.error}")
```

**`pipeline.py` must not be modified.** Delivery is triggered from the CLI layer only.

### Tests Required
- Add to `tests/test_delivery_orchestrator.py`:
  - `test_load_run_artifacts_success` — loads all three files correctly
  - `test_load_run_artifacts_no_llm_response` — llm_result is None; no error
  - `test_load_run_artifacts_missing_findings` — FileNotFoundError with clear message
  - `test_deliver_run_teams_only` — slack disabled → one result
  - `test_deliver_run_both_targets` → two results
  - `test_deliver_run_no_targets` → empty list (both disabled)
  - `test_deliver_run_failure_captured` — mock send raises → DeliveryResult(failed), no exception
  - `test_deliver_run_llm_fallback_flag` — manifest.llm_fallback=True → card built with llm_result=None

### Allowed Files
```
src/wbsb/delivery/orchestrator.py  ← create
src/wbsb/cli.py                    ← extend (wbsb deliver + --deliver flag on run)
tests/test_delivery_orchestrator.py ← create
```

### Files Not to Touch
```
src/wbsb/pipeline.py               ← must not be modified — this is the key architectural rule
src/wbsb/delivery/teams.py         ← frozen after I9-2
src/wbsb/delivery/slack.py         ← frozen after I9-3
```

---

---

## I9-6 — Failure Alerting Path

**Owner:** Claude
**Branch:** `feature/i9-6-failure-alerting`
**Depends on:** I9-5 merged

### Why Claude

Cross-cutting concern that touches all three delivery surfaces (Teams, Slack, CLI output). Requires judgment about what constitutes a "failure state" vs a normal pipeline outcome, and how to route the right alert to the right channel without duplicating delivery logic.

### What to Build

Three alert scenarios, each with a distinct payload:

**Alert 1 — LLM fallback**
Triggered when: `manifest.llm_fallback == True` after a run with `--llm-mode full`
Card/block: same structure as normal delivery but Situation block replaced with fallback banner. The banner is already handled in the card builders (I9-2, I9-3). This task wires the trigger condition and ensures the banner is shown when the pipeline runs with `--deliver`.

**Alert 2 — Pipeline error**
Triggered when: `run_pipeline()` raises (validation failure, missing columns, etc.)
This alert must fire even though no `brief.md` was produced.
Card/block: simplified — no signals, no metrics. Contains:
- Title: `"⚠️ WBSB Pipeline Error"`
- Error summary (first 200 chars of the exception message)
- Run ID (if assigned before the error)
- Instruction: `"Check logs for full audit trail."`

**Alert 3 — No new file detected**
Triggered when: scheduler runs but `detect_new_file()` returns None
Card/block:
- Title: `"📋 WBSB — No New Data Detected"`
- Message: `"No new weekly data file found in {watch_directory}. Upload a file to trigger the report."`

#### `src/wbsb/delivery/alerts.py`

```python
def build_pipeline_error_alert(error: str, run_id: str | None) -> dict:
    """Build a minimal alert payload (platform-agnostic dict) for pipeline errors."""

def build_no_file_alert(watch_directory: str) -> dict:
    """Build alert payload for no-new-file condition."""

def send_alert(alert: dict, delivery_cfg: dict) -> list[DeliveryResult]:
    """Dispatch alert to all enabled delivery targets. Never raises."""
```

**CLI output:** All three alert conditions also print a visible warning to stdout in the CLI (not just to the delivery channel).

### Tests Required (`tests/test_delivery_alerts.py`)
- `test_pipeline_error_alert_structure` — required keys present
- `test_no_file_alert_structure` — watch_directory in message
- `test_send_alert_non_raising` — mock send raises; function returns DeliveryResult(failed), no propagation
- `test_send_alert_skipped_when_disabled` — target disabled → DeliveryResult(skipped)

### Allowed Files
```
src/wbsb/delivery/alerts.py        ← create
src/wbsb/scheduler/watcher.py      ← add no-file alert trigger (if not already in I9-4)
src/wbsb/cli.py                    ← extend error handling to call send_alert
tests/test_delivery_alerts.py      ← create
```

---

---

## I9-7 — Feedback Webhook Server

**Owner:** Claude
**Branch:** `feature/i9-7-feedback-webhook`
**Depends on:** I9-5 merged (needs delivery config to know feedback URL)

### Why Claude

Security-critical component. The HTTP endpoint is the first inbound surface in the system — it accepts data from Teams/Slack button clicks and writes it to disk. The I7 tasks.md has explicit security requirements that require judgment to implement correctly. Codex should not own this.

### What to Build

#### `src/wbsb/feedback/server.py`

Minimal HTTP server using Python stdlib `http.server` (no framework dependency for MVP). Single route: `POST /feedback`.

```python
class FeedbackHandler(BaseHTTPRequestHandler):
    """
    POST /feedback
    Body: JSON with run_id, label, section, comment (optional), operator (optional)
    Response 200: {"status": "ok", "feedback_id": "..."}
    Response 400: {"status": "error", "message": "..."}
    """
```

**Security requirements (non-negotiable):**
- `run_id` validated against regex `^\d{8}T\d{6}Z_[a-f0-9]{6}$` — reject with 400 on mismatch
- `section` must be in `VALID_SECTIONS` — reject with 400
- `label` must be in `VALID_LABELS` — reject with 400
- `comment`: strip whitespace, cap at 1000 chars silently
- `operator`: cap at 100 chars, default `"anonymous"` if absent
- Body size cap: reject requests with `Content-Length > 4096` with 413
- `run_id` and `section` must never influence the file path (path is `feedback/{uuid4}.json`, always)
- Log only: `"feedback_received"` + `run_id` + `section` + `label`. Never log the comment value.
- No authentication for MVP — document this explicitly in `feedback/server.py` docstring

**Start command** (for Docker / scheduler use):
```bash
wbsb feedback serve [--host 0.0.0.0] [--port 8080]
```

#### `src/wbsb/cli.py` — extend `wbsb feedback` group

```
wbsb feedback serve [--host HOST] [--port PORT]
wbsb feedback list [--limit N]        ← already exists from I7
wbsb feedback summary                 ← already exists from I7
wbsb feedback export --run-id ID      ← already exists from I7
```

### Tests Required (`tests/test_feedback_server.py`)
- `test_valid_feedback_returns_200` — valid payload → 200 + feedback_id
- `test_invalid_run_id_returns_400` — bad format → 400
- `test_invalid_section_returns_400`
- `test_invalid_label_returns_400`
- `test_body_too_large_returns_413`
- `test_comment_truncated_silently` — 2000 char comment accepted, stored as 1000
- `test_feedback_id_not_derived_from_input` — run_id/section not in output file path

### Allowed Files
```
src/wbsb/feedback/server.py        ← create
src/wbsb/cli.py                    ← extend (wbsb feedback serve command)
tests/test_feedback_server.py      ← create
```

### Files Not to Touch
```
src/wbsb/feedback/store.py         ← frozen after I7-7
src/wbsb/feedback/models.py        ← frozen after I7-0
```

---

---

## I9-8 — Containerisation + Security Hardening

**Owner:** Claude
**Branch:** `feature/i9-8-containerization`
**Depends on:** I9-6 and I9-7 both merged

### Why Claude

Docker build decisions require ops judgment: layer caching strategy, volume mounts, no-secrets guarantee. The 9.5 security checklist (from `project-iterations.md`) has multiple grep-verification steps that require understanding of the full codebase.

### What to Build

#### `Dockerfile`

Single-stage build. The project is small — multi-stage adds complexity with no meaningful benefit.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cached until pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

# Copy source after deps (only invalidates this layer on code changes)
COPY src/ src/
COPY config/ config/

# Runtime directories populated via volume mounts — never baked in
RUN mkdir -p runs data/incoming feedback

# Secrets injected at runtime via --env-file or orchestrator env vars
# Never COPY .env or set ENV for secrets here

CMD ["wbsb", "--help"]
```

#### `docker-compose.yml`

```yaml
services:
  wbsb:
    build: .
    env_file: .env          # developer local — never committed
    volumes:
      - ./runs:/app/runs
      - ./data:/app/data
      - ./feedback:/app/feedback
    command: wbsb run -i /app/data/incoming/latest.csv --llm-mode full --deliver
```

#### Security hardening checklist verification

Before this task's PR is opened, the following must be confirmed and documented in the PR description:

```bash
# 1. No API key or webhook URL hardcoded
grep -rn "ANTHROPIC_API_KEY\s*=" src/ config/
# Expected: only os.environ reads and delivery.yaml placeholder

# 2. No webhook URLs logged at INFO
grep -rn "webhook_url" src/ | grep -v "log.error\|log.debug\|#"
# Expected: only config reads and HTTP POST calls — not log.info

# 3. No os.environ values printed
grep -rn "os.environ" src/
# Expected: only reads via os.environ.get — never printed or logged

# 4. Docker image contains no .env file
# Verified by .dockerignore
```

#### `.dockerignore`

```
.env
.env.*
runs/
feedback/
data/
*.pyc
__pycache__/
.git/
tests/
docs/
```

### Acceptance Criteria
- `docker build -t wbsb .` succeeds from clean state
- `docker run --rm wbsb wbsb --help` prints help and exits 0
- `docker run --rm wbsb ls -la | grep -c ".env"` returns 0 (no .env in image)
- All four security grep checks pass
- `docker-compose.yml` starts without errors (local test)
- All existing tests still pass

### Allowed Files
```
Dockerfile
docker-compose.yml
.dockerignore
```

---

---

## I9-9 — Architecture Review

**Owner:** You
**Depends on:** I9-8 merged

### What to Check

**Pipeline isolation — delivery must not be wired into pipeline.py:**
```bash
grep -n "delivery\|deliver\|DeliveryResult\|teams\|slack" src/wbsb/pipeline.py
```
Expected: no matches. Pipeline must have zero knowledge of delivery.

**No secrets in artifacts:**
```bash
cat runs/$(ls -t runs/ | head -1)/manifest.json | python3 -m json.tool | grep -i "webhook\|api_key"
```
Expected: no matches.

**Webhook URL not logged at INFO:**
```bash
grep -rn "webhook_url" src/wbsb/ | grep "log.info"
```
Expected: no matches.

**Feedback server validates all three fields:**
```bash
grep -n "VALID_SECTIONS\|VALID_LABELS\|run_id.*regex" src/wbsb/feedback/server.py
```
Expected: all three present.

**Path traversal guard in watcher:**
```bash
grep -n "resolve\|traversal" src/wbsb/scheduler/watcher.py
```
Expected: path resolution and guard present.

**Docker image has no .env:**
```bash
docker build -t wbsb-test . && docker run --rm wbsb-test ls -la | grep ".env"
```
Expected: no output.

**End-to-end delivery test:**
```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode off --deliver
```
Expected: runs without error; delivery logged as `skipped` (no webhook URLs configured in local env).

**wbsb eval still passes:**
```bash
wbsb eval
```
Expected: all golden cases pass, exit code 0.

**All tests pass:**
```bash
pytest --tb=short -q
ruff check .
```

### Review Checklist
- [ ] `pipeline.py` contains no references to delivery, Teams, Slack, or DeliveryResult
- [ ] `wbsb deliver --run-id` works standalone (re-delivery of past run succeeds)
- [ ] No webhook URLs in logs at INFO level
- [ ] No secrets in `manifest.json`, `findings.json`, or `llm_response.json`
- [ ] Feedback server validates run_id, section, label before writing
- [ ] File path never derived from user input in feedback server
- [ ] Path traversal guard present in watcher
- [ ] Docker image contains no `.env` file
- [ ] `.env.example` committed and up to date with all env vars
- [ ] `wbsb eval` golden cases all pass
- [ ] All 324+ tests passing
- [ ] Ruff clean

---

---

## I9-10 — Final Cleanup + Merge to Main

**Owner:** Claude
**Branch:** `feature/i9-10-final-cleanup`
**Depends on:** I9-9 complete

### What to Do
1. Fix any issues flagged in I9-9 review
2. Update `docs/project/TASKS.md` — all DoD boxes ticked, I9 status → Complete
3. Update `docs/project/project-iterations.md` — I9 status → Complete
4. Run `pytest` and `ruff check .`, confirm clean
5. Open final PR: `feature/iteration-9` → `main`

### Allowed Files
```
docs/project/TASKS.md
docs/project/project-iterations.md
src/wbsb/delivery/           ← only if review found bugs
src/wbsb/scheduler/          ← only if review found bugs
src/wbsb/feedback/server.py  ← only if review found bugs
src/wbsb/pipeline.py         ← only if review found bugs
src/wbsb/cli.py              ← only if review found bugs
tests/                       ← only if review found gaps
```

---

---

## Definition of Done — Iteration 9

**Delivery**
- [ ] Teams Adaptive Card rendered and POSTed when `delivery.teams.enabled = true` and `TEAMS_WEBHOOK_URL` is set
- [ ] Slack Block Kit message rendered and POSTed when `delivery.slack.enabled = true` and `SLACK_WEBHOOK_URL` is set
- [ ] LLM fallback banner appears in delivery card when `manifest.llm_fallback = true`
- [ ] Delivery reads from `runs/{run_id}/` artifacts — `pipeline.py` not modified
- [ ] `wbsb deliver --run-id` is idempotent — can re-run safely
- [ ] Delivery failure never blocks report generation or CLI exit code for `wbsb run`

**Failure Alerting**
- [ ] Pipeline error triggers alert delivery (not silence)
- [ ] No-new-file condition triggers reminder alert
- [ ] LLM fallback communicated clearly in delivery card

**Scheduler**
- [ ] `wbsb run --auto` reads I6 `runs/index.json` — no duplicate runs on same file
- [ ] Path traversal guard present and tested in `find_latest_input()`
- [ ] No separate scheduler state file — idempotency uses existing I6 index
- [ ] Cron usage documented in `config/delivery.yaml` comments

**Feedback Webhook**
- [ ] `POST /feedback` validates run_id, section, label — returns 400 on violation
- [ ] Body size capped at 4096 bytes — returns 413 if exceeded
- [ ] File path never derived from user-submitted fields
- [ ] `wbsb feedback serve` command operational

**Container + Security**
- [ ] `docker build` succeeds
- [ ] `docker run` executes pipeline end-to-end
- [ ] No `.env` file in Docker image
- [ ] Webhook URLs not logged at INFO level
- [ ] `.env.example` committed and complete

**Quality**
- [ ] All 324 baseline tests still passing + new I9 tests added
- [ ] Ruff clean
- [ ] `wbsb eval` golden cases all pass (I7 eval suite unaffected)
- [ ] `main` branch stable

---

*Created: 2026-03-12*
*Baseline: 324 tests passing, ruff clean, I7 complete, main stable.*
*I9 execution order: I9-0 → I9-1 → I9-2 ‖ I9-3 ‖ I9-4 → I9-5 → I9-6 ‖ I9-7 → I9-8 → review → I9-10.*
