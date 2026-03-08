# Iteration 4 Tasks — WBSB
## Optional LLM Narrative Layer

**Theme:** Deterministic Core · Optional LLM Enhancement · Safe Fallback · Structured Output

> **Revision note:** This document incorporates a post-draft architectural review. Changes applied:
> CLI mode/provider separation; system+user dual-prompt architecture; enforced deterministic
> context boundary; full prompt artifact logging; executive summary as primary deliverable;
> tests distributed across tasks; future conversational mode explicitly deferred.

---

## Section 1 — Architecture Audit (Post-Iteration 3)

### 1.1 Confirmed Pipeline Flow

```
CLI (cli.py)
  └── execute() [pipeline.py]
        ├── file_sha256 + yaml_sha256           → audit hashes
        ├── load_data()      [ingest/loader.py]  → DataFrame
        ├── validate_dataframe() [validate/schema.py] → audit_events, validated df
        ├── resolve_target_week() [utils/dates.py]
        ├── build_findings() [findings/build.py]
        │     ├── compute_metrics() × 2 weeks
        │     ├── compute_delta() per metric
        │     ├── evaluate_rules() [rules/engine.py] → List[Signal]
        │     └── → Findings (domain model)
        ├── render branch:
        │     if llm_mode == "off"  → render_template(findings)  [render/template.py]
        │     else                  → render_llm(findings, mode)  [render/llm.py]  ← STUB
        └── write_artifacts()  [export/write.py]
              → findings.json, brief.md, manifest.json, logs.jsonl
```

### 1.2 Findings Document (domain/models.py)

`Findings` contains:
- `schema_version: "1.2"`
- `run: RunMeta` — run_id, generated_at, input_file, hashes, git_commit
- `periods: Periods` — current and previous week dates
- `metrics: list[MetricResult]` — 14 metrics with id, name, format_hint, current, previous, delta_abs, delta_pct
- `signals: list[Signal]` — fired rules, sorted by severity/priority/rule_id, each with: rule_id, severity, metric_id, label, category, priority, condition, explanation (audit string), evidence (dict), guardrails, reliability
- `audit: list[AuditEvent]`

`Manifest` currently has: run_id, generated_at, hashes, elapsed_seconds, artifacts (dict of hashes), signals_warn_count, signals_info_count, audit_events_count, **render_mode** (already present), config_version.

### 1.3 Render Context Layer (render/context.py)

`prepare_render_context(findings)` is a pure function returning:
- `findings`, `warn_count`, `info_count`, `top_warn`
- `top_signals` — first 3 WARN signals (engine-ordered)
- `severity_by_category` — ordered dict `{display_label: count}` WARN only
- `affected_categories` — sorted set
- `category_labels`, `metric_by_id`
- `signal_contexts` — list of dicts, one per signal, each containing:
  - `signal`, `category`, `metric`, `format_hint`, `threshold_hint`
  - `narrative` — deterministic human-readable sentence
  - **`narrative_inputs`** — structured raw dict (metric_name, metric_id, condition, direction, current_value, previous_value, delta_pct, delta_abs, threshold[_pct][_abs], category, category_display, severity, priority, label, rule_id)

### 1.4 LLM Path — Current State

`render/llm.py` is a **stub** that raises `NotImplementedError`. The pipeline branching point exists. The CLI currently accepts `--llm off|openai|anthropic` — but this flag conflates **mode** (behavior) with **provider** (backend), which is a design flaw addressed in Iteration 4.

### 1.5 Artifact Writing (export/write.py)

Writes findings.json (Pydantic JSON), brief.md, manifest.json. Hashes all artifacts. Raises on IO failure. No LLM-specific artifact or metadata is written yet.

### 1.6 What Iteration 3 Accomplished for LLM Readiness

| Capability | Status |
|------------|--------|
| Structured `narrative_inputs` per signal | ✅ Complete |
| Human-readable `narrative` per signal | ✅ Complete |
| Clean separation of audit explanation vs display | ✅ Complete |
| `prepare_render_context()` as presentation boundary | ✅ Complete |
| `top_signals` and `severity_by_category` for summary | ✅ Complete |
| LLM branching point in pipeline | ✅ Exists (routes to stub) |
| `render_mode` in manifest | ✅ Already tracked |

### 1.7 Architectural Weaknesses to Address

1. **Either-or rendering branch**: `render_llm` fully replaces `render_template`. Target architecture is template-as-base + optional LLM overlay — not two competing renderers.

2. **`render_llm` stub takes `Findings` directly**: It bypasses the render context layer. The LLM should consume `narrative_inputs` from the context, not raw `Findings` or raw JSON.

3. **Manifest lacks LLM observability fields**: No model name, prompt version, generation status, fallback flag, or token usage are captured.

4. **No LLM response artifact**: No `llm_response.json` for audit or debugging.

5. **Prompt storage**: No prompt template files exist; no prompt infrastructure.

6. **CLI flag conflates mode and provider**: `--llm anthropic` tells you the backend but not the behavior mode. These must be separate flags.

---

## Section 2 — Iteration 4 Goal

### What Iteration 4 IS:

