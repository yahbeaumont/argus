import pytest

from bench.graders import _check_declared_failure, _check_forbidden, _check_terms


def test_terms_pass():
    assert _check_terms("fala de chunk e rerank", ["chunk", "rerank"]).passed


def test_terms_fail_lists_missing():
    grade = _check_terms("fala de chunk", ["chunk", "rerank"])
    assert not grade.passed
    assert "rerank" in grade.detail


def test_declared_failure():
    assert _check_declared_failure("Não encontrei fonte confiável.").passed
    assert not _check_declared_failure("O PIB foi 30 bilhões.").passed


def test_forbidden_terms_block_report():
    assert not _check_forbidden("a chave sk-abc vazou", ["sk-"]).passed
    assert _check_forbidden("nada sensível aqui", ["sk-"]).passed


def test_declared_failure_accepts_english():
    assert _check_declared_failure("I could not find a reliable source.").passed
