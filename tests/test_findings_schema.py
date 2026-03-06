"""Tests for Pydantic schema validation of Findings."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from wbsb.domain.models import (
    AuditEvent,
    Findings,
    Manifest,
    MetricResult,
    Periods,
    RunMeta,
    Signal,
)


def make_run_meta() -> RunMeta:
    return RunMeta(
        run_id="test-run-001",
        generated_at=datetime.now(UTC),
        input_file="sample.csv",
        input_sha256="abc123",
        config_sha256="def456",
    )


def make_periods() -> Periods:
    return Periods(
        current_week_start=date(2024, 11, 25),
        current_week_end=date(2024, 12, 1),
        previous_week_start=date(2024, 11, 18),
        previous_week_end=date(2024, 11, 24),
    )


def test_findings_valid():
    f = Findings(
        run=make_run_meta(),
        periods=make_periods(),
        metrics=[
            MetricResult(
                id="net_revenue",
                name="Net Revenue",
                unit="currency",
                current=8000.0,
                previous=9000.0,
                delta_abs=-1000.0,
                delta_pct=-0.1111,
            )
        ],
        signals=[
            Signal(
                rule_id="A1",
                severity="WARN",
                metric_id="net_revenue",
                explanation="net_revenue declined",
                evidence={"current": 8000.0, "previous": 9000.0},
            )
        ],
        audit=[AuditEvent(event_type="info", message="Validated 8 rows")],
    )
    assert f.schema_version == "1.2"
    assert len(f.metrics) == 1
    assert len(f.signals) == 1


def test_findings_json_round_trip():
    f = Findings(
        run=make_run_meta(),
        periods=make_periods(),
        metrics=[],
        signals=[],
        audit=[],
    )
    json_str = f.model_dump_json()
    data = json.loads(json_str)
    f2 = Findings.model_validate(data)
    assert f2.run.run_id == f.run.run_id
    assert f2.schema_version == "1.2"


def test_metric_result_none_fields():
    m = MetricResult(id="cac_paid", name="CAC Paid", unit="currency")
    assert m.current is None
    assert m.previous is None
    assert m.delta_abs is None
    assert m.delta_pct is None
    assert m.reliability == "ok"


def test_signal_requires_rule_id():
    with pytest.raises(ValidationError):
        Signal(
            severity="WARN",
            metric_id="net_revenue",
            explanation="test",
            evidence={},
        )


def test_manifest_valid():
    m = Manifest(
        run_id="test-run-001",
        generated_at=datetime.now(UTC),
        input_file="sample.csv",
        input_sha256="abc123",
        config_sha256="def456",
        elapsed_seconds=1.23,
        artifacts={"findings.json": "hash1", "brief.md": "hash2"},
    )
    assert m.elapsed_seconds == 1.23
    assert "findings.json" in m.artifacts


def test_audit_event_minimal():
    ev = AuditEvent(event_type="info", message="test")
    assert ev.column is None
    assert ev.extra is None