- An optional LLM narrative enhancement layer that augments deterministic output
- **Primary deliverable**: LLM-generated executive summary paragraph (`--llm-mode summary`)
- **Secondary deliverable**: Enriched per-signal narratives in addition to summary (`--llm-mode full`)
- The deterministic brief is always produced first; LLM content is overlaid where it exists
- Safe fallback to deterministic output when LLM is disabled or fails
- Full observability: LLM status, model, prompt version, and token usage in manifest
- Structured, validated LLM output — not freeform prose that cannot be trusted

### What Iteration 4 IS NOT:

- A replacement for the rules engine or findings pipeline
- A system where LLM decides which signals exist
- An unvalidated prompt→paste pipeline with no output contracts
- A change to the deterministic analytics path in any way
- A rewrite of the pipeline architecture
- An interactive system that responds to user questions about the report *(see note below)*

### Note — Future Conversational / Report Analysis Mode (Explicitly Deferred)

A natural future capability for this system is allowing a user to ask follow-up questions about a generated report — for example: "Why did revenue drop?" or "What should I prioritize next week?" This would use the same `narrative_inputs` and `findings.json` as context for an interactive conversation.

**This is NOT part of Iteration 4.** Iteration 4 is strictly automatic, batch, one-shot report narrative generation. The conversational mode is architecturally compatible with the Iteration 4 design (the `LLMClientProtocol` and structured input contract would be reused) but requires separate product design around session management, prompt history, and safety guardrails for open-ended queries. It is deferred to a future iteration.

---

## Section 3 — Proposed Architecture

### 3.1 Target Rendering Flow

The key principle: `prepare_render_context()` is **never modified** by LLM output. It remains pure and deterministic. LLM overlay happens in a separate subsequent step.

```
Findings
  └── prepare_render_context(findings)         ← PURE, DETERMINISTIC, UNCHANGED
        └── ctx (deterministic render context)
              ├── [if llm_mode != "off"]
              │     ├── build_prompt_inputs(ctx)    ← extract LLM-relevant fields from ctx
              │     ├── render_system_prompt(mode)  ← Jinja system prompt template
              │     ├── render_user_prompt(prompt_inputs, mode) ← Jinja user prompt template
              │     ├── call_api(system, user, provider, model, timeout)
              │     ├── validate_response(raw_json, mode, expected_rule_ids)
              │     └── LLMResult | None (on any failure → fallback)
              └── render_template(findings, llm_result=llm_result)
                    ├── merge_llm_into_ctx(ctx, llm_result)  ← adds executive_summary, llm_narratives
                    └── template.md.j2
                          ├── executive_summary section (if llm_result and not fallback)
                          ├── Weekly Priorities (precomputed deterministic context)
                          ├── Signals (sc.narrative OR llm_narratives[rule_id] in full mode)
                          └── Metrics, Data Quality, Audit
```

**Boundary rule**: `prepare_render_context()` is called once and returns an immutable deterministic context. The LLM merge step operates on a copy at render time and does not mutate the original context.

### 3.2 Module Boundaries

| Module | Role | Changes |
|--------|------|---------|
| `render/llm_adapter.py` | LLM client protocol + prompt inputs builder + API call + validation + fallback | **New** |
| `render/prompts/` | Versioned Jinja2 prompt templates (system + user, per mode) | **New directory** |
| `render/llm.py` | Orchestrates LLM path using adapter; replaces stub | **Replace** |
| `render/template.py` | Accepts optional `llm_result`; merges into ctx copy at render time | **Extend** |
| `render/context.py` | **No changes** — remains pure and deterministic | **No change** |
| `domain/models.py` | Add `LLMResult`; extend `Manifest` with LLM fields | **Extend** |
| `export/write.py` | Write `llm_response.json`; pass LLM fields to manifest | **Extend** |
| `pipeline.py` | Update branch to pass mode + provider; pass `llm_result` to write_artifacts | **Minimal change** |
| `cli.py` | Split `--llm` into `--llm-mode` and `--llm-provider` | **Update** |

### 3.3 Rendering Mode Design

| `--llm-mode` | Behavior |
|--------------|----------|
| `off` (default) | Deterministic template only. No API calls. Current behavior preserved exactly. |
| `summary` | Template base + LLM generates executive summary paragraph. Single API call. **Primary I4 feature.** |
| `full` | Template base + LLM generates executive summary AND enriched per-signal narratives. Single API call. |

**Rationale for single call in `full` mode**: Sending all signal `narrative_inputs` in one structured prompt is cheaper, faster, and more stylistically coherent than N separate per-signal calls.

### 3.4 Key Design Decision — LLM Enhances, Template Is Always Base

`render_llm.py` will:
1. Call `prepare_render_context(findings)` — deterministic context, never touched by LLM
2. Call `build_prompt_inputs(ctx)` — extract the minimal fields needed for the prompt
3. Call `render_system_prompt(mode)` and `render_user_prompt(inputs, mode)` — Jinja templates
4. Call the LLM API — returns `LLMResult | None`
5. Call `render_template(findings, llm_result=llm_result)` — template always runs
6. Return `(brief_md, llm_result)`

