#!/usr/bin/env bash
# Reproduz a medição do argus: bench nos dois braços, A/B pareado, gate e gráficos.
# Requer .env com OPENAI_API_KEY (e TAVILY_API_KEY se SEARCH_PROVIDER=tavily).
set -euo pipefail
cd "$(dirname "$0")/.."
stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
mkdir -p bench-out docs/img

echo "[$(stamp)] bench guarded (40 tarefas)"
python -m bench.run_bench --out bench-out --concurrency "${CONCURRENCY:-3}"

echo "[$(stamp)] bench unguarded (braço de controle)"
python -m bench.run_bench --no-guards --out bench-out --concurrency "${CONCURRENCY:-3}"

echo "[$(stamp)] A/B pareado"
python -m bench.ab --out bench-out/ab.json

echo "[$(stamp)] gráficos"
python scripts/plot_results.py --in bench-out --out docs/img

echo "[$(stamp)] gate (sai com 1 se houver regressão)"
python -m bench.gate --run bench-out/run-guarded.json --baseline bench/baseline.json \
  --verdict bench-out/verdict.json || echo "gate: regressão detectada (ver bench-out/verdict.md)"

echo "[$(stamp)] fim"
