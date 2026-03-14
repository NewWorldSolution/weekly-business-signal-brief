"""CLI entry point for WBSB."""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(name="wbsb", add_completion=False)

_VALID_LLM_MODES = {"off", "summary", "full"}
_VALID_LLM_PROVIDERS = {"anthropic", "openai"}


@app.command("run")
def run(
    input_path: Path | None = typer.Option(
        None, "--input", "-i", help="Input CSV or XLSX file (required unless --auto)"
    ),
    output_dir: Path = typer.Option(
        Path("runs"), "--output", "-o", help="Output directory for runs"
    ),
    llm_mode: str = typer.Option("off", "--llm-mode", help="LLM mode: off | summary | full"),
    llm_provider: str = typer.Option(
        "anthropic", "--llm-provider", help="LLM provider: anthropic"
    ),
    config_path: Path = typer.Option(
        Path("config/rules.yaml"), "--config", "-c", help="Rules config YAML"
    ),
    week: str = typer.Option(
        None, "--week", help="ISO week to analyse (YYYY-Www), defaults to latest"
    ),
    auto: bool = typer.Option(
        False, "--auto", help="Auto mode: discover and run on the latest unprocessed file"
    ),
    watch_dir: Path | None = typer.Option(
        None, "--watch-dir", help="Directory to scan for input files (--auto mode)"
    ),
    pattern: str | None = typer.Option(
        None, "--pattern", help="Glob pattern for input files (--auto mode)"
    ),
    index_path: Path = typer.Option(
        Path("runs/index.json"), "--index-path", help="History index path (--auto mode)"
    ),
    deliver: bool = typer.Option(
        False, "--deliver", help="Deliver the report to configured channels after the run"
    ),
) -> None:
    """Run the Weekly Business Signal Brief pipeline."""
    if auto:
        _run_auto(
            output_dir=output_dir,
            llm_mode=llm_mode,
            llm_provider=llm_provider,
            config_path=config_path,
            watch_dir=watch_dir,
            pattern=pattern,
            index_path=index_path,
            deliver=deliver,
        )
        return

    if input_path is None:
        typer.echo("Error: --input / -i is required unless --auto is set.", err=True)
        raise typer.Exit(1)

    if llm_mode not in _VALID_LLM_MODES:
        typer.echo(
            f"Error: --llm-mode must be one of: {', '.join(sorted(_VALID_LLM_MODES))}. "
            f"Got: {llm_mode!r}",
            err=True,
        )
        raise typer.Exit(1)

    if llm_provider not in _VALID_LLM_PROVIDERS:
        typer.echo(
            f"Error: --llm-provider must be one of: {', '.join(sorted(_VALID_LLM_PROVIDERS))}. "
            f"Got: {llm_provider!r}",
            err=True,
        )
        raise typer.Exit(1)

    if llm_provider == "openai":
        typer.echo(
            "Error: OpenAI provider is not yet implemented. "
            "Use --llm-provider anthropic instead.",
            err=True,
        )
        raise typer.Exit(1)

    from wbsb.pipeline import execute

    # Snapshot existing run directories before the run so we can identify
    # the new run by set difference rather than guessing by mtime.
    prior_run_dirs: set[str] = _snapshot_run_dirs(output_dir)

    try:
        exit_code = execute(
            input_path=input_path,
            output_dir=output_dir,
            llm_mode=llm_mode,
            llm_provider=llm_provider,
            config_path=config_path,
            target_week=week,
        )
    except Exception as exc:
        typer.echo(f"⚠️  Pipeline error: {exc}", err=True)
        _try_send_pipeline_error_alert(str(exc), run_id=None)
        raise typer.Exit(1)

    if exit_code == 0 and deliver:
        _try_deliver(output_dir, prior_run_dirs)

    raise typer.Exit(exit_code)


