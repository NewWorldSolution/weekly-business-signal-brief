# WBSB Task Prompt — I6-4: Deterministic Trend Engine

**Prepared by:** Burak Kilic

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
- **Feature branch for this task:** `feature/i6-4-trend-engine`
- **Tests passing:** 242
- **Ruff:** clean
- **Last completed task:** I6-3 — pipeline registers completed runs in history index
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I6-4 |
| Title | Deterministic Trend Engine |
| Iteration | Iteration 6 — Historical Memory & Trend Awareness |
| Owner | Claude |
| Iteration branch | `feature/iteration-6` |
| Feature branch | `feature/i6-4-trend-engine` |
| Depends on | I6-2 |
| Blocks | I6-5 |
| PR scope | One PR into `feature/iteration-6`. Never PR to `main`. |

---

## Task Goal

This task introduces a deterministic trend classification engine that analyses historical metric values and assigns a trend label.

The trend engine consumes historical metric values via `HistoryReader` and determines how a metric is evolving across multiple weeks. Trend classification is required for later integration into the LLM prompt (I6-5) so the brief can reference patterns such as:

- rising CAC
- recovering bookings
- stable revenue
- volatile refunds

The trend engine must produce deterministic classifications based strictly on historical data and configuration thresholds. No LLM or rendering logic is allowed in this module.

---

## Why Claude

This task implements the core analytical logic of Iteration 6. It requires careful reasoning about historical time series behaviour, config-driven thresholds, and deterministic classification rules. The module must correctly classify trends across many edge cases (gaps, flat runs, alternating patterns) and must avoid any hidden assumptions or hardcoded values.

---

## Files to Read Before Starting

Read these files in order before writing any code:

```
src/wbsb/history/store.py         ← understand HistoryReader.get_metric_history() signature and return shape
config/rules.yaml                  ← read the history: section — these are the ONLY allowed threshold values
src/wbsb/pipeline.py              ← see how dataset_key is derived and used
tests/test_history.py             ← understand how historical metrics are tested
```

---

## Existing Code This Task Builds On

### From I6-2 (`src/wbsb/history/store.py`) — already implemented, do not reimplement:

```python
class HistoryReader:
    def get_metric_history(
        self,
        metric_id: str,
        n_weeks: int = 4,
        before_week_start: str | None = None,
    ) -> list[tuple[str, float]]:
        """Returns (week_start, metric_value) pairs ordered oldest → newest."""
```

The last item in the returned list is the most recent week.

### From `config/rules.yaml` — already added in I6-1:

```yaml
history:
  n_weeks: 4            # default lookback window
  min_consecutive: 2    # consecutive weeks required to classify as rising or falling
  stable_band_pct: 0.02 # ±2% week-over-week change is considered flat
  stable_min_weeks: 3   # minimum observations required to classify as stable
```

These four values are the **only** threshold values permitted in this module. They must be loaded from config — never hardcoded.

---

## What to Build

Create one new module: `src/wbsb/history/trends.py`

### Public API

```python
def compute_trends(
    history_reader: HistoryReader,
    metric_ids: list[str],
    n_weeks: int | None = None,
) -> dict[str, TrendResult]:
    """Compute deterministic trend labels for a list of metric IDs.

    Args:
        history_reader: Already scoped to a dataset_key — do not re-scope.
        metric_ids: List of metric IDs to classify. Empty list returns {}.
        n_weeks: Lookback window. If None, use config value.

    Returns:
        Dict mapping metric_id → TrendResult for every ID in metric_ids.
        Never raises — returns insufficient_history for missing or sparse data.
    """
```

### `TrendResult` data shape

```python
class TrendResult(TypedDict):
    metric_id: str                    # e.g. "cac_paid"
    trend_label: str                  # one of the six labels below
    weeks_consecutive: int            # consecutive weeks in current direction
                                      # 0 for stable, volatile, insufficient_history
    baseline_delta_pct: float | None  # None when insufficient_history
    direction_sequence: list[str]     # ["up", "down", "flat", ...] oldest → newest
                                      # empty list when insufficient_history
```

### Example output

