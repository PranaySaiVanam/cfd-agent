"""Command line: cfd-agent run "..." | cfd-agent eval | cfd-agent check-env"""
from __future__ import annotations

from pathlib import Path

import typer

from .agent import run_request
from .llm_client import AnthropicLLM
from .runners import MockRunner, OpenFOAMRunner

app = typer.Typer(add_completion=False, help="LLM agent for automated OpenFOAM lid-driven cavity CFD")


def make_runner(runner: str, docker: bool):
    if runner == "mock":
        return MockRunner()
    r = OpenFOAMRunner(mode="docker" if docker else "native")
    if not r.available():
        typer.secho("OpenFOAM not available. Install it (WSL/Docker) or set CFD_AGENT_FOAM_BASHRC. "
                    "Use --runner mock only for dry runs (synthetic output).", fg="red", err=True)
        raise typer.Exit(2)
    return r


def make_llm(llm: str):
    if llm == "none":
        return None
    try:
        return AnthropicLLM()
    except Exception as e:  # missing key / SDK
        typer.secho(f"LLM unavailable ({e}); using the rule-based parser.", fg="yellow", err=True)
        return None


@app.command()
def run(request: str = typer.Argument(..., help='e.g. "simulate cavity flow at Re 400 on a 48x48 grid"'),
        runner: str = typer.Option("openfoam", help="openfoam | mock"),
        llm: str = typer.Option("none", help="none | anthropic"),
        docker: bool = typer.Option(False, help="run OpenFOAM inside Docker (untested path)"),
        out: Path = typer.Option(Path("runs"), help="output directory")):
    res = run_request(request, make_runner(runner, docker), make_llm(llm), out)
    color = {"success": "green", "failed": "red", "rejected": "yellow"}[res.status]
    typer.secho(f"[{res.status.upper()}] {res.message}", fg=color)
    for w in res.warnings:
        typer.secho(f"  warning: {w}", fg="yellow")
    typer.echo(f"report: {res.report_path}")
    raise typer.Exit(0 if res.status in ("success", "rejected") else 1)


@app.command("eval")
def eval_cmd(runner: str = typer.Option("openfoam"), llm: str = typer.Option("none"),
             docker: bool = typer.Option(False), out: Path = typer.Option(Path("runs/eval"))):
    from .evaluation import run_eval
    summary = run_eval(make_runner(runner, docker), make_llm(llm), out)
    raise typer.Exit(0 if summary["all_passed"] else 1)


@app.command("check-env")
def check_env():
    r = OpenFOAMRunner()
    typer.echo(f"native OpenFOAM available: {r.available()} (bashrc: {r.bashrc})")
    d = OpenFOAMRunner(mode="docker")
    typer.echo(f"docker available: {d.available()}")


if __name__ == "__main__":
    app()
