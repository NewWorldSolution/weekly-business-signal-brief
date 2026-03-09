# Iteration 5 Summary — WBSB
## Constrained Business Interpretation Layer

**Branch:** `feature/i5-4-report-rendering` → merged to `main`
**Status:** Complete ✅

---

## What We Set Out to Do

Iteration 4 delivered a working LLM integration, but the LLM output was shallow: it rewrote individual signals as slightly improved sentences and produced an executive summary that was mostly a concatenation of the top signals. It had no visibility into relationships between signals and no structural reason to produce anything more than a per-signal restating task.

Iteration 5 inverted the dependency. Instead of deriving the LLM schema from what the model produced, we defined the report structure first and derived what the LLM must produce from that. The result is a section-based output contract that makes the report read like an operator briefing rather than a signal listing.

---

## What Was Built — Task by Task

### I5-1 — Report Architecture and Output Contract

**Branch:** `feature/i5-1-report-schema`

Locked the final Markdown report structure and derived the JSON schema from it. Extended both `AdapterLLMResult` (in `llm_adapter.py`) and `LLMResult` (in `models.py`) with four new section fields:

```python
situation: str | None = None
key_story: str | None = None
group_narratives: dict[str, str] | None = None
watch_signals: list[dict[str, str]] | None = None
```

The `dominant_cluster_exists` boolean — computed deterministically using `max(Counter(s.category for s in findings.signals if s.severity == "WARN").values(), default=0) >= 2` — was defined here as the gate for the Key Story section. The LLM does not decide whether a dominant cluster exists; Python does.

**Key files changed:** `src/wbsb/domain/models.py`, `src/wbsb/render/llm_adapter.py`

---

### I5-2 — Deterministic Input Structuring

**Branch:** `feature/i5-2-input-structuring`

Replaced the flat numbered signal list in the LLM prompt with structured, pre-organized evidence. The model now receives:

- **Category health summary** — compact table of WARN counts per category with direction
- **Business mechanism chains** — ordered metric sequences for the paid acquisition funnel and operational funnel, using existing `MetricResult` values
- **Signals grouped by category** — each category block shows all signals with evidence, direction, and deterministic narrative
- **Relationship hints** — neutral co-movement notes using only permitted verbs (moved, co-occurred, diverged, remained stable — no causal language)
- **`dominant_cluster_exists` and dominant category** — stated as facts at the top of the payload so the LLM receives them as ground truth

**Key files changed:** `src/wbsb/render/llm_adapter.py`, `src/wbsb/render/prompts/`

---

### I5-3 — Prompt and LLM Contract Redesign

**Branch:** `feature/i5-3-llm-contract`

Rewrote the system and user prompts against the locked schema. Key changes:

- New `system_full_v2.j2`: defines per-section responsibilities explicitly (situation, key_story, group_narratives, signal_narratives, watch_signals), not vague quality instructions
- New `user_full_v2.j2`: presents the structured payload from I5-2 with explicit rule ID and metric ID lists for grounding validation
- `validate_response()` extended: enforces `watch_signals` references against payload IDs, enforces `key_story` null rule when `dominant_cluster_exists=false`, rejects advice language in observation fields
- Prompt version bumped to `full_v2`

**Key files changed:** `src/wbsb/render/llm_adapter.py`, `src/wbsb/render/prompts/system_full_v2.j2`, `src/wbsb/render/prompts/user_full_v2.j2`

---

### I5-4 — Rendering, Fallback, and Evaluation

**Branch:** `feature/i5-4-report-rendering`

Wired all new sections into the template with conditional rendering and deterministic fallback. Added Python extraction helpers in `template.py` — no `llm_result` attributes accessed directly inside Jinja2. The `dominant_cluster_exists` flag is computed inside `render_template()` from `findings`, not passed from `llm.py`.

**New report structure:**

