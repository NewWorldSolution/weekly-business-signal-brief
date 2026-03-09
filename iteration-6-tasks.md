# Iteration 6 — Historical Memory & Trend Awareness
## Detailed Task Plan

**Status:** I6-0 through I6-3 complete. PRs #27 (I6-2) and #28 (I6-3) ready for review into `feature/iteration-6`. I6-4 is next.
**Baseline:** 242 tests passing, ruff clean.

---

## Branching Strategy

Iteration 6 uses a **dedicated integration branch** rather than merging tasks directly to `main`.

```
main
 └── feature/iteration-6          ← iteration integration branch
      ├── feature/i6-1-history-config     (merged ✅)
      ├── feature/i6-2-history-store      (PR #27 ready ✅)
      ├── feature/i6-3-pipeline-integration (PR #28 ready ✅)
      ├── feature/i6-4-trend-engine       ← next
      ├── feature/i6-5-llm-trend-context
      └── feature/i6-6-prompt-template
```

**Rules:**
- Every task branch is created from `feature/iteration-6` (not from `main`)
- Every task PR targets `feature/iteration-6` (not `main`)
- `feature/iteration-6` is only merged into `main` once the full iteration passes the I6-7 architecture review and I6-8 cleanup
- `main` stays stable and production-ready throughout the entire iteration

---

## Execution Order

```
I6-0  [Claude]   Docs update                    ✅ DONE (merged to main)
I6-1  [Codex]    Config — history: section      ✅ DONE (merged to feature/iteration-6)
I6-2  [Claude]   History store + HistoryReader  ✅ DONE (PR #27 ready — 18 tests, 235 total)
I6-3  [Claude]   Pipeline integration           ✅ DONE (PR #28 ready — 7 tests, 242 total)
I6-4  [Claude]   Trend engine                   → depends on I6-2   ← next
I6-5  [Claude]   LLM adapter extension          → depends on I6-3 + I6-4
I6-6  [Codex]    Prompt template update         → depends on I6-5
I6-7  [You]      Architecture review            → depends on I6-6
I6-8  [Claude]   Final cleanup + merge to main  → depends on I6-7
```

**One task = one PR into `feature/iteration-6`. Never combine tasks. Never PR directly to `main`.**

---

## Per-Task Workflow (follow exactly for every task)

```bash
# 1. Start from the iteration branch
git checkout feature/iteration-6
git pull origin feature/iteration-6
git status                          # must be clean

# 2. Create and push the task branch
git checkout -b feature/i6-N-description
git push -u origin feature/i6-N-description

# 3. Open a DRAFT PR immediately — before writing any code
gh pr create \
  --base feature/iteration-6 \
  --head feature/i6-N-description \
  --title "I6-N: Task title" \
  --body "Work in progress. See prompt file for full task spec." \
  --draft

# 4. Verify baseline before touching anything
pytest                              # must pass
ruff check .                        # must be clean

# 5. Implement, then test and lint again
pytest && ruff check .

# 6. Verify scope
git diff --name-only feature/iteration-6
# Only allowed files should appear

# 7. Commit and push
git push origin feature/i6-N-description

# 8. Mark PR ready for review
gh pr ready feature/i6-N-description
```

**Note on I6-1:** I6-1 was merged into `feature/iteration-6` before this workflow was established.
It is the only task without a task-level PR. All tasks from I6-2 onwards follow the steps above.

---

## Task Summary

| Task | Owner | Description | Depends on |
|------|-------|-------------|------------|
| I6-0 | Claude | Architecture/docs update | — |
| I6-1 | Codex | Add `history:` section to `config/rules.yaml` | — |
| I6-2 | Claude | History store + dataset-scoped HistoryReader | I6-1 |
| I6-3 | Claude | Register completed runs in history index | I6-2 |
| I6-4 | Claude | Deterministic trend engine (all 6 labels) | I6-2 |
| I6-5 | Claude | Extend LLM adapter with trend context | I6-3, I6-4 |
| I6-6 | Codex | Update prompt template to consume trend context | I6-5 |
| I6-7 | You | Architecture review checklist | I6-6 |
| I6-8 | Claude | Final cleanup — all tests green, ruff clean | I6-7 |

---

---

## I6-0 — Architecture and Docs Update

**Owner:** Claude
**Status:** DONE
**Branch:** merged to main

### What Was Done
- `TASKS.md` updated with `dataset_key` in index record, `insufficient_history` label, and config-driven threshold notes
- `project-iterations.md` updated with the same three clarifications
- `config/rules.yaml` flagged as an allowed file for I6-2/I6-4
- Security principle 9 added to Architecture Principles