`render_template` is **always called**. LLM adds to it, never replaces it.

### 3.5 Fallback Strategy

```
LLM call fails (timeout / API error / rate limit / invalid JSON / schema violation)
  → log failure with reason
  → llm_result = None
  → render_template(findings, llm_result=None)  ← deterministic output, complete and correct
  → manifest records: llm_status="fallback", llm_fallback_reason="<reason>"
```

No partial LLM content is used. Either the full validated response is used, or nothing.

---

## Section 4 — LLM Integration Strategy

### 4.1 Where LLM Lives

`src/wbsb/render/llm_adapter.py` — single module.

`src/wbsb/render/prompts/` — directory containing versioned Jinja2 prompt templates:

```
render/prompts/
  system_summary_v1.j2   ← system prompt for summary mode
  user_summary_v1.j2     ← user (data) prompt for summary mode
  system_full_v1.j2      ← system prompt for full mode
  user_full_v1.j2        ← user (data) prompt for full mode
```

### 4.2 Prompt Architecture — System + Generated User Prompt

Two distinct prompt layers are used for every API call. This is not a cosmetic distinction — they serve different safety and versioning purposes.

**System Prompt** (`system_*.j2`)

Defines the assistant role, constraints, output format, and safety rules. It is static per mode version. It does not contain any run-specific data.

Required contents:
- Role statement: "You are a business analyst summarizing pre-computed weekly analytics findings."
- Hard constraints: "Do not invent signals, metrics, trends, or recommendations not present in the data payload you receive."
- Tone guidance: "Use executive language. Be concise. Avoid speculation."
- Output format instruction: "Respond ONLY with valid JSON matching this exact schema: `{...}`"
- Explicit prohibition: "Do not mention any business issues not listed in the signals payload."

**User Prompt** (`user_*.j2`)

This is not written by a human. It is **automatically generated** per run from the deterministic render context. It is a structured data payload rendered by Jinja2 from `build_prompt_inputs(ctx)`.

Required contents for `summary` mode:
- Period dates (current and previous week)
- `warn_count`, `info_count`
- `severity_by_category` (display labels and counts)
- Top 3 WARN signals: label, category, direction, delta_pct or delta_abs (formatted as strings)
- `narrative_inputs` for top 3 WARN signals (raw structured data)

Additional contents for `full` mode:
- All signal `narrative_inputs`
- Deterministic `narrative` string per signal (as grounding baseline)

**Why separate system and user prompts?**
- System prompt can be reviewed, audited, and versioned independently of data
- User prompt changes with every run (different data) but its structure is stable
- Prompt injection risk is reduced: system constraints apply regardless of data content
- Future: system prompt can be frozen while user prompt template evolves

### 4.3 Input Contract

`build_prompt_inputs(ctx: dict) -> dict` extracts from the render context only the fields needed for the user prompt template. It does not call LLM or modify ctx.

### 4.4 Output Contract

The LLM must return a JSON object conforming to this schema (Pydantic-validated):

```python
class LLMSignalNarratives(BaseModel):
    # rule_id → business-readable narrative sentence
    # Only rule_ids from the prompt input may appear
    narratives: dict[str, str] = Field(default_factory=dict)

class LLMResult(BaseModel):
    executive_summary: str           # 2-4 sentence summary paragraph
    signal_narratives: LLMSignalNarratives = Field(default_factory=LLMSignalNarratives)
    model: str = ""                  # model name set by adapter post-call
    prompt_version: str = ""         # e.g. "summary_v1" derived from template filename
    fallback: bool = False
    fallback_reason: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)  # prompt_tokens, completion_tokens
```

`LLMResult` is added to `domain/models.py`.

### 4.5 Response Validation

After the API call:
1. Parse response as JSON (fail → fallback)
2. Validate against `LLMResult` schema using Pydantic (fail → fallback)
3. Validate `executive_summary` is non-empty and under 800 characters (fail → fallback)
4. For `full` mode: validate each key in `signal_narratives.narratives` is a rule_id from the prompt input (unknown keys rejected, excess keys stripped)
5. Soft check: warn if any narrative appears to contain raw snake_case metric IDs (logged, not a hard fail)

### 4.6 Failure Handling

```python
def generate(ctx: dict, mode: str, provider: str, client: LLMClientProtocol) -> LLMResult | None:
    try:
        prompt_inputs = build_prompt_inputs(ctx)
        system_prompt = render_system_prompt(mode)
        user_prompt = render_user_prompt(prompt_inputs, mode)
        raw = client.complete(system_prompt, user_prompt, timeout=30)
        result = validate_response(raw, mode, expected_rule_ids=prompt_inputs["rule_ids"])
        return result
    except TimeoutError as e:
        _log_fallback("timeout", str(e))
        return None
    except APIError as e:
        _log_fallback("api_error", str(e))
        return None
    except (JSONDecodeError, ValidationError) as e:
        _log_fallback("invalid_response", str(e))
        return None
```

All failures return `None`. The caller (render_llm.py) handles `None` by rendering deterministically.

---

## Section 5 — Artifact and Manifest Strategy

