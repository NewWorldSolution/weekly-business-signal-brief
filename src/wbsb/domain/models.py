"""Pydantic domain models for WBSB."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """An audit/validation event."""

    event_type: str
    message: str
    column: str | None = None
    extra: dict[str, Any] | None = None


class RunConfig(BaseModel):
    """Runtime configuration derived from rules.yaml defaults."""

    min_prev_net_revenue: float = 3000.0
    volume_threshold: int = 5


class MetricResult(BaseModel):
    """Result of a single metric computation."""

    id: str
    name: str
    unit: str
    format_hint: str = "decimal"
    category: str = ""
    category_order: int = 0
    display_order: int = 0
    current: float | None = None
    previous: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    reliability: str = "ok"  # ok | low


class Signal(BaseModel):
    """A fired rule/signal."""

    rule_id: str
    severity: str  # WARN | INFO
    metric_id: str
    label: str = ""
    category: str = ""
    priority: int = 0
    condition: str = ""          # "delta_pct_lte" | "delta_pct_gte" |
                                 # "absolute_lt" | "absolute_gt" |
                                 # "hybrid_delta_pct_lte"
    explanation: str
    # evidence may include: threshold, threshold_pct, threshold_abs
    evidence: dict[str, Any]
    guardrails: list[str] = Field(default_factory=list)
    reliability: str = "ok"  # ok | low


class Periods(BaseModel):
    """Time periods for the analysis."""

    current_week_start: date
    current_week_end: date
    previous_week_start: date
    previous_week_end: date


class RunMeta(BaseModel):
    """Run metadata for audit trail."""

    run_id: str
    generated_at: datetime
    input_file: str
    input_sha256: str
    config_sha256: str
    git_commit: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)


class Findings(BaseModel):
    """Full findings document."""

    schema_version: str = "1.2"
    run: RunMeta
    periods: Periods
    metrics: list[MetricResult]
    signals: list[Signal]
    audit: list[AuditEvent]


class LLMSignalNarratives(BaseModel):
    """Optional LLM-authored narratives keyed by signal identifier."""

    narratives: dict[str, str] = Field(default_factory=dict)


class LLMResult(BaseModel):
    """Structured optional LLM output for report overlay and observability."""

    executive_summary: str = ""
    signal_narratives: LLMSignalNarratives = Field(default_factory=LLMSignalNarratives)
    model: str = ""
    prompt_version: str = ""
    fallback: bool = False
    fallback_reason: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    # I5-1 section-based output fields
    situation: str | None = None
    key_story: str | None = None
    group_narratives: dict[str, str] | None = None
    watch_signals: list[dict[str, str]] | None = None


class Manifest(BaseModel):
    """Run manifest with hashes and timings."""

    run_id: str
    generated_at: datetime
    input_file: str
    input_sha256: str
    config_sha256: str
    git_commit: str | None = None
    elapsed_seconds: float
    artifacts: dict[str, str] = Field(default_factory=dict)
    signals_warn_count: int = 0
    signals_info_count: int = 0
    audit_events_count: int = 0
    render_mode: str = "off"
    config_version: str = ""
    llm_status: str = "off"
    llm_mode: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    llm_prompt_version: str = ""
    llm_fallback_reason: str = ""
    llm_token_usage: dict[str, int] = Field(default_factory=dict)