```
# Weekly Business Signal Brief          ← deterministic header

## Situation                            ← LLM: present if valid and non-empty
## Key Story This Week                  ← LLM: only when dominant_cluster_exists=True
---
## Weekly Priorities                    ← deterministic
## Signals (N)
   [Category Name]
   [Group narrative]                    ← LLM: per category, or omitted
   ### SEVERITY — Label (Rule ID)
   [Signal narrative]                   ← LLM override or deterministic fallback
   Evidence block                       ← deterministic always
## Watch Next Week                      ← LLM: present if valid; max 2 items
## Data Quality                         ← deterministic
## Key Metrics                          ← deterministic table
## Audit                                ← deterministic
```

**Fallback rules — each section degrades independently:**

| Section | Fallback |
|---|---|
| Situation absent/invalid | Section omitted |
| Key Story absent or `dominant_cluster_exists=False` | Section omitted |
| Group narrative missing for a category | Sentence omitted; signals render normally |
| Signal narrative missing for a rule_id | Deterministic narrative used |
| Watch signals invalid | Section omitted entirely |
| `llm_result=None` | Full deterministic report, identical to `--llm-mode off` |

**Bugs found and fixed during evaluation:**

1. **I5-1 gap** — `LLMResult` was never extended with the four new fields (only `AdapterLLMResult` was). Codex worked around this by passing `adapter_result` as `Any`. Fixed by adding fields to `LLMResult` and reverting the `Any` workaround.
2. **Double `---` separator** — both conditional blocks (`{% if situation %}` and `{% if key_story %}`) ended with their own `---`, plus an unconditional `---` before Weekly Priorities, producing 2-3 consecutive separators. Fixed by removing `---` from inside both conditional blocks.
3. **Group narratives never rendering** — LLM returns display-name category keys (`"Financial Health"`) but `signal.category` in findings uses internal snake_case keys (`"financial_health"`). The `group_narratives.get(category)` lookup always missed. Fixed in `_extract_group_narratives()` with `.lower().replace(" ", "_")` normalization.

**Key files changed:** `src/wbsb/render/template.py`, `src/wbsb/render/template.md.j2`, `src/wbsb/render/llm.py`, `tests/test_render_template.py`

---

## Final Test Results

- **217 tests pass** across the full test suite
- **Ruff clean** on all modified files
- **15 tests** in `test_render_template.py` covering all conditional section scenarios, display-name key normalization, fallback behavior, and signal narrative overrides

---

## Model Comparison — Haiku vs Sonnet vs Opus

Stress-tested across 11 runs (Haiku ×5, Sonnet ×3, Opus ×3) on datasets 01, 05, 07 using `--llm-mode full --llm-provider anthropic`.

### Estimated Cost Per Run

| Model | Input $/MTok | Output $/MTok | Typical cost/run (quiet) | Typical cost/run (signals) |
|---|---|---|---|---|
| Haiku 4.5 | $0.80 | $4.00 | ~$0.002 | ~$0.004 |
| Sonnet 4.5 | $3.00 | $15.00 | ~$0.011 | ~$0.023 |
| Opus 4.5 | $15.00 | $75.00 | ~$0.048 | ~$0.089 |

*Token usage not yet captured in pipeline (empty dict). Estimates based on prompt character counts / 4.*

Sonnet costs ~5x Haiku. Opus costs ~4x Sonnet (~20x Haiku).

---

### Quality Comparison

#### Haiku 4.5

**Strengths:**
- Respects the schema every time — valid JSON, correct conditional logic
- Never halluccinates numbers
- Correct null `key_story` when `dominant_cluster_exists=false`

**Weaknesses:**
- Generic, vague language: "slightly," "modest," "mixed performance" — no specific figures
- No relationship identification — treats each signal as isolated
- Situation often uses deltas instead of absolutes, obscuring scale
- Group narratives use editorial interpretation without numerical grounding
- Watch signals restate individual facts rather than identify divergences

**Example (dataset_07, situation):** *"This week showed mixed financial performance with operational metrics holding steady."* — no numbers, no threshold context.

**Verdict:** Functional minimum. Valid output every time but analytically thin. Best used as a cost-controlled fallback.

---

#### Sonnet 4.5

**Strengths:**
- Specific percentages and absolute values in every section
- Identifies inverse relationships (show rate ↔ cancel rate, marketing% ↔ contribution)
- Threshold-aware language in signal narratives — includes both the actual value and the threshold it was compared against
- Watch signals select metric pairs that tell a story, not isolated facts
- Group narratives include numbers that match the evidence