### 5.1 New Artifact: `llm_response.json`

Written when `llm_mode != "off"` AND LLM was called (even on fallback, the attempt is recorded).

Content:
```json
{
  "llm_result": { ... },        // LLMResult model fields
  "raw_response": "...",        // raw string from the API (for debugging)
  "rendered_system_prompt": "...", // full rendered system prompt text
  "rendered_user_prompt": "...",   // full rendered user prompt text
  "prompt_hash": "sha256:..."      // SHA-256 of system+user concatenated
}
```

Storing the **full rendered prompts** (not just a hash) is essential for debugging prompt behavior after the fact. The hash allows deduplication and change detection across runs.

### 5.2 Manifest Extension

Add to `Manifest` model (all fields have defaults — backward compatible):

```python
llm_status: str = "off"              # "off" | "success" | "fallback"
llm_mode: str = ""                   # "summary" | "full" | ""
llm_provider: str = ""               # "anthropic" | "openai" | ""
llm_model: str = ""                  # e.g. "claude-haiku-4-5-20251001"
llm_prompt_version: str = ""         # e.g. "summary_v1"
llm_fallback_reason: str = ""        # populated only on fallback
llm_token_usage: dict[str, int] = Field(default_factory=dict)
```

Note: `llm_mode` and `llm_provider` are now distinct fields matching the separated CLI flags.

### 5.3 Brief Artifact

`brief.md` gains an **Executive Summary** section at the top when `llm_mode != "off"` and LLM succeeded:

```markdown
## Executive Summary

<LLM-generated paragraph here>

---

## Weekly Priorities
...
```

When mode is `full`, per-signal narrative slots use `llm_result.signal_narratives.narratives[rule_id]` if present, otherwise fall back to deterministic `sc.narrative`. The template handles this with a simple conditional — no business logic.

---

## Section 6 — CLI / Configuration Strategy

### 6.1 Mode and Provider Are Separate Concerns

The current `--llm` flag conflates behavior and backend. This is replaced with two distinct flags:

| Flag | Purpose | Values | Default |
|------|---------|--------|---------|
| `--llm-mode` | Controls what LLM generates | `off` · `summary` · `full` | `off` |
| `--llm-provider` | Selects the API backend | `anthropic` · `openai` | `anthropic` |
| `--llm-model` | Overrides the model name | any string | from env or hardcoded default |

Examples:
```bash
wbsb run -i data.csv                                          # off, no API call
wbsb run -i data.csv --llm-mode summary                      # summary, default provider
wbsb run -i data.csv --llm-mode full --llm-provider anthropic # full mode, explicit provider
wbsb run -i data.csv --llm-mode summary --llm-model claude-opus-4-6  # override model
```

### 6.2 Model Selection

Default model per provider:
- Anthropic: `claude-haiku-4-5-20251001` (cost-efficient for weekly batch)
- Can be overridden via `--llm-model` flag or `WBSB_LLM_MODEL` env var

For Iteration 4: implement Anthropic only. `--llm-provider openai` raises a clear error: "OpenAI provider is not yet implemented. Use --llm-provider anthropic."

### 6.3 Internal Plumbing

`pipeline.execute()` signature gains `llm_provider: str` alongside `llm_mode: str`. Both are passed to `render_llm()` and ultimately to the adapter.

`cli.py` change: replace `--llm` option with `--llm-mode` and `--llm-provider`. This is a **breaking CLI change** and must be noted in the PR description. Any scripts using `--llm anthropic` must be updated to `--llm-mode summary --llm-provider anthropic` (or `full`).

### 6.4 Safe Defaults

- `--llm-mode off` remains the default — zero risk of accidental API usage
- Missing API key → log warning + fallback to deterministic, exit code 0
- Timeout default: 30 seconds
- No retry in Iteration 4 (weekly batch runs tolerate a single failure gracefully)

---

## Section 7 — Task Breakdown

Each task includes its own tests. There is no standalone "tests task" — testing is the responsibility of the task that introduces the behavior.

---

### Task I4-1 — LLM Adapter Module + Prompt Templates

**Branch:** `feat/i4-task-1-llm-adapter`
**Dependencies:** None — fully independent
**Parallelizable with:** I4-2

**Description:**
Create `src/wbsb/render/llm_adapter.py` and `src/wbsb/render/prompts/`. This module is the sole boundary between WBSB and any external LLM API. All prompt engineering lives here. Tests for the adapter are included in this task.

**Files affected:**
- `src/wbsb/render/llm_adapter.py` (new)
- `src/wbsb/render/prompts/system_summary_v1.j2` (new)
- `src/wbsb/render/prompts/user_summary_v1.j2` (new)
- `src/wbsb/render/prompts/system_full_v1.j2` (new)
- `src/wbsb/render/prompts/user_full_v1.j2` (new)
- `tests/test_llm_adapter.py` (new)

**Implementation notes:**

`LLMClientProtocol`:
```python
class LLMClientProtocol(Protocol):
    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str: ...
```

`AnthropicClient(LLMClientProtocol)`: uses `anthropic` SDK; reads `ANTHROPIC_API_KEY` and model from env/config.

