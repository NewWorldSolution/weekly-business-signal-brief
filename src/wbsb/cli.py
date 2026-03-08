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


@app.command("version")
def version() -> None:
    """Print the WBSB version."""
    from wbsb import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
