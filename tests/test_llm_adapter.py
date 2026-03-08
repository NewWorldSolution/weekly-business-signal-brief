"""Tests for the LLM adapter module (Task I4-1).

All tests use injected mock clients — no live API calls are made.
Tests do not import from wbsb.domain.models indirectly through the adapter
(the adapter itself avoids that import; tests import from domain only for
building test Findings objects to derive a render context).
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from wbsb.domain.models import (
    Findings,
    MetricResult,
    Periods,
    RunMeta,
    Signal,
)
from wbsb.render.context import prepare_render_context
from wbsb.render.llm_adapter import (
    _EXECUTIVE_SUMMARY_MAX_CHARS,
    AdapterLLMResult,
    LLMClientProtocol,
    build_prompt_inputs,
    generate,
    render_system_prompt,
    render_user_prompt,
    validate_response,
)

# ---------------------------------------------------------------------------
# Shared test fixtures and helpers
# ---------------------------------------------------------------------------


def _run_meta() -> RunMeta:
    return RunMeta(
        run_id="test-run-i4-1",
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
    format_hint: str = "currency",
    current: float = 8000.0,
    previous: float = 10000.0,
) -> MetricResult:
    return MetricResult(
        id=id,
        name=name,
        unit="currency",
        format_hint=format_hint,
        current=current,
        previous=previous,
        delta_abs=current - previous,
        delta_pct=(current - previous) / previous if previous else None,
    )


def _make_signal(
    rule_id: str = "A1",
    metric_id: str = "net_revenue",
    condition: str = "delta_pct_lte",
    severity: str = "WARN",
    category: str = "revenue",
    label: str = "Revenue Decline",
    priority: int = 10,
    evidence: dict | None = None,
) -> Signal:
    if evidence is None:
        evidence = {
            "current": 8000.0,
            "previous": 10000.0,
            "delta_abs": -2000.0,
            "delta_pct": -0.20,
            "threshold": -0.15,
        }
    return Signal(
        rule_id=rule_id,
        severity=severity,
        metric_id=metric_id,
        label=label,
        category=category,
        priority=priority,
        condition=condition,
        explanation=f"{metric_id} changed -20.0% (threshold: ≤-15.0%)",
        evidence=evidence,
    )


def _make_findings(
    signals: list[Signal] | None = None,
    metrics: list[MetricResult] | None = None,
) -> Findings:
    return Findings(
        run=_run_meta(),
        periods=_periods(),
        metrics=metrics if metrics is not None else [_make_metric()],
        signals=signals if signals is not None else [],
        audit=[],
    )


def _make_ctx(
    signals: list[Signal] | None = None,
    metrics: list[MetricResult] | None = None,
) -> dict[str, Any]:
    findings = _make_findings(signals=signals, metrics=metrics)
    return prepare_render_context(findings)


def _make_summary_response(executive_summary: str = "This week saw a revenue decline.") -> str:
    return json.dumps({"executive_summary": executive_summary})


def _make_full_response(
    executive_summary: str = "Revenue and leads declined this week.",
    narratives: dict | None = None,
) -> str:
    return json.dumps({
        "executive_summary": executive_summary,
        "signal_narratives": {"narratives": narratives or {"A1": "Revenue dropped 20%."}},
    })


# ---------------------------------------------------------------------------
# Mock clients
# ---------------------------------------------------------------------------


class MockSuccessClient:
    """Returns a hardcoded valid LLM response JSON."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.model = "mock-model-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        return self._response


class MockTimeoutClient:
    """Raises TimeoutError on complete()."""

    model = "mock-model-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise TimeoutError("simulated timeout")


class MockAPIErrorClient:
    """Raises a generic Exception on complete()."""

    model = "mock-model-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        raise RuntimeError("simulated API error")


class MockInvalidJSONClient:
    """Returns malformed JSON."""

    model = "mock-model-v1"

    def complete(self, system_prompt: str, user_prompt: str, timeout: int) -> str:
        return "not valid json {"


# ---------------------------------------------------------------------------
# A. Prompt input building
# ---------------------------------------------------------------------------


