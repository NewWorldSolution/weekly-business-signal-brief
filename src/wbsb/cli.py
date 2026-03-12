"""CLI entry point for WBSB."""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(name="wbsb", add_completion=False)

_VALID_LLM_MODES = {"off", "summary", "full"}
_VALID_LLM_PROVIDERS = {"anthropic", "openai"}


@app.command("run")
def run(
    input_path: Path = typer.Option(..., "--input", "-i", help="Input CSV or XLSX file"),
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
) -> None:
    """Run the Weekly Business Signal Brief pipeline."""
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

    exit_code = execute(
        input_path=input_path,
        output_dir=output_dir,
        llm_mode=llm_mode,
        llm_provider=llm_provider,
        config_path=config_path,
        target_week=week,
    )
    raise typer.Exit(exit_code)


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


if __name__ == "__main__":
    app()