`build_prompt_inputs(ctx: dict) -> dict`: extracts the minimal fields from the deterministic render context needed for the user prompt template. Returns a flat dict — no Signal objects, no MetricResult objects, only serializable values. This is the only place that touches the render context in the LLM path.

`generate(ctx, mode, provider, client) -> LLMResult | None`: public API. Client is injected for testability.

Prompt templates (`system_*.j2`): static per mode; contain role, constraints, output schema, prohibition language.
Prompt templates (`user_*.j2`): rendered per run from `build_prompt_inputs(ctx)`; contain structured data payload.

**Tests included (tests/test_llm_adapter.py):**
```python
class TestPromptInputs:
    def test_build_prompt_inputs_summary_contains_required_fields()
    def test_build_prompt_inputs_full_contains_all_signal_narrative_inputs()
    def test_prompt_inputs_are_serializable()  # no domain objects

class TestSystemPromptRendering:
    def test_system_summary_prompt_renders()
    def test_system_full_prompt_renders()
    def test_system_prompt_contains_constraint_language()

class TestUserPromptRendering:
    def test_user_summary_prompt_renders_from_inputs()
    def test_user_full_prompt_includes_all_signals()
    def test_user_prompt_contains_no_snake_case_metric_ids()

class TestResponseValidation:
    def test_valid_summary_response_parses()
    def test_valid_full_response_parses()
    def test_invalid_json_returns_none()
    def test_schema_violation_returns_none()
    def test_executive_summary_too_long_returns_none()
    def test_unknown_rule_id_rejected()

class TestGenerateFunction:
    def test_success_returns_llm_result()
    def test_timeout_returns_none()
    def test_api_error_returns_none()
    def test_invalid_json_returns_none()
    def test_fallback_is_logged()
```

**Risks:**
- Prompt quality directly affects output quality — iterate on templates without code changes
- Pin `anthropic` SDK version in `pyproject.toml` to prevent breaking API changes

**Suitable agent:** Claude Code (API/SDK knowledge, prompt engineering)

---

### Task I4-2 — Domain Model + Manifest + Artifact Extension

**Branch:** `feat/i4-task-2-llm-domain-models`
**Dependencies:** None — schema additions only
**Parallelizable with:** I4-1

**Description:**
Extend the domain with `LLMResult`, extend `Manifest` with LLM observability fields, and update `export/write.py` to write `llm_response.json` including the full rendered prompts. Tests for all schema changes are included in this task.

**Files affected:**
- `src/wbsb/domain/models.py` (extend)
- `src/wbsb/export/write.py` (extend)
- `tests/test_findings_schema.py` (extend)

**Implementation notes:**

Add to `domain/models.py`:
```python
class LLMSignalNarratives(BaseModel):
    narratives: dict[str, str] = Field(default_factory=dict)

class LLMResult(BaseModel):
    executive_summary: str
    signal_narratives: LLMSignalNarratives = Field(default_factory=LLMSignalNarratives)
    model: str = ""
    prompt_version: str = ""
    fallback: bool = False
    fallback_reason: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
```

Extend `Manifest` (all defaults — backward compatible):
```python
llm_status: str = "off"
llm_mode: str = ""
llm_provider: str = ""
llm_model: str = ""
llm_prompt_version: str = ""
llm_fallback_reason: str = ""
llm_token_usage: dict[str, int] = Field(default_factory=dict)
```

Update `write_artifacts()` signature:
```python
def write_artifacts(
    ...,
    llm_result: LLMResult | None = None,
    llm_mode: str = "off",
    llm_provider: str = "",
    rendered_system_prompt: str = "",
    rendered_user_prompt: str = "",
) -> None:
```

When `llm_result` is provided: write `llm_response.json` containing `LLMResult` fields, `raw_response`, `rendered_system_prompt`, `rendered_user_prompt`, and `prompt_hash`. Add `llm_response.json` hash to manifest artifacts dict.

**Tests included (tests/test_findings_schema.py extension):**
```python
def test_llm_result_valid()
def test_llm_result_defaults()
def test_llm_result_json_round_trip()
def test_manifest_llm_fields_default_to_off()
def test_manifest_llm_mode_and_provider_are_separate_fields()
def test_write_artifacts_no_llm_result_no_llm_json(tmp_path)
def test_write_artifacts_with_llm_result_writes_llm_json(tmp_path)
def test_llm_response_json_contains_rendered_prompts(tmp_path)
def test_llm_response_json_hash_in_manifest_artifacts(tmp_path)
```

**Risks:**
- Schema additions must be backward compatible — verified by all existing tests continuing to pass
- `findings.json` schema_version stays at "1.2" — `LLMResult` is a separate artifact

**Suitable agent:** Either (pure data/schema work)

---

### Task I4-3 — render/llm.py + Pipeline + CLI Integration

**Branch:** `feat/i4-task-3-llm-pipeline`
**Dependencies:** I4-1 (adapter), I4-2 (domain models)
**Sequential after:** Both I4-1 and I4-2 merged

