# WBSB Task Prompt — I6-3: Pipeline Integration (History Registration)

---

## Project Context

**WBSB (Weekly Business Signal Brief)** is a deterministic analytics engine for appointment-based service businesses. It ingests weekly CSV/XLSX data, computes metrics, detects signals via a config-driven rules engine, and generates a structured business brief. An LLM is optionally used for narrative sections only — never for calculations.

**Core architecture:**
```
CSV/XLSX → Loader → Validator → Metrics → Deltas → Rules Engine → Findings → Renderer → brief.md
```

**Non-negotiable principles:**
- Analytics are deterministic. LLM is explanation only, never analytics.
- All thresholds live in `config/rules.yaml`. Zero hardcoded numbers in code.
- Every module has a strict boundary. Metrics, rules, and rendering never mix.
- No silent failures. Raise clearly or emit an `AuditEvent`.
- LLM is optional. Every mode produces a complete report without it.

---

## Repository State

- **Iteration integration branch:** `feature/iteration-6`
- **Feature branch for this task:** `feature/i6-3-pipeline-integration`
- **Tests passing:** 235
- **Ruff:** clean
- **Last completed task:** I6-2 — History store and HistoryReader implemented in `src/wbsb/history/store.py`
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I6-3 |
| Title | Pipeline Integration — Register Completed Runs |
| Iteration | Iteration 6 — Historical Memory & Trend Awareness |
| Owner | Claude |
| Iteration branch | `feature/iteration-6` |
| Feature branch | `feature/i6-3-pipeline-integration` |
| Depends on | I6-2 |
| Blocks | I6-5 |
| PR scope | One PR into `feature/iteration-6`. Never PR to `main`. |

---

## Task Goal

This task connects the pipeline execution process to the history storage layer implemented in I6-2.

After a successful pipeline run completes and all artifacts are written to disk, the system must register the run in the shared history index at:

```
{output_dir}/index.json
```

This enables later tasks (trend engine I6-4 and LLM context I6-5) to query past runs scoped to a specific dataset.

The pipeline must register runs **only after artifacts are fully written**. Runs that fail at any earlier stage must never appear in the index.

---

## Why Claude

This task modifies `pipeline.py` — the orchestrator that controls the entire execution flow. Placing the registration call in the wrong position (before artifact writes, or inside the except block) would either corrupt the index with incomplete runs or silently skip registration on success. This requires understanding the pipeline's artifact lifecycle and error boundary precisely.

---

## Files to Read Before Starting

Read these files in order before writing any code:

```
src/wbsb/pipeline.py              ← understand full execution flow and artifact write location
src/wbsb/history/store.py         ← understand RunRecord shape, derive_dataset_key(), register_run()
src/wbsb/domain/models.py         ← see AuditEvent and Findings models
src/wbsb/export/write.py          ← see what artifacts write_artifacts() produces and where
tests/test_e2e_pipeline.py        ← understand how pipeline tests simulate runs end-to-end
```

---

## Existing Code This Task Builds On

### From I6-2 (`src/wbsb/history/store.py`) — already implemented, do not reimplement:

```python
def derive_dataset_key(input_file: str | Path) -> str:
    """Return stable dataset key from input filename stem (strips date, lowercased)."""

def register_run(run: RunRecord, index_path: Path) -> None:
    """Append a completed run to the JSON index. Atomic write. Raises on duplicate or missing findings."""

class RunRecord(TypedDict):
    run_id: str          # e.g. "20260309T094756Z_4c43f0"
    dataset_key: str     # e.g. "weekly_data"
    input_file: str      # full path as string
    week_start: str      # ISO date "2026-03-03"
    week_end: str        # ISO date "2026-03-09"
    signal_count: int    # total number of signals fired
    findings_path: str   # full path to findings.json as string
    registered_at: str   # ISO datetime of registration
```

### From `pipeline.py` — values already available in scope:

```python
run_id          # str — generated at top of execute()
run_dir         # Path — run's artifact directory (output_dir / run_id)
output_dir      # Path — parent directory for all runs
input_path      # Path — original input file
week_start      # date — resolved by resolve_target_week(); use .isoformat()
findings        # Findings — built by build_findings()
log             # structured logger from get_logger() — accepts keyword args
```

### Important: two different loggers in this project

`pipeline.py` uses the **structured logger** (`get_logger()` from `wbsb.observability.logging`).
This logger **accepts keyword arguments**:
```python
log.info("history.registered", run_id=run_id, dataset_key=dataset_key)  # CORRECT in pipeline.py
```

`store.py` uses the **standard Python logger** (`logging.getLogger(__name__)`).
That logger does NOT accept keyword arguments — use positional format strings there.
Do not confuse the two.

---

## What to Build

Modify `src/wbsb/pipeline.py` only. Add the history registration step after `write_artifacts()` succeeds.

### Step 1 — Add imports at top of file

```python
from datetime import timedelta
from wbsb.history.store import RunRecord, derive_dataset_key, register_run
```

Place these with the existing imports. Do not reorganise unrelated imports.

### Step 2 — Derive `dataset_key`

Immediately after `week_start, prev_week_start = resolve_target_week(...)`:

```python
dataset_key = derive_dataset_key(input_path)
```

This is a pure function — no I/O, no side effects. It is safe to call early.

### Step 3 — Compute `week_end`

`week_start` is a `date` object. The analysis period covers 7 days:

```python
week_end = week_start + timedelta(days=6)
```

### Step 4 — Construct `RunRecord` and register after artifacts

Immediately after `write_artifacts(...)` returns (before `log.info("pipeline.done", ...)`):

```python
run_record: RunRecord = {
    "run_id": run_id,
    "dataset_key": dataset_key,
    "input_file": str(input_path),
    "week_start": week_start.isoformat(),
    "week_end": week_end.isoformat(),
    "signal_count": len(findings.signals),
    "findings_path": str(run_dir / "findings.json"),
    "registered_at": datetime.now(UTC).isoformat(),
}
index_path = output_dir / "index.json"
register_run(run_record, index_path)
log.info("history.registered", run_id=run_id, dataset_key=dataset_key, index=str(index_path))
```

### Step 5 — Error handling

`register_run` raises `ValueError` (duplicate run_id) or `FileNotFoundError` (missing findings).
Both are fatal — do not catch them here. Let them propagate to the outer `except Exception` block,
which already logs and returns exit code 1.

Do not add any new try/except around the registration call.

### Exact position in execution order

```
write_artifacts(...)      ← already exists
                          ← INSERT: derive dataset_key, compute week_end, build RunRecord, register_run
log.info("pipeline.done") ← already exists
print("✅  Run complete")  ← already exists
return 0                  ← already exists
```

---

## Architecture Constraints

These apply to every task without exception:

1. **Deterministic first** — no randomness, no time-dependent logic in metrics or rules.
2. **Config-driven** — all thresholds in `config/rules.yaml`. Zero hardcoded numbers.
3. **Auditability** — emit `AuditEvent` after every significant state change.
4. **No silent failure** — never use `except: pass`. Raise `ValueError` with a clear message.
5. **Separation of concerns** — metrics, rules, and rendering are strictly isolated.
6. **LLM is optional** — `--llm-mode off` must always produce a complete, valid report.
7. **Stable ordering** — signals sorted by `rule_id`. Metrics in a stable, deterministic order.
8. **Secrets never in code** — API keys and tokens from environment variables only. Never logged.

---

## Allowed Files

```
src/wbsb/pipeline.py               ← modify: add history registration after artifact write
tests/test_pipeline_history.py     ← new: pipeline + history integration tests
```

---

## Files NOT to Touch

```
src/wbsb/history/store.py          ← owned by I6-2, already complete
src/wbsb/history/trends.py         ← owned by I6-4, does not exist yet
src/wbsb/render/llm_adapter.py    ← owned by I6-5
src/wbsb/domain/models.py         ← frozen for this iteration
src/wbsb/export/write.py          ← do not change artifact structure
config/rules.yaml                  ← no new config needed for this task
```

