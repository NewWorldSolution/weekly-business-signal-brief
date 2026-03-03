"""CLI entry point for WBSB."""
from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(name="wbsb", add_completion=False)


@app.command()
def run(
    input: Path = typer.Option(..., "--input", "-i", help="Input CSV or XLSX file"),
    output: Path = typer.Option(Path("runs"), "--output", "-o", help="Output directory for runs"),
    llm: str = typer.Option("off", "--llm", help="LLM mode: off | openai | anthropic"),
    config: Path = typer.Option(Path("config/rules.yaml"), "--config", "-c", help="Rules config YAML"),
    week: str = typer.Option(None, "--week", help="ISO week to analyse (YYYY-Www), defaults to latest"),
) -> None:
    """Run the Weekly Business Signal Brief pipeline."""
    from wbsb.pipeline import execute

    exit_code = execute(
        input_path=input,
        output_dir=output,
        llm_mode=llm,
        config_path=config,
        target_week=week,
    )
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