---

---

## I6-1 — Add `history:` Config Section

**Owner:** Codex
**Branch:** `feature/i6-1-history-config`
**Depends on:** nothing — can start immediately

### Why Codex
Bounded, single-file config edit. The values are fully specified here. No architectural judgment required.

### Why This Must Come First
Every subsequent task reads thresholds from config. If any coding task starts before I6-1 is merged, the implementer will be tempted to hardcode values temporarily. That creates tech debt. Merge I6-1 first, then unlock all other tasks.

### What to Build

Add the following block to `config/rules.yaml`, after the existing `defaults:` section and before `rules:`:

```yaml
history:
  n_weeks: 4                  # default lookback window for all trend queries
  min_consecutive: 2          # minimum consecutive weeks to classify as rising or falling
  stable_band_pct: 0.02       # week-over-week change within ±2% is considered flat/stable
  stable_min_weeks: 3         # minimum weeks of stability to assign the "stable" label
```

**Notes:**
- Do not change any existing key in the file
- Do not change `schema_version` or `config_version`
- YAML indentation must be 2 spaces, consistent with the rest of the file
- These four keys are the complete set. Do not add extras unless explicitly asked.

### Acceptance Criteria
- `config/rules.yaml` loads without error via `yaml.safe_load()`
- The four keys are present and have the correct types (int or float)
- No existing rules or defaults modified
- Ruff clean (YAML is not linted by ruff, but the file must remain valid YAML)

### Allowed Files
```
config/rules.yaml    ← add history: section only
```

---

---

## I6-2 — History Store and Dataset-Scoped HistoryReader

**Owner:** Claude
**Branch:** `feature/i6-2-history-store`
**Status:** ✅ DONE — PR #27 ready for review
**Depends on:** I6-1 merged

### Actual Deliverables
- `src/wbsb/history/__init__.py` — empty package marker
- `src/wbsb/history/store.py` — `RunRecord`, `derive_dataset_key()`, `register_run()` (atomic write), `HistoryReader`
- `tests/test_history.py` — 18 tests (6 derive_dataset_key, 5 register_run, 7 HistoryReader)
- Test count after: 235 (up from 217)

### Deviations from Spec
- None. All 18 tests pass. All acceptance criteria met.
- Code review found `except OSError: pass` in temp-file cleanup (fixed) and weak n_weeks assertion (strengthened).



### Why Claude
This module establishes the architectural foundation for all of Iteration 6. It touches file I/O, data isolation logic, and the shape of the index that every downstream task depends on. It requires architectural judgment about failure modes, race conditions (single-user, not multi-process, but still), and the contract the rest of the system will build against.

### Why I6-2 Merges GPT's I6-2 and I6-5
GPT proposed creating `store.py` first and adding `dataset_key` filtering in a separate task. That approach is wrong: it would produce intentionally incomplete code that passes review as a PR, only to be overwritten in the next PR. Dataset isolation is a core invariant of the store — not a feature added on top. It must be built in from the first line.

### What to Build

#### New package: `src/wbsb/history/`

Create `src/wbsb/history/__init__.py` (empty, marks the package).

#### `src/wbsb/history/store.py`

Two public surfaces: a write-side function and a read-side class.

**`derive_dataset_key(input_file: str | Path) -> str`**

A module-level helper that converts an input file path to a stable identity key. This is the canonical function — called by `pipeline.py` when registering a run and by any caller that needs to scope a query.

Derivation rule:
1. Take the filename (not the full path), strip the extension.
2. Apply regex to strip a trailing date segment matching `_YYYY-MM-DD` or `-YYYY-MM-DD` or `_YYYYMMDD`.
3. Strip any trailing underscores or dashes.
4. Return the result as a lowercase string.

```python
# Examples
derive_dataset_key("weekly_data_2026-03-03.csv")     # → "weekly_data"
derive_dataset_key("dataset_07_extreme_ad_spend.csv") # → "dataset_07_extreme_ad_spend"
derive_dataset_key("report_20260303.xlsx")            # → "report"
derive_dataset_key("/runs/data/weekly_data_2026-03-10.csv") # → "weekly_data"
```

This function must be pure — no I/O, no side effects, always returns the same string for the same input.

**`register_run(run: RunRecord, index_path: Path) -> None`**

Appends a run record to the JSON index. Raises `ValueError` if the `run_id` is already present. Raises `FileNotFoundError` if `findings_path` does not exist at the time of registration.

`RunRecord` is a `TypedDict` or `dataclass` with these fields:

```python
{
    "run_id": str,            # e.g. "20260309T094756Z_4c43f0"
    "dataset_key": str,       # e.g. "weekly_data"
    "input_file": str,        # full path for traceability
    "week_start": str,        # ISO date "2026-03-03"
    "week_end": str,          # ISO date "2026-03-09"
    "signal_count": int,
    "findings_path": str,     # full path to findings.json
    "registered_at": str,     # ISO datetime of registration
}
```

Index format (append-only JSON array):
```json
[
  { "run_id": "...", "dataset_key": "weekly_data", ... },
  { "run_id": "...", "dataset_key": "weekly_data", ... }
]
```

Behavior:
- If `runs/index.json` does not exist: create it with this record as the first (and only) entry.
- If it exists: load the array, check for duplicate `run_id`, append, write back atomically.
- Write atomically: write to a temp file in the same directory, then `os.replace()`. Never leave a half-written index.
- Emit an `AuditEvent` with `event="history_registered"` after successful write.

**`class HistoryReader`**

Read-only access to the index. Scoped to a single `dataset_key`.

```python
class HistoryReader:
    def __init__(self, index_path: Path, dataset_key: str) -> None: ...

    def get_metric_history(
        self,
        metric_id: str,
        n_weeks: int = 4,
        before_week_start: str | None = None,
    ) -> list[tuple[str, float]]:
        """Return up to n_weeks of prior (week_start, metric_value) pairs.

        Ordered chronologically (oldest first).
        Scoped strictly to self.dataset_key — never returns results from other datasets.
        Reads metric value from the findings.json at each indexed run's findings_path.
        Skips runs whose findings_path does not exist (emits a warning, does not raise).
        before_week_start: if provided, only returns runs with week_start < this date.
        """
```

Implementation notes:
- Load index, filter by `dataset_key` — this filter happens before any other processing.
- Sort filtered entries by `week_start` descending.
- Take the first `n_weeks` entries (prior to `before_week_start` if given).
- For each entry, open `findings_path`, extract the value for `metric_id`.
- Return sorted ascending by `week_start`.
- If the index does not exist: return `[]` (first-run path).

**Where to find metric values in `findings.json`:**

The `findings.json` structure already exists. Metric values are in `findings.metrics[].current`. The `HistoryReader` should extract `current` for the requested `metric_id`. If a metric is absent from a historical findings file (schema evolution), skip that entry silently with a `logger.warning`.

### Tests Required (`tests/test_history.py`)

| Test | What it verifies |
|------|-----------------|
| `test_derive_dataset_key_strips_date` | `weekly_data_2026-03-03.csv` → `weekly_data` |
| `test_derive_dataset_key_no_date` | `dataset_07_extreme_ad_spend.csv` → unchanged stem |
| `test_derive_dataset_key_full_path` | Full path input returns same key as filename only |
| `test_register_run_creates_index` | First registration creates `runs/index.json` |
| `test_register_run_appends` | Second registration appends, does not overwrite |
| `test_register_run_rejects_duplicate_run_id` | Duplicate `run_id` raises `ValueError` |
| `test_register_run_rejects_missing_findings` | Non-existent `findings_path` raises `FileNotFoundError` |
| `test_history_reader_returns_empty_on_no_index` | `HistoryReader.get_metric_history()` returns `[]` when index absent |
| `test_history_reader_scoped_to_dataset_key` | Runs from a different `dataset_key` never appear in results |
| `test_history_reader_ordering` | Returns results in chronological order (oldest first) |
| `test_history_reader_respects_n_weeks` | Returns at most `n_weeks` entries |
| `test_history_reader_skips_missing_findings_path` | Stale index entry (missing file) is skipped, no exception |

### Acceptance Criteria
- All 12 tests above pass
- Dataset isolation is verified by test — not just described
- Atomic write confirmed (no partial state possible)
- All existing 217+ tests still pass
- Ruff clean

### Allowed Files
```
src/wbsb/history/__init__.py       ← new (empty)
src/wbsb/history/store.py          ← new
tests/test_history.py              ← new
```

---

---

## I6-3 — Pipeline Integration (History Registration)

**Owner:** Claude
**Branch:** `feature/i6-3-pipeline-integration`
**Status:** ✅ DONE — PR #28 ready for review
**Depends on:** I6-2 merged

### Actual Deliverables
- `src/wbsb/pipeline.py` — added `derive_dataset_key()`, `week_end = week_start + timedelta(days=6)`, `RunRecord` construction, `register_run()` call after `write_artifacts()`
- `tests/test_pipeline_history.py` — 7 integration tests (new file; pipeline-level tests kept separate from store unit tests)
- Test count after: 242 (up from 235)

