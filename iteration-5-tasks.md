# Iteration 5 Tasks — WBSB
## Constrained Business Interpretation Layer

**Theme:** Report Architecture First · Section-Based LLM Output · Deterministic Input Structuring · Grounded Interpretation · Safe Fallback

---

## Section 1 — Architecture Audit (Post-Iteration 4)

### 1.1 What Iteration 4 Delivered

| Capability | Status |
|---|---|
| `--llm-mode off \| summary \| full` CLI flags | ✅ Complete |
| `--llm-provider anthropic` with OpenAI guard | ✅ Complete |
| `render_llm()` with deterministic fallback | ✅ Complete |
| `render_template(findings, llm_result)` with LLM overlay | ✅ Complete |
| Per-signal narrative overrides in `full` mode | ✅ Complete |
| Executive summary injection | ✅ Complete |
| `llm_response.json` artifact with prompts and raw response | ✅ Complete |
| Manifest LLM observability fields | ✅ Complete |
| `validate_response()` with JSON and schema validation | ✅ Complete |
| Markdown fence stripping before JSON parse | ✅ Complete |
| `AnthropicClient` with safe text block extraction | ✅ Complete |
| Deterministic fallback on all LLM failure modes | ✅ Complete |

### 1.2 Current LLM Output Contract

The LLM currently produces two fields:

```json
{
  "executive_summary": "string",
  "signal_narratives": {
    "narratives": {
      "<rule_id>": "string"
    }
  }
}
```

The `executive_summary` maps to a section prepended to the report.
The `signal_narratives` overrides per-signal deterministic sentences in the report body.

### 1.3 What the LLM Currently Does

In practice, the LLM in full mode:

- Restates individual signals as slightly improved sentences
- Writes an executive summary that is mostly a concatenation of the top signals
- Does not explain relationships between signals
- Does not identify which cluster of signals is driving the primary business outcome
- Treats nine independent signals as nine independent writing tasks

This is the correct starting point for a system that prioritizes safety and grounding. It is not the right stopping point for a system that is supposed to help an operator understand their business.

### 1.4 Root Cause of the Summarizer Behavior

Two structural causes, not a prompt quality problem:

**Input structure:** Signals arrive at the LLM as a flat numbered list. Acquisition signals that are causally linked (CAC, conversion rate, new clients) appear as items 4, 8, and 6 in a sequence with no structural indication that they are related. The model must independently infer the relationship before reasoning about it.

**Output schema:** The current schema requests one sentence per signal. This is a per-signal restating task, not a relational synthesis task. The model produces what the schema requests.

Neither problem is solved by adding adjectives to prompt instructions. Both require structural changes.

### 1.5 Current Report Structure

```
# Weekly Business Signal Brief          ← deterministic header
## Executive Summary                    ← LLM executive_summary (if present)
---
## Weekly Priorities                    ← deterministic
## Signals (N)                          ← per-signal, grouped by category
   narrative line                       ← LLM or deterministic fallback per signal
   Evidence block                       ← deterministic
## Data Quality                         ← deterministic
## Key Metrics                          ← deterministic table
## Audit                                ← deterministic
```

This structure derives its layout from what the LLM produces. Iteration 5 inverts the dependency: the report structure defines what the LLM must produce.

---

## Section 2 — Iteration 5 Goal

### What Iteration 5 IS

- Define the final Markdown report structure before redesigning prompts
- Improve the structure of evidence passed to the LLM without modifying the analytics engine
- Replace the per-signal output schema with a section-level output schema
- Make the report read like an operator briefing, not a signal listing
- Add a conditional synthesis section that only fires when the data supports it
- Preserve all deterministic fallback behavior

### What Iteration 5 IS NOT

- A change to deterministic metric calculations
- A change to signal detection or the rules engine
- A change to the pipeline architecture or domain models
- A change to the artifact structure (findings.json, manifest.json schemas)
- A recommendation engine or action generator
- A causal inference system embedded in deterministic code
- An attempt to build a hidden second analytics layer
- A full-text rewrite of the report by the LLM

---

## Section 3 — Architectural Principles

These principles govern all design decisions in Iteration 5. Any proposal that violates a principle must be revised, not approved.

