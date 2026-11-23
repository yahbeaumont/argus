"""A/B pareado guarded vs unguarded, com bootstrap e McNemar exato."""

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from argus.logging import configure, get_logger
from bench.ab_shared import (
    bootstrap_diff,
    by_category,
    load_run,
    mcnemar_exact,
    paired,
    summarize,
)

configure()
log = get_logger(__name__)
app = typer.Typer(add_completion=False)


def compare(guarded: dict, unguarded: dict, n_boot: int = 10_000, seed: int = 1337) -> dict:
    a, b = guarded["results"], unguarded["results"]
    pairs = paired(a, b)
    diff, lo, hi = bootstrap_diff(pairs, n_boot=n_boot, seed=seed)
    ma, mb = summarize(a), summarize(b)
    cats_a, cats_b = by_category(a), by_category(b)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "n_pairs": len(pairs),
        "discordant": {
            "guarded_only": sum(1 for _, x, y in pairs if x and not y),
            "unguarded_only": sum(1 for _, x, y in pairs if y and not x),
            "both": sum(1 for _, x, y in pairs if x and y),
            "neither": sum(1 for _, x, y in pairs if not x and not y),
        },
        "success_rate": {"guarded": ma["success_rate"], "unguarded": mb["success_rate"],
                         "diff": diff, "ci95": [lo, hi],
                         "mcnemar_p": mcnemar_exact(pairs)},
        "latency": {"p50_guarded": ma["p50_latency_s"], "p50_unguarded": mb["p50_latency_s"],
                    "p95_guarded": ma["p95_latency_s"], "p95_unguarded": mb["p95_latency_s"]},
        "loop_aborts": {"guarded": int(ma["loop_aborts"]), "unguarded": int(mb["loop_aborts"])},
        "cost_per_task_usd": {"guarded": ma["cost_per_task_usd"],
                              "unguarded": mb["cost_per_task_usd"]},
        "citation_support": {"guarded": ma["citation_support"],
                             "unguarded": mb["citation_support"]},
        "categories": {
            cat: {"guarded": cats_a.get(cat, (0, 0)), "unguarded": cats_b.get(cat, (0, 0))}
            for cat in sorted(set(cats_a) | set(cats_b))
        },
    }


def to_markdown(payload: dict) -> str:
    s = payload["success_rate"]
    d = payload["discordant"]
    lines = [
        "# A/B pareado — guarded vs unguarded",
        "",
        f"Pares: {payload['n_pairs']} tarefas · discordantes: "
        f"{d['guarded_only']} só guarded, {d['unguarded_only']} só unguarded",
        "",
        "| Métrica | Unguarded | Guarded | Δ |",
        "|---|---|---|---|",
        f"| Sucesso | {s['unguarded']:.1%} | {s['guarded']:.1%} | "
        f"{s['diff']:+.1%} (IC95 {s['ci95'][0]:+.1%} a {s['ci95'][1]:+.1%}) |",
        f"| McNemar exato (p) | | {s['mcnemar_p']:.4f} | |",
        f"| p50 | {payload['latency']['p50_unguarded']:.1f}s | "
        f"{payload['latency']['p50_guarded']:.1f}s | |",
        f"| p95 | {payload['latency']['p95_unguarded']:.1f}s | "
        f"{payload['latency']['p95_guarded']:.1f}s | |",
        f"| Loops abortados | {payload['loop_aborts']['unguarded']} | "
        f"{payload['loop_aborts']['guarded']} | |",
        f"| Custo/tarefa | US$ {payload['cost_per_task_usd']['unguarded']:.4f} | "
        f"US$ {payload['cost_per_task_usd']['guarded']:.4f} | |",
        f"| Citações suportadas | {payload['citation_support']['unguarded']:.1%} | "
        f"{payload['citation_support']['guarded']:.1%} | |",
        "",
        "| Categoria | Unguarded | Guarded |",
        "|---|---|---|",
    ]
    for cat, vals in payload["categories"].items():
        u_ok, u_n = vals["unguarded"]
        g_ok, g_n = vals["guarded"]
        lines.append(f"| {cat} | {u_ok}/{u_n} | {g_ok}/{g_n} |")
    return "\n".join(lines) + "\n"


@app.command()
def main(
    guarded: Path = typer.Option(Path("bench-out/run-guarded.json")),
    unguarded: Path = typer.Option(Path("bench-out/run-unguarded.json")),
    n_boot: int = typer.Option(10_000),
    seed: int = typer.Option(1337),
    out: Path = typer.Option(Path("bench-out/ab.json")),
) -> None:
    payload = compare(load_run(guarded), load_run(unguarded), n_boot, seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    out.with_suffix(".md").write_text(to_markdown(payload), encoding="utf-8")
    typer.echo(to_markdown(payload))


if __name__ == "__main__":
    app()
