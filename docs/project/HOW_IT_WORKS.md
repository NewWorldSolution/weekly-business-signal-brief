# How WBSB Works
## Weekly Business Signal Brief — System Guide

---

## What This System Does

WBSB takes your weekly business data (a single CSV or Excel file) and produces a structured Markdown report that tells you what happened in your business this week, which signals crossed meaningful thresholds, and — when patterns exist — what the dominant story is across your metrics.

It is built for appointment-based service businesses (clinics, studios, agencies, salons) where the key metrics are: bookings, show rate, cancellations, acquisition cost, conversion rates, gross margin, and marketing spend.

**What makes it different from a dashboard:**
- A dashboard shows you numbers. WBSB tells you which numbers crossed thresholds, how they relate to each other, and what to watch next week.
- Everything is explainable: every signal has a rule ID, a threshold, and a deterministic narrative. Nothing is a black box.
- AI is optional. The report is fully meaningful without it. AI adds narrative quality, not analytical logic.

---

## How It Works — The Pipeline

```
Your CSV/XLSX file
      │
      ▼
  1. Ingestion          Load data, detect format
      │
      ▼
  2. Validation         Check required columns, coerce types, log issues
      │
      ▼
  3. Metrics            Calculate 16 business metrics for current + prior week
      │
      ▼
  4. Deltas             Compute week-over-week absolute and % change per metric
      │
      ▼
  5. Signal Detection   Evaluate 11 rules against thresholds → WARN / INFO signals
      │
      ▼
  6. Findings           Assemble everything into a structured Findings document
      │
      ▼
  7. Rendering          Produce brief.md (deterministic or LLM-enhanced)
      │
      ▼
  Output: runs/<run_id>/brief.md
```

Every stage is deterministic. The same input file always produces the same findings, the same signals, and the same deterministic report. The run ID, SHA-256 hashes of your input file and config, and a full audit log are stored with every run.

---

## What Goes In — Your Data File

### Format
CSV or Excel (`.csv`, `.xlsx`). One row per week. You need at least two rows: the current week and the prior week. The pipeline automatically selects the two most recent weeks unless you specify `--week`.

### Required Columns

| Column | Type | Description |
|---|---|---|
| `week_start_date` | Date | Week start date (any standard date format) |
| `gross_revenue` | Float | Total gross revenue before refunds |
| `refunds` | Float | Total refunds issued |
| `variable_cost` | Float | Direct variable costs (COGS) |
| `bookings_total` | Integer | Total appointment bookings |
| `appointments_completed` | Integer | Completed appointments |
| `appointments_cancelled` | Integer | Cancelled appointments |
| `new_clients_paid` | Integer | New clients from paid channels |
| `new_clients_organic` | Integer | New clients from organic channels |
| `returning_clients` | Integer | Returning clients |
| `leads_paid` | Integer | Paid leads generated |
| `leads_organic` | Integer | Organic leads generated |
| `ad_spend_google` | Float | Google Ads spend |
| `ad_spend_meta` | Float | Meta Ads spend |
| `ad_spend_other` | Float | Other paid ad spend |
| `clicks_total` | Integer | Total ad clicks |
| `impressions_total` | Integer | Total ad impressions |

### Derived Columns
The system automatically computes these from the columns above — you do not need to include them:

| Derived Column | Formula |
|---|---|
| `net_revenue` | `gross_revenue - refunds` |
| `ad_spend_total` | `ad_spend_google + ad_spend_meta + ad_spend_other` |
| `leads_total` | `leads_paid + leads_organic` |
| `new_clients_total` | `new_clients_paid + new_clients_organic` |

### Data Tips
- **Missing values:** the validator will coerce blank numeric cells to zero and log an `AuditEvent`. If a required column is missing entirely, the run will fail with a clear error.
- **Date formats:** `2024-11-25`, `25/11/2024`, `Nov 25 2024` — all handled automatically.
- **Zero values:** valid, not treated as missing. A week with zero paid leads is a valid data point.
- **Two weeks minimum:** the pipeline requires at least one prior week to compute deltas. With only one row, the run will fail.

### Example File Structure

```
week_start_date,gross_revenue,refunds,variable_cost,bookings_total,...
2024-11-18,10500,220,3200,62,...
2024-11-25,8100,100,3600,42,...
```

The second row (most recent week) is the current week. The first row is the prior week.