### Deviations from Spec
- Test file is `tests/test_pipeline_history.py`, not `tests/test_history.py` — cleaner separation of concerns (store unit tests vs pipeline integration tests)
- Code review added 2 missing tests: `test_pipeline_register_run_error_propagates` (monkeypatched register_run) and `test_pipeline_second_run_appends_index`; strengthened type assertions on index entry fields



### Why Claude
`pipeline.py` is the orchestrator that touches every stage in order. Adding history registration in the wrong place (e.g., before artifacts are written, or in a try/except that swallows errors) would silently corrupt the history index or break the audit trail. This requires understanding of the pipeline's existing error handling and artifact lifecycle.

### Why This Is a Separate Task from I6-2
The store module and the pipeline integration have different failure modes and different reviewable surfaces. Keeping them separate makes each PR small and reviewable. A reviewer can verify the store contract in one PR and the pipeline wiring in another.

### What to Build

In `src/wbsb/pipeline.py`, after all artifacts are successfully written (i.e., after `findings.json`, `manifest.json`, and any LLM artifacts are confirmed written):

1. Call `derive_dataset_key(input_file)` to get the `dataset_key`.
2. Construct a `RunRecord` from the current run's data (use values already computed: `run_id`, `week_start`, `week_end`, `signal_count` from findings, `findings_path`).
3. Call `register_run(run_record, index_path)`.
4. If `register_run` raises, log the error and re-raise — do not swallow it.

**`index_path` location:** `runs/index.json` — same `runs/` directory used for per-run artifact folders. The path should be derived from the existing `runs_dir` configuration already present in `pipeline.py`.

**Registration must happen after artifacts are written.** If the pipeline fails before artifacts are written, no registration should occur. The index must only contain runs that completed successfully.

**`dataset_key` must be stored on the pipeline's run context** so it can be passed to `compute_trends()` in I6-5 without re-deriving it.

### First-Run Behavior
If `runs/index.json` does not exist, `register_run` creates it. No special handling needed in `pipeline.py` — the store handles this transparently.

### Tests Required (extend `tests/test_history.py`)

| Test | What it verifies |
|------|-----------------|
| `test_pipeline_registers_run_in_index` | After a full pipeline run, `runs/index.json` exists and contains the run |
| `test_pipeline_index_entry_has_correct_fields` | All required fields present in the index entry |
| `test_pipeline_registration_after_artifacts` | Index entry's `findings_path` points to a file that exists |
| `test_pipeline_no_registration_on_validation_failure` | A run that fails validation does not create an index entry |

Use the existing test fixtures/helpers from `tests/` where possible (e.g., synthetic dataset loading patterns already established in I1–I5 tests).

### Acceptance Criteria
- `runs/index.json` is created and updated after every successful pipeline run
- Failed runs (validation error, missing columns) do not produce index entries
- `dataset_key` is stored on the run context for downstream use
- All existing 217+ tests still pass
- Ruff clean

### Allowed Files
```
src/wbsb/pipeline.py               ← register run; derive and store dataset_key
tests/test_history.py              ← extend
```

---

---

## I6-4 — Deterministic Trend Engine

**Owner:** Claude
**Branch:** `feature/i6-4-trend-engine`
**Depends on:** I6-2 merged (I6-3 can run in parallel)

### Why Claude
This is the most logic-dense module in Iteration 6. The six trend label definitions must be implemented precisely, with careful handling of edge cases (gaps in history, alternating signals, the boundary between `volatile` and `recovering`). It also requires reading config without hardcoding and threading `dataset_key` through correctly.

### Why This Can Run in Parallel with I6-3
I6-4 only creates a new file (`trends.py`) and extends tests. It does not touch `pipeline.py`. I6-3 only touches `pipeline.py`. They do not conflict. If team velocity allows, both PRs can be open simultaneously and merged in either order before I6-5 begins.

### What to Build

#### `src/wbsb/history/trends.py`

**`compute_trends(history_reader, metric_ids, n_weeks=None) -> dict[str, TrendResult]`**

```python
def compute_trends(
    history_reader: HistoryReader,
    metric_ids: list[str],
    n_weeks: int | None = None,
) -> dict[str, TrendResult]:
    """Compute deterministic trend labels for a list of metric IDs.

    Uses history_reader (already scoped to a dataset_key) to fetch prior values.
    Reads thresholds from config/rules.yaml under the history: key.
    Returns a TrendResult for every metric_id in the input list.
    Never raises — returns insufficient_history for any metric with missing data.
    """
```

