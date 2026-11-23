from argus import citations


def test_normalize_strips_www_fragment_and_slash():
    assert citations.normalize("https://www.Example.com/a/#x") == "https://example.com/a"


def test_verify_counts_supported_and_unsupported():
    report = "Veja https://example.com/a e https://inventado.dev/b."
    findings = ["[fetch_page] https://example.com/a\nconteúdo"]
    total, supported, unsupported = citations.verify(report, findings)
    assert total == 2
    assert supported == 1
    assert unsupported == ["https://inventado.dev/b"]


def test_verify_without_citations_is_neutral():
    assert citations.verify("relatório sem link", []) == (0, 0, [])
