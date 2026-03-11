# WBSB Task Prompt — I6-1: Add History Configuration Section

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
- LLM is optional. Every mode produces a complete, valid report without it.

---

## Repository State

- **Active branch:** `main` (all prior tasks merged)
- **Feature branch for this task:** `feature/i6-1-history-config`
- **Tests passing:** 217
- **Ruff:** clean
- **Last completed task:** Iteration 5 complete — all I5 branches merged to main
- **Python:** 3.11
- **Package install:** `pip install -e .` (installed as `wbsb`)

---

## Task Metadata

| Field | Value |
|-------|-------|
| Task ID | I6-1 |
| Title | Add history configuration section |
| Iteration | Iteration 6 — Historical Memory & Trend Awareness |
| Owner | Codex |
| Feature branch | `feature/i6-1-history-config` |
| Depends on | none |
| Blocks | I6-2 (history store), I6-4 (trend engine) |
| PR scope | One PR. One task. Do not combine with adjacent tasks. |

---

## Task Goal

Iteration 6 introduces deterministic historical trend analysis. The trend engine must classify metrics as rising, falling, stable, recovering, or volatile based on prior weeks of data. All thresholds that control these classifications must come from configuration — not from hardcoded numbers in code.

This task adds a `history:` section to `config/rules.yaml` so that the trend engine implemented in later tasks can read the following values from configuration:
- number of prior weeks to inspect
- minimum consecutive weeks required to classify a trend as rising or falling
- the percentage band used to determine whether a metric is stable
- minimum weeks of stability required to assign the stable label

This follows the same config-driven architecture already used by the rules engine.

**No Python code is changed in this task.**

---

## Why Codex

This is a bounded configuration edit to a single file. No architectural reasoning or multi-module coordination is required. The change is mechanical, the YAML structure already exists, and the values to add are fully specified in this prompt.

---

## Files to Read Before Starting

Read these files in order before making any edits:

```
config/rules.yaml    ← understand the exact structure, quoting style, and indentation in use
```

Pay attention to:
- How `schema_version` and `config_version` are quoted (they use double quotes: `"1.0"`, `"mvp-v1"`)
- Indentation is 2 spaces throughout
- The order of top-level sections: `schema_version` → `config_version` → `defaults` → `rules`

---

## Existing Code This Task Builds On

The current top of `config/rules.yaml` looks like this (exact values — do not alter them):

```yaml
schema_version: "1.0"
config_version: "mvp-v1"

defaults:
  min_prev_net_revenue: 3000
  volume_threshold: 5

rules:
  - id: A1
  ...
```

The new `history:` section must be inserted **after the `defaults:` block and before the `rules:` block**.

---

## What to Build

Modify one file only: `config/rules.yaml`

Add the following block exactly as shown, in the position described above (after `defaults:`, before `rules:`):

```yaml
history:
  n_weeks: 4                  # default lookback window for trend queries
  min_consecutive: 2          # minimum consecutive weeks to classify rising or falling
  stable_band_pct: 0.02       # week-over-week change within ±2% is considered stable
  stable_min_weeks: 3         # minimum weeks of stability to assign the stable label
```

The resulting file structure (top-level order) must be:
```
schema_version
config_version
defaults
history        ← new section, inserted here
rules
```

### Field meanings

| Key | Type | Meaning |
|-----|------|---------|
| `n_weeks` | int | Number of prior weeks used for trend evaluation |
| `min_consecutive` | int | Minimum consecutive weeks in one direction to classify as rising or falling |
| `stable_band_pct` | float | Week-over-week change within this band (±) is treated as flat/stable |
| `stable_min_weeks` | int | Minimum number of weeks within the stable band to assign the `stable` label |

### Behaviour rules