```python
{
    "cac_paid": {
        "metric_id": "cac_paid",
        "trend_label": "rising",
        "weeks_consecutive": 3,
        "baseline_delta_pct": 0.12,
        "direction_sequence": ["up", "up", "up"],
    },
    "net_revenue": {
        "metric_id": "net_revenue",
        "trend_label": "insufficient_history",
        "weeks_consecutive": 0,
        "baseline_delta_pct": None,
        "direction_sequence": [],
    },
}
```

---

## Trend Labels and Classification Rules

### Six labels (evaluate in this exact priority order)

| Priority | Label | Condition |
|----------|-------|-----------|
| 1 | `insufficient_history` | Fewer than 2 historical data points |
| 2 | `stable` | All changes within `±stable_band_pct` AND at least `stable_min_weeks` data points |
| 3 | `rising` | Last `min_consecutive` **non-flat** steps are all `"up"` |
| 4 | `falling` | Last `min_consecutive` **non-flat** steps are all `"down"` |
| 5 | `recovering` | Last non-flat step is `"up"` AND the step before it (non-flat) is `"down"` |
| 6 | `volatile` | None of the above |

Return the **first** matching label. Do not evaluate further once a match is found.

### Direction classification per step

Each week-over-week change is classified as:

```
up   → change > +stable_band_pct
down → change < -stable_band_pct
flat → within ±stable_band_pct (inclusive)
```

Where `change = (this_week - prev_week) / prev_week`.

### Flat step handling

`"flat"` steps are **neutral** — they do not break or reset a trend direction.
Rising/falling/recovering labels are evaluated using only the **non-flat** direction steps.

Examples:
```
["up", "flat", "up"]           → rising  (2 non-flat steps, both "up")
["up", "flat", "flat", "up"]   → rising  (2 non-flat steps, both "up")
["down", "flat", "up"]         → recovering (last non-flat = "up", prev non-flat = "down")
["up", "flat", "down"]         → volatile (last non-flat = "down", min_consecutive not met)
```

### `weeks_consecutive`

For `rising` and `falling`: count all consecutive matching steps at the end of the **full** `direction_sequence` (including flat — stop counting when direction changes).
For `stable`, `volatile`, `insufficient_history`: always `0`.
For `recovering`: always `1`.

### `baseline_delta_pct`

```
baseline = mean of all values returned by get_metric_history()
current  = most recent value (last item in history list)
baseline_delta_pct = (current - baseline) / baseline
```

Set to `None` when `trend_label == "insufficient_history"`.

---

## Config Loading

Load config **once at module level** — not on every function call.

```python
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[3] / "config" / "rules.yaml"

def _load_history_config() -> dict:
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f).get("history", {})

_HISTORY_CFG: dict = _load_history_config()
```

Access thresholds as:
```python
n_weeks_default   = _HISTORY_CFG["n_weeks"]
min_consecutive   = _HISTORY_CFG["min_consecutive"]
stable_band_pct   = _HISTORY_CFG["stable_band_pct"]
stable_min_weeks  = _HISTORY_CFG["stable_min_weeks"]
```

Raise a descriptive `KeyError` if any required key is absent — do not use `.get()` with silent fallbacks.

---

## Architecture Constraints

1. **Deterministic first** — no randomness, no time-dependent logic.
2. **Config-driven** — all thresholds from `config/rules.yaml`. Zero hardcoded numbers.
3. **No silent failure** — never `except: pass`. Propagate or log clearly.
4. **Separation of concerns** — no pipeline wiring, no LLM logic, no rendering in this module.
5. **LLM is optional** — this module has zero LLM dependency.
6. **Stable ordering** — `direction_sequence` always ordered oldest → newest.
7. **`compute_trends` never raises** — catch all per-metric exceptions, return `insufficient_history` with a `logger.warning`.

---

## Allowed Files

```
src/wbsb/history/trends.py     ← new
tests/test_trends.py           ← new (trend engine unit tests, separate from store tests)
```

---

## Files NOT to Touch

```
src/wbsb/history/store.py      ← complete, frozen
src/wbsb/pipeline.py           ← owned by I6-3, complete
src/wbsb/render/llm_adapter.py ← owned by I6-5
src/wbsb/domain/models.py      ← frozen for this iteration
config/rules.yaml              ← do not modify — thresholds already present from I6-1
tests/test_history.py          ← do not extend — store unit tests only
```

If any of these files seem like they need to change, **stop and raise it** — do not modify them.

---

## Acceptance Criteria