1. **Report structure before prompt wording.** The Markdown report structure defines what the LLM must produce. The JSON schema is derived from the report. Prompt instructions are written against section responsibilities. No prompts are written before the report structure is settled.

2. **Input structure matters more than prompt adjectives.** Structured, pre-organized evidence reduces the inference burden on the model. A model given a pre-clustered acquisition funnel view will reason about it more reliably than a model instructed to "look for relationships" in a flat list.

3. **Deterministic preprocessing organizes evidence; it does not interpret it.** The Python layer may group signals by category, compute category-level summaries, and present metric chains as sequences. It may not classify root causes, assign blame, or make causal claims.

4. **LLM output is section-based, not a free-form rewrite.** The model fills discrete report sections, each with a defined responsibility. It does not produce a single narrative block that replaces the whole report.

5. **Validation and graceful fallback are mandatory.** Every LLM-produced section is optional from the template's perspective. If a section is invalid or absent, the template renders a deterministic fallback or omits the section. The deterministic report is always valid.

6. **Do not force a narrative when the data does not support one.** The "Key Story" synthesis section is conditional. If signals are distributed independently across unrelated categories, the section is omitted. The triggering condition is deterministic.

7. **Interpretation sections require grounding.** If the LLM references a signal, metric, or trend, that reference must correspond to something in the findings payload. Validation must check this. Fabricated cross-category stories must be rejected.

8. **Neutral verbs in deterministic hints.** Any relationship hints passed to the LLM from the deterministic layer must use neutral, factual language. Allowed: moved, changed, co-occurred, diverged, offset, remained stable. Not allowed: because, driven by, indicates, suggests, caused, due to.

---

## Section 4 — Report Structure Definition

This is the target Markdown structure that Task 1 must finalize and that all subsequent tasks must implement.

```
# Weekly Business Brief — Week of [DATE]
[Run ID, generated timestamp, period dates]                ← deterministic

---

## Situation                                               ← LLM: situation field
[2–3 sentences. Operator-level. No signal identifiers.    LLM-generated or ABSENT
No metric IDs. What happened in the business this week.]

---

## Key Story This Week                                     ← CONDITIONAL
[Present ONLY when dominant_cluster_exists = True.        LLM: key_story field or ABSENT
1–2 paragraphs. Identifies which cluster drove the
primary outcome. Explains relationships between signals
in that cluster. No fabricated cross-category stories.]

---

## Signal Detail                                           ← Template-rendered
                                                           Grouped by category
[Category name — N WARN signals]
[Group narrative: one sentence for the cluster]           ← LLM: group_narratives[category]
                                                             or deterministic fallback

  ### SEVERITY — Signal Label (Rule ID)
  [Signal narrative]                                       ← LLM signal_narratives[rule_id]
  **Evidence:**                                              or deterministic fallback
  - Current / Previous / Delta / Threshold               ← deterministic always

---

## Watch Next Week                                         ← CONDITIONAL
[1–2 observation targets for the coming week.             LLM: watch_signals field or ABSENT
Not advice. What to monitor and why the direction
of each metric will indicate recovery or compounding.
Only metrics/signals present in findings.]

---

## Metrics Snapshot                                        ← deterministic always

---

## Data Quality / Audit                                    ← deterministic always
```

### Section Responsibilities

| Section | Source | Condition |
|---|---|---|
| Header | Deterministic | Always |
| Situation | LLM `situation` | Present if LLM succeeded and field is valid |
| Key Story | LLM `key_story` | Only when `dominant_cluster_exists = True` |
| Signal Detail — group narrative | LLM `group_narratives[category]` | Per category if valid; else deterministic |
| Signal Detail — per-signal narrative | LLM `signal_narratives[rule_id]` | Per signal if valid; else deterministic |
| Signal Detail — evidence | Deterministic | Always |
| Watch Next Week | LLM `watch_signals` | Present if field is valid; else omit |
| Metrics Snapshot | Deterministic | Always |
| Data Quality / Audit | Deterministic | Always |

### JSON Schema (Target)

Derived from the report structure above. This schema replaces the current two-field schema.

