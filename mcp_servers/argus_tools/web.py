import asyncio
import hashlib
import os
from pathlib import Path

import httpx
import trafilatura

CACHE = Path(os.getenv("ARGUS_CACHE", ".cache/web"))
TIMEOUT = 15.0
UA = "argus-agent/0.4 (+https://github.com/)"


def _cache_path(key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / hashlib.sha256(key.encode()).hexdigest()[:32]


async def search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    key = f"search:{query}:{max_results}"
    path = _cache_path(key)
    if path.exists():
        import json
        return json.loads(path.read_text())

    provider = os.getenv("SEARCH_PROVIDER", "ddg").lower()
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA},
                                 follow_redirects=True) as client:
        if provider == "tavily" and os.getenv("TAVILY_API_KEY"):
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": os.environ["TAVILY_API_KEY"], "query": query,
                      "max_results": max_results},
            )
            resp.raise_for_status()
            data = [
                {"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("content", "")}
                for r in resp.json().get("results", [])
            ]
        else:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": UA},
            )
            resp.raise_for_status()
            data = _parse_ddg(resp.text, max_results)

    import json
    path.write_text(json.dumps(data, ensure_ascii=False))
    return data


def _parse_ddg(html: str, limit: int) -> list[dict[str, str]]:
    from html.parser import HTMLParser
    from urllib.parse import parse_qs, unquote, urlparse

    class P(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.out: list[dict[str, str]] = []
            self.cur: dict[str, str] | None = None
            self.grab = ""

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "a" and "result__a" in (a.get("class") or ""):
                href = a.get("href", "")
                if "uddg=" in href:
                    href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
                self.cur = {"title": "", "url": href, "snippet": ""}
                self.grab = "title"
            elif tag == "a" and self.cur and "result__snippet" in (a.get("class") or ""):
                self.grab = "snippet"

        def handle_data(self, data):
            if self.cur and self.grab:
                self.cur[self.grab] += data

        def handle_endtag(self, tag):
            if tag == "a" and self.cur:
                self.grab = ""
                if self.cur["title"].strip() and self.cur["url"]:
                    self.out.append({k: v.strip() for k, v in self.cur.items()})
                self.cur = None

    parser = P()
    parser.feed(html)
    return parser.out[:limit]


async def fetch_text(url: str) -> str:
    key = f"page:{url}"
    path = _cache_path(key)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")

    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA},
                                 follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content) > 1_000_000:
            return "erro: página acima de 1 MB"
        html = resp.text

    text = await asyncio.to_thread(
        lambda: trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    )
    if not text.strip():
        return "erro: sem texto extraível"
    path.write_text(text, encoding="utf-8")
    return text
