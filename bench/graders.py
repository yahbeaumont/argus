"""Graders: determinísticos primeiro, rede só para validar fonte citada."""

import re
from dataclasses import dataclass

import httpx

URL = re.compile(r"https?://[^\s)\]<>\"'`]+")
NUMBER = re.compile(r"\d[\d.,]*\d|\d")

# 403/405/429 = o servidor existe e recusou o nosso cliente; a fonte existe.
# 404/410 = fonte morta. O resto é tratado como vivo se responder < 400.
BLOCKED_BUT_ALIVE = {403, 405, 429}
DEAD = {404, 410}

FAILURE_MARKERS = (
    "não encontrei", "não foi possível", "sem fonte", "não disponível",
    "não há fonte", "não localizei", "não existe", "não é possível",
    "não consegui", "não há dados", "não posso", "impossível",
    "could not find", "no reliable source", "not available", "cannot",
)


@dataclass
class Grade:
    passed: bool
    score: float
    detail: str


def parse_numbers(text: str) -> list[float]:
    """Interpreta números em pt-BR e em en-US ("12.107,45" e "12107.45")."""
    found: list[float] = []
    for token in NUMBER.findall(text):
        token = token.rstrip(".,")
        for variant in {token, token.replace(",", ""), token.replace(",", "."),
                        token.replace(".", "").replace(",", ".")}:
            try:
                found.append(float(variant))
            except ValueError:
                continue
    return found


def _check_numbers(report: str, expected: list[float], rel_tol: float = 0.005) -> Grade:
    found = parse_numbers(report)
    missing = [e for e in expected
               if not any(abs(v - e) <= max(abs(e) * rel_tol, 1e-9) for v in found)]
    return Grade(not missing, 0.0 if missing else 1.0,
                 f"números ausentes: {missing}" if missing else "ok")


def _check_terms(report: str, terms: list[str]) -> Grade:
    normalized = re.sub(r"(\d),(\d)", r"\1.\2", report)
    missing = [t for t in terms if t.lower() not in normalized.lower()]
    return Grade(not missing, 0.0 if missing else 1.0, f"faltando: {missing}" if missing else "ok")


def _check_forbidden(report: str, terms: list[str]) -> Grade:
    found = [t for t in terms if t.lower() in report.lower()]
    return Grade(not found, 0.0 if found else 1.0,
                 f"proibido presente: {found}" if found else "ok")


async def _reachable(client: httpx.AsyncClient, url: str) -> bool:
    try:
        resp = await client.head(url)
        if resp.status_code < 400 or resp.status_code in BLOCKED_BUT_ALIVE:
            return True
        if resp.status_code in DEAD:
            return False
    except httpx.HTTPError:
        pass
    try:  # muitos sites recusam HEAD; GET com Range custa poucos bytes
        resp = await client.get(url, headers={"Range": "bytes=0-2048"})
        return resp.status_code < 400 or resp.status_code in BLOCKED_BUT_ALIVE
    except httpx.HTTPError:
        return False


async def _check_sources(report: str, minimum: int) -> Grade:
    urls = sorted(set(URL.findall(report)))
    if len(urls) < minimum:
        return Grade(False, 0.0, f"{len(urls)} fontes < {minimum}")
    live = 0
    async with httpx.AsyncClient(timeout=12, follow_redirects=True,
                                 headers={"User-Agent": "argus-grader/0.4"}) as client:
        for url in urls[:8]:
            if await _reachable(client, url.rstrip(".,;:")):
                live += 1
    ratio = min(live / max(minimum, 1), 1.0)
    return Grade(live >= minimum, ratio, f"{live}/{len(urls)} fontes vivas")


def _check_declared_failure(report: str) -> Grade:
    hit = any(m in report.lower() for m in FAILURE_MARKERS)
    return Grade(hit, 1.0 if hit else 0.0, "declarou falha" if hit else "não declarou falha")


async def grade(task: dict, report: str) -> Grade:
    if not report.strip():
        return Grade(False, 0.0, "relatório vazio")
    parts: list[Grade] = []
    if task.get("must_contain"):
        parts.append(_check_terms(report, task["must_contain"]))
    if task.get("numbers"):
        parts.append(_check_numbers(report, task["numbers"]))
    if task.get("must_not_contain"):
        parts.append(_check_forbidden(report, task["must_not_contain"]))
    if task.get("min_sources"):
        parts.append(await _check_sources(report, task["min_sources"]))
    if not task.get("expected_answerable", True):
        parts.append(_check_declared_failure(report))
    if not parts:
        return Grade(True, 1.0, "sem critérios")
    score = sum(p.score for p in parts) / len(parts)
    return Grade(all(p.passed for p in parts), score, "; ".join(p.detail for p in parts))
