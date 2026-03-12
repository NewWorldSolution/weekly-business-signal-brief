# Golden Dataset — Governance Rules

This directory contains the golden evaluation cases for the WBSB evaluation framework.
Each subdirectory is one named case. The `wbsb eval` CLI runs all cases and reports
pass/fail against their declared criteria.

---

## Case structure

```
<case_name>/
├── findings.json       ← required: Findings document for this case
├── llm_response.json   ← optional: absent for fallback cases
└── criteria.json       ← required: pass/fail thresholds
```

---

## Governance rules

- **Golden cases are created from real production runs after I9 deployment.**
  For MVP (pre-I9), initial cases use synthetic data. Replace with real-run data
  after I9 deployment.

- **A new case requires:** `findings.json` + `llm_response.json` from a real run
  + a manually reviewed `criteria.json`.

- **Criteria values must be set conservatively.** Do not set `min_grounding: 1.0`
  unless you have verified every cited number against the findings evidence. Start
  with `min_grounding: 0.70` and tighten only after observing production runs.

- **Case updates require a PR review.** Do not edit `criteria.json` in place
  without a pull request and at least one reviewer. Loosening thresholds must
  include a written justification in the PR description.

- **`fallback_no_llm` must always be present and must always pass.** This case
  has no `llm_response.json` and verifies the LLM fallback path is handled cleanly.
  Never delete this case.

- **Do not add golden cases to `tests/`.** Golden cases live here, in
  `src/wbsb/eval/golden/`. They are part of the package and run via `wbsb eval`.

---

## Case index

| Case | Description |
|------|-------------|
| `clean_week` | All metrics healthy, strong LLM output, high grounding |
| `single_dominant_cluster` | One category dominates with 3 WARN signals |
| `independent_signals` | WARN signals spread across two categories |
| `low_volume_guardrail` | Low-volume week; guardrail fired, minimal signals |
| `zero_signals` | Completely clean week, no signals, no numbers cited |
| `fallback_no_llm` | LLM fallback path — no LLM output, eval skipped cleanly |
