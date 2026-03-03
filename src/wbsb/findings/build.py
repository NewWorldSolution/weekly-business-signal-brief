"""Build the Findings document from computed metrics and signals."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from wbsb.compare.delta import compute_delta
from wbsb.domain.models import (
    AuditEvent,
    Findings,
    MetricResult,
    Periods,
    RunConfig,
    RunMeta,
    Signal,
)
from wbsb.metrics.calculate import compute_metrics
from wbsb.metrics.registry import METRIC_REGISTRY_BY_ID
from wbsb.rules.engine import evaluate_rules
from wbsb.utils.dates import week_end_date
from wbsb.utils.hash import git_commit_hash
from wbsb.utils.hash import tool_versions


def build_findings(
    df: pd.DataFrame,
    week_start: date,
    prev_week_start: date,
    run_id: str,
    input_path: Path,
    input_hash: str,
    config_hash: str,
    config_path: Path,
    raw_config: dict[str, Any],
    run_config: RunConfig,
    audit_events: list[AuditEvent],
) -> Findings:
    """Build a Findings document from the DataFrame and config.

    Args:
        df: Validated DataFrame with derived columns.
        week_start: Current analysis week start date.
        prev_week_start: Previous week start date.
        run_id: Unique run identifier.
        input_path: Path to input file.
        input_hash: SHA-256 of input file.
        config_hash: SHA-256 of config YAML.
        config_path: Path to config file.
        raw_config: Parsed YAML config.
        run_config: RunConfig parameters.
        audit_events: Validation events from schema check.

    Returns:
        Fully populated Findings object.
    """
    # Extract rows
    curr_row = _get_row(df, week_start)
    prev_row = _get_row(df, prev_week_start)

    # Compute metrics
    curr_metrics = compute_metrics(curr_row)
    prev_metrics = compute_metrics(prev_row)

    # Add raw count fields for rule guards
    prev_metrics["leads_paid"] = prev_row.get("leads_paid")
    prev_metrics["new_clients_paid"] = prev_row.get("new_clients_paid")
    prev_metrics["bookings_total"] = prev_row.get("bookings_total")

    # Reliability based on previous net_revenue
    prev_net_rev = prev_metrics.get("net_revenue") or 0.0
    reliability = "low" if prev_net_rev < run_config.min_prev_net_revenue else "ok"

    # Compute deltas
    deltas: dict[str, tuple] = {}
    for metric_id in curr_metrics:
        deltas[metric_id] = compute_delta(curr_metrics.get(metric_id), prev_metrics.get(metric_id))

    # Build MetricResult list
    metric_results: list[MetricResult] = []
    for metric_def in sorted(METRIC_REGISTRY_BY_ID.values(), key=lambda m: m.id):
        m_id = metric_def.id
        delta_abs, delta_pct = deltas.get(m_id, (None, None))
        metric_results.append(
            MetricResult(
                id=m_id,
                name=metric_def.name,
                unit=metric_def.unit,
                current=curr_metrics.get(m_id),
                previous=prev_metrics.get(m_id),
                delta_abs=delta_abs,
                delta_pct=delta_pct,
                reliability=reliability,
            )
        )

    # Evaluate rules
    signals: list[Signal] = evaluate_rules(
        current_metrics=curr_metrics,
        previous_metrics=prev_metrics,
        deltas=deltas,
        raw_config=raw_config,
        run_config=run_config,
        reliability=reliability,
    )

    run_meta = RunMeta(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        input_file=input_path.name,
        input_sha256=input_hash,
        config_sha256=config_hash,
        git_commit=git_commit_hash(),
        tool_versions=tool_versions(),
    )

    periods = Periods(
        current_week_start=week_start,
        current_week_end=week_end_date(week_start),
        previous_week_start=prev_week_start,
        previous_week_end=week_end_date(prev_week_start),
    )

    return Findings(
        run=run_meta,
        periods=periods,
        metrics=metric_results,
        signals=signals,
        audit=audit_events,
    )


def _get_row(df: pd.DataFrame, week_start: date) -> dict[str, Any]:
    """Extract a single row as a dict."""
    mask = df["week_start_date"] == pd.Timestamp(week_start)
    rows = df[mask]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()