- [ ] `compute_trends()` returns `TrendResult` for every metric_id in input
- [ ] All six trend labels implemented and reachable
- [ ] `insufficient_history` returned when fewer than 2 historical data points
- [ ] `stable` requires at least `stable_min_weeks` observations
- [ ] Rising/falling evaluated using non-flat steps only (flat steps are neutral)
- [ ] `baseline_delta_pct` = `(current - mean) / mean`; `None` for insufficient_history
- [ ] `weeks_consecutive` = 0 for stable, volatile, insufficient_history
- [ ] All thresholds loaded from config — `grep -n "0\.02\|min_consecutive\|stable_band\|n_weeks = [0-9]" src/wbsb/history/trends.py` returns nothing
- [ ] Empty `metric_ids` list returns `{}`
- [ ] All 242 existing tests still pass
- [ ] Ruff clean

---

## Tests Required

**New test file:** `tests/test_trends.py`

Keep `tests/test_history.py` for store unit tests only. Trend tests go in a dedicated file.

| Test function | What it verifies |
|---------------|-----------------|
| `test_trend_insufficient_history_no_points` | Empty history → `insufficient_history` |
| `test_trend_insufficient_history_one_point` | 1 data point → `insufficient_history` |
| `test_trend_stable` | All changes within ±2% for 3+ weeks → `stable` |
| `test_trend_rising` | Last 2 non-flat steps are `"up"` → `rising` |
| `test_trend_falling` | Last 2 non-flat steps are `"down"` → `falling` |
| `test_trend_recovering` | Last non-flat = `"up"`, prior non-flat = `"down"` → `recovering` |
| `test_trend_volatile` | Alternating up/down → `volatile` |
| `test_trend_flat_steps_do_not_break_rising` | `["up", "flat", "up"]` → `rising` |
| `test_trend_respects_config_thresholds` | Changing `stable_band_pct` changes label output |
| `test_compute_trends_empty_metric_list` | `metric_ids=[]` → `{}`, no exception |
| `test_direction_sequence_oldest_first` | `direction_sequence` order matches history oldest → newest |
| `test_baseline_delta_pct_calculation` | `(current - mean) / mean` correct with known values |
| `test_weeks_consecutive_zero_for_stable` | `stable` → `weeks_consecutive == 0` |
| `test_insufficient_history_baseline_is_none` | `insufficient_history` → `baseline_delta_pct is None` |

```python
# Test pattern — use a mock HistoryReader to control history data exactly
from unittest.mock import MagicMock
from wbsb.history.trends import compute_trends

def _make_reader(history: list[tuple[str, float]]) -> MagicMock:
    reader = MagicMock()
    reader.get_metric_history.return_value = history
    return reader

def test_trend_rising():
    reader = _make_reader([
        ("2026-01-01", 100.0),
        ("2026-01-08", 105.0),  # +5% > stable_band_pct
        ("2026-01-15", 110.0),  # +5% > stable_band_pct
    ])
    result = compute_trends(reader, ["net_revenue"])
    assert result["net_revenue"]["trend_label"] == "rising"
    assert result["net_revenue"]["weeks_consecutive"] == 2
```

---

## Edge Cases to Handle

| Edge case | Expected behaviour |
|-----------|-------------------|
| `get_metric_history()` returns `[]` | `trend_label = "insufficient_history"` |
| `get_metric_history()` returns 1 point | `trend_label = "insufficient_history"` |
| Gap in weekly data (non-consecutive dates) | Compute direction from available points — do not raise |
| `metric_ids = []` | Return `{}` immediately |
| Previous value is 0 (division by zero in delta) | Skip that step or return `insufficient_history` for that metric — log warning |

---

## What NOT to Do

- Do not import or call anything from `src/wbsb/render/` — no LLM, no templates
- Do not modify `pipeline.py` — pipeline wiring is I6-5's responsibility
- Do not hardcode `0.02`, `2`, `3`, or `4` anywhere in `trends.py`
- Do not use `.get("key", default_value)` for required config keys — raise clearly on missing key
- Do not modify `domain/models.py` — `TrendResult` lives in `trends.py` as a `TypedDict`
- Do not add `except: pass` or any silent failure
- Do not refactor code outside allowed files

---

## Handoff: What the Next Task Needs From This One

