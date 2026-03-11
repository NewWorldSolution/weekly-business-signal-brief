WBSB Task Prompt — I6-6: Prompt Template Update (Trend Context)

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

LLM role:

• Generate narrative text
• Never compute analytics
• Never receive raw arrays or time series

Iteration 6 adds:

• historical memory
• trend classification
• trend context in the prompt

Trend context was generated in I6-5 and is now available in the prompt inputs.
This task updates the prompt template to display that information to the LLM.

---

Repository State

Iteration branch: feature/iteration-6
Feature branch for this task: feature/i6-6-prompt-template

Previous tasks complete and merged into feature/iteration-6:

I6-1 history config
I6-2 history store
I6-3 pipeline integration
I6-4 trend engine
I6-5 LLM adapter extension (PR #30 — merged)

Current baseline:

271 tests passing
ruff clean

Dependency:

I6-5 must be merged into feature/iteration-6 before this branch is cut.

---

Task Metadata

Task ID: I6-6
Title: Prompt Template Update (Trend Context)
Owner: Codex

Iteration branch: feature/iteration-6
Feature branch: feature/i6-6-prompt-template

Depends on: I6-5
Blocks: I6-7

PR scope: One PR into feature/iteration-6

---

Why Codex

This task modifies a single Jinja2 template and requires no architectural decisions.
The data contract was fully defined in I6-5. Codex can implement the template block.

---

What This Task Must Do

Update the prompt template to include a TREND CONTEXT section when trend data exists.

Trend context is passed into the template as:

    trend_context_for_prompt

This variable is a list of dictionaries. When empty, the section must not appear.

---

File To Modify

    src/wbsb/render/prompts/user_full_v2.j2

No other files should be changed.

---

Template Contract From I6-5

Variable available in template context:

    trend_context_for_prompt

Type:

    list[dict]

Each element contains exactly these keys:

    metric_id           str
    trend_label         str    — one of: rising, falling, recovering, volatile, stable
    weeks_consecutive   int    — 0 when label is stable or volatile
    baseline_delta_pct  float | None

Example element:

    {
        "metric_id": "cac_paid",
        "trend_label": "rising",
        "weeks_consecutive": 3,
        "baseline_delta_pct": 0.12
    }

When no valid trends exist:

    trend_context_for_prompt = []

Important:
- direction_sequence is NEVER present (filtered in I6-5)
- insufficient_history entries are NEVER present (filtered in I6-5)

---

What To Implement

Add a TREND CONTEXT section.

Placement:

    After BUSINESS MECHANISM CHAINS
    Before SIGNALS GROUPED BY CATEGORY

This is the existing structure of the template (do not reorder other sections):

    WEEKLY ANALYTICS REPORT — FULL MODE
    [header block]

    DOMINANT CLUSTER FACTS
    SIGNAL CLUSTER SUMMARY
    BUSINESS MECHANISM CHAINS
    ← INSERT TREND CONTEXT HERE
    SIGNALS GROUPED BY CATEGORY
    RELATIONSHIP HINTS
    [instruction block]

---

Template Logic

The section must only render when trend_context_for_prompt is non-empty.

Required conditional guard:

    {% if trend_context_for_prompt %}
    ...
    {% endif %}

When the list is empty, absolutely nothing from this section may appear.

---

Section Format

Required output:

    TREND CONTEXT

    metric_id — trend_label | X consecutive weeks | +Y.Z% vs baseline

Example rendered output when two trends exist:

    TREND CONTEXT

    cac_paid — rising | 3 consecutive weeks | +12.0% vs baseline
    refund_rate — falling | 2 consecutive weeks | -5.0% vs baseline

Example when weeks_consecutive is 0 (stable):

    gross_margin — stable

Example when baseline_delta_pct is None:

    bookings_total — recovering | 1 consecutive weeks

---

Exact Template Implementation

Insert this block immediately before the line that starts with
"SIGNALS GROUPED BY CATEGORY":

    {% if trend_context_for_prompt %}
    TREND CONTEXT

    {% for entry in trend_context_for_prompt %}
    {{ entry.metric_id }} — {{ entry.trend_label }}{% if entry.weeks_consecutive > 0 %} | {{ entry.weeks_consecutive }} consecutive weeks{% endif %}{% if entry.baseline_delta_pct is not none %} | {{ "%+.1f%%" | format(entry.baseline_delta_pct * 100) }} vs baseline{% endif %}

    {% endfor %}
    {% endif %}

Jinja2 notes:
- Use `is not none` (lowercase) to check for None — this is correct Jinja2 syntax
- `"%+.1f%%" | format(value)` uses Python % formatting — produces "+12.0%" correctly
- Do NOT use `| ljust(N)` — it is not a Jinja2 built-in filter and will cause a render error
- Do NOT use `{{ history_n_weeks }}` — this variable is not in the template context
  and would silently render as empty string

---

Important Restrictions

Do NOT modify:

• The response schema (INSTRUCTION / SECTION RULES / CONSTRAINTS blocks)
• Any existing section (header, DOMINANT CLUSTER FACTS, SIGNALS GROUPED BY CATEGORY, etc.)
• Variable names
• Any prompt logic outside the new TREND CONTEXT block

Do NOT introduce new template variables.
Use only: trend_context_for_prompt (already provided by build_prompt_inputs).

---

Allowed Files

    src/wbsb/render/prompts/user_full_v2.j2

---

Files That Must NOT Change

    src/wbsb/render/llm_adapter.py
    src/wbsb/pipeline.py
    src/wbsb/history/trends.py
    src/wbsb/history/store.py
    src/wbsb/domain/models.py
    config/rules.yaml
    Any test file

If any of these appear in git diff --name-only feature/iteration-6 → stop.

---

No New Tests Required

This task modifies only a Jinja2 template. The prompt template is tested
indirectly through the existing LLM adapter and integration tests.

All 271 existing tests must continue to pass unchanged.

---

Acceptance Criteria

• TREND CONTEXT block appears when trend_context_for_prompt is non-empty
• TREND CONTEXT block is completely absent when list is empty
• Template renders without Jinja2 errors in all cases
• SIGNALS GROUPED BY CATEGORY section is unchanged and in its original position
• No new template variables introduced (no history_n_weeks, no new keys)
• All 271 existing tests pass
• ruff check . is clean (template file is not Python — ruff will not flag it)
• Only src/wbsb/render/prompts/user_full_v2.j2 appears in scope diff

---

Edge Cases

First run (no history):

    trend_context_for_prompt = []

TREND CONTEXT must not appear. Template must still render correctly.

Dataset change (history empty):

    trend_context_for_prompt = []

Section must not appear.

LLM disabled mode (--llm-mode off):

Pipeline must still run successfully. Template is never called in this mode.

All stable / volatile metrics (weeks_consecutive == 0):

    cac_paid — stable

No consecutive-weeks segment appears. Correct.

All baseline_delta_pct == None:

    cac_paid — rising | 3 consecutive weeks

No vs-baseline segment appears. Correct.

---

Execution Workflow

Step 1 — Branch

    git checkout feature/iteration-6
    git pull origin feature/iteration-6
    git status

    git checkout -b feature/i6-6-prompt-template
    git branch --show-current

    git commit --allow-empty -m "chore: open draft PR for I6-6 prompt template update"
    git push -u origin feature/i6-6-prompt-template

Create draft PR:

    gh pr create \
        --title "I6-6: Add TREND CONTEXT block to prompt template" \
        --body "Draft — I6-6: adds conditional TREND CONTEXT section to user_full_v2.j2." \
        --base feature/iteration-6 \
        --draft

Step 2 — Verify baseline

    pytest
    ruff check .

Both must pass before touching any file.

Step 3 — Implement

Modify only:

    src/wbsb/render/prompts/user_full_v2.j2

Insert the TREND CONTEXT block per the spec above.

Step 4 — Run tests

    pytest
    ruff check .

Step 5 — Verify scope

    git diff --name-only feature/iteration-6

Expected output (exactly one file):

    src/wbsb/render/prompts/user_full_v2.j2

If any other file appears — stop and investigate.

Step 6 — Commit

    git add src/wbsb/render/prompts/user_full_v2.j2
    git commit -m "$(cat <<'EOF'
feat: add TREND CONTEXT section to prompt template (I6-6)

Adds conditional TREND CONTEXT block to user_full_v2.j2 using
trend_context_for_prompt produced by llm_adapter. Section renders
only when trend context exists; absent on first run or empty history.

Co-Authored-By: Codex <noreply@openai.com>
EOF
)"
    git push

Step 7 — Mark PR ready

    gh pr ready feature/i6-6-prompt-template

---

Definition of Done

• TREND CONTEXT rendered correctly when data exists
• TREND CONTEXT absent when list is empty
• Existing prompt structure unchanged
• No Jinja2 render errors
• 271 tests pass
• ruff clean
• PR ready for review into feature/iteration-6