def _run_auto(
    output_dir: Path,
    llm_mode: str,
    llm_provider: str,
    config_path: Path,
    watch_dir: Path | None,
    pattern: str | None,
    index_path: Path,
    deliver: bool = False,
) -> None:
    """Execute the auto-run flow: discover → check → run pipeline.

    Loads scheduler defaults from config/delivery.yaml when present; CLI
    arguments override config values.
    """
    from wbsb.scheduler.auto import already_processed, find_latest_input

    # Load scheduler defaults from config/delivery.yaml if available.
    # CLI arguments take precedence over config values.
    delivery_config_path = Path("config/delivery.yaml")
    if delivery_config_path.exists():
        try:
            from wbsb.delivery.config import load_delivery_config

            dcfg = load_delivery_config(delivery_config_path)
            sched = dcfg.get("scheduler", {})
            if watch_dir is None and sched.get("watch_directory"):
                watch_dir = Path(sched["watch_directory"])
            if pattern is None and sched.get("filename_pattern"):
                pattern = sched["filename_pattern"]
        except Exception:
            pass

    # Apply hardcoded fallbacks when neither config nor CLI provided values.
    if pattern is None:
        pattern = "*.csv"

    if watch_dir is None:
        typer.echo("Error: --watch-dir is required in --auto mode.", err=True)
        raise typer.Exit(1)

    if llm_mode not in _VALID_LLM_MODES:
        typer.echo(
            f"Error: --llm-mode must be one of: {', '.join(sorted(_VALID_LLM_MODES))}. "
            f"Got: {llm_mode!r}",
            err=True,
        )
        raise typer.Exit(1)

    if llm_provider not in _VALID_LLM_PROVIDERS:
        typer.echo(
            f"Error: --llm-provider must be one of: {', '.join(sorted(_VALID_LLM_PROVIDERS))}. "
            f"Got: {llm_provider!r}",
            err=True,
        )
        raise typer.Exit(1)

    if llm_provider == "openai":
        typer.echo(
            "Error: OpenAI provider is not yet implemented. "
            "Use --llm-provider anthropic instead.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        candidate = find_latest_input(watch_dir, pattern)
    except ValueError as exc:
        typer.echo(f"Auto-run: skipping — {exc}", err=True)
        return

    if candidate is None:
        typer.echo("⚠️  Auto-run: no new data file found. Skipping.")
        _try_send_no_file_alert(str(watch_dir))
        return

    if already_processed(candidate, index_path):
        typer.echo(f"Auto-run: {candidate.name} already processed. Skipping.")
        return

    typer.echo(f"Auto-run: processing {candidate.name}")

    from wbsb.pipeline import execute

    prior_run_dirs: set[str] = _snapshot_run_dirs(output_dir)

    try:
        exit_code = execute(
            input_path=candidate,
            output_dir=output_dir,
            llm_mode=llm_mode,
            llm_provider=llm_provider,
            config_path=config_path,
            target_week=None,
        )
    except Exception as exc:
        typer.echo(f"⚠️  Pipeline error: {exc}", err=True)
        _try_send_pipeline_error_alert(str(exc), run_id=None)
        raise typer.Exit(1)

    if exit_code == 0 and deliver:
        _try_deliver(output_dir, prior_run_dirs)

    raise typer.Exit(exit_code)


def _snapshot_run_dirs(output_dir: Path) -> set[str]:
    """Return the set of subdirectory names currently in output_dir."""
    if not output_dir.exists():
        return set()
    try:
        return {d.name for d in output_dir.iterdir() if d.is_dir()}
    except OSError:
        return set()


def _try_deliver(output_dir: Path, prior_run_dirs: set[str]) -> None:
    """Find the run just completed by set-difference and deliver it.

    Never raises — all failures are reported to stdout/stderr and swallowed
    so the run exit code is unaffected.
    """
    from wbsb.delivery.config import load_delivery_config
    from wbsb.delivery.models import DeliveryStatus
    from wbsb.delivery.orchestrator import deliver_run

    delivery_config_path = Path("config/delivery.yaml")
    if not delivery_config_path.exists():
        typer.echo("Delivery: config/delivery.yaml not found — skipping.", err=True)
        return

    try:
        delivery_cfg = load_delivery_config(delivery_config_path)
    except Exception as exc:
        typer.echo(f"Delivery: error loading config — {exc}", err=True)
        return

    try:
        current_dirs = {d.name for d in output_dir.iterdir() if d.is_dir()}
    except OSError as exc:
        typer.echo(f"Delivery: cannot read output directory — {exc}", err=True)
        return

    new_dirs = current_dirs - prior_run_dirs
    if not new_dirs:
        typer.echo("Delivery: could not identify the completed run — skipping.", err=True)
        return

    run_id = next(iter(new_dirs))

    # Alert 1 — LLM fallback: print visible warning when AI analysis was unavailable.
    import json

    manifest_path = output_dir / run_id / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("llm_status") in ("fallback", "error"):
            typer.echo(
                "⚠️  LLM fallback: AI analysis unavailable — report delivered with fallback banner."
            )
    except Exception:  # noqa: BLE001
        pass  # manifest unreadable; non-fatal

    try:
        results = deliver_run(run_id, delivery_cfg, output_dir)
    except Exception as exc:
        typer.echo(f"Delivery: unexpected error — {exc}", err=True)
        return

    for r in results:
        if r.status == DeliveryStatus.success:
            typer.echo(f"✅ {r.target.value}: delivered")
        else:
            typer.echo(f"⚠️  Delivery failed ({r.target.value}): {r.error}")


def _try_send_pipeline_error_alert(error: str, run_id: str | None) -> None:
    """Load delivery config and dispatch a pipeline error alert. Never raises."""
    from wbsb.delivery.alerts import build_pipeline_error_alert, send_alert
    from wbsb.delivery.config import load_delivery_config

    delivery_config_path = Path("config/delivery.yaml")
    if not delivery_config_path.exists():
        return
    try:
        delivery_cfg = load_delivery_config(delivery_config_path)
        if not delivery_cfg.get("alerts", {}).get("on_pipeline_error", False):
            return
        alert = build_pipeline_error_alert(error, run_id)
        send_alert(alert, delivery_cfg)
    except Exception:  # noqa: BLE001
        pass  # alert dispatch is best-effort; never crash the CLI


def _try_send_no_file_alert(watch_directory: str) -> None:
    """Load delivery config and dispatch a no-new-file alert. Never raises."""
    from wbsb.delivery.alerts import build_no_file_alert, send_alert
    from wbsb.delivery.config import load_delivery_config

    delivery_config_path = Path("config/delivery.yaml")
    if not delivery_config_path.exists():
        return
    try:
        delivery_cfg = load_delivery_config(delivery_config_path)
        if not delivery_cfg.get("alerts", {}).get("on_no_new_file", False):
            return
        alert = build_no_file_alert(watch_directory)
        send_alert(alert, delivery_cfg)
    except Exception:  # noqa: BLE001
        pass  # alert dispatch is best-effort; never crash the CLI


@app.command("deliver")
def deliver_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to deliver"),
    output_dir: Path = typer.Option(
        Path("runs"), "--output", "-o", help="Output directory containing runs"
    ),
    config_path: Path = typer.Option(
        Path("config/delivery.yaml"), "--config", "-c", help="Delivery config YAML"
    ),
) -> None:
    """Deliver a completed run to configured channels (Teams/Slack)."""
    from wbsb.delivery.config import load_delivery_config
    from wbsb.delivery.models import DeliveryStatus
    from wbsb.delivery.orchestrator import deliver_run

    try:
        delivery_cfg = load_delivery_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error loading delivery config: {exc}", err=True)
        raise typer.Exit(1)

    results = deliver_run(run_id, delivery_cfg, output_dir)

    any_failed = False
    for r in results:
        if r.status == DeliveryStatus.success:
            typer.echo(f"✅ {r.target.value}: delivered")
        else:
            typer.echo(f"❌ {r.target.value}: failed — {r.error}")
            any_failed = True

    if any_failed:
        raise typer.Exit(1)