```json
{
  "situation": "string (2–3 sentences, no signal IDs, no metric IDs)",
  "key_story": "string or null",
  "group_narratives": {
    "<category>": "string"
  },
  "signal_narratives": {
    "<rule_id>": "string"
  },
  "watch_signals": [
    {
      "metric_or_signal": "string (must match metric_id or rule_id in findings)",
      "observation": "string (one clause: what the direction will indicate)"
    }
  ]
}
```

`key_story` is `null` when `dominant_cluster_exists` is `False`.
`group_narratives` contains only categories that have signals.
`signal_narratives` is optional; if absent, deterministic narratives are used for all signals.
`watch_signals` contains at most 2 items.

### Dominant Cluster Condition

Computed deterministically in Python before the LLM call:

```python
cluster_sizes = Counter(s.category for s in findings.signals if s.severity == "WARN")
dominant_cluster_exists = max(cluster_sizes.values(), default=0) >= 2
```

This flag is passed to the prompt as a fact. The LLM does not decide whether a dominant cluster exists.

---

## Section 5 — Task Breakdown

---

### Task I5-1 — Report Architecture and Output Contract

**Purpose:** Finalize the report structure, derive the JSON schema, and establish the output contract before any prompt or template code is written. All subsequent tasks depend on this.

**This task defines — it does not implement.**

#### Deliverables

1. **Finalized report structure** — the Markdown skeleton from Section 4, reviewed and locked. Section responsibilities documented with explicit source (deterministic vs LLM) and condition for each section.

2. **Locked JSON schema** — derived from the report structure. Every field has a defined type, a defined condition (required/optional/conditional), and a defined fallback behavior.

3. **Dominant cluster algorithm** — the deterministic boolean `dominant_cluster_exists`, computed from findings. Formula: `max(WARN signals per category) >= 2`. Algorithm must not reference LLM output.

4. **Updated `AdapterLLMResult`** — extend with the new fields: `situation`, `key_story`, `group_narratives`, `watch_signals`. The existing `executive_summary` and `signal_narratives` fields are retained for backward compatibility until Task I5-4 removes them.

5. **Updated `LLMResult` domain model** — mirror the new fields. No pipeline logic changes.

#### Allowed Files

```
src/wbsb/domain/models.py           ← add fields to LLMResult
src/wbsb/render/llm_adapter.py      ← add fields to AdapterLLMResult; update validate_response
```

#### Acceptance Criteria

- Report structure documented and frozen (this document updated if changes occur)
- JSON schema table is complete: field name, type, condition, fallback
- `AdapterLLMResult` and `LLMResult` extended without breaking existing tests
- `validate_response()` updated to validate new fields without rejecting old responses (backward-compatible transition)
- All existing tests pass
- Ruff clean

---

### Task I5-2 — Deterministic Input Structuring

**Purpose:** Improve the structure of evidence passed to the LLM. The model receives pre-organized, category-clustered input rather than a flat signal list. No analytical interpretation is introduced in Python.

#### What Changes

**Signal presentation in user prompt:** Signals are grouped by category with a category-level header and cluster summary before individual signals. The flat numbered list is replaced by a categorized structure.

Current:
```
Signal 1: rule_id: B1, label: CAC Rising, category: acquisition ...
Signal 4: rule_id: C1, label: Conversion Falling, category: acquisition ...
Signal 6: rule_id: G1, label: New Clients Falling, category: acquisition ...
```

Target:
```
ACQUISITION (3 WARN signals — all adverse)
  Signal B1: Customer Acquisition Cost Rising
    current: $236 | prior: $146 | +61.5%
  Signal C1: Paid Lead Conversion Falling
    current: 64.3% | prior: 83.9% | -23.4%
  Signal G1: New Client Acquisition Falling
    current: 29 | prior: 41 | -29.3%
```

**Business mechanism chains:** For the paid acquisition funnel, present the key metrics as an ordered chain using existing `MetricResult` values. This is arithmetic over already-computed data.

```
PAID ACQUISITION CHAIN
Ad spend:          $X → $Y     ↑/↓ Z%
Paid leads:        N → M       ↑/↓ Z%
Conversion rate:   X% → Y%     ↑/↓ Z%
Paid new clients:  N → M       ↑/↓ Z%
CAC:               $X → $Y     ↑/↓ Z%
```