Note: `history_reader` is already scoped to a `dataset_key` (set at construction time in I6-2). No additional `dataset_key` argument is needed here — isolation is enforced at the store layer.

**`TrendResult` (TypedDict or dataclass):**

```python
{
    "metric_id": str,
    "trend_label": str,          # one of the six labels below
    "weeks_consecutive": int,    # consecutive weeks in current direction; 0 for stable/volatile/insufficient
    "baseline_delta_pct": float | None,  # vs n-week average; None when insufficient history
    "direction_sequence": list[str],     # ["up", "down", "flat", ...] oldest to newest
}
```

**The six trend labels and their exact definitions:**

| Label | Condition |
|-------|-----------|
| `insufficient_history` | Fewer than 2 prior data points available (cannot compute direction) |
| `stable` | All week-over-week changes are within `±stable_band_pct` AND at least `stable_min_weeks` data points exist |
| `rising` | The last `min_consecutive` or more direction steps are all `"up"` (change > `+stable_band_pct`) |
| `falling` | The last `min_consecutive` or more direction steps are all `"down"` (change < `-stable_band_pct`) |
| `recovering` | The direction sequence ends with at least one `"up"` step, AND the prior step(s) before that were `"down"` |
| `volatile` | None of the above — direction alternates without a sustained trend |

**Label priority (when multiple could apply):** `insufficient_history` > `stable` > `rising` > `falling` > `recovering` > `volatile`. Evaluate in this order and return on first match.

**Direction classification per week:**
- `"up"` — week-over-week change > `+stable_band_pct`
- `"down"` — week-over-week change < `-stable_band_pct`
- `"flat"` — change within `±stable_band_pct`

Flat steps are neutral: a sequence `["up", "flat", "up"]` does not break a `rising` classification if the last two non-flat steps are both `"up"`. Apply judgment here — document the chosen approach in a module docstring.

**Config loading:**

```python
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[3] / "config" / "rules.yaml"

def _load_history_config() -> dict:
    with _CONFIG_PATH.open() as f:
        cfg = yaml.safe_load(f)
    return cfg.get("history", {})
```

Load config once at module level (cached). Do not re-read the file on every call. Do not hardcode fallback values — raise a clear `KeyError` with a useful message if a required key is missing from the config.

**`baseline_delta_pct` calculation:**

```
baseline = mean of the prior n_weeks metric values
baseline_delta_pct = (current_value - baseline) / baseline
```

Where `current_value` is the current week's value (passed as the most recent value in the history reader's results or as a separate argument — decide based on what `pipeline.py` has available). Document the choice clearly.

### Tests Required (extend `tests/test_history.py`)

| Test | What it verifies |
|------|-----------------|
| `test_trend_insufficient_history_zero_points` | 0 prior weeks → `insufficient_history` |
| `test_trend_insufficient_history_one_point` | 1 prior week → `insufficient_history` |
| `test_trend_stable` | 3+ weeks all within ±2% → `stable` |
| `test_trend_rising_exact_min_consecutive` | Exactly `min_consecutive` up weeks → `rising` |
| `test_trend_rising_more_than_min` | 4 up weeks → `rising`, `weeks_consecutive=4` |
| `test_trend_falling` | 2+ consecutive down weeks → `falling` |
| `test_trend_recovering` | Prior weeks down, last week up → `recovering` |
| `test_trend_volatile` | Alternating up/down → `volatile` |
| `test_trend_missing_week_gap` | Gap in history (missing week) handled without exception |
| `test_trend_config_driven` | Changing `min_consecutive` in config changes label output |
| `test_trend_dataset_scoped` | `history_reader` scoped to dataset A does not include dataset B runs |
| `test_compute_trends_empty_metric_ids` | Empty input → empty dict, no exception |
| `test_baseline_delta_pct_calculation` | Correct arithmetic verified with known values |

### Acceptance Criteria
- All 13 tests pass
- No hardcoded threshold values anywhere in `trends.py`
- All six labels producible and unit-tested
- `insufficient_history` entries are in the output dict (not absent)
- Config load path is documented and resolves correctly when running tests from the repo root
- All existing 217+ tests still pass
- Ruff clean

### Allowed Files
```
src/wbsb/history/trends.py         ← new
tests/test_history.py              ← extend
```

---

---

## I6-5 — LLM Adapter Extension (Trend Context)

**Owner:** Claude
**Branch:** `feature/i6-5-llm-trend-context`
**Depends on:** I6-3 merged AND I6-4 merged

