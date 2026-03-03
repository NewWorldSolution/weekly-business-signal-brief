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
    explanation: str
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

    schema_version: str = "1.0"
    run: RunMeta
    periods: Periods
    metrics: list[MetricResult]
    signals: list[Signal]
    audit: list[AuditEvent]


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