Similarly for the operational chain: `bookings → show_rate → cancel_rate → completed appointments`.

**Category health summary:** Prepend a compact status table to the signal section:

```
SIGNAL CLUSTER SUMMARY
Acquisition:      3 WARN — all signals adverse
Financial Health: 3 WARN — all signals adverse
Operations:       2 WARN — all signals adverse
Revenue:          1 WARN
```

**Dominant cluster flag:** Include `dominant_cluster_exists: true/false` and the dominant category name in the user prompt header so the LLM receives this as a stated fact, not something it must infer.

#### Guardrails for Relationship Hints

If any descriptive co-movement notes are added, they must:

- Reference only deterministic fields (current value, previous value, delta)
- Use only neutral verbs: moved, changed, co-occurred, diverged, offset, remained stable
- Never use causal language: because, driven by, indicates, suggests, caused, due to
- Never make recommendations
- Never reference future periods

#### What Does NOT Change

- `prepare_render_context()` — not modified
- `build_prompt_inputs()` — extended, not restructured
- All metric calculations and signal detection — untouched

#### Allowed Files

```
src/wbsb/render/llm_adapter.py      ← extend build_prompt_inputs()
src/wbsb/render/prompts/            ← update user prompt templates
tests/test_llm_adapter.py           ← extend tests for new prompt input structure
```

#### Acceptance Criteria

- User prompt presents signals grouped by category, not as a flat list
- Business mechanism chains are included for acquisition and operational funnels
- Category health summary is present in user prompt
- `dominant_cluster_exists` and dominant category are stated in user prompt
- No causal language in any deterministic-layer text passed to the LLM
- All existing tests pass; new tests added for extended `build_prompt_inputs()`
- Ruff clean

---

### Task I5-3 — Prompt and LLM Contract Redesign

**Purpose:** Redesign the system and user prompts so the model produces section-level output against the locked schema from Task I5-1. Prompt instructions are written against section responsibilities, not against vague quality targets.

#### System Prompt Redesign

Replace the current system prompt with one that:

1. Defines the analyst role with behavioral specificity:
   > You are a senior business analyst producing a structured weekly performance brief for an appointment-based service business. Your job is to fill specific sections of a structured report using the data you are given. You are not summarizing signals. You are interpreting what the signals collectively mean for the business, within the strict constraints below.

2. Defines section-level responsibilities explicitly:
   - **Situation:** 2–3 sentences at operator level. No signal identifiers. No metric IDs. State what happened in the business.
   - **Key Story:** Only produce this if `dominant_cluster_exists: true` is stated in the payload. Explain what the dominant cluster of signals means for the business. Reference signal relationships within the cluster. Do not fabricate connections to other categories.
   - **Group narratives:** One sentence per category that fired. Synthesize the signals in that category. Do not restate individual signal labels.
   - **Signal narratives:** One concise sentence per signal. Reference the direction and magnitude from the evidence. No invented numbers.
   - **Watch signals:** At most 2 items. Use only metric_ids or rule_ids that appear in the payload. State what the metric's direction next week will indicate — not what the operator should do.

3. Defines anti-hallucination constraints:
   - Do not reference business conditions not evidenced by a signal in the payload
   - Do not invent numbers; all figures must appear in the evidence data
   - Do not suggest root causes not present in the payload
   - Do not reference external factors (seasonality, market conditions, competition)
   - If `dominant_cluster_exists: false`, set `key_story` to null

4. States the grounding requirement:
   - Every reference in `watch_signals` must match a `metric_id` or `rule_id` in the payload
   - Every figure cited in any narrative must appear in the evidence fields

#### User Prompt Redesign

The user prompt is the data payload. It should:

1. State `dominant_cluster_exists` and the dominant category at the top
2. Present the cluster summary (from Task I5-2)
3. Present business mechanism chains (from Task I5-2)
4. Present signals grouped by category (from Task I5-2)
5. End with the explicit rule ID list for grounding validation

Remove: the flat numbered signal list from the current prompt.

#### Prompt Versioning

New templates are `system_full_v2.j2` and `user_full_v2.j2`. The version constant in `llm_adapter.py` is updated to `full_v2`. The v1 templates are retained in git history and can be restored via revert; they are not maintained as live parallel files.

