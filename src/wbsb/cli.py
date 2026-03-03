"""CLI entry point for WBSB."""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(name="wbsb", add_completion=False)


@app.command("run")
def run(
    input_path: Path = typer.Option(..., "--input", "-i", help="Input CSV or XLSX file"),
    output_dir: Path = typer.Option(
        Path("runs"), "--output", "-o", help="Output directory for runs"
    ),
    llm_mode: str = typer.Option("off", "--llm", help="LLM mode: off | openai | anthropic"),
    config_path: Path = typer.Option(
        Path("config/rules.yaml"), "--config", "-c", help="Rules config YAML"
    ),
    week: str = typer.Option(
        None, "--week", help="ISO week to analyse (YYYY-Www), defaults to latest"
    ),
) -> None:
    """Run the Weekly Business Signal Brief pipeline."""
    from wbsb.pipeline import execute

    exit_code = execute(
        input_path=input_path,
        output_dir=output_dir,
        llm_mode=llm_mode,
        config_path=config_path,
        target_week=week,
    )
    raise typer.Exit(exit_code)


@app.command("version")
def version() -> None:
    """Print the WBSB version."""
    from wbsb import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
