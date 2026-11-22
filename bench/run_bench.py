"""Executa o benchmark. Guarded por padrão; --no-guards é o braço de controle."""

import asyncio
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer

from argus.config import get_settings
from argus.graph import run
from argus.logging import configure, get_logger
from bench import graders
from bench.ab_shared import summarize
from bench.report import render

configure()
log = get_logger(__name__)
app = typer.Typer(add_completion=False)


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True, timeout=5).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


async def run_task(task: dict) -> dict:
    state, tracer = await run(task["objective"])
    grade = await graders.grade(task, state.report)
    return {
        "id": task["id"],
        "category": task["category"],
        "passed": grade.passed,
        "score": grade.score,
        "detail": grade.detail,
        "steps": len(state.steps),
        "aborted": state.aborted,
        "abort_reason": state.abort_reason,
        "tokens": state.tokens_used,
        "cost_usd": state.cost_usd,
        "latency_s": state.elapsed_s,
        "citations_total": state.citations_total,
        "citations_supported": state.citations_supported,
        "spans": tracer.by_name(),
        "report": state.report,
    }


def _failed(task: dict, exc: Exception) -> dict:
    log.error("task.failed", id=task["id"], error=str(exc))
    return {
        "id": task["id"], "category": task["category"], "passed": False, "score": 0.0,
        "detail": f"exceção: {exc}", "steps": 0, "aborted": True,
        "abort_reason": f"exception:{type(exc).__name__}", "tokens": 0, "cost_usd": 0.0,
        "latency_s": 0.0, "citations_total": 0, "citations_supported": 0, "spans": {},
        "report": "",
    }


async def main_async(limit: int | None, out: Path, no_guards: bool,
                     concurrency: int, tasks_path: Path) -> None:
    if no_guards:
        os.environ["GUARDS_ENABLED"] = "false"
        get_settings.cache_clear()
    tasks = [json.loads(line) for line in tasks_path.read_text().splitlines() if line.strip()]
    if limit:
        tasks = tasks[:limit]
    sem = asyncio.Semaphore(concurrency)

    async def bound(task: dict) -> dict:
        async with sem:
            try:
                return await run_task(task)
            except Exception as exc:
                return _failed(task, exc)

    results = await asyncio.gather(*(bound(t) for t in tasks))
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "label": "unguarded" if no_guards else "guarded",
        "model": get_settings().model,
        "commit": _commit(),
        "metrics": summarize(results),
        "results": results,
    }
    out.mkdir(parents=True, exist_ok=True)
    name = "run-unguarded" if no_guards else "run-guarded"
    (out / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    render(payload, out / f"{name}.md")
    log.info("bench.done", success=sum(r["passed"] for r in results), n=len(results),
             label=payload["label"], out=str(out))


@app.command()
def main(
    limit: int | None = typer.Option(None),
    out: Path = typer.Option(Path("bench-out")),
    no_guards: bool = typer.Option(False, "--no-guards"),
    concurrency: int = typer.Option(4),
    tasks: Path = typer.Option(Path("bench/tasks.jsonl")),
) -> None:
    asyncio.run(main_async(limit, out, no_guards, concurrency, tasks))


if __name__ == "__main__":
    app()