### Why Claude
`llm_adapter.py` is sensitive. It controls what the LLM sees, what gets validated, and what falls back gracefully. Connecting trend output to the prompt payload requires understanding the existing `build_prompt_inputs()` contract, the existing fallback chain, and the `pipeline.py` call flow established in I6-3. This is not a mechanical edit.

### Why Both I6-3 and I6-4 Must Be Done First
- I6-3 established that `dataset_key` is stored on the run context and that `compute_trends()` will be called from `pipeline.py`. I6-5 wires the output of that call into `render_llm()`.
- I6-4 defined `TrendResult` shape and `compute_trends()` signature. I6-5 consumes both.

### What to Build

#### In `src/wbsb/pipeline.py`

After `compute_trends()` is called (using the `HistoryReader` scoped to the current `dataset_key`), pass the result to `render_llm()`:

```python
trend_context = compute_trends(history_reader, metric_ids=signal_metric_ids)
# ... existing render call, extended:
render_llm(findings, ctx, mode=llm_mode, trend_context=trend_context)
```

`signal_metric_ids` = the list of `metric_id` values from the current findings' signals. Trend context is only computed for metrics that fired a signal — not all 16 metrics.

If `compute_trends()` raises an unexpected exception, log it and pass `trend_context={}` to `render_llm()`. The LLM call must still proceed.

#### In `src/wbsb/render/llm_adapter.py`

Extend `build_prompt_inputs()` to accept an optional `trend_context: dict[str, TrendResult]` parameter (default `{}`).

Add a `trend_context_for_prompt` key to the returned dict, containing only the filtered, serializable trend entries:

```python
def _build_trend_context_for_prompt(
    trend_context: dict[str, TrendResult],
) -> list[dict]:
    """Filter and serialize trend context for the LLM prompt.

    Excludes metrics with trend_label == 'insufficient_history'.
    Returns an empty list when no valid entries remain (first run, or all insufficient).
    Never sends raw historical arrays.
    """
```

Each entry in the output list:
```python
{
    "metric_id": str,
    "trend_label": str,          # e.g. "rising"
    "weeks_consecutive": int,
    "baseline_delta_pct": float | None,
}
```

`direction_sequence` is **not** included — it is an internal diagnostic, not LLM input. Raw arrays are never sent to the LLM.

The returned list is what `user_full_v2.j2` will iterate over in I6-6.

### Prompt Template Contract (for I6-6)

After this task merges, the following variable is available in the Jinja2 template context:

```
trend_context_for_prompt   list of dicts, may be empty
```

Each dict has exactly: `metric_id`, `trend_label`, `weeks_consecutive`, `baseline_delta_pct`.

The template (I6-6) must check `{% if trend_context_for_prompt %}` before rendering the section.

### Tests Required (extend `tests/test_llm_adapter.py`)

| Test | What it verifies |
|------|-----------------|
| `test_build_prompt_inputs_with_no_trend_context` | `trend_context={}` → `trend_context_for_prompt` is empty list |
| `test_build_prompt_inputs_excludes_insufficient_history` | Entries with `trend_label="insufficient_history"` are filtered out |
| `test_build_prompt_inputs_includes_valid_trends` | Valid trend entries appear in `trend_context_for_prompt` |
| `test_build_prompt_inputs_no_raw_arrays` | `direction_sequence` is absent from prompt output |
| `test_trend_context_empty_when_all_insufficient` | All metrics insufficient → `trend_context_for_prompt = []` |
| `test_pipeline_passes_trend_context_to_render` | Integration: pipeline calls render with trend_context |

### Acceptance Criteria
- `trend_context_for_prompt` present in `build_prompt_inputs()` output in all cases
- Empty list (not absent key) when no valid trends
- `direction_sequence` never in prompt output
- `insufficient_history` entries never reach the prompt
- LLM fallback mode still works correctly with and without trend context
- All existing 217+ tests still pass
- Ruff clean

### Allowed Files
```
src/wbsb/render/llm_adapter.py          ← extend build_prompt_inputs()
src/wbsb/pipeline.py                    ← call compute_trends(); pass to render_llm()
tests/test_llm_adapter.py               ← extend
```

---

---

## I6-6 — Prompt Template Update

**Owner:** Codex
**Branch:** `feature/i6-6-prompt-template`
**Depends on:** I6-5 merged

### Why Codex
Template work is bounded and mechanical once the data contract is defined. After I6-5 merges, the exact variable name (`trend_context_for_prompt`) and the exact shape of each entry are locked. Codex can implement the Jinja2 block without risk of architectural drift.

