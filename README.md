# Weekly Business Signal Brief (WBSB)

> **AI-assisted operational intelligence for small and medium businesses.**
> Turn weekly operational data into a plain-language business briefing — automatically, every week.

---

## What This Is

Most business owners collect the same operational data every week: revenue, bookings, marketing spend, new customers, cancellations. The numbers are there. The interpretation is not.

WBSB closes that gap. It processes your weekly data file, detects meaningful business signals, identifies relationships between them, and produces a structured executive brief that answers five questions:

1. What happened in the business this week?
2. What is the main story behind the numbers?
3. Which areas triggered signals — and why?
4. How are those signals related to each other?
5. What should be watched closely next week?

The output is a brief a business owner can read in under two minutes and act on immediately.

**All analytical logic is deterministic and auditable. AI is used only for narrative explanation — never for computation.**

---

## Example Output

```markdown
## Situation
Revenue declined this week as customer acquisition efficiency weakened across the paid
channel. Conversion rate fell 23% while marketing spend remained constant, resulting in
fewer new clients and a 31% higher cost per acquisition.

## Key Story This Week
Three acquisition signals triggered simultaneously. Paid lead volume held steady but
conversion dropped sharply, meaning leads are arriving but not converting. Because spend
did not decrease proportionally, each new client now costs significantly more to acquire.

## Signals (4)

**Acquisition**
All three acquisition signals moved unfavorably this week.
- ⚠️ WARN — Customer Acquisition Cost Rising (Rule B1) — +61.5% week-over-week
- ⚠️ WARN — Paid Lead Conversion Falling (Rule C1) — -23.4% week-over-week
- ⚠️ WARN — New Client Acquisition Falling (Rule G1) — -29.3% week-over-week

**Financial Health**
- ⚠️ WARN — Marketing Spend Overweight (Rule H2) — above 40% threshold

## Watch Next Week
- conversion rate — recovery would likely stabilise CAC; continued decline signals a
  structural change in paid channel quality
- CAC trend — three consecutive weeks rising would indicate a meaningful efficiency shift
```

---

## Quick Start

### Requirements
- Python 3.11+
- Install: `pip install -e .`
- For AI mode: `ANTHROPIC_API_KEY` in environment or `.env` file

### Run a Report

**Deterministic mode (no API key required):**
```bash
wbsb run -i your_data.csv
```

**AI-enhanced mode (recommended):**
```bash
wbsb run -i your_data.csv --llm-mode full --llm-provider anthropic
```

**Try it with example data:**
```bash
wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full
```

Output is written to `runs/<run_id>/brief.md`. Open it and read.

### LLM Mode Options

| Flag | Behaviour |
|---|---|
| `--llm-mode off` | Deterministic report only. No API key needed. Fast. |
| `--llm-mode full` | Full AI narrative — Situation, Key Story, signal explanations, Watch Next Week. |

### Model Selection

Override the default model via environment variable (no code change needed):

```bash
WBSB_LLM_MODEL=claude-sonnet-4-5 wbsb run -i data.csv --llm-mode full
```

| Model | Quality | Est. cost/run | Recommended for |
|---|---|---|---|
| `claude-haiku-4-5-20251001` | Basic | ~$0.003 | Cost-sensitive or fallback |
| `claude-sonnet-4-5` | High | ~$0.023 | **Default — best balance** |
| `claude-opus-4-5` | Highest | ~$0.089 | Complex weeks with conflicting signals |

---

## How It Works

```
Your CSV/XLSX
     │
     ▼
1. Ingestion       Load and detect format
2. Validation      Check columns, coerce types, log issues
3. Metrics         Calculate 16 business metrics (current + prior week)
4. Deltas          Compute week-over-week absolute and % change
5. Signals         Evaluate 11 rules → WARN / INFO events
6. Findings        Assemble structured Findings document
7. Rendering       Produce brief.md (deterministic + optional AI narrative)
     │
     ▼
runs/<run_id>/brief.md
```

The pipeline is fully deterministic through step 6. The same input always produces the same findings and signals. AI in step 7 adds narrative quality — it does not change the analytical output.

### Input Format

A single CSV or Excel file. One row per week. Two rows minimum (current week + prior week).

| Column | Type | Description |
|---|---|---|
| `week_start_date` | Date | Week start date |
| `gross_revenue` | Float | Gross revenue before refunds |
| `refunds` | Float | Total refunds |
| `variable_cost` | Float | Direct variable costs |
| `bookings_total` | Integer | Total appointment bookings |
| `appointments_completed` | Integer | Completed appointments |
| `appointments_cancelled` | Integer | Cancelled appointments |
| `new_clients_paid` | Integer | New clients from paid channels |
| `new_clients_organic` | Integer | New clients from organic channels |
| `returning_clients` | Integer | Returning clients |
| `leads_paid` | Integer | Paid leads |
| `leads_organic` | Integer | Organic leads |
| `ad_spend_google` | Float | Google Ads spend |
| `ad_spend_meta` | Float | Meta Ads spend |
| `ad_spend_other` | Float | Other paid spend |
| `clicks_total` | Integer | Total ad clicks |
| `impressions_total` | Integer | Total impressions |