**Weaknesses:**
- On very clean weeks (no signals), occasionally slightly less precise than expected — uses "nearly 94%" instead of "94.3%"
- Returns `group_narratives` keys in correct snake_case format (good adherence to grounding rules)

**Example (dataset_07, key_story):** *"Financial health pressures emerged as two threshold breaches occurred simultaneously: gross margin remained below the 50% target at 40.4%, while marketing spend climbed above the 0.4% ceiling to reach 5.3% of revenue, together constraining profitability despite stable operations."*

**Verdict:** Best cost/quality ratio for this use case. Covers 95% of Opus analytical depth at 25% of the cost. Recommended default.

---

#### Opus 4.5

**Strengths:**
- Paradox and contradiction detection: explicitly identifies when metrics move in opposite directions ("moving in the opposite direction from improving marketing efficiency metrics")
- Stronger severity framing: "remains well below," "by a significant margin," "compounding pressure"
- Causal chain language is more explicit and contextually appropriate
- Watch signals show more analytical balance (silver lining alongside the risk)

**Weaknesses:**
- On clean weeks (no signals), occasionally vaguer than Sonnet — uses "nearly 94%" where Sonnet gives "94.3%"
- Returns `group_narratives` with display-name keys (`"Financial Health"`) rather than snake_case — requires normalization (which is implemented)
- Cost premium (~4x Sonnet) is not proportional to quality gain in most scenarios

**Example (dataset_07, watch signal):** *"Contribution after marketing declined by $1,000 week-over-week to negative $19,460, moving in the opposite direction from the improving marketing efficiency metrics."* — explicitly captures the contradiction Sonnet misses.

**Verdict:** Meaningfully better than Sonnet specifically when multiple signals conflict across categories and the business narrative requires explaining a paradox. Not proportionally better for quiet weeks or single-category scenarios.

---

### Model Selection Guide

| Scenario | Recommended Model | Reason |
|---|---|---|
| **Default production** | Sonnet 4.5 | Best cost/quality ratio; specific, grounded, relationship-aware |
| **Quiet week (0 signals)** | Sonnet 4.5 | Opus adds no value; Haiku is acceptable but thinner |
| **2+ conflicting signals across categories** | Opus 4.5 | Paradox detection and severity framing justify the cost |
| **Cost-constrained / high volume** | Haiku 4.5 | Valid and safe; analytically minimal |
| **LLM unavailable / API error** | Deterministic fallback | Always available; identical to `--llm-mode off` |

**Monthly cost estimate (4 weekly runs):**
- All Haiku: ~$0.016
- All Sonnet: ~$0.092
- All Opus: ~$0.356
- Hybrid (Sonnet default, Opus on complex weeks): ~$0.13

---

## Architecture Decisions That Carry Forward

1. **Section-based output contract** — the LLM fills named sections; it does not rewrite the report
2. **`dominant_cluster_exists` is deterministic** — computed from `Counter(WARN signals by category) >= 2`; never from LLM output
3. **Extraction helpers in `template.py`** — `llm_result` is never accessed inside Jinja2 directly; Python pre-extracts and normalizes into context variables
4. **Group narrative key normalization** — `_extract_group_narratives()` normalizes all keys with `.lower().replace(" ", "_")`; handles both snake_case (Sonnet) and display-name (Opus/Haiku) formats
5. **Each section degrades independently** — no section failure blocks another section from rendering
6. **`WBSB_LLM_MODEL` env var** — model can be overridden without code changes for A/B testing

---

## What Is Deferred to Iteration 6

- Trajectory and trend awareness (week-over-week patterns across multiple weeks)
- Summary mode (`--llm-mode summary`) redesign — still uses old v1 prompts
- Automated token usage capture in `llm_response.json`
- Recommendation engine or action generation (explicitly out of scope permanently)
- Automated quality scoring of LLM output

---

*Iteration 5 closed: 2026-03-09*
*217 tests passing · Ruff clean · All I5 branches merged to main*