### Why This Must Wait for I6-5
Codex must not invent variable names. The template must consume exactly what `build_prompt_inputs()` produces. If I6-6 runs before I6-5, there is a high risk of name mismatches that cause silent empty sections (the same class of bug that caused the `group_narratives` key mismatch fixed in I5).

### What to Build

In `src/wbsb/render/prompts/user_full_v2.j2`, add a TREND CONTEXT block. Place it **above** the existing SIGNALS section (after the header block, before signals):

```jinja2
{% if trend_context_for_prompt %}
TREND CONTEXT (prior {{ history_n_weeks }} weeks)
{% for entry in trend_context_for_prompt %}
{{ entry.metric_id | ljust(30) }} {{ entry.trend_label }}{% if entry.weeks_consecutive > 0 %} | {{ entry.weeks_consecutive }} consecutive weeks{% endif %}{% if entry.baseline_delta_pct is not none %} | {{ "%+.1f%%" | format(entry.baseline_delta_pct * 100) }} vs {{ history_n_weeks }}-week average{% endif %}

{% endfor %}
{% endif %}
```

**Notes:**
- The section is omitted entirely when `trend_context_for_prompt` is empty (first run, all insufficient)
- `history_n_weeks` should be available in the prompt context (passed from `build_prompt_inputs()` — Claude must add this key in I6-5 if not already present; Codex should check the I6-5 PR before implementing)
- Do not change any existing section of the template
- Do not add any new LLM output fields or response schema changes — the response schema is unchanged
- The template must still render correctly when `trend_context_for_prompt` is `[]`

### Tests
No new test file needed. Verify by running the existing `tests/test_llm_adapter.py` and `tests/test_render_template.py` — they must all pass. If any test fails due to the template change, fix the template (not the tests).

### Acceptance Criteria
- Template renders TREND CONTEXT when `trend_context_for_prompt` is non-empty
- Template renders correctly (no section, no error) when `trend_context_for_prompt` is `[]`
- Existing template sections (Situation, Signals, etc.) are unchanged
- All existing 217+ tests still pass
- Ruff clean (Jinja2 is not linted by ruff, but no Python files should be touched)

### Allowed Files
```
src/wbsb/render/prompts/user_full_v2.j2    ← add TREND CONTEXT block only
```

---

---

## I6-7 — Architecture Review

**Owner:** You
**Depends on:** I6-6 merged

### Why You
Not a coding task. This is a structured inspection pass before the final cleanup. The goal is to catch design mistakes before they are cemented in test coverage and documentation.

### What to Review

Run these checks manually against the codebase after I6-6 merges:

**Hardcoded thresholds:**
```bash
grep -rn "0\.02\|min_consecutive\|stable_band" src/wbsb/history/
```
Expected: all numbers should be read from config. Any literal `0.02`, `2`, `3`, `4` inside `trends.py` is a violation.

**Dataset contamination:**
```bash
grep -n "dataset_key" src/wbsb/history/store.py
grep -n "dataset_key" src/wbsb/pipeline.py
```
Expected: `dataset_key` is used in every history query path. If any `get_metric_history()` call omits the filter, it is a bug.

**LLM overreach:**
Check that `trends.py` contains no strings that sound like interpretation ("this indicates", "suggesting", "likely", "probably"). The trend engine must only emit labels, numbers, and direction strings.

**Schema drift:**
```bash
grep -n "TrendResult\|trend_label\|trend_context" src/wbsb/domain/models.py
```
Expected: the `Findings` domain model should not be modified. Trend context is a pipeline-layer construct, not a domain model field.

**Prompt inflation:**
Check `build_prompt_inputs()` output for `direction_sequence`. Expected: absent. Raw arrays must not reach the LLM.

**First-run behavior:**
Manually run:
```bash
wbsb run -i examples/datasets/dataset_01_clean_healthy.csv
```
On a clean environment (no `runs/index.json`). Expected: completes without error, creates `runs/index.json`, TREND CONTEXT section absent from `brief.md`.