**Description:**
Replace the `render/llm.py` stub with a real implementation. Update `pipeline.py` and `cli.py` to use the separated `--llm-mode` / `--llm-provider` flags. Extend `render_template` to accept an optional `llm_result`. Integration tests and fallback tests are included in this task.

**Files affected:**
- `src/wbsb/render/llm.py` (replace stub)
- `src/wbsb/render/template.py` (extend signature)
- `src/wbsb/pipeline.py` (update branch + write_artifacts call)
- `src/wbsb/cli.py` (replace `--llm` with `--llm-mode` + `--llm-provider`)
- `tests/test_llm_integration.py` (new)
- `tests/test_e2e_pipeline.py` (extend)

**Implementation notes:**

New `render/llm.py`:
```python
def render_llm(
    findings: Findings,
    mode: str,
    provider: str,
    client: LLMClientProtocol | None = None,
) -> tuple[str, LLMResult | None, str, str]:
    """Returns (brief_md, llm_result, rendered_system_prompt, rendered_user_prompt)."""
    ctx = prepare_render_context(findings)
    prompt_inputs = build_prompt_inputs(ctx)
    system_prompt = render_system_prompt(mode)
    user_prompt = render_user_prompt(prompt_inputs, mode)
    resolved_client = client or AnthropicClient(provider=provider)
    llm_result = generate(ctx, mode, provider, resolved_client)
    brief_md = render_template(findings, llm_result=llm_result)
    return brief_md, llm_result, system_prompt, user_prompt
```

`render_template(findings, llm_result=None)` extension: internally merges `executive_summary` and `llm_narratives` into the ctx copy before rendering. `prepare_render_context()` itself is not modified.

`pipeline.py` update:
```python
if llm_mode == "off":
    brief_md = render_template(findings)
    llm_result, system_prompt, user_prompt = None, "", ""
else:
    brief_md, llm_result, system_prompt, user_prompt = render_llm(
        findings, mode=llm_mode, provider=llm_provider
    )

write_artifacts(
    ...,
    llm_result=llm_result,
    llm_mode=llm_mode,
    llm_provider=llm_provider,
    rendered_system_prompt=system_prompt,
    rendered_user_prompt=user_prompt,
)
```

`cli.py` update: replace `--llm` with `--llm-mode` (default `"off"`) and `--llm-provider` (default `"anthropic"`). This is a **breaking CLI change** — document in PR.

**Tests included:**

`tests/test_llm_integration.py` (new):
```python
class MockSuccessClient:
    """Returns hardcoded valid LLMResult JSON."""

class MockFallbackClient:
    """Raises APIError."""

def test_render_llm_summary_returns_brief_and_result()
def test_render_llm_full_returns_brief_and_result()
def test_render_llm_fallback_returns_brief_and_none()
def test_brief_contains_executive_summary_on_success()
def test_brief_excludes_executive_summary_on_fallback()
def test_llm_narratives_used_in_full_mode_when_provided()
def test_deterministic_narrative_used_when_llm_absent()
def test_rendered_prompts_returned_even_on_fallback()
```

`tests/test_e2e_pipeline.py` extension:
```python
def test_e2e_summary_mode_with_mock_client(tmp_path)
    # brief.md contains "## Executive Summary"
    # llm_response.json exists with rendered prompts
    # manifest has llm_status="success", llm_mode="summary", llm_provider="anthropic"

def test_e2e_full_mode_fallback_with_mock_client(tmp_path)
    # brief.md is valid deterministic output
    # manifest has llm_status="fallback"
    # "## Executive Summary" NOT in brief.md

def test_e2e_off_mode_unchanged(tmp_path)
    # no llm_response.json
    # manifest llm_status="off"
    # brief.md byte-identical to pre-I4 behavior
```

**Risks:**
- `--llm-mode` / `--llm-provider` is a breaking CLI change — existing scripts using `--llm` will break
- `render_template` signature change — default `llm_result=None` ensures backward compat

**Suitable agent:** Claude Code

---

### Task I4-4 — Template Integration + Context Merge

**Branch:** `feat/i4-task-4-template-llm-sections`
**Dependencies:** I4-1 (output schema), I4-3 (context merge pattern + context keys)
**Sequential after:** I4-3

**Description:**
Update `template.md.j2` to render the executive summary section when available, and prefer LLM signal narratives over deterministic ones in `full` mode. Template must degrade gracefully when LLM output is absent. Template tests are included in this task.

**Files affected:**
- `src/wbsb/render/template.md.j2` (extend)
- `tests/test_render_context.py` (extend — test llm merge into render context copy)

**Implementation notes:**

Executive summary section (before Weekly Priorities):
```jinja2
{% if executive_summary %}
## Executive Summary

{{ executive_summary }}

---
{% endif %}
```

Per-signal narrative in Signals loop:
```jinja2
{% set sig_narrative = (llm_narratives or {}).get(sc.signal.rule_id, sc.narrative) %}
{{ sig_narrative }}
```

Context keys added by `render_template` merge step (from `llm_result`):
- `executive_summary`: `str | None` — `None` when llm_result is None or fallback
- `llm_narratives`: `dict[str, str]` — empty dict when mode is `summary` or fallback

