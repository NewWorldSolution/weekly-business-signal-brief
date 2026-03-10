"""Top-level pipeline orchestrator."""
from __future__ import annotations

import sys
import time
from datetime import UTC, timedelta
from pathlib import Path

from wbsb.domain.models import RunConfig
from wbsb.export.write import write_artifacts
from wbsb.findings.build import build_findings
from wbsb.history.store import HistoryReader, RunRecord, derive_dataset_key, register_run
from wbsb.history.trends import compute_trends
from wbsb.ingest.loader import load_data
from wbsb.observability.logging import get_logger, init_run_logger
from wbsb.render.llm import render_llm
from wbsb.render.template import render_template
from wbsb.utils.dates import resolve_target_week
from wbsb.utils.hash import file_sha256, yaml_sha256
from wbsb.validate.schema import validate_dataframe


def execute(
    input_path: Path,
    output_dir: Path,
    llm_mode: str,
    llm_provider: str,
    config_path: Path,
    target_week: str | None,
) -> int:
    """Execute the full pipeline and return exit code (0=success, 1=error).

    Args:
        input_path: Path to input CSV or XLSX file.
        output_dir: Directory under which the run sub-directory is created.
        llm_mode: LLM operating mode — "off", "summary", or "full".
        llm_provider: LLM provider — currently only "anthropic" is implemented.
        config_path: Path to rules YAML configuration file.
        target_week: ISO week string (YYYY-Www) or None to use the latest week.

    Returns:
        0 on success, 1 on unrecoverable error.
    """
    import uuid
    from datetime import datetime

    import yaml

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    init_run_logger(run_dir / "logs.jsonl")
    log = get_logger()

    log.info(
        "pipeline.start",
        run_id=run_id,
        input=str(input_path),
        llm_mode=llm_mode,
        llm_provider=llm_provider,
    )

    start_time = time.monotonic()

    try:
        # Hashes for auditability
        input_hash = file_sha256(input_path)
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)
        config_hash = yaml_sha256(raw_config)

        log.info("ingest.start", file=str(input_path), sha256=input_hash)
        df = load_data(input_path)
        log.info("ingest.done", rows=len(df))

        log.info("validate.start")
        audit_events, df = validate_dataframe(df)
        for ev in audit_events:
            log.info("validate.event", **ev.model_dump())
        log.info("validate.done", events=len(audit_events))

        # Resolve which week to analyse
        week_start, prev_week_start = resolve_target_week(df, target_week)
        log.info("weeks.resolved", current=str(week_start), previous=str(prev_week_start))

        dataset_key = derive_dataset_key(input_path)
        week_end = week_start + timedelta(days=6)

        run_config = RunConfig(
            min_prev_net_revenue=raw_config["defaults"]["min_prev_net_revenue"],
            volume_threshold=raw_config["defaults"]["volume_threshold"],
        )

        log.info("findings.build.start")
        findings = build_findings(
            df=df,
            week_start=week_start,
            prev_week_start=prev_week_start,
            run_id=run_id,
            input_path=input_path,
            input_hash=input_hash,
            config_hash=config_hash,
            config_path=config_path,
            raw_config=raw_config,
            run_config=run_config,
            audit_events=audit_events,
        )
        log.info(
            "findings.build.done",
            signals=len(findings.signals),
            metrics=len(findings.metrics),
        )

        # Render brief — deterministic path or optional LLM overlay
        llm_result = None
        rendered_system_prompt = ""
        rendered_user_prompt = ""

        if llm_mode == "off":
            log.info("render.template")
            brief_md = render_template(findings)
        else:
            # Compute trend context from historical signal metrics
            index_path = output_dir / "index.json"
            history_reader = HistoryReader(index_path=index_path, dataset_key=dataset_key)
            signal_metric_ids = list({s.metric_id for s in findings.signals if s.metric_id})
            try:
                trend_context = compute_trends(
                    history_reader,
                    metric_ids=signal_metric_ids,
                )
            except Exception as exc:
                log.error("trends.compute.error", error=str(exc))
                trend_context = {}

            log.info("render.llm", mode=llm_mode, provider=llm_provider)
            brief_md, llm_result, rendered_system_prompt, rendered_user_prompt = render_llm(
                findings=findings,
                mode=llm_mode,
                provider=llm_provider,
                trend_context=trend_context,
            )
            if llm_result is None:
                log.info("render.llm.fallback", mode=llm_mode, provider=llm_provider)
            else:
                log.info("render.llm.success", model=llm_result.model)

        elapsed = time.monotonic() - start_time

        write_artifacts(
            run_dir=run_dir,
            findings=findings,
            brief_md=brief_md,
            elapsed_seconds=elapsed,
            run_id=run_id,
            input_path=input_path,
            input_hash=input_hash,
            config_hash=config_hash,
            signals_warn_count=len([s for s in findings.signals if s.severity == "WARN"]),
            signals_info_count=len([s for s in findings.signals if s.severity == "INFO"]),
            audit_events_count=len(findings.audit),
            render_mode=llm_mode,
            config_version=raw_config.get("config_version", ""),
            llm_result=llm_result,
            llm_mode=llm_mode,
            llm_provider=llm_provider,
            rendered_system_prompt=rendered_system_prompt,
            rendered_user_prompt=rendered_user_prompt,
        )

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
        log.info(
            "history.registered",
            run_id=run_id,
            dataset_key=dataset_key,
            index=str(index_path),
        )

        log.info("pipeline.done", run_dir=str(run_dir), elapsed_seconds=round(elapsed, 3))
        print(f"\n✅  Run complete: {run_dir}", flush=True)
        return 0

    except Exception as exc:
        log.error("pipeline.error", error=str(exc), exc_info=True)
        print(f"\n❌  Pipeline error: {exc}", file=sys.stderr, flush=True)
        return 1