---

## What Comes Out — The Report

Every run produces a folder in `runs/` named by timestamp and run ID:

```
runs/20260309T092734Z_085775/
    brief.md           ← the report (open this)
    findings.json      ← structured findings data
    manifest.json      ← run metadata, SHA-256 hashes, LLM info
    logs.jsonl         ← structured pipeline log
    llm_response.json  ← LLM prompt, raw response, scores (if LLM mode used)
```

### Report Structure

```markdown
# Weekly Business Signal Brief
[Run ID, generated timestamp, period dates]

## Situation                    ← AI: what happened this week (2-3 sentences)
## Key Story This Week          ← AI: dominant signal cluster (only when signals cluster)

---

## Weekly Priorities            ← Deterministic: WARN/INFO counts, top issue
## Signals (N)                  ← Deterministic + AI narrative per signal
   Financial Health
   [AI group narrative]
   ### WARN — Gross Margin Below Threshold (Rule H1)
   [Signal narrative]
   Evidence: Current / Previous / Δ% / Threshold

## Watch Next Week              ← AI: 1-2 metrics to monitor next week
## Data Quality                 ← Deterministic: validation events
## Key Metrics                  ← Deterministic: full metric table
## Audit                        ← Deterministic: event log
```

**Sections in bold are always present regardless of LLM mode.**
Situation, Key Story, and Watch Next Week are only present when running with `--llm-mode full` and LLM succeeds.

---

## The 11 Business Signals

Signals are evaluated by comparing the current week to the prior week against fixed thresholds defined in `config/rules.yaml`. A signal fires as WARN (action-worthy) or INFO (notable) when its condition is met.

| ID | Signal | Category | Fires When |
|---|---|---|---|
| A1 | Revenue Decline | Revenue | Net revenue fell more than 15% week-over-week |
| A2 | Revenue Surge | Revenue | Net revenue rose more than 25% week-over-week |
| B1 | Customer Acquisition Cost Rising | Acquisition | CAC (paid) rose more than 20% week-over-week |
| C1 | Paid Lead Conversion Falling | Acquisition | Paid lead-to-client rate fell more than 15% week-over-week |
| D1 | Show Rate Declining | Operations | Show rate fell more than 10% week-over-week |
| E1 | Cancellation Rate Rising | Operations | Cancel rate rose more than 15% week-over-week |
| F1 | Bookings Volume Falling | Operations | Booking volume fell more than 20% week-over-week (or by more than 3) |
| G1 | New Client Acquisition Falling | Acquisition | New client count fell more than 20% week-over-week (or by more than 3) |
| H1 | Gross Margin Below Threshold | Financial Health | Gross margin is below 50% (absolute, not a delta) |
| H2 | Marketing Spend Overweight | Financial Health | Marketing spend exceeds 40% of revenue (absolute) |
| H3 | Contribution Margin Declining | Financial Health | Contribution after marketing fell more than 25% week-over-week |

### Guardrails
Some signals are suppressed when volume is too low to be statistically meaningful. For example:
- **B1** (CAC rising) is suppressed if the prior week had zero paid new clients — a percentage change on near-zero is meaningless
- **A1** (revenue decline) is suppressed if prior week revenue was below $3,000 — a small dollar business can swing 15% from a single appointment
- **F1** and **G1** use a hybrid rule: they fire if either the percentage threshold OR an absolute count threshold is crossed

These guardrails prevent false alarms on low-volume weeks.

### Dominant Cluster
When two or more WARN signals fire within the same business category in the same week, the system marks this as a **dominant cluster**. This is computed deterministically:

```
dominant_cluster_exists = max(WARN signals per category) >= 2
```

When a dominant cluster exists, the AI Key Story section activates and focuses specifically on explaining the relationship between signals in that cluster. The AI is instructed not to fabricate connections to other categories.

---

## The 16 Calculated Metrics

These are computed for both the current and prior week and compared:

