import pytest
from types import SimpleNamespace

from argus import llm


def test_cost_uses_price_table():
    # 1M tokens de entrada + 1M de saída no gpt-5-mini = 0,25 + 2,00
    assert llm.cost_usd("gpt-5-mini", 1_000_000, 1_000_000) == pytest.approx(2.25)


def test_unknown_model_costs_zero():
    assert llm.cost_usd("modelo-inexistente", 10_000, 10_000) == 0.0


def test_parse_json_accepts_fenced_block():
    assert llm.parse_json('texto antes ```json\n{"tool": "x"}\n```')["tool"] == "x"


def test_parse_json_rejects_non_object():
    with pytest.raises(llm.LLMError):
        llm.parse_json("[1, 2, 3]")


def test_parse_json_rejects_empty():
    with pytest.raises(llm.LLMError):
        llm.parse_json("")


def test_content_raises_on_null_choices():
    resp = SimpleNamespace(choices=None)
    with pytest.raises(llm.LLMError):
        llm._content(resp)


def test_tool_calls_are_extracted():
    fn = SimpleNamespace(name="web_search", arguments='{"query": "rag"}')
    resp = SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=None, tool_calls=[SimpleNamespace(function=fn)]))])
    assert llm._content(resp) == ""
    assert llm._tool_calls(resp)[0]["name"] == "web_search"