After this task merges, the following is available for I6-5:

```python
from wbsb.history.trends import compute_trends, TrendResult

# Call signature (I6-5 will call this from pipeline.py):
trend_context = compute_trends(
    history_reader=HistoryReader(index_path, dataset_key),
    metric_ids=signal_metric_ids,   # metrics that fired signals this week
    n_weeks=None,                   # uses config default
)

# Each TrendResult in the returned dict:
# {
#     "metric_id": str,
#     "trend_label": "rising" | "falling" | "stable" | "recovering" | "volatile" | "insufficient_history",
#     "weeks_consecutive": int,          # 0 for stable/volatile/insufficient_history
#     "baseline_delta_pct": float | None,# None for insufficient_history
#     "direction_sequence": list[str],   # [] for insufficient_history
# }
```

`direction_sequence` is an internal diagnostic field. I6-5 must **not** include it in the LLM prompt.

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
git checkout -b feature/i6-4-trend-engine

# 4. Confirm correct branch
git branch --show-current
# Expected: feature/i6-4-trend-engine

# 5. Push immediately
git push -u origin feature/i6-4-trend-engine

# 6. Open draft PR — GitHub requires at least one commit; use an empty commit
git commit --allow-empty -m "chore: open draft PR for I6-4 trend engine"
git push origin feature/i6-4-trend-engine

gh pr create \
  --base feature/iteration-6 \
  --head feature/i6-4-trend-engine \
  --title "I6-4: Deterministic trend engine" \
  --body "Work in progress. See prompt-task-4.md for full task spec." \
  --draft
```

### Step 1 — Verify baseline

```bash
pytest
# Expected: 242 tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

Stop if either fails — do not proceed until baseline is clean.

### Step 2 — Read before writing

Read all four files listed in "Files to Read Before Starting" in order.

### Step 3 — Implement

Create `src/wbsb/history/trends.py` with `compute_trends()`, `TrendResult`, config loading, and direction classification as specified.

### Step 4 — Test and lint

```bash
pytest
# Must pass: 242 prior tests + 14 new tests. Zero failures.

ruff check .
# Must be clean.
```

### Step 5 — Verify scope

```bash
git diff --name-only feature/iteration-6
```

Expected output (exactly these two files):
```
src/wbsb/history/trends.py
tests/test_trends.py
```

### Step 6 — Commit

```bash
git add src/wbsb/history/trends.py tests/test_trends.py
git commit -m "$(cat <<'EOF'
feat: implement deterministic trend engine (I6-4)

Adds compute_trends() in src/wbsb/history/trends.py with six trend labels:
rising, falling, stable, recovering, volatile, insufficient_history.
Direction classification uses non-flat steps for rising/falling/recovering;
flat steps are neutral and do not break trend sequences. All thresholds
loaded from config/rules.yaml (history: section). baseline_delta_pct
computed as (current - mean) / mean against the prior n_weeks window.
Never raises — insufficient_history returned for sparse or missing data.
Enables I6-5 LLM adapter to attach trend context to the brief.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 7 — Mark PR ready

```bash
git push origin feature/i6-4-trend-engine
gh pr ready feature/i6-4-trend-engine
```

Do not merge — merging is a human decision.

---

## Definition of Done

This task is complete when ALL of the following are true:

- [ ] `src/wbsb/history/trends.py` implemented with `compute_trends()` and `TrendResult`
- [ ] All six trend labels implemented and unit-tested
- [ ] `insufficient_history` returned (not raised) when fewer than 2 data points
- [ ] `stable` requires at least `stable_min_weeks` observations
- [ ] Flat steps are neutral — `["up", "flat", "up"]` is classified as `rising`
- [ ] `baseline_delta_pct = (current - mean) / mean`; `None` for insufficient history
- [ ] `weeks_consecutive = 0` for stable, volatile, insufficient_history
- [ ] All thresholds from config — no literal `0.02`, `2`, `3`, `4` in `trends.py`
- [ ] All 242 prior tests still pass
- [ ] All 14 new tests in `tests/test_trends.py` pass
- [ ] Ruff clean
- [ ] Only `src/wbsb/history/trends.py` and `tests/test_trends.py` in the diff
- [ ] Feature branch pushed, PR marked ready for review
- [ ] No `except: pass`, no hardcoded values, no silent failures
