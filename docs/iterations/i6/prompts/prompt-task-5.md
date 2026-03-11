WBSB Task Prompt — I6-5: LLM Adapter Extension (Trend Context)

Prepared by: Burak Kilic

---

Project Context

WBSB (Weekly Business Signal Brief) is a deterministic analytics engine for
appointment-based service businesses.

Pipeline architecture:

CSV/XLSX
→ Loader
→ Validator
→ Metrics
→ Deltas
→ Rules Engine
→ Findings
→ Renderer
→ brief.md

LLM usage rules:

• LLM generates narrative only
• LLM never performs analytics
• All analytics come from deterministic modules

Iteration 6 introduces:

• historical memory
• trend classification
• trend-aware prompt context

---

Repository State

Iteration branch: feature/iteration-6
Feature branch for this task: feature/i6-5-llm-trend-context

Completed tasks:

I6-1 — history config section
I6-2 — history store
I6-3 — pipeline registration
I6-4 — deterministic trend engine

Current baseline:

262 tests passing
ruff clean

Dependencies satisfied:

I6-3 and I6-4 are merged into feature/iteration-6 before this task begins.

---

Task Metadata

Task ID: I6-5
Title: LLM Adapter Extension (Trend Context)
Iteration: Iteration 6 — Historical Memory & Trend Awareness

Owner: Claude

Iteration branch: feature/iteration-6
Feature branch: feature/i6-5-llm-trend-context

Depends on: I6-3, I6-4
Blocks: I6-6

PR scope: One PR into feature/iteration-6

---

Task Goal

Extend the LLM adapter so that the prompt receives trend context derived from
historical analysis.

The trend engine already produces deterministic results via compute_trends().

This task connects that output into the prompt system so the LLM can reference
historical trends when generating the brief.

The adapter must ensure that:

• raw historical arrays never reach the LLM
• insufficient_history entries do not appear in the prompt
• LLM prompt context remains compact and structured

---

Files to Read Before Starting

Read these in order before writing code:

src/wbsb/pipeline.py
→ understand pipeline execution: signals, render_llm call, register_run location

src/wbsb/history/trends.py
→ understand compute_trends() output and TrendResult shape

src/wbsb/history/store.py
→ understand HistoryReader constructor and get_metric_history() parameters

src/wbsb/render/llm.py
→ understand render_llm() signature and internal call chain

src/wbsb/render/llm_adapter.py
→ understand build_prompt_inputs() and generate() signatures

tests/test_llm_adapter.py
→ existing prompt tests (to understand test patterns)

tests/test_pipeline_history.py
→ existing pipeline integration tests (to understand test patterns)

---

Existing Code This Task Builds On

From I6-2 (store.py):

HistoryReader(index_path, dataset_key)
    .get_metric_history(metric_id, n_weeks=None, before_week_start=None)
    → list[tuple[str, float]]   # (week_start_iso, value)

From I6-4 (trends.py):

compute_trends(history_reader, metric_ids, n_weeks=None)
    → dict[str, TrendResult]

TrendResult TypedDict fields:
    metric_id           str
    trend_label         str    # one of six labels
    weeks_consecutive   int
    baseline_delta_pct  float | None
    direction_sequence  list[str]   ← internal only, must NOT reach LLM

Current render_llm() signature (render/llm.py):

render_llm(findings, mode, provider, client=None)
    → tuple[str, LLMResult | None, str, str]

Current build_prompt_inputs() signature (llm_adapter.py):

build_prompt_inputs(ctx)
    → dict[str, Any]

Both signatures will be extended in this task.

---

What to Build

This task has three modifications:
  1. pipeline.py    — compute trend context and pass to renderer
  2. render/llm.py  — thread trend_context through to build_prompt_inputs and generate
  3. llm_adapter.py — filter/serialize trend context, expose in prompt inputs

---

Part 1 — Pipeline Integration

File: src/wbsb/pipeline.py

Location in pipeline:
After findings are built and before render_llm() is called.

Add these imports at the top of the file:

    from wbsb.history.store import HistoryReader
    from wbsb.history.trends import compute_trends

Step A — Construct HistoryReader:

    index_path = output_dir / "index.json"
    history_reader = HistoryReader(index_path=index_path, dataset_key=dataset_key)