Summary mode prompts are not redesigned in this iteration. The current `summary_v1` templates remain.

#### Grounding Validation in `validate_response()`

Extend `validate_response()` to check:

- `watch_signals` entries reference only `metric_id` or `rule_id` values present in `expected_rule_ids` (passed in from prompt inputs)
- No field exceeds defined length bounds (existing behavior retained)
- `key_story` is null when `dominant_cluster_exists` was false in the prompt payload

#### Allowed Files

```
src/wbsb/render/llm_adapter.py           ← update validate_response(); update version constant
src/wbsb/render/prompts/system_full_v2.j2    ← new
src/wbsb/render/prompts/user_full_v2.j2      ← new
tests/test_llm_adapter.py                ← extend validation tests
```

#### Acceptance Criteria

- `system_full_v2.j2` and `user_full_v2.j2` exist and are the active templates
- System prompt defines section responsibilities explicitly, not by quality adjectives
- User prompt presents clustered, structured evidence (depends on Task I5-2)
- `validate_response()` enforces grounding for `watch_signals`
- `validate_response()` enforces `key_story` null rule
- All existing tests pass; new validation tests added
- Ruff clean

---

### Task I5-4 — Rendering, Validation, Fallback, and Evaluation

**Purpose:** Integrate the new report sections into `template.md.j2` and `render_template()` with correct conditional logic and deterministic fallback. Establish the evaluation harness.

#### Template Changes

Implement the report structure from Section 4:

1. **Situation section** — conditional on `llm_result` present and `situation` field valid and non-empty. Placed before Weekly Priorities.

2. **Key Story section** — conditional on `dominant_cluster_exists = True` AND `llm_result` present AND `key_story` field valid and non-empty. If condition is false or key_story is null, section is omitted entirely. No fallback content.

3. **Signal Detail grouping** — signals are already grouped by category in the current template. Add `group_narratives[category]` rendering above each group's signal list. If the group narrative for a category is absent or invalid, omit the group-level sentence and render signals normally.

4. **Watch Next Week section** — conditional on `llm_result` present and `watch_signals` field valid and non-empty. Omit if invalid or absent.

5. **Weekly Priorities** — retained as-is (deterministic).

6. **Metrics Snapshot and Audit** — unchanged.

#### Render Context Changes

Extend `render_template(findings, llm_result)` to pass:

- `situation` — extracted from `llm_result.situation` or `None`
- `key_story` — extracted from `llm_result.key_story` or `None`
- `group_narratives` — extracted from `llm_result.group_narratives` or `{}`
- `watch_signals` — extracted from `llm_result.watch_signals` or `[]`
- `dominant_cluster_exists` — computed deterministically from findings (not from LLM)

#### Fallback Rules

| Section | Fallback behavior |
|---|---|
| Situation invalid or absent | Section omitted |
| Key Story invalid | Section omitted (never force a fallback narrative) |
| Key Story when `dominant_cluster_exists = False` | Section omitted regardless of LLM output |
| Group narrative invalid for a category | Group-level sentence omitted; per-signal rendering continues normally |
| Signal narrative invalid for a rule_id | Deterministic narrative used for that signal |
| Watch signals invalid | Section omitted |
| Metrics Snapshot | Always deterministic |
| Data Quality / Audit | Always deterministic |

#### Evaluation Harness

A lightweight evaluation process, not an automated scoring system.

**Canonical dataset:** 6–8 real historical run datasets (from `runs/` or `examples/datasets/`) selected to represent distinct analytical situations:

| Case | Description | Key expected behavior |
|---|---|---|
| Clean week | No signals fired | Situation present, no Key Story, no Watch signals |
| Single cluster | 3+ WARN in acquisition only | Key Story present, references acquisition signals |
| Independent signals | 1 WARN per category, unrelated | Key Story absent, group narratives only |
| High-volume compound | 5+ WARN in 2+ categories | Key Story for dominant; group narratives for others |
| Fallback test | Mock LLM returns invalid JSON | Full deterministic report, no LLM sections |
| Fallback test | Mock LLM returns null key_story | Key Story absent; other sections present |