class TestPromptInputs:
    def test_build_prompt_inputs_summary_contains_required_fields(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)

        required = {
            "generated_at",
            "current_week_start",
            "current_week_end",
            "previous_week_start",
            "previous_week_end",
            "warn_count",
            "info_count",
            "severity_by_category",
            "top_signals",
            "all_signals",
            "rule_ids",
        }
        assert required.issubset(inputs.keys())

    def test_build_prompt_inputs_warn_count_correct(self):
        ctx = _make_ctx(signals=[
            _make_signal(rule_id="A1", severity="WARN"),
            _make_signal(rule_id="B1", severity="INFO", label="Info Signal"),
        ])
        inputs = build_prompt_inputs(ctx)
        assert inputs["warn_count"] == 1
        assert inputs["info_count"] == 1

    def test_build_prompt_inputs_top_signals_max_3(self):
        signals = [
            _make_signal(rule_id=f"W{i}", severity="WARN", label=f"Signal {i}")
            for i in range(5)
        ]
        ctx = _make_ctx(signals=signals)
        inputs = build_prompt_inputs(ctx)
        assert len(inputs["top_signals"]) == 3

    def test_build_prompt_inputs_top_signals_warn_only(self):
        signals = [
            _make_signal(rule_id="A1", severity="WARN"),
            _make_signal(rule_id="B1", severity="INFO", label="Info only"),
        ]
        ctx = _make_ctx(signals=signals)
        inputs = build_prompt_inputs(ctx)
        assert all(s["severity"] == "WARN" for s in inputs["top_signals"])

    def test_build_prompt_inputs_full_contains_all_signal_narrative_inputs(self):
        signals = [
            _make_signal(rule_id="A1", severity="WARN"),
            _make_signal(rule_id="B1", severity="INFO", label="Info"),
            _make_signal(rule_id="C1", severity="WARN", label="Another warn"),
        ]
        ctx = _make_ctx(signals=signals)
        inputs = build_prompt_inputs(ctx)
        # all_signals includes all signals regardless of severity
        assert len(inputs["all_signals"]) == 3
        rule_ids_in_all = {s["rule_id"] for s in inputs["all_signals"]}
        assert {"A1", "B1", "C1"} == rule_ids_in_all

    def test_build_prompt_inputs_rule_ids_matches_all_signals(self):
        signals = [
            _make_signal(rule_id="A1", severity="WARN"),
            _make_signal(rule_id="B1", severity="INFO", label="Info"),
        ]
        ctx = _make_ctx(signals=signals)
        inputs = build_prompt_inputs(ctx)
        assert set(inputs["rule_ids"]) == {"A1", "B1"}

    def test_prompt_inputs_are_serializable(self):
        """All values in prompt_inputs must be JSON-serializable — no domain objects."""
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        # This must not raise
        serialized = json.dumps(inputs)
        assert isinstance(serialized, str)

    def test_build_prompt_inputs_does_not_mutate_ctx(self):
        ctx = _make_ctx(signals=[_make_signal()])
        original_warn = ctx["warn_count"]
        original_sc_len = len(ctx["signal_contexts"])
        build_prompt_inputs(ctx)
        assert ctx["warn_count"] == original_warn
        assert len(ctx["signal_contexts"]) == original_sc_len

    def test_all_signals_include_deterministic_narrative(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        for sig in inputs["all_signals"]:
            assert "deterministic_narrative" in sig
            assert isinstance(sig["deterministic_narrative"], str)

    def test_all_signals_include_required_fields(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        required = {
            "rule_id", "label", "category", "category_display", "severity",
            "metric_name", "metric_id", "direction", "current_value",
            "previous_value", "delta_pct", "delta_abs",
        }
        for sig in inputs["all_signals"]:
            assert required.issubset(sig.keys()), f"Missing keys: {required - sig.keys()}"


# ---------------------------------------------------------------------------
# B. System prompt rendering
# ---------------------------------------------------------------------------


class TestSystemPromptRendering:
    def test_system_summary_prompt_renders(self):
        prompt = render_system_prompt("summary")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_system_full_prompt_renders(self):
        prompt = render_system_prompt("full")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_system_summary_prompt_contains_constraint_language(self):
        prompt = render_system_prompt("summary")
        # Must forbid inventing data
        assert "not" in prompt.lower() or "do not" in prompt.lower()
        has_constraint = (
            "invent" in prompt.lower()
            or "fabricate" in prompt.lower()
            or "not permitted" in prompt.lower()
        )
        assert has_constraint

    def test_system_full_prompt_contains_constraint_language(self):
        prompt = render_system_prompt("full")
        has_constraint = (
            "invent" in prompt.lower()
            or "fabricate" in prompt.lower()
            or "not permitted" in prompt.lower()
        )
        assert has_constraint

    def test_system_prompts_require_json_response(self):
        for mode in ("summary", "full"):
            prompt = render_system_prompt(mode)
            assert "json" in prompt.lower(), f"{mode} system prompt lacks JSON instruction"

    def test_system_prompt_mentions_role(self):
        for mode in ("summary", "full"):
            prompt = render_system_prompt(mode)
            assert "business analyst" in prompt.lower(), (
                f"{mode} system prompt should mention role"
            )

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown llm mode"):
            render_system_prompt("invalid_mode")


# ---------------------------------------------------------------------------
# C. User prompt rendering
# ---------------------------------------------------------------------------


class TestUserPromptRendering:
    def test_user_summary_prompt_renders_from_inputs(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        prompt = render_user_prompt(inputs, "summary")
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_user_full_prompt_renders_from_inputs(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        prompt = render_user_prompt(inputs, "full")
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_user_summary_prompt_contains_period_dates(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        prompt = render_user_prompt(inputs, "summary")
        assert "2026-03-02" in prompt
        assert "2026-03-08" in prompt

    def test_user_full_prompt_includes_all_signals(self):
        signals = [
            _make_signal(rule_id="A1", severity="WARN"),
            _make_signal(rule_id="B1", severity="INFO", label="Info signal"),
        ]
        ctx = _make_ctx(signals=signals)
        inputs = build_prompt_inputs(ctx)
        prompt = render_user_prompt(inputs, "full")
        assert "A1" in prompt
        assert "B1" in prompt

    def test_user_prompt_contains_rule_ids(self):
        ctx = _make_ctx(signals=[_make_signal(rule_id="REV_DROP")])
        inputs = build_prompt_inputs(ctx)
        for mode in ("summary", "full"):
            prompt = render_user_prompt(inputs, mode)
            assert "REV_DROP" in prompt

    def test_user_prompt_no_raw_domain_objects(self):
        """User prompts must not contain Python repr strings of domain objects."""
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        for mode in ("summary", "full"):
            prompt = render_user_prompt(inputs, mode)
            assert "Signal(" not in prompt
            assert "MetricResult(" not in prompt
            assert "Findings(" not in prompt

    def test_user_prompt_unknown_mode_raises(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        with pytest.raises(ValueError, match="Unknown llm mode"):
            render_user_prompt(inputs, "unknown")

    def test_user_full_prompt_includes_deterministic_narrative(self):
        ctx = _make_ctx(signals=[_make_signal()])
        inputs = build_prompt_inputs(ctx)
        prompt = render_user_prompt(inputs, "full")
        # Should include the deterministic narrative grounding
        assert "deterministic_narrative" in prompt or "week-over-week" in prompt.lower()


# ---------------------------------------------------------------------------
# D. Response validation
# ---------------------------------------------------------------------------


class TestResponseValidation:
    def test_valid_summary_response_parses(self):
        raw = _make_summary_response("Revenue declined 20% this week against the prior period.")
        result = validate_response(raw, "summary", expected_rule_ids=["A1"])
        assert result is not None
        assert isinstance(result, AdapterLLMResult)
        assert "Revenue declined" in result.executive_summary

    def test_valid_full_response_parses(self):
        raw = _make_full_response(
            "Revenue and leads both declined this week.",
            narratives={"A1": "Revenue dropped 20% driven by fewer new paid clients."},
        )
        result = validate_response(raw, "full", expected_rule_ids=["A1"])
        assert result is not None
        assert result.signal_narratives.narratives.get("A1") is not None

    def test_invalid_json_returns_none(self):
        result = validate_response("not json {{{", "summary", expected_rule_ids=[])
        assert result is None

    def test_schema_violation_returns_none(self):
        # Missing executive_summary field
        raw = json.dumps({"signal_narratives": {}})
        result = validate_response(raw, "summary", expected_rule_ids=[])
        assert result is None

    def test_executive_summary_too_long_returns_none(self):
        long_summary = "A" * (_EXECUTIVE_SUMMARY_MAX_CHARS + 1)
        raw = json.dumps({"executive_summary": long_summary})
        result = validate_response(raw, "summary", expected_rule_ids=[])
        assert result is None

    def test_empty_executive_summary_returns_none(self):
        raw = json.dumps({"executive_summary": "   "})
        result = validate_response(raw, "summary", expected_rule_ids=[])
        assert result is None

    def test_unknown_rule_id_stripped_in_full_mode(self):
        raw = _make_full_response(
            "Good week overall.",
            narratives={"A1": "Known signal.", "UNKNOWN_XYZ": "Invented signal."},
        )
        result = validate_response(raw, "full", expected_rule_ids=["A1"])
        assert result is not None
        assert "UNKNOWN_XYZ" not in result.signal_narratives.narratives
        assert "A1" in result.signal_narratives.narratives

    def test_valid_rule_id_preserved_in_full_mode(self):
        raw = _make_full_response(
            "Summary here.",
            narratives={"A1": "Signal one.", "B2": "Signal two."},
        )
        result = validate_response(raw, "full", expected_rule_ids=["A1", "B2"])
        assert result is not None
        assert "A1" in result.signal_narratives.narratives
        assert "B2" in result.signal_narratives.narratives

    def test_summary_mode_does_not_require_signal_narratives(self):
        raw = _make_summary_response("A clean week with no major anomalies detected.")
        result = validate_response(raw, "summary", expected_rule_ids=["A1"])
        assert result is not None
        # signal_narratives defaults to empty dict
        assert result.signal_narratives.narratives == {}

    def test_flat_signal_narratives_dict_is_normalised(self):
        """LLM may return signal_narratives as a flat dict; adapter normalises it."""
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "signal_narratives": {"A1": "Signal narrative."},
        })
        result = validate_response(raw, "full", expected_rule_ids=["A1"])
        assert result is not None
        assert result.signal_narratives.narratives["A1"] == "Signal narrative."


# ---------------------------------------------------------------------------
# D2. I5 schema extensions
# ---------------------------------------------------------------------------


class TestI5SchemaExtensions:
    """Tests for Iteration 5 optional fields in AdapterLLMResult / validate_response."""

    def test_old_i4_response_still_passes(self):
        """Backward compatibility: a valid I4 response (executive_summary only) still validates."""
        raw = json.dumps({
            "executive_summary": "Revenue declined 20% this week.",
            "signal_narratives": {"A1": "Revenue dropped."},
        })
        result = validate_response(raw, "full", expected_rule_ids=["A1"])
        assert result is not None
        assert result.executive_summary == "Revenue declined 20% this week."
        assert result.situation is None
        assert result.key_story is None
        assert result.group_narratives is None
        assert result.watch_signals is None

    def test_i5_situation_field_accepted(self):
        """I5 responses with situation field are accepted."""
        raw = json.dumps({
            "executive_summary": "Revenue declined 20% this week.",
            "situation": "Revenue contraction with rising CAC.",
            "signal_narratives": {"A1": "Revenue dropped."},
        })
        result = validate_response(raw, "full", expected_rule_ids=["A1"])
        assert result is not None
        assert result.situation == "Revenue contraction with rising CAC."

    def test_i5_key_story_field_accepted(self):
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "key_story": "CAC spike is the root driver this week.",
            "signal_narratives": {},
        })
        result = validate_response(raw, "summary", expected_rule_ids=[])
        assert result is not None
        assert result.key_story == "CAC spike is the root driver this week."

    def test_i5_group_narratives_accepted(self):
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "group_narratives": {
                "Revenue": "Revenue category saw a 25% decline.",
                "Acquisition": "CAC rose 60%.",
            },
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is not None
        assert result.group_narratives is not None
        assert result.group_narratives["Revenue"] == "Revenue category saw a 25% decline."

    def test_i5_watch_signals_valid_structure_accepted(self):
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "watch_signals": [
                {
                    "metric_or_signal": "CAC (Paid)",
                    "observation": "CAC rising but within threshold.",
                },
                {"metric_or_signal": "Total Bookings", "observation": "Volume recovering."},
            ],
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is not None
        assert result.watch_signals is not None
        assert len(result.watch_signals) == 2
        assert result.watch_signals[0]["metric_or_signal"] == "CAC (Paid)"

    def test_i5_watch_signals_missing_required_key_rejected(self):
        """watch_signals entry missing 'observation' key causes the whole field to be rejected."""
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "watch_signals": [
                {"metric_or_signal": "CAC (Paid)"},  # missing 'observation'
            ],
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is not None  # overall response still valid
        assert result.watch_signals is None  # but watch_signals field is cleared

    def test_i5_watch_signals_missing_metric_key_rejected(self):
        """watch_signals entry missing 'metric_or_signal' key causes field to be rejected."""
        raw = json.dumps({
            "executive_summary": "Revenue declined.",
            "watch_signals": [
                {"observation": "Something to watch."},  # missing 'metric_or_signal'
            ],
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is not None
        assert result.watch_signals is None

    def test_situation_replaces_executive_summary_when_summary_empty(self):
        """I5 response with empty executive_summary is valid when situation is present."""
        raw = json.dumps({
            "executive_summary": "",
            "situation": "Revenue contraction across all categories.",
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is not None
        assert result.situation == "Revenue contraction across all categories."

    def test_empty_summary_and_no_situation_still_returns_none(self):
        """Empty executive_summary with no situation field must still fail."""
        raw = json.dumps({
            "executive_summary": "   ",
            "signal_narratives": {},
        })
        result = validate_response(raw, "full", expected_rule_ids=[])
        assert result is None


# ---------------------------------------------------------------------------
# E. generate() behavior
# ---------------------------------------------------------------------------


class TestGenerateFunction:
    def _ctx_with_signal(self) -> dict[str, Any]:
        return _make_ctx(signals=[_make_signal(rule_id="A1")])

    def test_success_returns_adapter_llm_result(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_summary_response("This week revenue declined by 20%."))
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is not None
        assert isinstance(result, AdapterLLMResult)
        assert "revenue" in result.executive_summary.lower()

    def test_success_sets_prompt_version(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_summary_response("Revenue declined this week."))
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is not None
        assert result.prompt_version == "summary_v1"

    def test_success_full_mode_sets_correct_prompt_version(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_full_response(
            "Revenue declined this week.",
            narratives={"A1": "Revenue dropped."},
        ))
        result = generate(ctx, mode="full", provider="anthropic", client=client)
        assert result is not None
        assert result.prompt_version == "full_v1"

    def test_success_sets_model_from_client(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_summary_response("Revenue declined this week."))
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is not None
        assert result.model == "mock-model-v1"

    def test_timeout_returns_none(self):
        ctx = self._ctx_with_signal()
        client = MockTimeoutClient()
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is None

    def test_api_error_returns_none(self):
        ctx = self._ctx_with_signal()
        client = MockAPIErrorClient()
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is None

    def test_invalid_json_returns_none(self):
        ctx = self._ctx_with_signal()
        client = MockInvalidJSONClient()
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is None

    def test_unsupported_provider_returns_none(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_summary_response("Summary."))
        result = generate(ctx, mode="summary", provider="openai", client=client)
        assert result is None

    def test_fallback_is_not_set_on_success(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_summary_response("Revenue declined this week."))
        result = generate(ctx, mode="summary", provider="anthropic", client=client)
        assert result is not None
        assert result.fallback is False

    def test_generate_full_mode_success(self):
        ctx = self._ctx_with_signal()
        client = MockSuccessClient(_make_full_response(
            "Revenue declined this week.",
            narratives={"A1": "Revenue dropped by 20%."},
        ))
        result = generate(ctx, mode="full", provider="anthropic", client=client)
        assert result is not None
        assert result.signal_narratives.narratives.get("A1") is not None

    def test_generate_does_not_raise_on_any_failure(self):
        """generate() must swallow all LLM-related errors."""
        ctx = self._ctx_with_signal()
        for client in (MockTimeoutClient(), MockAPIErrorClient(), MockInvalidJSONClient()):
            # Must not raise
            result = generate(ctx, mode="summary", provider="anthropic", client=client)
            assert result is None


# ---------------------------------------------------------------------------
# F. Protocol conformance
# ---------------------------------------------------------------------------


class TestLLMClientProtocol:
    def test_mock_success_client_is_protocol(self):
        assert isinstance(MockSuccessClient("{}"), LLMClientProtocol)

    def test_mock_timeout_client_is_protocol(self):
        assert isinstance(MockTimeoutClient(), LLMClientProtocol)

    def test_mock_api_error_client_is_protocol(self):
        assert isinstance(MockAPIErrorClient(), LLMClientProtocol)
