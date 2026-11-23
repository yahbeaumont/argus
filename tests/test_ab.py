import pytest

from bench.ab import compare, to_markdown
from bench.ab_shared import bootstrap_diff, mcnemar_exact, paired


def _run(passed_ids: set[str], label: str) -> dict:
    results = [
        {"id": f"t{i}", "category": "compute", "passed": f"t{i}" in passed_ids,
         "latency_s": 10.0 + i, "cost_usd": 0.01, "aborted": False, "steps": 3,
         "citations_total": 2, "citations_supported": 2}
        for i in range(10)
    ]
    return {"label": label, "results": results}


def test_paired_only_common_ids():
    a = _run({"t1"}, "a")
    b = _run({"t1"}, "b")
    b["results"] = b["results"][:5]
    assert len(paired(a["results"], b["results"])) == 5


def test_bootstrap_diff_detects_separation():
    pairs = [("t1", True, False)] * 6 + [("t2", False, True)] * 4
    diff, lo, hi = bootstrap_diff(pairs, n_boot=500, seed=7)
    assert diff == pytest.approx(0.2)
    assert lo <= diff <= hi


def test_mcnemar_no_discordant_is_one():
    assert mcnemar_exact([("t1", True, True), ("t2", False, False)]) == 1.0


def test_mcnemar_flags_one_sided_discordance():
    pairs = [("t1", True, False)] * 9 + [("t2", False, True)] * 1
    assert mcnemar_exact(pairs) < 0.05


def test_compare_and_markdown():
    guarded = _run({f"t{i}" for i in range(8)}, "guarded")
    unguarded = _run({f"t{i}" for i in range(4)}, "unguarded")
    payload = compare(guarded, unguarded, n_boot=500, seed=7)
    assert payload["n_pairs"] == 10
    assert payload["success_rate"]["diff"] == pytest.approx(0.4)
    assert payload["discordant"]["guarded_only"] == 4
    md = to_markdown(payload)
    assert "A/B pareado" in md
    assert "| Sucesso |" in md
