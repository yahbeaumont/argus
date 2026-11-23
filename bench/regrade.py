"""Reaplica os graders sobre relatórios já gravados, sem reexecutar o agente.

Serve para corrigir critérios de avaliação (ex.: número em formato pt-BR) sem
gastar uma nova rodada de LLM. O relatório é o mesmo; só a régua muda.
"""

import asyncio
import json
from pathlib import Path

import typer

from argus.logging import configure, get_logger
from bench import graders
from bench.ab_shared import summarize
from bench.report import render

configure()
log = get_logger(__name__)
app = typer.Typer(add_completion=False)


async def regrade(run_path: Path, tasks_path: Path, out: Path) -> dict:
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    tasks = {json.loads(line)["id"]: json.loads(line)
             for line in tasks_path.read_text().splitlines() if line.strip()}
    changed = 0
    for result in payload["results"]:
        task = tasks[result["id"]]
        grade = await graders.grade(task, result["report"])
        if grade.passed != result["passed"]:
            changed += 1
        result.update({"passed": grade.passed, "score": grade.score, "detail": grade.detail})
    payload["metrics"] = summarize(payload["results"])
    payload["regraded"] = True
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    render(payload, out.with_suffix(".md"))
    log.info("regrade.done", file=run_path.name, changed=changed,
             success=payload["metrics"]["success_rate"])
    return payload


@app.command()
def main(runs: list[Path] = typer.Argument(...),
         tasks: Path = typer.Option(Path("bench/tasks.jsonl")),
         out_dir: Path = typer.Option(Path("bench-out"))) -> None:
    for run_path in runs:
        out = out_dir / run_path.name
        asyncio.run(regrade(run_path, tasks, out))


if __name__ == "__main__":
    app()