| Metric | Category | Description |
|---|---|---|
| Net Revenue | Revenue | gross_revenue − refunds |
| New Client Ratio | Revenue | new_clients_total / (new_clients_total + returning_clients) |
| CAC (Paid) | Acquisition | ad_spend_total / new_clients_paid |
| Cost per Paid Lead | Acquisition | ad_spend_total / leads_paid |
| Paid Lead-to-Client Rate | Acquisition | new_clients_paid / leads_paid |
| Paid Share of New Clients | Acquisition | new_clients_paid / new_clients_total |
| Total New Clients | Acquisition | new_clients_paid + new_clients_organic |
| Show Rate | Operations | appointments_completed / bookings_total |
| Cancel Rate | Operations | appointments_cancelled / bookings_total |
| Revenue per Completed Appointment | Operations | net_revenue / appointments_completed |
| Total Bookings | Operations | bookings_total (raw) |
| Gross Margin | Financial Health | (net_revenue − variable_cost) / net_revenue |
| Marketing % of Revenue | Financial Health | ad_spend_total / net_revenue |
| Contribution After Marketing | Financial Health | net_revenue − variable_cost − ad_spend_total |
| Total Leads | Derived | leads_paid + leads_organic |
| Total Ad Spend | Derived | ad_spend_google + ad_spend_meta + ad_spend_other |

All divisions use `safe_div` — if the denominator is zero, the metric returns `None` instead of raising an error. A `None` metric cannot trigger a signal.

---

## Running a Report

### Prerequisites
- Python 3.11+
- Install: `pip install -e .` (from the project root)
- For AI mode: set `ANTHROPIC_API_KEY` in your environment or `.env` file

### Basic Run (Deterministic — No AI)

```bash
wbsb run -i your_data.csv
```

Produces a complete, readable report. No API key required. Fast (under 1 second).

### AI-Enhanced Run (Recommended)

```bash
wbsb run -i your_data.csv --llm-mode full --llm-provider anthropic
```

Adds Situation, Key Story, group narratives, signal narratives, and Watch Next Week sections. Requires `ANTHROPIC_API_KEY`.

### All Options

```bash
wbsb run \
  -i your_data.csv \                          # required: input file
  -o runs/ \                                  # optional: output directory (default: runs/)
  --llm-mode full \                           # off | summary | full (default: off)
  --llm-provider anthropic \                  # anthropic (only supported provider currently)
  --config config/rules.yaml \                # optional: custom rules config
  --week 2024-W48                             # optional: specific ISO week to analyse
```

### Choosing a Week
By default the pipeline uses the two most recent weeks in your file. If you want to analyse a specific historical week:

```bash
wbsb run -i your_data.csv --week 2024-W48
```

The specified week becomes the "current week" and the week before it becomes the "prior week".

### Changing the AI Model
Without code changes, override the model via environment variable:

```bash
WBSB_LLM_MODEL=claude-opus-4-5 wbsb run -i your_data.csv --llm-mode full
```

| Model | Quality | Cost/run | When to use |
|---|---|---|---|
| `claude-haiku-4-5-20251001` | Basic | ~$0.003 | Cost-sensitive; fallback |
| `claude-sonnet-4-5` | High | ~$0.023 | **Default — best balance** |
| `claude-opus-4-5` | Highest | ~$0.089 | Complex weeks with conflicting signals |

Default is Haiku (fast, cheap). Set `WBSB_LLM_MODEL=claude-sonnet-4-5` in your `.env` for production use.

### Reading the Output

After a run completes:

```
✅  Run complete: runs/20260309T092734Z_085775
```

Open the report:
```bash
# On macOS
open runs/20260309T092734Z_085775/brief.md

# Or read directly
cat runs/20260309T092734Z_085775/brief.md
```

---

## What Happens When Things Go Wrong

### Bad Data
- Missing required column → pipeline stops with a clear error listing the column name
- Column has non-numeric values → coerced to zero with an `AuditEvent` logged; run continues
- Only one week of data → pipeline stops; needs at least two weeks for delta computation
- Zero value in a denominator metric → that metric returns `None`; signals that depend on it are skipped

### LLM Failure
If the AI call fails for any reason (network timeout, invalid API key, malformed response, API error), the pipeline automatically falls back to the deterministic report. You get a complete, valid report with no AI sections. The fallback reason is logged in `manifest.json` and `llm_response.json`.

The fallback banner appears in the log:
```
WARNING  LLM fallback triggered. Reason: api_error — ...
```

**The deterministic report is always valid.** AI failure never blocks you from getting a report.

### No Signals
If all metrics are within thresholds:
```markdown
## Signals (0)

No signals fired this week. All metrics within thresholds.
```

This is a good week. The report still includes the full metrics table and audit log.

---

