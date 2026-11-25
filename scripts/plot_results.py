"""Gera os gráficos do README a partir dos JSONs reais do bench.

Sem dado inventado: cada figura lê `bench-out/run-guarded.json`, `run-unguarded.json`
e `ab.json`. Se um número for ruim, o gráfico mostra o número ruim.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import typer

from bench.ab_shared import by_category, summarize

CATEGORIES = ["synthesis", "compute", "data", "adversarial"]
LABELS = {"synthesis": "Síntese", "compute": "Cálculo", "data": "Dados",
          "adversarial": "Adversariais"}
COLORS = {"guarded": "#1f6feb", "unguarded": "#d29922"}


def _save(fig, out: Path, name: str) -> None:
    fig.tight_layout()
    fig.savefig(out / name, dpi=100)
    plt.close(fig)
    print(f"  {name}")


def plot_categories(guarded: dict, unguarded: dict, out: Path) -> None:
    cat_g = by_category(guarded["results"])
    cat_u = by_category(unguarded["results"])
    fig, ax = plt.subplots(figsize=(16, 9))
    width = 0.38
    for i, cat in enumerate(CATEGORIES):
        for j, (arm, data) in enumerate([("unguarded", cat_u), ("guarded", cat_g)]):
            ok, total = data.get(cat, (0, 1))
            rate = ok / total if total else 0
            x = i + (j - 0.5) * width
            ax.bar(x, rate * 100, width, color=COLORS[arm],
                   label=arm.capitalize() if i == 0 else None)
            ax.text(x, rate * 100 + 1.5, f"{ok}/{total}", ha="center", fontsize=13)
    ax.set_xticks(range(len(CATEGORIES)))
    ax.set_xticklabels([LABELS[c] for c in CATEGORIES], fontsize=14)
    ax.set_ylabel("Tarefas aprovadas (%)", fontsize=14)
    ax.set_ylim(0, 108)
    ax.set_title("Sucesso por categoria — 40 tarefas, mesma seed", fontsize=18)
    ax.legend(fontsize=13)
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out, "success-by-category.png")


def plot_latency(guarded: dict, unguarded: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    for arm, payload in [("unguarded", unguarded), ("guarded", guarded)]:
        lat = sorted(r["latency_s"] for r in payload["results"])
        ax.plot(range(1, len(lat) + 1), lat, marker="o", markersize=4,
                color=COLORS[arm], label=f"{arm} (n={len(lat)})")
    ax.set_xlabel("Tarefas ordenadas por latência", fontsize=14)
    ax.set_ylabel("Latência (s)", fontsize=14)
    ax.set_title("Distribuição de latência por tarefa", fontsize=18)
    ax.legend(fontsize=13)
    ax.grid(alpha=0.3)
    _save(fig, out, "latency-distribution.png")


def plot_cost_scatter(guarded: dict, unguarded: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    for arm, payload in [("unguarded", unguarded), ("guarded", guarded)]:
        for passed in (True, False):
            pts = [r for r in payload["results"] if bool(r["passed"]) is passed]
            ax.scatter([r["latency_s"] for r in pts],
                       [r["cost_usd"] * 1000 for r in pts],
                       s=[60 + 40 * r["steps"] for r in pts],
                       marker="o" if arm == "guarded" else "s",
                       color=COLORS[arm], alpha=0.85 if passed else 0.45,
                       edgecolor="black" if not passed else "none",
                       label=f"{arm} · {'aprovada' if passed else 'reprovada'}")
    ax.set_xlabel("Latência (s)", fontsize=14)
    ax.set_ylabel("Custo da tarefa (mUS$)", fontsize=14)
    ax.set_title("Custo vs latência por tarefa (tamanho = passos, contorno = reprovada)",
                 fontsize=18)
    ax.legend(fontsize=12)
    ax.grid(alpha=0.3)
    _save(fig, out, "cost-vs-latency.png")


def plot_ab(ab: dict, guarded: dict, unguarded: dict, out: Path) -> None:
    mg, mu = summarize(guarded["results"]), summarize(unguarded["results"])
    fig, axes = plt.subplots(1, 3, figsize=(16, 9))
    metrics = [
        ("Taxa de sucesso (%)", mg["success_rate"] * 100, mu["success_rate"] * 100, "{:.1f}"),
        ("p95 (s)", mg["p95_latency_s"], mu["p95_latency_s"], "{:.1f}"),
        ("Custo/tarefa (mUS$)", mg["cost_per_task_usd"] * 1000,
         mu["cost_per_task_usd"] * 1000, "{:.2f}"),
    ]
    for ax, (title, g, u, fmt) in zip(axes, metrics, strict=True):
        bars = ax.bar(["unguarded", "guarded"], [u, g], color=[COLORS["unguarded"],
                                                              COLORS["guarded"]])
        for bar, value in zip(bars, [u, g], strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, value, fmt.format(value),
                    ha="center", va="bottom", fontsize=15)
        ax.set_title(title, fontsize=16)
        ax.grid(axis="y", alpha=0.3)
        ax.margins(y=0.15)
    s = ab["success_rate"]
    fig.suptitle(
        f"A/B pareado · Δ sucesso {s['diff']:+.1%} "
        f"(IC95 {s['ci95'][0]:+.1%} a {s['ci95'][1]:+.1%}) · McNemar p={s['mcnemar_p']:.3f}",
        fontsize=17,
    )
    _save(fig, out, "ab-summary.png")


def plot_citations(guarded: dict, unguarded: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    arms = ["unguarded", "guarded"]
    payloads = {"unguarded": unguarded, "guarded": guarded}
    support, aborts, totals = [], [], []
    for arm in arms:
        res = payloads[arm]["results"]
        cited = sum(r["citations_supported"] for r in res)
        total = sum(r["citations_total"] for r in res)
        support.append(cited / total * 100 if total else 0)
        aborts.append(sum(1 for r in res if r["aborted"]))
        totals.append(len(res))
    x = range(len(arms))
    ax.bar(x, support, color=[COLORS[a] for a in arms], width=0.5)
    for i, (value, aborted, total) in enumerate(zip(support, aborts, totals, strict=True)):
        ax.text(i, value + 1.5, f"{value:.1f}%", ha="center", fontsize=15)
        ax.text(i, 3, f"{aborted}/{total} abortadas", ha="center", fontsize=13, color="white")
    ax.set_xticks(list(x))
    ax.set_xticklabels(["unguarded", "guarded"], fontsize=14)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Citações com URL realmente coletada (%)", fontsize=14)
    ax.set_title("Verificação de citações e abortos por guarda", fontsize=18)
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out, "citations-and-aborts.png")


def main(inp: Path = typer.Option(Path("bench-out"), "--in"),
         out: Path = typer.Option(Path("docs/img"), "--out")) -> None:
    guarded = json.loads((inp / "run-guarded.json").read_text(encoding="utf-8"))
    unguarded = json.loads((inp / "run-unguarded.json").read_text(encoding="utf-8"))
    ab_path = inp / "ab.json"
    out.mkdir(parents=True, exist_ok=True)
    print(f"gerando gráficos em {out}")
    plot_categories(guarded, unguarded, out)
    plot_latency(guarded, unguarded, out)
    plot_cost_scatter(guarded, unguarded, out)
    plot_citations(guarded, unguarded, out)
    if ab_path.exists():
        plot_ab(json.loads(ab_path.read_text(encoding="utf-8")), guarded, unguarded, out)


if __name__ == "__main__":
    typer.run(main)
