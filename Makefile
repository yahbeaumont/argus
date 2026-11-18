.PHONY: install fixture smoke bench bench-unguarded ab gate verdict plots reproduce promote test lint fmt clean

install:
	pip install -e ".[dev]"

fixture:
	python -c "from argus_tools.server import ensure_db; ensure_db()"

smoke:
	python -m bench.run_bench --limit 3 --out bench-out/smoke

bench:
	python -m bench.run_bench --out bench-out

bench-unguarded:
	python -m bench.run_bench --no-guards --out bench-out

ab:
	python -m bench.ab --out bench-out/ab.json

gate:
	python -m bench.gate --run bench-out/run-guarded.json --baseline bench/baseline.json

verdict:
	python -m bench.gate --run bench-out/run-guarded.json --baseline bench/baseline.json \
	  --verdict bench-out/verdict.json

plots:
	python scripts/plot_results.py --in bench-out --out docs/img

reproduce:
	./scripts/reproduce.sh

promote:
	python -m bench.gate --run bench-out/run-guarded.json --baseline bench/baseline.json \
	  --update-baseline

test:
	pytest -q

lint:
	ruff check src bench mcp_servers tests scripts && mypy src

fmt:
	ruff format src bench mcp_servers tests scripts

clean:
	rm -rf bench-out .pytest_cache .ruff_cache .mypy_cache .cache