## Adjusting Thresholds

All signal thresholds live in `config/rules.yaml`. To change a threshold, edit the file directly — no code changes required.

**Example: tighten the revenue decline threshold from 15% to 10%:**
```yaml
- id: A1
  label: Revenue Decline
  threshold: -0.10    # was -0.15
```

**Example: raise the gross margin floor from 50% to 60%:**
```yaml
- id: H1
  label: Gross Margin Below Threshold
  threshold: 0.60    # was 0.50
```

After editing `config/rules.yaml`, the next run will use the new thresholds. The config SHA-256 hash in `manifest.json` will change, making it auditable that the rules changed.

---

## Understanding the Run Artifacts

### `brief.md`
The report. This is what you read.

### `findings.json`
Machine-readable version of everything in the report — metrics, signals, periods, run metadata. Useful for building integrations or dashboards on top of WBSB output.

### `manifest.json`
Run provenance:
- `run_id` — unique identifier for this run
- `generated_at` — timestamp
- `input_file` — filename of the data file used
- `input_sha256` — SHA-256 hash of the input file (proves which file was used)
- `config_sha256` — SHA-256 hash of `config/rules.yaml` (proves which rules were active)
- `llm_model` — model used (if LLM mode was active)
- `llm_fallback` — whether AI fell back to deterministic
- `git_commit` — git commit hash of the codebase at run time

### `logs.jsonl`
Structured JSON log of every pipeline stage. Useful for debugging.

### `llm_response.json`
Present only in LLM modes. Contains:
- The exact system prompt and user prompt sent to the model (so you can audit what the AI was told)
- The raw model response
- The parsed, validated LLM result
- `prompt_hash` — hash of the prompt templates used
- `model`, `provider`, `timestamp`

---

## Example Dataset

The `examples/datasets/` directory contains 10 synthetic test datasets:

| File | Scenario |
|---|---|
| `dataset_01_clean_baseline.csv` | No signals — everything within thresholds |
| `dataset_02_missing_values.csv` | Missing/blank cells — tests validation robustness |
| `dataset_03_negative_values.csv` | Negative revenue — edge case handling |
| `dataset_04_duplicate_weeks.csv` | Duplicate week rows in the file |
| `dataset_05_misaligned_dates.csv` | Week dates not on Monday |
| `dataset_06_float_in_int_columns.csv` | Float values in integer columns |
| `dataset_07_extreme_ad_spend.csv` | Extreme marketing spend — triggers H1, H2 |
| `dataset_08_zero_revenue_week.csv` | Zero revenue — tests guardrails |
| `dataset_09_low_volume.csv` | Low booking volume — tests hybrid rules |
| `dataset_10_missing_required_column.csv` | Missing column — tests error handling |

To run any of them:
```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full
```

---

## Project Structure

```
weekly-business-signal-brief/
├── src/wbsb/
│   ├── ingest/loader.py          # CSV/XLSX ingestion
│   ├── validate/schema.py        # Column validation and coercion
│   ├── metrics/calculate.py      # 16 metric calculations
│   ├── compare/delta.py          # Week-over-week delta computation
│   ├── rules/engine.py           # Signal detection against rules
│   ├── findings/build.py         # Findings document assembly
│   ├── render/
│   │   ├── template.py           # Jinja2 render context and extraction helpers
│   │   ├── template.md.j2        # Markdown report template
│   │   ├── llm.py                # LLM orchestration and fallback
│   │   ├── llm_adapter.py        # Anthropic API client and validation
│   │   └── prompts/              # System and user prompt templates
│   ├── domain/models.py          # Pydantic domain models
│   ├── pipeline.py               # Pipeline orchestrator
│   └── cli.py                    # Typer CLI (wbsb run, wbsb version)
├── config/
│   └── rules.yaml                # All signal thresholds and guardrail values
├── examples/datasets/            # 10 synthetic test datasets
├── runs/                         # Output directory (one folder per run)
├── tests/                        # pytest test suite (271 tests)
├── docs/project/project-iterations.md   # Full roadmap (I1–I10)
├── docs/iterations/i5/summary.md           # Iteration 5 detailed summary
└── docs/project/HOW_IT_WORKS.md         # This file
```

---

*System state as of Iteration 6 — March 2026.*
*271 tests passing. Ruff clean. All thresholds configurable via `config/rules.yaml`.*
