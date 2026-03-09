# WBSB Task Prompt — I6-2: History Store and Dataset-Scoped HistoryReader

---

## Project Context

WBSB (Weekly Business Signal Brief) is a deterministic analytics engine for appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics, detects signals via a config-driven rules engine, and generates a structured business brief. An LLM is optionally used for narrative sections only — never for calculations.

Core architecture:
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

Non-negotiable principles:
- Analytics are deterministic. LLM is explanation only, never analytics.
- All thresholds live in `config/rules.yaml`. Zero hardcoded numbers in code.
- Every module has a strict boundary. Metrics, rules, and rendering never mix.
- No silent failures. Raise clearly or emit an `AuditEvent`.
- LLM is optional. Every mode produces a complete report without it.

---

## Repository State

- **Iteration integration branch:** `feature/iteration-6`
- **Feature branch for this task:** `feature/i6-2-history-store`
- **Tests passing:** 217
- **Ruff:** clean
- **Last completed task:** I6-1 — `history:` config section added to `config/rules.yaml`
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I6-2 |
| Title | History Store and Dataset-Scoped HistoryReader |
| Iteration | Iteration 6 — Historical Memory & Trend Awareness |
| Owner | Claude |
| Iteration branch | `feature/iteration-6` |
| Feature branch | `feature/i6-2-history-store` |
| Depends on | I6-1 |
| Blocks | I6-3, I6-4 |
| PR scope | One PR into `feature/iteration-6`. Do not combine tasks. Do not PR to `main`. |

---

## Task Goal

This task introduces persistent historical memory for completed pipeline runs. The system currently operates statelessly, comparing only the current week against the previous one. Iteration 6 requires access to prior runs so the trend engine can analyze metric trajectories across multiple weeks.

This task creates the history storage layer, consisting of:
- A JSON index of completed runs at `runs/index.json`
- A function to register runs in that index
- A dataset-scoped reader for retrieving metric history

The design must guarantee dataset isolation so runs from different datasets never contaminate each other's historical analysis.

---

## Why Claude

This module defines the architecture that every later Iteration 6 component relies on. It touches filesystem persistence, run identity, dataset isolation rules, and historical queries. These require careful handling of failure modes and clear contracts for downstream tasks (I6-3, I6-4).

---

## Files to Read Before Starting

Read these files in order before writing any code:

```
src/wbsb/pipeline.py          ← understand how runs are executed and where registration will occur
src/wbsb/domain/models.py     ← see existing AuditEvent and findings models
config/rules.yaml             ← understand config-driven patterns used in this system
tests/test_e2e_pipeline.py    ← see test fixtures and tmp_path patterns used in pipeline tests
```

---

## Existing Code This Task Builds On

The pipeline already produces run artifacts written to the `runs/` directory:

```
runs/
  <run_id>/
    findings.json     ← metric values live here under findings.metrics[].current
    manifest.json
    brief.md
    logs.jsonl
```

