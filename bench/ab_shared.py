"""Estatística compartilhada do A/B: resumo, bootstrap pareado e McNemar exato."""

import json
import math
import random
from pathlib import Path

from argus.telemetry import percentile


def load_run(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summarize(results: list[dict]) -> dict[str, float]:
    n = len(results) or 1
    latencies = [r["latency_s"] for r in results]
    cited = sum(r.get("citations_supported", 0) for r in results)
    total = sum(r.get("citations_total", 0) for r in results)
    return {
        "tasks": len(results),
        "success_rate": sum(bool(r["passed"]) for r in results) / n,
        "p50_latency_s": percentile(latencies, 50),
        "p95_latency_s": percentile(latencies, 95),
        "loop_aborts": float(sum(bool(r.get("aborted")) for r in results)),
        "cost_per_task_usd": sum(r["cost_usd"] for r in results) / n,
        "cost_total_usd": sum(r["cost_usd"] for r in results),
        "mean_steps": sum(r.get("steps", 0) for r in results) / n,
        "citation_support": cited / total if total else 1.0,
    }


def paired(a: list[dict], b: list[dict]) -> list[tuple[str, bool, bool]]:
    """Pareia por id de tarefa: só entra o que rodou nos dois braços."""
    index_b = {r["id"]: bool(r["passed"]) for r in b}
    return [(r["id"], bool(r["passed"]), index_b[r["id"]]) for r in a if r["id"] in index_b]


def bootstrap_diff(
    pairs: list[tuple[str, bool, bool]], n_boot: int = 10_000, seed: int = 1337
) -> tuple[float, float, float]:
    """Diferença de taxa de sucesso (a - b) com IC95 por bootstrap pareado."""
    if not pairs:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(pairs)
    observed = sum(a for _, a, _ in pairs) / n - sum(b for _, _, b in pairs) / n
    deltas = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        deltas.append(sum(a for _, a, _ in sample) / n - sum(b for _, _, b in sample) / n)
    deltas.sort()
    lo = deltas[int(0.025 * (n_boot - 1))]
    hi = deltas[int(0.975 * (n_boot - 1))]
    return observed, lo, hi


def mcnemar_exact(pairs: list[tuple[str, bool, bool]]) -> float:
    """p-valor bicaudal exato para pares discordantes (distribuição binomial)."""
    b = sum(1 for _, a, c in pairs if a and not c)
    c = sum(1 for _, a, d in pairs if d and not a)
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def by_category(results: list[dict]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for r in results:
        bucket = out.setdefault(r["category"], [0, 0])
        bucket[0] += bool(r["passed"])
        bucket[1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}
