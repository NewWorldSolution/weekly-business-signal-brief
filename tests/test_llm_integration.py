"""Integration tests for LLM orchestration — Task I4-3.

Covers:
  - render_llm success path
  - render_llm fallback paths (timeout, API error, invalid JSON, unsupported provider)
  - pipeline execute() behavior with llm_mode=off / summary / full

All tests use injected mock clients — no live API calls are made.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from wbsb.domain.models import (
    Findings,
    LLMResult,
    MetricResult,
    Periods,
    RunMeta,
    Signal,
)
from wbsb.render.llm import render_llm

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


def _run_meta() -> RunMeta:
    return RunMeta(
        run_id="test-i4-3",
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
        input_file="test.csv",
        input_sha256="a" * 64,
        config_sha256="b" * 64,
    )


def _periods() -> Periods:
    return Periods(
        current_week_start=date(2026, 3, 2),
        current_week_end=date(2026, 3, 8),
        previous_week_start=date(2026, 2, 23),
        previous_week_end=date(2026, 3, 1),
    )


def _make_metric(
    id: str = "net_revenue",
    name: str = "Net Revenue",
    current: float = 8000.0,
    previous: float = 10000.0,
) -> MetricResult:
    return MetricResult(
        id=id,
        name=name,
        unit="currency",
        format_hint="currency",
        current=current,
        previous=previous,
        delta_abs=current - previous,
        delta_pct=(current - previous) / previous if previous else None,
    )


def _make_signal(
    rule_id: str = "A1",
    severity: str = "WARN",
    metric_id: str = "net_revenue",
) -> Signal:
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id=metric_id,
        label="Revenue Decline",
        category="revenue",
        priority=10,
        condition="delta_pct_lte",
        explanation="net_revenue changed -20.0% (threshold: ≤-15.0%)",
        evidence={
            "current": 8000.0,
            "previous": 10000.0,
            "delta_abs": -2000.0,
            "delta_pct": -0.20,
            "threshold": -0.15,
        },
    )


def _make_findings(
    signals: list[Signal] | None = None,
    metrics: list[MetricResult] | None = None,
) -> Findings:
    return Findings(
        run=_run_meta(),
        periods=_periods(),
        metrics=metrics if metrics is not None else [_make_metric()],
        signals=signals if signals is not None else [_make_signal()],
        audit=[],
    )


def _valid_summary_json(summary: str = "Revenue declined 20% week-over-week.") -> str:
    return json.dumps({"executive_summary": summary})


def _valid_full_json(
    summary: str = "Revenue and leads declined this week.",
    narratives: dict | None = None,
    situation: str | None = None,
    key_story: str | None = None,
    watch_signals: list[dict[str, str]] | None = None,
) -> str:
    payload: dict[str, object] = {
        "executive_summary": summary,
        "signal_narratives": {"narratives": narratives or {"A1": "Revenue dropped 20%."}},
    }
    if situation is not None:
        payload["situation"] = situation
    if key_story is not None:
        payload["key_story"] = key_story
    if watch_signals is not None:
        payload["watch_signals"] = watch_signals
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Mock LLM clients
# ---------------------------------------------------------------------------


class _SuccessClient:
    model = "mock-v1"

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        return self._response


class _TimeoutClient:
    model = "mock-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise TimeoutError("simulated timeout")


class _APIErrorClient:
    model = "mock-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise RuntimeError("simulated API error")


class _InvalidJSONClient:
    model = "mock-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        return "not valid json {"


# ---------------------------------------------------------------------------
# A. render_llm — success path
# ---------------------------------------------------------------------------


class TestRenderLLMSuccess:
    def test_returns_four_tuple(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        result = render_llm(findings, mode="summary", provider="anthropic", client=client)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_brief_md_is_string(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        brief_md, llm_result, sys_prompt, user_prompt = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert isinstance(brief_md, str)
        assert len(brief_md) > 0

    def test_llm_result_is_domain_model(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json("Revenue declined 20%."))
        _, llm_result, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert isinstance(llm_result, LLMResult)

    def test_llm_result_contains_executive_summary(self):
        findings = _make_findings()
        summary = "Revenue declined 20% week-over-week."
        client = _SuccessClient(_valid_summary_json(summary))
        _, llm_result, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert llm_result.executive_summary == summary

    def test_summary_mode_brief_does_not_render_legacy_executive_summary_section(self):
        findings = _make_findings()
        summary = "Revenue declined sharply this week."
        client = _SuccessClient(_valid_summary_json(summary))
        brief_md, _, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert "## Executive Summary" not in brief_md
        assert "## Situation" not in brief_md

    def test_rendered_prompts_non_empty(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        _, _, sys_prompt, user_prompt = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert isinstance(sys_prompt, str) and len(sys_prompt) > 0
        assert isinstance(user_prompt, str) and len(user_prompt) > 0

    def test_full_mode_success_returns_llm_result(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_full_json(narratives={"A1": "Revenue dropped."}))
        _, llm_result, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert llm_result.signal_narratives.narratives.get("A1") == "Revenue dropped."

    def test_prompt_version_propagated(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        _, llm_result, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert llm_result.prompt_version == "summary_v1"

    def test_model_propagated_from_client(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        _, llm_result, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert llm_result.model == "mock-v1"


# ---------------------------------------------------------------------------
# B. render_llm — fallback paths
# ---------------------------------------------------------------------------


class TestRenderLLMFallback:
    def _assert_fallback(self, result: tuple) -> str:
        """Assert fallback tuple shape and return brief_md."""
        brief_md, llm_result, sys_prompt, user_prompt = result
        assert isinstance(brief_md, str) and len(brief_md) > 0
        assert llm_result is None
        return brief_md

    def test_timeout_returns_deterministic_fallback(self):
        findings = _make_findings()
        client = _TimeoutClient()
        result = render_llm(findings, mode="summary", provider="anthropic", client=client)
        self._assert_fallback(result)

    def test_api_error_returns_deterministic_fallback(self):
        findings = _make_findings()
        client = _APIErrorClient()
        result = render_llm(findings, mode="summary", provider="anthropic", client=client)
        self._assert_fallback(result)

    def test_invalid_json_returns_deterministic_fallback(self):
        findings = _make_findings()
        client = _InvalidJSONClient()
        result = render_llm(findings, mode="summary", provider="anthropic", client=client)
        self._assert_fallback(result)

    def test_unsupported_provider_returns_deterministic_fallback(self):
        findings = _make_findings()
        client = _SuccessClient(_valid_summary_json())
        result = render_llm(findings, mode="summary", provider="openai", client=client)
        self._assert_fallback(result)

    def test_fallback_brief_contains_deterministic_content(self):
        """The fallback brief must be the real deterministic output (not empty)."""
        findings = _make_findings()
        client = _TimeoutClient()
        brief_md, _, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        # Deterministic brief always contains the week header
        assert "Weekly" in brief_md or "Revenue" in brief_md

    def test_fallback_prompts_still_returned_on_adapter_failure(self):
        """Even when the adapter fails, rendered prompts should be returned."""
        findings = _make_findings()
        client = _TimeoutClient()
        _, _, sys_prompt, user_prompt = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        # Prompts are rendered before the adapter call; they should be non-empty
        assert isinstance(sys_prompt, str) and len(sys_prompt) > 0
        assert isinstance(user_prompt, str) and len(user_prompt) > 0

    def test_render_llm_does_not_raise_on_any_client_failure(self):
        """render_llm must never raise for expected LLM failure modes."""
        findings = _make_findings()
        for client in (_TimeoutClient(), _APIErrorClient(), _InvalidJSONClient()):
            # Must not raise
            result = render_llm(findings, mode="summary", provider="anthropic", client=client)
            assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# C. pipeline execute() — llm_mode=off
# ---------------------------------------------------------------------------


class TestPipelineOffMode:
    def test_off_mode_produces_artifacts(self, tmp_path):
        from wbsb.pipeline import execute

        exit_code = execute(
            input_path=Path("examples/sample_weekly.csv"),
            output_dir=tmp_path,
            llm_mode="off",
            llm_provider="anthropic",
            config_path=Path("config/rules.yaml"),
            target_week=None,
        )
        assert exit_code == 0

        run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]
        assert (run_dir / "findings.json").exists()
        assert (run_dir / "brief.md").exists()
        assert (run_dir / "manifest.json").exists()

    def test_off_mode_manifest_shows_no_llm(self, tmp_path):
        from wbsb.pipeline import execute

        execute(
            input_path=Path("examples/sample_weekly.csv"),
            output_dir=tmp_path,
            llm_mode="off",
            llm_provider="anthropic",
            config_path=Path("config/rules.yaml"),
            target_week=None,
        )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["llm_status"] == "off"
        assert manifest["llm_mode"] == "off"

    def test_off_mode_no_llm_response_artifact(self, tmp_path):
        from wbsb.pipeline import execute

        execute(
            input_path=Path("examples/sample_weekly.csv"),
            output_dir=tmp_path,
            llm_mode="off",
            llm_provider="anthropic",
            config_path=Path("config/rules.yaml"),
            target_week=None,
        )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        assert not (run_dir / "llm_response.json").exists()

    def test_off_mode_does_not_call_llm_adapter(self, tmp_path):
        from wbsb.pipeline import execute

        with patch("wbsb.render.llm_adapter.generate") as mock_gen:
            execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="off",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
            mock_gen.assert_not_called()

    def test_off_mode_brief_has_no_llm_sections(self, tmp_path):
        from wbsb.pipeline import execute

        execute(
            input_path=Path("examples/sample_weekly.csv"),
            output_dir=tmp_path,
            llm_mode="off",
            llm_provider="anthropic",
            config_path=Path("config/rules.yaml"),
            target_week=None,
        )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        brief_md = (run_dir / "brief.md").read_text()
        assert "## Situation" not in brief_md
        assert "## Key Story This Week" not in brief_md
        assert "## Watch Next Week" not in brief_md


# ---------------------------------------------------------------------------
# D. pipeline execute() — llm_mode=summary
# ---------------------------------------------------------------------------


class TestPipelineSummaryMode:
    def _mock_generate(self, response: str):
        """Return a patch target that yields a valid AdapterLLMResult."""
        from wbsb.render.llm_adapter import AdapterLLMResult

        parsed = AdapterLLMResult.model_validate(json.loads(response))
        parsed = parsed.model_copy(update={"model": "mock-v1", "prompt_version": "summary_v1"})
        return parsed

    def test_summary_mode_produces_artifacts(self, tmp_path):
        from wbsb.pipeline import execute

        mock_result = self._mock_generate(_valid_summary_json("Revenue fell 20%."))
        with patch("wbsb.render.llm_adapter.generate", return_value=mock_result):
            exit_code = execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="summary",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        assert exit_code == 0

        run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        run_dir = run_dirs[0]
        assert (run_dir / "findings.json").exists()
        assert (run_dir / "brief.md").exists()
        assert (run_dir / "manifest.json").exists()

    def test_summary_mode_llm_response_artifact_written(self, tmp_path):
        from wbsb.pipeline import execute

        mock_result = self._mock_generate(_valid_summary_json("Revenue fell this week."))
        with patch("wbsb.render.llm_adapter.generate", return_value=mock_result):
            execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="summary",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        assert (run_dir / "llm_response.json").exists()

    def test_summary_mode_manifest_shows_success(self, tmp_path):
        from wbsb.pipeline import execute

        mock_result = self._mock_generate(_valid_summary_json("Revenue fell this week."))
        with patch("wbsb.render.llm_adapter.generate", return_value=mock_result):
            execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="summary",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["llm_mode"] == "summary"
        assert manifest["llm_provider"] == "anthropic"
        assert manifest["llm_status"] == "success"

    def test_summary_mode_fallback_on_adapter_none(self, tmp_path):
        """When adapter returns None the pipeline must still succeed (exit 0)."""
        from wbsb.pipeline import execute

        with patch("wbsb.render.llm_adapter.generate", return_value=None):
            exit_code = execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="summary",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        assert exit_code == 0

    def test_summary_mode_fallback_no_llm_response_artifact(self, tmp_path):
        """When LLM fails, llm_response.json should not be written."""
        from wbsb.pipeline import execute

        with patch("wbsb.render.llm_adapter.generate", return_value=None):
            execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="summary",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        assert not (run_dir / "llm_response.json").exists()


# ---------------------------------------------------------------------------
# E. pipeline execute() — llm_mode=full
# ---------------------------------------------------------------------------


class TestPipelineFullMode:
    def _mock_generate(self, response: str):
        from wbsb.render.llm_adapter import AdapterLLMResult

        parsed = AdapterLLMResult.model_validate(json.loads(response))
        return parsed.model_copy(update={"model": "mock-v1", "prompt_version": "full_v1"})

    def test_full_mode_produces_artifacts(self, tmp_path):
        from wbsb.pipeline import execute

        mock_result = self._mock_generate(_valid_full_json("Summary for full mode."))
        with patch("wbsb.render.llm_adapter.generate", return_value=mock_result):
            exit_code = execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="full",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        assert exit_code == 0

        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        assert (run_dir / "brief.md").exists()
        assert (run_dir / "findings.json").exists()

    def test_full_mode_manifest_shows_correct_mode(self, tmp_path):
        from wbsb.pipeline import execute

        mock_result = self._mock_generate(_valid_full_json("Full narrative summary."))
        with patch("wbsb.render.llm_adapter.generate", return_value=mock_result):
            execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="full",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["llm_mode"] == "full"
        assert manifest["llm_status"] == "success"

    def test_full_mode_fallback_does_not_crash(self, tmp_path):
        """LLM failure in full mode must not abort the run."""
        from wbsb.pipeline import execute

        with patch("wbsb.render.llm_adapter.generate", return_value=None):
            exit_code = execute(
                input_path=Path("examples/sample_weekly.csv"),
                output_dir=tmp_path,
                llm_mode="full",
                llm_provider="anthropic",
                config_path=Path("config/rules.yaml"),
                target_week=None,
            )
        assert exit_code == 0


# ---------------------------------------------------------------------------
# F. render_llm — full-mode signal narrative substitution in brief.md
# ---------------------------------------------------------------------------


class TestRenderLLMSignalNarrativeSubstitution:
    """Prove that LLM signal narratives actually appear in the rendered brief.md.

    This is the regression guard for the bug where render_llm called
    render_template(findings) without llm_result, causing signal narratives
    to be silently discarded.
    """

    def _full_response_with_narratives(
        self,
        rule_id: str,
        narrative: str,
        situation: str | None = None,
        key_story: str | None = None,
        watch_signals: list[dict[str, str]] | None = None,
    ) -> str:
        return json.dumps({
            "executive_summary": "Revenue fell sharply this week.",
            **({"situation": situation} if situation is not None else {}),
            **({"key_story": key_story} if key_story is not None else {}),
            **({"watch_signals": watch_signals} if watch_signals is not None else {}),
            "signal_narratives": {"narratives": {rule_id: narrative}},
        })

    def test_full_mode_signal_narrative_appears_in_brief(self):
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        llm_narrative = "Net revenue dropped $2,000 (20%), crossing the alert threshold."
        client = _SuccessClient(self._full_response_with_narratives("A1", llm_narrative))
        brief_md, llm_result, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert llm_result is not None
        assert llm_narrative in brief_md, (
            "LLM signal narrative must appear verbatim in the rendered brief"
        )

    def test_full_mode_signal_narrative_replaces_deterministic(self):
        """The LLM narrative must override, not append to, the deterministic one."""
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        deterministic_narrative = "Net Revenue declined 20.0% week-over-week."
        llm_narrative = "LLM-UNIQUE-NARRATIVE: Revenue fell below threshold."
        client = _SuccessClient(self._full_response_with_narratives("A1", llm_narrative))
        brief_md, _, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert llm_narrative in brief_md
        assert deterministic_narrative not in brief_md

    def test_full_mode_situation_section_renders_when_present(self):
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        client = _SuccessClient(
            self._full_response_with_narratives(
                "A1",
                "Revenue dropped significantly.",
                situation="Weekly performance softened across acquisition and revenue.",
            )
        )
        brief_md, _, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert "## Situation" in brief_md
        assert "Weekly performance softened across acquisition and revenue." in brief_md

    def test_full_mode_key_story_hidden_without_dominant_cluster(self):
        findings = _make_findings(
            signals=[
                Signal(
                    rule_id="A1",
                    severity="WARN",
                    metric_id="net_revenue",
                    label="Revenue Decline",
                    category="revenue",
                    priority=10,
                    condition="delta_pct_lte",
                    explanation="net_revenue changed -20.0% (threshold: ≤-15.0%)",
                    evidence={
                        "current": 8000.0,
                        "previous": 10000.0,
                        "delta_abs": -2000.0,
                        "delta_pct": -0.20,
                        "threshold": -0.15,
                    },
                ),
                Signal(
                    rule_id="B1",
                    severity="WARN",
                    metric_id="cac_paid",
                    label="CAC Rising",
                    category="acquisition",
                    priority=8,
                    condition="delta_pct_gte",
                    explanation="cac_paid changed 20.0% (threshold: ≥20.0%)",
                    evidence={
                        "current": 180.0,
                        "previous": 150.0,
                        "delta_abs": 30.0,
                        "delta_pct": 0.20,
                        "threshold": 0.20,
                    },
                ),
            ]
        )
        client = _SuccessClient(
            self._full_response_with_narratives(
                "A1",
                "Revenue dropped significantly.",
                key_story="This key story should not render.",
            )
        )
        brief_md, _, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert "## Key Story This Week" not in brief_md

    def test_full_mode_watch_next_week_renders_when_present(self):
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        client = _SuccessClient(
            self._full_response_with_narratives(
                "A1",
                "Revenue dropped significantly.",
                watch_signals=[
                    {
                        "metric_or_signal": "A1",
                        "observation": "Revenue remained below prior week.",
                    }
                ],
            )
        )
        brief_md, _, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert "## Watch Next Week" in brief_md
        assert "- A1 — Revenue remained below prior week." in brief_md

    def test_summary_mode_does_not_inject_signal_narratives(self):
        """In summary mode the LLM response has no signal_narratives; template must
        use deterministic narratives for all signals."""
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        client = _SuccessClient(_valid_summary_json("Executive summary only."))
        brief_md, llm_result, _, _ = render_llm(
            findings, mode="summary", provider="anthropic", client=client
        )
        assert llm_result is not None
        # summary response has no narratives — deterministic text must appear
        assert "Net Revenue declined 20.0% week-over-week." in brief_md

    def test_fallback_brief_uses_deterministic_narratives(self):
        """On adapter failure the brief must contain the deterministic narratives."""
        findings = _make_findings(signals=[_make_signal(rule_id="A1")])
        client = _TimeoutClient()
        brief_md, llm_result, _, _ = render_llm(
            findings, mode="full", provider="anthropic", client=client
        )
        assert llm_result is None
        assert "Net Revenue declined 20.0% week-over-week." in brief_md