Template must work correctly across all combinations:
- `executive_summary=None, llm_narratives={}` → full deterministic brief
- `executive_summary="...", llm_narratives={}` → summary mode output
- `executive_summary="...", llm_narratives={...}` → full mode output

**Tests included (tests/test_render_context.py extension):**
```python
def test_render_template_with_no_llm_result_produces_deterministic_brief()
def test_render_template_with_llm_result_includes_executive_summary()
def test_render_template_off_mode_has_no_executive_summary_section()
def test_render_template_full_mode_uses_llm_narrative_when_present()
def test_render_template_full_mode_falls_back_to_sc_narrative_when_absent()
def test_render_template_summary_mode_uses_sc_narrative_for_signals()
def test_prepare_render_context_unchanged_after_llm_render()  # purity check
```

**Risks:**
- Template must not error when `llm_narratives` key is missing — guard with `(llm_narratives or {})`
- `prepare_render_context()` must remain unmodified — verify in tests

**Suitable agent:** Either

---

## Section 8 — Parallelization Plan

```
START
  ├── I4-1: LLM Adapter + Prompts + Adapter Tests    ←─────┐ PARALLEL
  └── I4-2: Domain Models + Export + Schema Tests    ←─────┘

After BOTH I4-1 and I4-2 merged to main:
  └── I4-3: Pipeline + CLI Integration + Integration Tests  (sequential bottleneck)

After I4-3 merged:
  └── I4-4: Template + Context Merge + Template Tests  (sequential, needs I4-3)

DONE
```

**Parallelizable pairs:**
- **I4-1 + I4-2** — completely independent. Can be assigned to separate agents simultaneously.

**Sequential bottleneck:**
- I4-3 cannot start until both I4-1 and I4-2 are merged. Keep I4-3 scope minimal.
- I4-4 cannot start until I4-3 is merged (needs the context merge pattern and ctx keys).

**Impact of review corrections on parallelization:**
- The original plan had I4-5 (tests) as a separate final task that also depended on everything.
- By distributing tests into each task, I4-4 is now the final task, not a separate I4-5. The critical path is shorter (I4-1/I4-2 → I4-3 → I4-4) and each task is self-contained and verifiable.

**Agent recommendations:**
- I4-1: Claude Code (API/SDK, prompt engineering)
- I4-2: Either (pure schema)
- I4-3: Claude Code (integration, CLI change, pipeline)
- I4-4: Either (template, simple Jinja + render tests)

---

## Section 9 — Acceptance Criteria

### I4-1 — LLM Adapter + Prompts
- [ ] `llm_adapter.py` exports `generate(ctx, mode, provider, client)` with injected client
- [ ] `LLMClientProtocol` accepts `system_prompt` and `user_prompt` separately
- [ ] Four prompt templates exist: `system_summary_v1.j2`, `user_summary_v1.j2`, `system_full_v1.j2`, `user_full_v1.j2`
- [ ] System prompts contain explicit constraint language
- [ ] User prompts are rendered from `build_prompt_inputs(ctx)` output (no domain objects)
- [ ] `generate()` returns `LLMResult` on success
- [ ] `generate()` returns `None` on timeout, API error, JSON error, schema violation
- [ ] All failure paths tested with injected mock clients
- [ ] No live API calls in any test
- [ ] `ruff check .` clean; all tests pass

### I4-2 — Domain Models + Artifacts
- [ ] `LLMResult` Pydantic model exists with all specified fields
- [ ] `Manifest` has separate `llm_mode` and `llm_provider` fields (not one combined field)
- [ ] `Manifest` has all other LLM observability fields with backward-compatible defaults
- [ ] `write_artifacts()` accepts `llm_result`, `llm_mode`, `llm_provider`, `rendered_system_prompt`, `rendered_user_prompt`
- [ ] `llm_response.json` written when llm_result is provided; not written when None
- [ ] `llm_response.json` contains `rendered_system_prompt` and `rendered_user_prompt` full text
- [ ] `llm_response.json` hash added to manifest artifacts dict
- [ ] `findings.json` schema unchanged (schema_version "1.2")
- [ ] All existing tests pass; `ruff check .` clean

### I4-3 — Pipeline + CLI Integration
- [ ] `--llm` flag replaced by `--llm-mode` and `--llm-provider` in CLI
- [ ] `wbsb run --llm-mode off` — identical to pre-I4 behavior (no API, no llm_response.json)
- [ ] `wbsb run --llm-mode summary` — brief includes Executive Summary section
- [ ] `wbsb run --llm-mode full` — brief includes Executive Summary + enriched signal narratives
- [ ] Missing API key → warning logged, deterministic brief produced, exit code 0
- [ ] `render_llm()` returns `(brief_md, llm_result, system_prompt, user_prompt)`
- [ ] `render_template()` accepts `llm_result=None` without behavioral change
- [ ] All existing tests pass (no test breaks from CLI change — tests use `execute()` directly)
- [ ] E2E tests cover summary+success, full+fallback, off modes
- [ ] `ruff check .` clean

