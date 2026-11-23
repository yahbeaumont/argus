"""Gate de regressão do benchmark. Direção por métrica: higher ou lower é melhor."""

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from argus.logging import configure, get_logger
from bench.ab_shared import load_run, summarize

configure()
log = get_logger(__name__)
app = typer.Typer(add_completion=False)

DIRECTION = {
    "success_rate": "higher",
    "p95_latency_s": "lower",
    "loop_aborts": "lower",
    "cost_per_task_usd": "lower",
}


def check(baseline: dict, current: dict[str, float]) -> list[dict]:
    failures = []
    for metric, base in baseline["metrics"].items():
        if metric not in DIRECTION or metric not in current:
            continue
        tolerance = baseline["tolerance"][metric]
        value = current[metric]
        worse_by = base - value if DIRECTION[metric] == "higher" else value - base
        if worse_by > tolerance:
            failures.append({"metric": metric, "base": base, "current": value,
                             "worse_by": round(worse_by, 4), "tolerance": tolerance})
    return failures


def verdict(baseline: dict, current: dict[str, float], failures: list[dict]) -> dict:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "passed": not failures,
        "metrics": {
            metric: {
                "baseline": baseline["metrics"].get(metric),
                "current": round(current[metric], 4),
                "direction": DIRECTION[metric],
                "tolerance": baseline["tolerance"][metric],
                "ok": metric not in {f["metric"] for f in failures},
            }
            for metric in DIRECTION
            if metric in current
        },
        "failures": failures,
    }


def to_markdown(payload: dict) -> str:
    lines = [
        "# Veredito do gate",
        "",
        f"Resultado: **{'PASSOU' if payload['passed'] else 'FALHOU'}** · `{payload['timestamp']}`",
        "",
        "| Métrica | Baseline | Atual | Direção | Tolerância | OK |",
        "|---|---|---|---|---|---|",
    ]
    for metric, row in payload["metrics"].items():
        lines.append(
            f"| {metric} | {row['baseline']} | {row['current']} | {row['direction']} | "
            f"{row['tolerance']} | {'sim' if row['ok'] else 'não'} |"
        )
    if payload["failures"]:
        lines += ["", "## Regressões", ""]
        for f in payload["failures"]:
            lines.append(f"- `{f['metric']}` piorou {f['worse_by']} (tolerância {f['tolerance']})")
    return "\n".join(lines) + "\n"


@app.command()
def main(
    run: Path = typer.Option(Path("bench-out/run-guarded.json")),
    baseline: Path = typer.Option(Path("bench/baseline.json")),
    update_baseline: bool = typer.Option(False, "--update-baseline"),
    verdict_out: Path | None = typer.Option(None, "--verdict"),
) -> None:
    payload = load_run(run)
    results = payload["results"] if isinstance(payload, dict) else payload
    current = summarize(results)
    base = json.loads(baseline.read_text(encoding="utf-8"))

    if update_baseline:
        base["metrics"] = {k: round(v, 4) for k, v in current.items() if k in DIRECTION}
        base.setdefault("_meta", {}).update({
            "commit": payload.get("commit", "unknown"),
            "date": datetime.now(UTC).date().isoformat(),
            "model": payload.get("model", "unknown"),
            "tasks": len(results),
        })
        baseline.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.secho("baseline atualizado", fg="green")
        return

    failures = check(base, current)
    for metric in DIRECTION:
        if metric in current:
            typer.echo(f"{metric:22s} {base['metrics'][metric]:.4f} -> {current[metric]:.4f}")

    if verdict_out:
        payload_out = verdict(base, current, failures)
        verdict_out.parent.mkdir(parents=True, exist_ok=True)
        verdict_out.write_text(json.dumps(payload_out, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        verdict_out.with_suffix(".md").write_text(to_markdown(payload_out), encoding="utf-8")

    if not failures:
        typer.secho("\nsem regressões", fg="green")
        raise typer.Exit(0)
    for f in failures:
        typer.secho(f"  REGRESSÃO {f['metric']}: piorou {f['worse_by']:.4f} "
                    f"(tolerância {f['tolerance']})", fg="red", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