@app.command("eval")
def eval_cmd(
    case: str = typer.Option(None, "--case", help="Run a single named case."),
) -> None:
    """Run evaluation against golden dataset cases."""
    from wbsb.eval.runner import load_case, run_all_cases, run_case

    if case:
        results = [run_case(load_case(case))]
    else:
        results = run_all_cases()

    any_failed = False
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        typer.echo(f"[{status}] {result['name']}")
        for failure in result["failures"]:
            typer.echo(f"  - {failure}")
        if not result["passed"]:
            any_failed = True

    if any_failed:
        raise typer.Exit(code=1)


@app.command("version")
def version() -> None:
    """Print the WBSB version."""
    from wbsb import __version__

    typer.echo(__version__)


feedback_app = typer.Typer()
app.add_typer(feedback_app, name="feedback")


@feedback_app.command("list")
def feedback_list(limit: int = typer.Option(50, "--limit", help="Max entries to show.")):
    """List recent feedback entries."""
    from wbsb.feedback.store import list_feedback

    entries = list_feedback(limit=limit)
    for e in entries:
        typer.echo(f"[{e.submitted_at}] {e.run_id} | {e.section} | {e.label} | {e.comment[:80]}")


@feedback_app.command("summary")
def feedback_summary():
    """Show feedback summary by label and section."""
    from wbsb.feedback.store import summarize_feedback

    summary = summarize_feedback()
    typer.echo(f"Total: {summary['total']}")
    typer.echo("By label:")
    for label, count in summary["by_label"].items():
        typer.echo(f"  {label}: {count}")
    typer.echo("By section:")
    for section, count in summary["by_section"].items():
        typer.echo(f"  {section}: {count}")


@feedback_app.command("export")
def feedback_export(run_id: str = typer.Option(..., "--run-id", help="Run ID to export.")):
    """Export all feedback for a specific run."""
    import json

    from wbsb.feedback.store import export_feedback

    entries = export_feedback(run_id)
    typer.echo(json.dumps([e.model_dump() for e in entries], indent=2))


@feedback_app.command("serve")
def feedback_serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8080, "--port", help="Port to listen on"),
) -> None:
    """Start the feedback webhook server (POST /feedback)."""
    from wbsb.feedback.server import run_server

    typer.echo(f"Starting feedback server on {host}:{port}")
    run_server(host=host, port=port)


if __name__ == "__main__":
    app()