### I4-4 — Template Integration
- [ ] Executive Summary section appears in brief only when `executive_summary` is not None
- [ ] Executive Summary section absent when llm_result is None (off/fallback)
- [ ] `full` mode: signal narratives prefer `llm_narratives[rule_id]` when present
- [ ] `full` mode: deterministic `sc.narrative` used when rule_id absent from llm_narratives
- [ ] `summary` mode: all signal narratives use deterministic `sc.narrative`
- [ ] Template renders without error when `llm_narratives` not in context
- [ ] `prepare_render_context()` output confirmed unmodified after LLM render
- [ ] `ruff check .` clean; all tests pass

---

## Section 10 — Testing Strategy

### 10.1 Distribution of Tests Across Tasks

| Task | Test file | Scope |
|------|-----------|-------|
| I4-1 | `tests/test_llm_adapter.py` (new) | Prompt building, response validation, generate() failure modes |
| I4-2 | `tests/test_findings_schema.py` (extend) | LLMResult schema, Manifest LLM fields, llm_response.json writing |
| I4-3 | `tests/test_llm_integration.py` (new) | render_llm(), fallback, brief content, mock clients |
| I4-3 | `tests/test_e2e_pipeline.py` (extend) | E2E with mocked client, all three modes |
| I4-4 | `tests/test_render_context.py` (extend) | Template rendering with/without llm_result, purity check |

### 10.2 Mock / Stub Strategy

`LLMClientProtocol` enables clean dependency injection. Tests never import `AnthropicClient`.

```python
class MockSuccessClient:
    def __init__(self, executive_summary: str, narratives: dict | None = None):
        self._response = json.dumps({
            "executive_summary": executive_summary,
            "signal_narratives": {"narratives": narratives or {}}
        })
    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        return self._response

class MockErrorClient:
    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise APIError("simulated failure")

class MockTimeoutClient:
    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise TimeoutError("simulated timeout")
```

### 10.3 Regression Protection

- All 91 pre-I4 tests must pass throughout every task
- `--llm-mode off` (or `llm_mode="off"` in `execute()`) must produce byte-identical output to pre-I4
- No test may make a real HTTP call — enforced by never importing `AnthropicClient` in tests

---

## Section 11 — Definition of Done

### Functional

- [ ] `wbsb run -i data.csv` — identical to pre-I4 behavior (default mode off)
- [ ] `wbsb run -i data.csv --llm-mode summary` — brief includes Executive Summary
- [ ] `wbsb run -i data.csv --llm-mode full` — brief includes Executive Summary + enriched narratives
- [ ] `wbsb run -i data.csv --llm-mode full --llm-provider anthropic` — explicit provider works
- [ ] Any API failure → deterministic brief produced, exit code 0
- [ ] Missing `ANTHROPIC_API_KEY` → warning logged, deterministic brief, exit code 0

### Artifacts

- [ ] `brief.md` always written
- [ ] `llm_response.json` written when `llm-mode != off`; contains full rendered prompts
- [ ] `manifest.json` has separate `llm_mode`, `llm_provider`, `llm_status`, `llm_model`, `llm_prompt_version`, `llm_fallback_reason`, `llm_token_usage`
- [ ] `findings.json` schema unchanged from Iteration 3

### Architecture

- [ ] LLM logic contained in `render/llm_adapter.py` and `render/llm.py` only
- [ ] No LLM imports in `pipeline.py`, `rules/engine.py`, `metrics/`, `findings/`, `validate/`
- [ ] `prepare_render_context()` is not modified; remains pure and deterministic
- [ ] `render/context.py` has no LLM dependency
- [ ] Rules engine untouched
- [ ] `narrative_inputs` contract unchanged (LLM reads it; does not modify it)

### Quality

- [ ] All tests pass (minimum 91 existing + new LLM tests in I4-1 through I4-4)
- [ ] `ruff check .` clean
- [ ] No live API calls in any test
- [ ] System prompt templates reviewed for constraint language and anti-hallucination wording
- [ ] PR reviews completed for all 4 tasks

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM invents business conclusions not in data | High | System prompt hard constraints; validate output references only provided rule_ids; no open-ended recommendations |
| Prompt drift changes behavior silently | Medium | Versioned templates in `prompts/`; `prompt_version` in manifest; full rendered prompt in `llm_response.json` |
| Output formatting instability | Medium | Structured JSON output via system prompt instruction; Pydantic validation rejects malformed responses |
| API errors / rate limits | Low | Full fallback path; 30s timeout; no retry (batch use) |
| Cost blowup | Low | Single API call per run; ~2000-3000 tokens input; weekly cadence; `summary` mode is cheaper alternative |
| Reproducibility limits | Accepted | LLM output is non-deterministic; documented; deterministic analytics are the truth layer |
| Architectural contamination | Low | Protocol boundary enforced; no LLM imports outside `render/` |
| CLI breaking change (`--llm` removed) | Medium | Document in PR; note in release; test suite uses `execute()` directly so no test breakage |
| I4-3 bottleneck | Low | I4-3 scope is deliberately minimal; I4-1+I4-2 unblock immediately and in parallel |

---

*Iteration 3 ends here. Iteration 4 begins with I4-1 and I4-2 in parallel.*