Step B — Derive signal_metric_ids from findings:

    signal_metric_ids = list({s.metric_id for s in findings.signals if s.metric_id})

Only metrics that fired signals are included.

Step C — Compute trend context with failure handling:

    try:
        trend_context = compute_trends(
            history_reader,
            metric_ids=signal_metric_ids,
            before_week_start=week_start.isoformat(),
        )
    except Exception as exc:
        log.warning("trends.compute.error", error=str(exc))
        trend_context = {}

The before_week_start parameter ensures the current week is excluded from
history (current run is not registered yet, but prior reruns for the same
week would be — this guard prevents data leakage).

Step D — Pass trend_context to render_llm():

    brief_md, llm_result, rendered_system_prompt, rendered_user_prompt = render_llm(
        findings=findings,
        mode=llm_mode,
        provider=llm_provider,
        trend_context=trend_context,
    )

Note: trend_context is computed regardless of llm_mode. If llm_mode is "off",
the render path skips render_llm() entirely and trend_context is never used.
Only compute it in the llm_mode != "off" branch.

---

Part 2 — Thread trend_context Through render/llm.py

File: src/wbsb/render/llm.py

Extend render_llm() to accept and thread trend_context:

def render_llm(
    findings: Findings,
    mode: str,
    provider: str,
    client: LLMClientProtocol | None = None,
    trend_context: dict | None = None,
) -> tuple[str, LLMResult | None, str, str]:

Default: trend_context = None  (treat internally as {})

Inside render_llm():

  a) Pass trend_context to build_prompt_inputs():

         prompt_inputs = llm_adapter.build_prompt_inputs(ctx, trend_context=trend_context)

  b) Pass trend_context to generate():

         adapter_result = llm_adapter.generate(
             ctx, mode=mode, provider=provider, client=client,
             trend_context=trend_context,
         )

---

Part 3 — Extend LLM Adapter

File: src/wbsb/render/llm_adapter.py

3a — Extend build_prompt_inputs()

New signature:

    def build_prompt_inputs(
        ctx: dict[str, Any],
        trend_context: dict | None = None,
    ) -> dict[str, Any]:

Add to the return dict:

    "trend_context_for_prompt": _build_trend_context_for_prompt(trend_context or {}),

3b — Add _build_trend_context_for_prompt()

    def _build_trend_context_for_prompt(
        trend_context: dict,
    ) -> list[dict[str, Any]]:

Purpose:
Filter and serialize trend context before it reaches the LLM.

Rules:
• Remove entries where trend_label == "insufficient_history"
• Exclude direction_sequence from every entry (never expose raw arrays to LLM)
• Return [] if trend_context is empty or all entries were filtered out
• The key "trend_context_for_prompt" must always be present in prompt inputs

Output shape — each element:

    {
        "metric_id":          str,
        "trend_label":        str,
        "weeks_consecutive":  int,
        "baseline_delta_pct": float | None,
    }

3c — Extend generate()

New signature:

    def generate(
        ctx: dict[str, Any],
        mode: str,
        provider: str,
        client: LLMClientProtocol | None = None,
        trend_context: dict | None = None,
    ) -> AdapterLLMResult | None:

Pass trend_context to build_prompt_inputs() inside generate():

    prompt_inputs = build_prompt_inputs(ctx, trend_context=trend_context)

---

Prompt Template Contract

After this task merges, the prompt template will receive:

    trend_context_for_prompt

This will be used in Task I6-6.
No template changes are allowed in this task.

---

Allowed Files

src/wbsb/pipeline.py
src/wbsb/render/llm.py
src/wbsb/render/llm_adapter.py
tests/test_llm_adapter.py
tests/test_pipeline_history.py

---

Files NOT to Touch

src/wbsb/history/store.py
src/wbsb/history/trends.py
src/wbsb/domain/models.py
src/wbsb/render/context.py
src/wbsb/render/prompts/user_full_v2.j2
config/rules.yaml

Template changes belong to I6-6.

---

Tests Required

In tests/test_llm_adapter.py — unit tests for build_prompt_inputs() and helper:

test_build_prompt_inputs_no_trend_context
    call: build_prompt_inputs(ctx)  (no trend_context arg)
    assert: result["trend_context_for_prompt"] == []

test_build_prompt_inputs_trend_context_empty_dict
    call: build_prompt_inputs(ctx, trend_context={})
    assert: result["trend_context_for_prompt"] == []