History storage must track those runs without modifying the existing artifact structure or the pipeline itself (pipeline wiring is I6-3's responsibility).

The `AuditEvent` model already exists in `src/wbsb/domain/models.py`. Emit one after a successful index write.

`config/rules.yaml` now contains a `history:` section (added in I6-1):
```yaml
history:
  n_weeks: 4
  min_consecutive: 2
  stable_band_pct: 0.02
  stable_min_weeks: 3
```

---

## What to Build

### New package: `src/wbsb/history/`

```
src/wbsb/history/__init__.py    ← new, empty file (marks the package)
src/wbsb/history/store.py       ← new, contains all public API for this task
```

---

### Public API — `src/wbsb/history/store.py`

#### `derive_dataset_key(input_file: str | Path) -> str`

Converts an input file path to a stable dataset identity key used for history isolation.

```python
def derive_dataset_key(input_file: str | Path) -> str:
    """Return a stable dataset key derived from the input filename.

    Rules (applied in order):
    1. Take the filename only — ignore directory components.
    2. Strip the file extension.
    3. Remove a trailing date segment matching: _YYYY-MM-DD, -YYYY-MM-DD, _YYYYMMDD.
    4. Strip any remaining trailing underscores or dashes.
    5. Return as lowercase string.

    This function is pure — no I/O, no side effects.
    """
```

Examples:
```python
derive_dataset_key("weekly_data_2026-03-03.csv")          # → "weekly_data"
derive_dataset_key("report_20260303.xlsx")                 # → "report"
derive_dataset_key("dataset_07_extreme_ad_spend.csv")      # → "dataset_07_extreme_ad_spend"
derive_dataset_key("/full/path/to/weekly_data_2026-03-10.csv")  # → "weekly_data"
```

---

#### `RunRecord` (TypedDict)

```python
class RunRecord(TypedDict):
    run_id: str          # e.g. "20260309T094756Z_4c43f0"
    dataset_key: str     # e.g. "weekly_data"
    input_file: str      # full path, for traceability
    week_start: str      # ISO date "2026-03-03"
    week_end: str        # ISO date "2026-03-09"
    signal_count: int
    findings_path: str   # full path to findings.json
    registered_at: str   # ISO datetime of registration
```

---

#### `register_run(run: RunRecord, index_path: Path) -> None`

Appends a completed pipeline run to the history index.

```python
def register_run(run: RunRecord, index_path: Path) -> None:
    """Append a run record to the JSON index at index_path.

    Raises:
        ValueError: If run_id already exists in the index.
        FileNotFoundError: If run['findings_path'] does not exist.
    """
```

Behavior rules:
- If `index_path` does not exist: create it with this record as the first entry.
- If it exists: load the array, check for duplicate `run_id`, append, write back.
- **Atomic write:** write to a temp file in the same directory, then `os.replace()`. Never leave a partially written index.
- Emit an `AuditEvent` with `event="history_registered"` after successful write.

Index format — a JSON array of `RunRecord` dicts:
```json
[
  { "run_id": "20260302T...", "dataset_key": "weekly_data", ... },
  { "run_id": "20260309T...", "dataset_key": "weekly_data", ... }
]
```

---

#### `class HistoryReader`

Read-only access to the index, scoped to a single dataset.

```python
class HistoryReader:
    def __init__(self, index_path: Path, dataset_key: str) -> None:
        """Scope all queries to dataset_key. index_path need not exist yet."""

    def get_metric_history(
        self,
        metric_id: str,
        n_weeks: int = 4,
        before_week_start: str | None = None,
    ) -> list[tuple[str, float]]:
        """Return up to n_weeks of prior (week_start, metric_value) pairs.

        Returns results ordered chronologically (oldest first).
        Scoped strictly to self.dataset_key — never returns results from other datasets.

        Args:
            metric_id: The metric ID to look up (e.g. "cac_paid").
            n_weeks: Maximum number of prior weeks to return.
            before_week_start: If given, only include runs with week_start < this date.

        Returns:
            List of (week_start, value) tuples, oldest first.
            Empty list if no history exists.
        """
```

Implementation steps:
1. If `index_path` does not exist → return `[]`.
2. Load index, **filter by `dataset_key`** — this filter happens first, before anything else.
3. Sort filtered entries by `week_start` descending.
4. Apply `before_week_start` filter if provided.
5. Take the first `n_weeks` entries.
6. For each entry, open `findings_path`, parse JSON, extract `findings.metrics[].current` for `metric_id`.
7. Return sorted ascending by `week_start`.

Edge cases:
- `findings_path` does not exist → skip entry, `logger.warning(...)`, continue.
- `metric_id` not found in findings → skip entry, continue.
- Index is empty after filtering → return `[]`.

---

## Architecture Constraints

1. **Deterministic first** — no randomness, no time-dependent logic in metrics or rules.
2. **Config-driven** — all thresholds in `config/rules.yaml`. Zero hardcoded numbers.
3. **Auditability** — emit `AuditEvent` after every significant state change.
4. **No silent failure** — never use `except: pass`. Raise `ValueError` with a clear message.
5. **Separation of concerns** — this module is storage only. No trend computation here.
6. **LLM is optional** — this module has no dependency on LLM code.
7. **Secrets never in code** — no API keys or tokens involved in this module.

---

## Allowed Files

```
src/wbsb/history/__init__.py    ← new (empty)
src/wbsb/history/store.py       ← new
tests/test_history.py           ← new
```

---

## Files NOT to Touch

```
src/wbsb/pipeline.py                      ← pipeline wiring is I6-3's task
src/wbsb/domain/models.py                 ← domain model is frozen
src/wbsb/render/llm_adapter.py            ← LLM integration is I6-5's task
src/wbsb/render/prompts/user_full_v2.j2   ← template is I6-6's task
```

If any of these appear to require changes, stop and ask rather than modifying them.

---

## Acceptance Criteria

- [ ] `derive_dataset_key()` returns correct keys for all examples shown above
- [ ] `register_run()` creates `runs/index.json` on first call
- [ ] `register_run()` appends without overwriting prior entries
- [ ] Duplicate `run_id` raises `ValueError` with a descriptive message
- [ ] Non-existent `findings_path` raises `FileNotFoundError`
- [ ] Atomic write confirmed — temp file + `os.replace()` pattern used
- [ ] `AuditEvent` emitted with `event="history_registered"` after successful write
- [ ] `HistoryReader` returns empty list when index does not exist
- [ ] `HistoryReader` never returns entries from a different `dataset_key`
- [ ] Results returned in chronological order (oldest first)
- [ ] Missing `findings_path` skipped with warning, no exception raised
- [ ] All 217+ existing tests still pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only allowed files appear in `git diff --name-only feature/iteration-6`

---

## Tests Required

**Test file:** `tests/test_history.py`

Use `tmp_path` for all file I/O. Never write to the real `runs/` directory in tests.

| Test | What it verifies |
|------|-----------------|
| `test_derive_dataset_key_strips_date` | `weekly_data_2026-03-03.csv` → `weekly_data` |
| `test_derive_dataset_key_strips_yyyymmdd` | `report_20260303.xlsx` → `report` |
| `test_derive_dataset_key_no_date` | `dataset_07_extreme_ad_spend.csv` → stem unchanged |
| `test_derive_dataset_key_handles_full_path` | Full path returns same result as filename only |
| `test_register_run_creates_index` | First call creates `index.json` with one entry |
| `test_register_run_appends_records` | Second call appends, does not overwrite |
| `test_register_run_rejects_duplicate_run_id` | Same `run_id` raises `ValueError` |
| `test_register_run_rejects_missing_findings` | Non-existent `findings_path` raises `FileNotFoundError` |
| `test_history_reader_empty_when_no_index` | Returns `[]` when index file absent |
| `test_history_reader_dataset_isolation` | Run registered under `"dataset_a"` not returned by reader scoped to `"dataset_b"` |
| `test_history_reader_returns_chronological_order` | Multiple entries returned oldest-first |
| `test_history_reader_respects_n_weeks_limit` | Returns at most `n_weeks` entries |
| `test_history_reader_skips_missing_findings` | Stale index entry (file deleted) is skipped, no exception |
| `test_history_reader_skips_missing_metric` | Metric absent from findings is skipped, no exception |

Test pattern:
```python
def test_register_run_creates_index(tmp_path):
    # Arrange
    findings_path = tmp_path / "findings.json"
    findings_path.write_text('{"metrics": []}')
    record = RunRecord(
        run_id="20260309T000000Z_aabbcc",
        dataset_key="weekly_data",
        input_file="weekly_data_2026-03-09.csv",
        week_start="2026-03-03",
        week_end="2026-03-09",
        signal_count=2,
        findings_path=str(findings_path),
        registered_at="2026-03-09T10:00:00",
    )
    index_path = tmp_path / "index.json"

    # Act
    register_run(record, index_path)

    # Assert
    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert len(data) == 1
    assert data[0]["run_id"] == "20260309T000000Z_aabbcc"
```

---

## Edge Cases to Handle

| Edge case | Expected behaviour |
|-----------|-------------------|
| `index.json` does not exist on first call | Create it with the single record |
| `findings_path` does not exist at registration time | Raise `FileNotFoundError` immediately |
| `findings_path` disappears after registration (stale index) | Skip entry in `get_metric_history`, log warning |
| Metric absent from a historical findings file | Skip that entry, continue |
| Index contains runs from multiple datasets | Only return entries matching `dataset_key` |
| `before_week_start` filter excludes all entries | Return `[]` |

---

## What NOT to Do

- Do not introduce SQLite or any external database
- Do not modify `pipeline.py` — pipeline wiring is I6-3's job
- Do not hardcode threshold values — this module reads from config where needed
- Do not mix datasets in historical queries — isolation is enforced at the store layer
- Do not use `except: pass` or silently swallow unexpected exceptions
- Do not create any files outside `src/wbsb/history/` and `tests/`

---

## Handoff: What I6-3 and I6-4 Need From This Task

After this PR merges, the following will be available at `from wbsb.history.store import ...`:

```python
derive_dataset_key(input_file: str | Path) -> str
    # Pure function. I6-3 calls this in pipeline.py to derive the key for each run.

register_run(run: RunRecord, index_path: Path) -> None
    # I6-3 calls this after findings artifacts are written.

class HistoryReader:
    def __init__(self, index_path: Path, dataset_key: str) -> None
    def get_metric_history(self, metric_id, n_weeks, before_week_start) -> list[tuple[str, float]]
    # I6-4 constructs HistoryReader and calls get_metric_history() for each metric.
```

**These names are final. I6-3 and I6-4 will import them exactly as shown.**

---

## Execution Workflow

### Step 0 — Branch setup and draft PR

```bash
# 1. Start from the iteration integration branch
git checkout feature/iteration-6
git pull origin feature/iteration-6

# 2. Confirm clean working tree
git status
# Expected: nothing to commit, working tree clean

# 3. Create task branch
git checkout -b feature/i6-2-history-store
git branch --show-current
# Expected: feature/i6-2-history-store

# 4. Push immediately
git push -u origin feature/i6-2-history-store

# 5. Open draft PR before writing any code
gh pr create \
  --base feature/iteration-6 \
  --head feature/i6-2-history-store \
  --title "I6-2: History store and dataset-scoped HistoryReader" \
  --body "Work in progress. See prompt-task-2.md for full task spec." \
  --draft
```

### Step 1 — Verify baseline

```bash
pytest
# Expected: 217 tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

If either fails, stop. Do not proceed until the baseline is clean.

### Step 2 — Read before writing

Read all files listed in "Files to Read Before Starting" before writing a line of code.

### Step 3 — Plan

This task touches 3 files. Present the implementation plan before writing any code.

### Step 4 — Implement

Write code that satisfies all acceptance criteria and handles all edge cases.

### Step 5 — Test and lint

```bash
pytest
ruff check .
```

Both must pass before continuing.

### Step 6 — Verify scope

```bash
git diff --name-only feature/iteration-6
```

Expected: `src/wbsb/history/__init__.py`, `src/wbsb/history/store.py`, `tests/test_history.py`, `prompt-task-2.md`.
If any other file appears, review and revert it.

### Step 7 — Commit

```
feat: implement history store and dataset-scoped HistoryReader (I6-2)

Adds src/wbsb/history/store.py with derive_dataset_key(), register_run(),
and HistoryReader. Index stored at runs/index.json as an append-only JSON
array. Writes are atomic (temp file + os.replace). HistoryReader enforces
dataset isolation by filtering on dataset_key before all other operations.
First-run behavior (no index) handled gracefully. AuditEvent emitted after
each successful registration. 14 new tests in tests/test_history.py.

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 8 — Mark PR ready for review

```bash
gh pr ready feature/i6-2-history-store
```

Add a comment to the PR summarising what was built and any decisions made during implementation.

---

## Definition of Done

- [ ] `src/wbsb/history/__init__.py` exists (empty)
- [ ] `src/wbsb/history/store.py` implemented with full public API
- [ ] All 14 tests in `tests/test_history.py` pass
- [ ] All 217+ prior tests still pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only allowed files in `git diff --name-only feature/iteration-6`
- [ ] Draft PR marked ready and pushed to `feature/i6-2-history-store`
- [ ] No `except: pass`, no hardcoded values, no silent failures