- Do not modify any existing key or value anywhere in the file
- Do not change `schema_version` or `config_version`
- Do not modify any rule thresholds under `rules:`
- Use 2-space indentation, consistent with the rest of the file
- Inline comments (after `#`) are part of the spec — include them exactly as shown
- The file must remain valid YAML after the change

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
config/rules.yaml    ← modify: add history: section after defaults:, before rules:
```

---

## Files NOT to Touch

```
src/wbsb/pipeline.py
src/wbsb/domain/models.py
src/wbsb/render/llm_adapter.py
src/wbsb/history/          ← does not exist yet; do not create it
tests/
```

If any of these appear to require changes to complete this task, stop and ask rather than modifying them.

---

## Acceptance Criteria

- [ ] The `history:` section exists in `config/rules.yaml` with all four keys: `n_weeks`, `min_consecutive`, `stable_band_pct`, `stable_min_weeks`
- [ ] The section is positioned after `defaults:` and before `rules:`
- [ ] Values match exactly: `n_weeks: 4`, `min_consecutive: 2`, `stable_band_pct: 0.02`, `stable_min_weeks: 3`
- [ ] All existing keys and values in the file are unchanged
- [ ] The file is valid YAML (no parse errors)
- [ ] All 217+ existing tests pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only `config/rules.yaml` appears in `git diff --name-only main`

---

## Tests Required

No new tests are required for this task. The change is configuration only and does not affect any runtime code path yet.

The following must still pass without modification:

```bash
pytest    # all 217 existing tests, exit code 0
```

If any existing test fails after this change, the YAML is invalid or an existing value was accidentally modified. Fix the YAML — do not modify the tests.

---

## Edge Cases to Handle

| Edge case | Expected behaviour |
|-----------|-------------------|
| `history:` key already exists in the file | Do not duplicate it. Read the file first — if it already exists, stop and report rather than overwriting |
| Indentation inconsistency | Match the 2-space style already in the file exactly. Do not use tabs |
| Trailing whitespace or blank lines | Do not introduce them. Keep the file consistent with its current style |

---

## What NOT to Do

- Do not add any keys not listed in the spec (`n_weeks`, `min_consecutive`, `stable_band_pct`, `stable_min_weeks` are the complete set)
- Do not change `schema_version: "1.0"` or `config_version: "mvp-v1"` — including their quoting
- Do not reformat, reorder, or clean up any existing content in the file
- Do not add the section at the end of the file — placement is specified (after `defaults:`, before `rules:`)
- Do not create any Python files or test files

---

## Handoff: What the Next Tasks Need From This One

After this PR merges, the following keys will be available in `config/rules.yaml` under the `history:` section. Both I6-2 (history store) and I6-4 (trend engine) depend on these exact names and types.

```
history.n_weeks           int    — default lookback window
history.min_consecutive   int    — weeks to classify rising/falling
history.stable_band_pct   float  — ±band for stable classification
history.stable_min_weeks  int    — minimum weeks to label as stable
```

**Key names are final. The trend engine will reference these exact names. Do not rename them.**

---

## Execution Workflow

### Step 0 — Branch setup

```bash
git checkout main
git pull origin main
git status
# Expected: "nothing to commit, working tree clean"
# If not clean: stop and resolve before continuing

git checkout -b feature/i6-1-history-config
git branch --show-current
# Expected: feature/i6-1-history-config
```

### Step 1 — Verify baseline

Before making any change, confirm the existing suite is green:

```bash
pytest
# Expected: 217 tests passing, exit code 0

ruff check .
# Expected: no issues, exit code 0
```

If either fails, stop. Do not proceed until the baseline is clean.

### Step 2 — Read the file

Read `config/rules.yaml` in full before editing. Note the exact structure, quoting style, and indentation.

### Step 3 — Implement

Add the `history:` section exactly as specified, after `defaults:` and before `rules:`.

### Step 4 — Validate

```bash
python -c "import yaml; yaml.safe_load(open('config/rules.yaml'))"
# Expected: no output, no exception — the file is valid YAML
```

### Step 5 — Test and lint

```bash
pytest
ruff check .
```

Both must pass before continuing.

### Step 6 — Verify scope

```bash
git diff --name-only main
```

Expected output: `config/rules.yaml` only. If any other file appears, review and revert it.

### Step 7 — Commit

```
feat: add history configuration section for trend engine (I6-1)

Adds a history: block to config/rules.yaml after the defaults: section
and before rules:. Provides four config-driven thresholds (n_weeks,
min_consecutive, stable_band_pct, stable_min_weeks) that the Iteration 6
trend engine will read instead of using hardcoded values. No Python code
changed. All 217 existing tests pass.

Co-Authored-By: Codex <noreply@openai.com>
```

### Step 8 — Push and open PR

```bash
git push -u origin feature/i6-1-history-config
```

Open a pull request from `feature/i6-1-history-config` into `main`. Do not merge — merging is a human decision.

---

## Definition of Done

This task is complete when ALL of the following are true:

- [ ] `history:` section present in `config/rules.yaml` with all four keys and correct values
- [ ] Section positioned after `defaults:` and before `rules:`
- [ ] No existing keys or values modified anywhere in the file
- [ ] File is valid YAML — `python -c "import yaml; yaml.safe_load(open('config/rules.yaml'))"` exits cleanly
- [ ] All 217 existing tests pass (`pytest` exit code 0)
- [ ] Ruff clean (`ruff check .` exit code 0)
- [ ] Only `config/rules.yaml` in `git diff --name-only main`
- [ ] Feature branch pushed, PR open, not merged