test_build_prompt_inputs_filters_insufficient_history
    input: trend_context with one entry where trend_label="insufficient_history"
    assert: result["trend_context_for_prompt"] == []

test_build_prompt_inputs_valid_trend_entries
    input: trend_context with one valid entry (trend_label="rising")
    assert: entry appears in trend_context_for_prompt with correct fields

test_build_prompt_inputs_excludes_direction_sequence
    input: valid trend entry including direction_sequence key
    assert: "direction_sequence" not in any element of trend_context_for_prompt

test_trend_context_empty_when_all_insufficient
    input: trend_context where all entries have trend_label="insufficient_history"
    assert: trend_context_for_prompt == []

In tests/test_pipeline_history.py — pipeline integration test:

test_pipeline_passes_trend_context_to_render
    verify: pipeline calls render_llm with trend_context argument
    use monkeypatch to capture the call
    assert: trend_context kwarg is present in the call

---

Acceptance Criteria

• pipeline computes trend_context only when llm_mode != "off"
• signal metric IDs derived from findings.signals
• before_week_start=week_start.isoformat() passed to HistoryReader
• compute_trends() failure is caught, logged, sets trend_context={}, continues
• render_llm() receives trend_context kwarg
• build_prompt_inputs() exposes "trend_context_for_prompt" key always
• insufficient_history entries filtered out
• direction_sequence excluded from all prompt entries
• [] returned when no valid entries
• template unchanged (no .j2 edits)
• existing 262 tests pass
• new tests pass
• ruff clean

---

Edge Cases

First run:
    history empty → all insufficient_history → filtered → []
    LLM prompt still renders correctly (trend_context_for_prompt present, empty)

Dataset switch:
    dataset_key different → HistoryReader finds no matching entries → []

llm_mode == "off":
    trend context not computed, render_llm not called, no error

---

Execution Workflow

Step 1 — Commit prompt to integration branch first

    git checkout feature/iteration-6
    git pull origin feature/iteration-6
    git status   # verify clean

Commit this prompt file:

    git add docs/prompts/prompt-task-5.md
    git commit -m "docs: add task prompt for I6-5 (LLM adapter trend context)"
    git push origin feature/iteration-6

Step 2 — Create task branch

    git checkout -b feature/i6-5-llm-trend-context
    git branch --show-current

    git commit --allow-empty -m "chore: open draft PR for I6-5 LLM trend context"
    git push -u origin feature/i6-5-llm-trend-context

Create draft PR:

    gh pr create \
        --title "I6-5: Extend LLM adapter with trend context" \
        --body "Draft — I6-5: thread compute_trends() output into build_prompt_inputs() for trend-aware prompts." \
        --base feature/iteration-6 \
        --draft

Step 3 — Verify baseline

    pytest
    ruff check .

Must pass before writing code.

Step 4 — Implement

Modify pipeline.py, render/llm.py, and llm_adapter.py per spec above.

Step 5 — Run tests

    pytest
    ruff check .

Step 6 — Verify scope

    git diff --name-only feature/iteration-6

Expected files only:

    src/wbsb/pipeline.py
    src/wbsb/render/llm.py
    src/wbsb/render/llm_adapter.py
    tests/test_llm_adapter.py
    tests/test_pipeline_history.py

Step 7 — Commit

    git add src/wbsb/pipeline.py src/wbsb/render/llm.py src/wbsb/render/llm_adapter.py \
             tests/test_llm_adapter.py tests/test_pipeline_history.py

    git commit -m "$(cat <<'EOF'
feat: extend LLM adapter with trend context (I6-5)

Compute trend context from historical signals and thread it through
render_llm() and build_prompt_inputs(). Filters insufficient_history
entries and excludes direction_sequence from LLM prompt payload.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"

    git push

Step 8 — Mark PR ready

    gh pr ready feature/i6-5-llm-trend-context

---

Definition of Done

• compute_trends output integrated into pipeline (llm_mode != "off" only)
• trend context passed to render_llm with before_week_start guard
• prompt inputs always contain trend_context_for_prompt key
• insufficient_history filtered
• direction_sequence excluded
• template unchanged
• all tests pass (262 + new)
• ruff clean
• PR ready for review into feature/iteration-6