If any of these files seem like they need to change, **stop and raise it** rather than modifying them.

---

## Acceptance Criteria

- [ ] After a successful pipeline run, `{output_dir}/index.json` exists
- [ ] Index entry contains all `RunRecord` fields with correct types
- [ ] `dataset_key` is derived via `derive_dataset_key()` — not hardcoded
- [ ] `week_end` is `week_start + 6 days` expressed as ISO date string
- [ ] `findings_path` in the index entry points to a file that actually exists
- [ ] Registration happens **after** `write_artifacts()` returns — not before
- [ ] A pipeline run that raises an exception does **not** create an index entry
- [ ] `register_run` errors propagate — pipeline returns exit code 1, not 0
- [ ] All 235 existing tests still pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] `git diff --name-only feature/iteration-6` shows only allowed files

---

## Tests Required

**New test file:** `tests/test_pipeline_history.py`

Keep history unit tests in `tests/test_history.py`. This new file is for pipeline-level integration tests only.

| Test function | What it verifies |
|---------------|-----------------|
| `test_pipeline_creates_index_after_successful_run` | After `execute()` returns 0, `output_dir/index.json` exists |
| `test_pipeline_index_entry_has_all_required_fields` | Index entry contains `run_id`, `dataset_key`, `week_start`, `week_end`, `signal_count`, `findings_path`, `registered_at` |
| `test_pipeline_index_entry_findings_path_exists` | `findings_path` in the index entry points to a file that actually exists on disk |
| `test_pipeline_dataset_key_derived_from_filename` | `dataset_key` in the index matches `derive_dataset_key(input_path)` |
| `test_pipeline_failed_run_does_not_create_index_entry` | When `execute()` returns 1 (e.g. non-existent input file), no index entry is created |

Use `tmp_path` for all filesystem isolation. Use the real example datasets in `examples/datasets/` as inputs for successful run tests.

```python
# Pattern for pipeline integration tests
from wbsb.pipeline import execute
from wbsb.history.store import derive_dataset_key
import json

def test_pipeline_creates_index_after_successful_run(tmp_path):
    input_path = Path("examples/datasets/dataset_01_clean_week.csv")
    exit_code = execute(
        input_path=input_path,
        output_dir=tmp_path,
        llm_mode="off",
        llm_provider="anthropic",
        config_path=Path("config/rules.yaml"),
        target_week=None,
    )
    assert exit_code == 0
    index_path = tmp_path / "index.json"
    assert index_path.exists()
    entries = json.loads(index_path.read_text())
    assert len(entries) == 1
```

---

## Edge Cases to Handle

| Edge case | Expected behaviour |
|-----------|-------------------|
| First run — no index file | `register_run` creates it automatically (already handled by I6-2) |
| Second run on same dataset | Second entry appended to index (run_ids are unique by construction) |
| Pipeline fails before `write_artifacts` | Exception propagates to outer `except`; no index entry created |
| `register_run` raises (e.g. duplicate run_id) | Exception propagates; pipeline returns exit code 1 |

---

## What NOT to Do

- Do not implement any history logic directly in `pipeline.py` — use `register_run()` from `store.py`
- Do not duplicate the `register_run` logic anywhere
- Do not catch exceptions from `register_run` — let them propagate
- Do not register the run before `write_artifacts()` returns
- Do not modify `store.py` — it is complete and frozen
- Do not add `except: pass` or any silent failure
- Do not create new directories — the `runs/` structure already exists via `run_dir.mkdir()`
- Do not refactor code outside the allowed files, even if you notice improvements

---

## Handoff: What the Next Task Needs From This One

After this task merges, the following will be available for I6-4 and I6-5:

```python
# Every successful pipeline run now writes an entry to {output_dir}/index.json
# Structure of each entry (all strings):
{
    "run_id": "20260309T094756Z_4c43f0",
    "dataset_key": "weekly_data",          # derived from input filename
    "input_file": "/path/to/input.csv",
    "week_start": "2026-03-03",
    "week_end": "2026-03-09",
    "signal_count": 5,
    "findings_path": "/path/to/run_dir/findings.json",
    "registered_at": "2026-03-09T10:00:00+00:00",
}

# HistoryReader can now be constructed with:
from wbsb.history.store import HistoryReader
reader = HistoryReader(index_path=output_dir / "index.json", dataset_key=dataset_key)
history = reader.get_metric_history("net_revenue", n_weeks=4, before_week_start="2026-03-09")
```

---

## Execution Workflow

Follow this sequence exactly. Do not skip or reorder steps.

### Step 0 — Branch setup and draft PR

```bash
# 1. Start from the iteration integration branch
git checkout feature/iteration-6
git pull origin feature/iteration-6

# 2. Confirm clean working tree
git status
# Expected: "nothing to commit, working tree clean"

# 3. Create and switch to task branch
git checkout -b feature/i6-3-pipeline-integration

# 4. Confirm correct branch
git branch --show-current
# Expected: feature/i6-3-pipeline-integration

# 5. Push immediately
git push -u origin feature/i6-3-pipeline-integration

# 6. Open draft PR before writing any code
gh pr create \
  --base feature/iteration-6 \
  --head feature/i6-3-pipeline-integration \
  --title "I6-3: Pipeline integration for history registration" \
  --body "Work in progress. See prompt-task-3.md for full task spec." \
  --draft
```

### Step 1 — Verify baseline

```bash
pytest
# Expected: 235 tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

Stop if either fails — do not proceed until baseline is clean.

### Step 2 — Read before writing

Read all five files listed in "Files to Read Before Starting" before writing a single line.

### Step 3 — Implement

Add `dataset_key` derivation, `week_end` computation, `RunRecord` construction, and `register_run()` call
as specified in "What to Build". Insert immediately after `write_artifacts(...)`, before `log.info("pipeline.done")`.

### Step 4 — Test and lint

```bash
pytest
# Must pass: 235 prior tests + 5 new tests = 240 total. Zero failures.

ruff check .
# Must be clean.
```

### Step 5 — Verify scope

```bash
git diff --name-only feature/iteration-6
```

Expected output (exactly these two files):
```
src/wbsb/pipeline.py
tests/test_pipeline_history.py
```

If any unexpected file appears, review and revert it before committing.

### Step 6 — Commit

```bash
git add src/wbsb/pipeline.py tests/test_pipeline_history.py
git commit -m "$(cat <<'EOF'
feat: integrate history registration into pipeline after artifact write (I6-3)

Adds dataset_key derivation and register_run() call in pipeline.execute()
immediately after write_artifacts() returns. RunRecord is constructed from
existing pipeline context (run_id, week_start, input_path, findings) and
registered in {output_dir}/index.json. week_end is week_start + 6 days.
Registration errors propagate — failed or incomplete runs are never recorded.
Enables downstream trend engine (I6-4) and LLM context (I6-5) to query
prior runs scoped by dataset_key.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 7 — Mark PR ready

```bash
git push origin feature/i6-3-pipeline-integration
gh pr ready feature/i6-3-pipeline-integration
```

Do not merge — merging is a human decision.

---

## Definition of Done

This task is complete when ALL of the following are true:

- [ ] `{output_dir}/index.json` is created after a successful pipeline run
- [ ] All `RunRecord` fields are populated correctly (including `week_end` as `week_start + 6 days`)
- [ ] `dataset_key` derived via `derive_dataset_key()`, not hardcoded
- [ ] Registration occurs after `write_artifacts()` — never before
- [ ] Failed pipeline runs do not create index entries
- [ ] `register_run` errors propagate and cause exit code 1
- [ ] All 235 prior tests still pass
- [ ] All 5 new integration tests pass
- [ ] Ruff clean
- [ ] Only `src/wbsb/pipeline.py` and `tests/test_pipeline_history.py` are in the diff
- [ ] Feature branch pushed, PR marked ready for review
- [ ] No `except: pass`, no hardcoded values, no silent failures introduced
