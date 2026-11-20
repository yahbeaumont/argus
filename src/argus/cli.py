import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from argus.graph import run
from argus.logging import configure

configure()
app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    objective: str,
    out: Path | None = typer.Option(None, help="grava o relatório em Markdown"),
    spans: bool = typer.Option(False, "--spans", help="mostra os spans do tracer"),
) -> None:
    """Executa o agente para um objetivo e imprime o relatório com as fontes verificadas."""
    state, tracer = asyncio.run(run(objective))
    console.print(Markdown(state.report))
    console.print(
        f"\n[dim]{len(state.steps)} passos · {state.tokens_used} tokens · "
        f"US$ {state.cost_usd:.4f} · {state.elapsed_s:.1f}s · "
        f"citações {state.citations_supported}/{state.citations_total} · "
        f"{'abortado: ' + str(state.abort_reason) if state.aborted else 'concluído'}[/dim]"
    )
    if spans:
        for span in tracer.dump():
            console.print(f"[dim]{span['name']:8} {span['ms']:6} ms {span}[/dim]")
    if out:
        out.write_text(state.report, encoding="utf-8")


if __name__ == "__main__":
    app()