The system automatically derives `net_revenue`, `ad_spend_total`, `leads_total`, and `new_clients_total` — you do not need to include these.

### Signals Detected

11 business rules across 4 categories, evaluated against configurable thresholds in `config/rules.yaml`:

| ID | Signal | Category |
|---|---|---|
| A1 | Revenue Decline | Revenue |
| A2 | Revenue Surge | Revenue |
| B1 | Customer Acquisition Cost Rising | Acquisition |
| C1 | Paid Lead Conversion Falling | Acquisition |
| D1 | Show Rate Declining | Operations |
| E1 | Cancellation Rate Rising | Operations |
| F1 | Bookings Volume Falling | Operations |
| G1 | New Client Acquisition Falling | Acquisition |
| H1 | Gross Margin Below Threshold | Financial Health |
| H2 | Marketing Spend Overweight | Financial Health |
| H3 | Contribution Margin Declining | Financial Health |

All thresholds are configurable in `config/rules.yaml` without touching code.

---

## Output Artifacts

Each run writes a timestamped folder to `runs/`:

```
runs/20260309T092734Z_085775/
    brief.md            ← the report (this is what you read)
    findings.json       ← structured findings data
    manifest.json       ← run metadata, SHA-256 hashes, LLM info
    logs.jsonl          ← structured pipeline log
    llm_response.json   ← LLM prompt, raw response, eval scores (LLM mode only)
```

`manifest.json` records the SHA-256 hash of both the input file and the active rules config — every run is fully auditable.

---

## Project Status

**Iteration 5 of 10 — Foundation phase complete.**

| Iteration | Theme | Status |
|---|---|---|
| I1 | Pipeline Foundation | ✅ Complete |
| I2 | Signal Architecture | ✅ Complete |
| I3 | Business Reporting Layer | ✅ Complete |
| I4 | LLM Integration | ✅ Complete |
| I5 | Analytical Reasoning Upgrade | ✅ Complete |
| I6 | Historical Memory & Trend Awareness | 🔲 Next |
| I9 | Deployment & Delivery (Teams/Slack) | 🔲 Planned |
| I7 | Evaluation Framework & Feedback Loop | 🔲 Planned |
| I8 | Dashboard & Visual Reporting | 🔲 Planned |
| I10 | Multi-File Data Consolidation | 🔲 Planned |

**MVP** closes when I6, I9, and I7 are complete.

Current state: 217 tests passing · Ruff clean · All thresholds configurable via `config/rules.yaml`

---

## Documentation

| Document | Audience | Description |
|---|---|---|
| [`docs/project/HOW_IT_WORKS.md`](docs/project/HOW_IT_WORKS.md) | Developers / operators | Full system guide — pipeline, metrics, signals, CLI reference, artifacts |
| [`docs/project/PROJECT_BRIEF.md`](docs/project/PROJECT_BRIEF.md) | Clients / investors / stakeholders | Business-oriented product brief — problem, value, vision, roadmap |
| [`docs/project/project-iterations.md`](docs/project/project-iterations.md) | Product / engineering | Full iteration roadmap with task breakdowns and acceptance criteria |
| [`docs/iterations/iteration-5-summary.md`](docs/iterations/iteration-5-summary.md) | Engineering | Detailed I5 summary — what was built, bugs fixed, model comparison |
| [`CLAUDE.md`](CLAUDE.md) | Contributors | Architecture rules, coding constraints, working conventions |

---

## Project Structure

```
src/wbsb/
├── ingest/loader.py          # CSV/XLSX ingestion
├── validate/schema.py        # Column validation and type coercion
├── metrics/calculate.py      # 16 deterministic metric calculations
├── compare/delta.py          # Week-over-week delta computation
├── rules/engine.py           # Signal detection against rules
├── findings/build.py         # Findings document assembly
├── render/
│   ├── template.py           # Jinja2 context preparation
│   ├── template.md.j2        # Markdown report template
│   ├── llm.py                # LLM orchestration and fallback
│   ├── llm_adapter.py        # Anthropic API client and response validation
│   └── prompts/              # System and user prompt templates (v2)
├── domain/models.py          # Pydantic domain models
├── pipeline.py               # Pipeline orchestrator
└── cli.py                    # Typer CLI

config/rules.yaml             # All signal thresholds — edit here, not in code
examples/datasets/            # 10 synthetic test datasets
tests/                        # 217 pytest tests
```

---

## Design Principles

- **Deterministic first** — same input always produces the same signals and findings
- **AI explains, analytics compute** — AI is never in the analytical path
- **Config-driven rules** — all thresholds in `config/rules.yaml`, none hardcoded
- **Section-level fallback** — if any AI section fails, the rest of the report is unaffected
- **Full auditability** — SHA-256 hashes, structured logs, and an AuditEvent trail on every run
- **No recommendation engine** — the system observes and explains; it never advises
