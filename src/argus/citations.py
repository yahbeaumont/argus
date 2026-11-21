"""Verifica se as URLs citadas no relatório vieram das evidências realmente coletadas.

O writer pode inventar um link plausível. Aqui comparamos cada URL do relatório com as
URLs que apareceram nas observações das ferramentas: sem essa checagem, "citou fonte"
e "citou fonte real" seriam a mesma coisa no benchmark.
"""

import re
from urllib.parse import urlsplit, urlunsplit

URL = re.compile(r"https?://[^\s)\]<>\"'`]+")
TRAILING = ".,;:!?"


def normalize(url: str) -> str:
    url = url.rstrip(TRAILING)
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, "", ""))


def extract_urls(text: str) -> set[str]:
    return {normalize(u) for u in URL.findall(text)}


def verify(report: str, findings: list[str]) -> tuple[int, int, list[str]]:
    """Devolve (citadas, suportadas, não suportadas)."""
    cited = extract_urls(report)
    collected = extract_urls("\n".join(findings))
    unsupported = sorted(u for u in cited if u not in collected)
    return len(cited), len(cited) - len(unsupported), unsupported