**Evaluation checklist per case:**
- [ ] Situation section present/absent as expected
- [ ] Key Story present only when `dominant_cluster_exists = True`
- [ ] Key Story references signals from the dominant category only
- [ ] Group narratives present for firing categories
- [ ] Watch signals reference only metric_ids or rule_ids from findings
- [ ] No fabricated figures in any narrative
- [ ] Deterministic fallback renders cleanly when LLM output is invalid
- [ ] Metrics table and audit unchanged in all cases

**Evaluation is manual.** Run each case, read the output, check the list. No automated quality scoring.

#### Allowed Files

```
src/wbsb/render/template.py          ← extend extraction helpers; pass new context fields
src/wbsb/render/template.md.j2       ← implement new section structure
src/wbsb/render/llm.py               ← pass dominant_cluster_exists to render_template
tests/test_render_template.py        ← add conditional section tests
tests/test_llm_integration.py        ← add fallback behavior tests for new sections
```

#### Acceptance Criteria

- All new report sections render correctly in full mode with valid LLM output
- All conditional sections are absent when conditions are not met
- Deterministic fallback renders a valid, complete report when LLM fails entirely
- No LLM content appears in deterministic (`--llm-mode off`) runs
- Evaluation harness documented and run against canonical cases
- All existing tests pass; new tests added for conditional rendering
- Ruff clean

---

## Section 6 — Dependencies and Execution Order

### Dependency Graph

```
Task I5-1 (Report Architecture + Schema)
    │
    ├──► Task I5-2 (Deterministic Input Structuring)
    │         │
    │         └──► Task I5-3 (Prompt Redesign)  ◄── also depends on I5-1
    │                   │
    └──────────────────►│
                        └──► Task I5-4 (Rendering + Fallback + Evaluation)
```

Tasks I5-2 and I5-3 can begin in parallel after I5-1 is complete. Task I5-3 is finalized only after I5-2 is done because the user prompt structure depends on the input structuring decisions.

### Execution Phases

**Phase A — Architecture (sequential, required first)**

Complete Task I5-1 entirely. Lock the report structure and JSON schema. Update `AdapterLLMResult` and `LLMResult` with new fields. No prompt or template work begins until this is done.

**Phase B — Input and Prompt (partially parallel)**

Task I5-2 can begin immediately after Phase A. Task I5-3 can begin after Phase A and drafts a system prompt; user prompt finalization waits for I5-2 to be complete. These two tasks share the user prompt template — coordinate to avoid conflicts.

**Phase C — Rendering and Evaluation (sequential, last)**

Task I5-4 begins only after I5-1, I5-2, and I5-3 are complete. It assembles and integrates everything.

### Why This Is Not Fully Parallel

The report structure (I5-1) is the source of truth for both the JSON schema (used in I5-3 validation) and the template sections (built in I5-4). Starting prompt or template work before the structure is locked creates rework. The Phase A gate is not bureaucratic overhead — it prevents rewriting the same code twice.

---

## Section 7 — Ownership Matrix

### Ownership Logic

**Claude** is better suited for decisions that require evaluating whether output reads like an operator briefing, whether a conditional section is justified, and whether a narrative constraint is sufficient to prevent a specific failure mode.

**Codex** is better suited for decisions about schema design, validation logic, fallback implementation, deterministic computation, and test coverage.

### Task Ownership

| Task | Lead | Reviewer |
|---|---|---|
| I5-1 Report Architecture and Output Contract | Claude | Codex reviews schema feasibility and backward compatibility |
| I5-2 Deterministic Input Structuring | Codex | Claude reviews whether structure supports synthesis without over-constraining |
| I5-3 Prompt and LLM Contract Redesign | Codex | Claude reviews whether section instructions produce operator-quality output |
| I5-4 Rendering, Validation, Fallback, Evaluation | Codex | Claude optionally reviews final report readability against canonical cases |

### Practical Split

For a solo developer using both Claude and Codex:

- Use Claude for document review, narrative constraint design, and final report readability checks
- Use Codex for implementation of schema changes, validation logic, template mechanics, and test coverage
- Do not use either for architectural decisions without the other present — the ownership split is for implementation, not for the design decisions captured in this document

---

## Section 8 — Minimum Viable Iteration 5

For a solo developer who needs to ship the most meaningful improvement with the least risk, the minimum viable Iteration 5 is:

### Three Tasks

**1. Define report architecture and section responsibilities (I5-1)**
Lock the structure. Derive the schema. Update the domain models. Nothing else ships until this is done.

**2. Add deterministic structured input improvements (I5-2)**
Group signals by category in the user prompt. Add the category health summary. Add the acquisition and operational chain views using existing metrics. No causal language.

**3. Redesign the LLM contract and wire the rendering/fallback (I5-3 + I5-4 merged)**
Update the system prompt to define section responsibilities. Update the JSON schema to match the report structure. Add Situation, Key Story (conditional), and Watch signals to the template with full fallback behavior.

### What Is Explicitly Deferred

- Recommendation or action generation of any kind
- Complex causal graph logic in the deterministic layer
- Automated quality scoring of LLM output
- A hidden second analytics layer that makes business judgments in Python
- Large expansion of deterministic business rules to support interpretation
- Summary mode redesign
- Trajectory and trend awareness (planned for Iteration 6)

---

## Section 9 — Risks and Guardrails

| Risk | Severity | Mitigation |
|---|---|---|
| Prompt redesign produces plausible but fabricated cross-category stories | High | Grounding validation in `validate_response()`; Key Story condition gated on deterministic flag |
| Dominant cluster condition triggers too aggressively | Medium | Threshold of 2 is conservative; can be raised to 3 if needed |
| New JSON schema breaks backward compatibility with existing valid responses | Medium | New fields are additive; old fields retained; validation is non-strict on new fields initially |
| Input structuring introduces causal language in Python-layer text | High | All deterministic text reviewed against neutral-verb guardrail before shipping |
| Evaluation is skipped under time pressure | Medium | Evaluation checklist is part of Task I5-4 acceptance criteria; not optional |
| `watch_signals` grounding validation too strict | Low | Validate against `metric_id` OR `rule_id`; at most 2 items reduces surface area |
| Watch signals section degrades into advice | High | Template renders as observation targets only; system prompt forbids recommendations |
| Schema expansion increases validate_response complexity | Low | Each new field has a defined validation rule; rules are independent and testable |

---

## Section 10 — Acceptance Criteria (Iteration 5 Complete)

Iteration 5 is complete when all of the following are true:

**Architecture**
- [ ] Report structure is documented, locked, and implemented
- [ ] JSON schema is derived from the report structure (not the reverse)
- [ ] `dominant_cluster_exists` is computed deterministically and not influenced by LLM output

**Input Structuring**
- [ ] Signals are grouped by category in the user prompt
- [ ] Category health summary is present in the user prompt
- [ ] Business mechanism chains are included for acquisition and operational funnels
- [ ] No causal language appears in any deterministic text passed to the LLM

**LLM Output**
- [ ] `situation` field produced and validated
- [ ] `key_story` produced when `dominant_cluster_exists = True`; null when false
- [ ] `group_narratives` produced per firing category
- [ ] `watch_signals` grounding validated against findings payload
- [ ] Schema validation rejects fabricated watch signal references

**Rendering**
- [ ] Situation section renders in full mode when valid
- [ ] Key Story section renders only when `dominant_cluster_exists = True` and field is valid
- [ ] Key Story section is absent in all deterministic-mode runs
- [ ] Group narratives render above signal groups; fall back gracefully when absent
- [ ] Watch signals render when valid; omitted otherwise
- [ ] Metrics Snapshot and Audit are deterministic and unchanged in all modes

**Fallback**
- [ ] `--llm-mode off` produces an identical report to the current deterministic baseline
- [ ] Complete LLM failure (any failure mode) produces a valid deterministic report
- [ ] Individual section failures degrade gracefully without affecting other sections

**Evaluation**
- [ ] Canonical evaluation dataset assembled (6–8 real historical runs)
- [ ] Evaluation checklist run against all canonical cases
- [ ] No fabricated cross-category stories found in any canonical case

**Quality**
- [ ] All existing tests pass
- [ ] New tests cover conditional rendering, grounding validation, and fallback behavior
- [ ] Ruff clean

---

*Document created post-Iteration 4. Reflects design decisions from architectural review sessions.*
*All implementation decisions within each task defer to the principles in Section 3.*
