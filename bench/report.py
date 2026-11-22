"""Renderização dos resultados do bench em Markdown."""

from pathlib import Path

from bench.ab_shared import by_category, summarize


def render(payload: dict, path: Path) -> None:
    results = payload["results"]
    m = summarize(results)
    cats = by_category(results)
    lines = [
        f"# Benchmark — {payload['label']}",
        "",
        f"Execução: `{payload['timestamp']}` · modelo "
        f"`{payload.get('model', '?')}` · "
        f"commit `{payload.get('commit', '?')}`",
        "",
        f"- Sucesso: **{m['success_rate']:.1%}** "
        f"({sum(r['passed'] for r in results)}/{len(results)})",
        f"- Loops abortados: {int(m['loop_aborts'])}",
        f"- p50: {m['p50_latency_s']:.1f}s · p95: {m['p95_latency_s']:.1f}s",
        f"- Custo/tarefa: US$ {m['cost_per_task_usd']:.4f} · "
        f"total US$ {m['cost_total_usd']:.4f}",
        f"- Passos médios: {m['mean_steps']:.1f} · "
        f"citações suportadas: {m['citation_support']:.1%}",
        "",
        "| Categoria | Sucesso |",
        "|---|---|",
    ]
    for cat, (ok, total) in sorted(cats.items()):
        lines.append(f"| {cat} | {ok}/{total} |")
    lines += ["", "## Falhas", ""]
    for r in results:
        if not r["passed"]:
            lines.append(f"- `{r['id']}` ({r['category']}): {r['detail']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