**Second run behavior:**
Run again:
```bash
wbsb run -i examples/datasets/dataset_02_revenue_decline.csv
```
Expected: `runs/index.json` has two entries. TREND CONTEXT section may appear in `brief.md` if the dataset keys match (they won't in this case — different dataset keys). If you run the same dataset twice, TREND CONTEXT should appear on the second run.

### Review Checklist
- [ ] No hardcoded thresholds in `trends.py`
- [ ] Every `get_metric_history()` call is dataset-scoped
- [ ] `direction_sequence` not present in prompt output
- [ ] `Findings` domain model unchanged
- [ ] `trend_label: "insufficient_history"` never reaches the LLM prompt
- [ ] First-run works cleanly with no prior index
- [ ] Second run (same dataset) produces trend context
- [ ] LLM fallback still works (`wbsb run -i ... --llm-mode off`)
- [ ] All 217+ tests passing after `pytest`
- [ ] Ruff clean after `ruff check .`

If any checklist item fails: open a specific issue and assign to I6-8 cleanup.

---

---

## I6-8 — Final Cleanup Pass

**Owner:** Claude
**Branch:** `feature/i6-8-final-cleanup`
**Depends on:** I6-7 complete (review findings incorporated)

### Why Claude
Cross-cutting reconciliation — fixing any issues surfaced by the architecture review, verifying no orphaned imports, ensuring all docs reflect the final implementation.

### What to Do

1. **Fix any issues** flagged in the I6-7 review checklist. Document each fix in the commit message.

2. **Update `TASKS.md`** Definition of Done checkboxes to reflect completion:
   - All six checkboxes ticked
   - Iteration status updated to "Complete"

3. **Update `project-iterations.md`** I6 status from "Planned" to "Complete".

4. **Verify test count** — run `pytest --collect-only | grep "test session starts" -A 5` and confirm the baseline has grown from 217 to reflect all new tests.

5. **Verify no orphaned files** — confirm `src/wbsb/history/__init__.py` exists, that `store.py` and `trends.py` are importable without error.

6. **Verify `runs/.gitkeep`** is still present and `runs/index.json` is listed in `.gitignore** (the index file must not be committed).

   If `runs/index.json` is not in `.gitignore`, add it:
   ```
   runs/index.json
   ```

7. **Run a final end-to-end test** with LLM mode:
   ```bash
   export $(cat .env | xargs)
   wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode full
   ```
   Confirm TREND CONTEXT appears in the brief on second run of the same dataset.

### Acceptance Criteria
- All issues from I6-7 review resolved
- `TASKS.md` and `project-iterations.md` reflect I6 complete
- `runs/index.json` is in `.gitignore`
- Test count confirmed grown from 217 baseline
- `pytest` passes, `ruff check .` clean
- `main` branch stable

### Allowed Files
```
TASKS.md
project-iterations.md
.gitignore                             ← add runs/index.json if missing
src/wbsb/history/store.py             ← only if review found bugs
src/wbsb/history/trends.py            ← only if review found bugs
src/wbsb/pipeline.py                  ← only if review found bugs
src/wbsb/render/llm_adapter.py        ← only if review found bugs
src/wbsb/render/prompts/user_full_v2.j2 ← only if review found bugs
tests/test_history.py                 ← only if review found gaps
tests/test_llm_adapter.py             ← only if review found gaps
```

---

---

## Definition of Done — Iteration 6

Iteration 6 is complete when ALL of the following are true:

**History Store (I6-2, I6-3)**
- [ ] `runs/index.json` created and updated after every successful pipeline run
- [ ] Each entry contains `run_id`, `dataset_key`, `input_file`, `week_start`, `week_end`, `signal_count`, `findings_path`, `registered_at`
- [ ] Failed runs do not produce index entries
- [ ] Runs from different `dataset_key` values are never mixed in query results

**Trend Engine (I6-4)**
- [ ] All six trend labels (`rising`, `falling`, `stable`, `recovering`, `volatile`, `insufficient_history`) computed correctly
- [ ] All thresholds read from `config/rules.yaml` — zero hardcoded numbers in `trends.py`
- [ ] `insufficient_history` returned as an explicit label, not as an absent key

**LLM Integration (I6-5, I6-6)**
- [ ] `trend_context_for_prompt` present in prompt inputs in all pipeline modes
- [ ] TREND CONTEXT section present in `brief.md` when valid trend history exists
- [ ] TREND CONTEXT section absent on first run and when all trends are `insufficient_history`
- [ ] `direction_sequence` never sent to the LLM
- [ ] LLM fallback mode (`--llm-mode off`) unchanged and unaffected

**Quality**
- [ ] All tests from 217 baseline still passing
- [ ] New tests cover all six trend labels, dataset isolation, first-run, and prompt filtering
- [ ] Ruff clean
- [ ] `runs/index.json` in `.gitignore`
- [ ] `main` branch stable

---

*Created: 2026-03-09*
*Reflects I6 architecture decisions from pre-coding review (I6-0).*
*Update this file at end of each task with actual vs planned deliverables.*
