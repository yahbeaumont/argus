from bench.gate import check, summarize, verdict

BASE = {
    "metrics": {"success_rate": 0.80, "p95_latency_s": 60.0, "loop_aborts": 2.0,
                "cost_per_task_usd": 0.05},
    "tolerance": {"success_rate": 0.05, "p95_latency_s": 10.0, "loop_aborts": 1.0,
                  "cost_per_task_usd": 0.01},
}


def _results(passed: int, latency: float, cost: float, aborted: int = 0) -> list[dict]:
    rows = [{"id": f"t{i}", "category": "x", "passed": i < passed, "latency_s": latency,
             "cost_usd": cost, "aborted": i < aborted, "steps": 3,
             "citations_total": 2, "citations_supported": 2} for i in range(10)]
    return rows


def test_summarize_metrics():
    m = summarize(_results(8, 30.0, 0.01, aborted=2))
    assert m["success_rate"] == 0.8
    assert m["loop_aborts"] == 2.0
    assert m["cost_per_task_usd"] == 0.01
    assert m["citation_support"] == 1.0


def test_check_ignores_improvement():
    current = summarize(_results(10, 20.0, 0.01, aborted=0))
    assert check(BASE, current) == []


def test_check_flags_regression_beyond_tolerance():
    current = summarize(_results(5, 20.0, 0.01))
    failures = {f["metric"] for f in check(BASE, current)}
    assert "success_rate" in failures


def test_check_respects_tolerance():
    # 0,80 -> 0,78 piora 0,02, dentro da tolerância de 0,05
    current = summarize(_results(8, 60.0, 0.05))
    current["success_rate"] = 0.78
    assert check(BASE, current) == []


def test_verdict_lists_every_metric():
    current = summarize(_results(5, 200.0, 0.09))
    failures = check(BASE, current)
    payload = verdict(BASE, current, failures)
    assert payload["passed"] is False
    assert set(payload["metrics"]) == set(BASE["metrics"])
    assert payload["metrics"]["success_rate"]["ok"] is False
