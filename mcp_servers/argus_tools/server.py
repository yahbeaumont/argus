"""Servidor MCP (stdio) que expõe as ferramentas do argus."""

import asyncio
import json
import os
import sqlite3
from pathlib import Path

try:  # MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server
except ModuleNotFoundError:  # MCP SDK 2.x renomeou FastMCP para MCPServer
    from mcp.server.mcpserver import MCPServer as _Server

from argus_tools import sandbox, web
from argus_tools.files import guard_url

mcp = _Server("argus-tools")
DB_PATH = Path(os.getenv("ARGUS_DB", "bench/fixtures/seed.db"))
SEED_PATH = DB_PATH.with_name("seed.sql")
MAX_OUT = 8_000


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_OUT else text[:MAX_OUT] + "\n…[truncado]"


def ensure_db() -> None:
    """Cria a base de fixtures a partir do seed.sql quando ela ainda não existe."""
    if DB_PATH.exists() or not SEED_PATH.exists():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(SEED_PATH.read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """Busca na web. Retorna JSON com título, url e snippet."""
    results = await web.search(query, max_results=min(max_results, 10))
    return _truncate(json.dumps(results, ensure_ascii=False))


@mcp.tool()
async def fetch_page(url: str) -> str:
    """Extrai o texto principal de uma URL http(s)."""
    guard_url(url)
    text = await web.fetch_text(url)
    return _truncate(text)


@mcp.tool()
async def python_exec(code: str) -> str:
    """Executa Python puro (sem rede). Use para cálculo e parsing."""
    return _truncate(await asyncio.to_thread(sandbox.run, code))


@mcp.tool()
def sqlite_query(sql: str, limit: int = 500) -> str:
    """Executa SELECT somente-leitura na base de fixtures. Retorna JSON."""
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        return "erro: apenas SELECT/WITH"
    ensure_db()
    if not DB_PATH.exists():
        return "erro: base de fixtures ausente (rode make fixture)"
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql).fetchmany(min(limit, 500))
        return _truncate(json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str))
    except sqlite3.Error as exc:
        return f"erro sql: {exc}"
    finally:
        con.close()


@mcp.tool()
def calculator(expression: str) -> str:
    """Avalia expressão aritmética com precisão decimal."""
    from decimal import Decimal, InvalidOperation

    allowed = set("0123456789.+-*/()% ")
    if not set(expression) <= allowed:
        return "erro: caracteres inválidos"
    try:
        # expressão já filtrada por whitelist de caracteres; sem builtins
        return str(Decimal(str(eval(expression, {"__builtins__": {}}, {}))))
    except (InvalidOperation, ZeroDivisionError, SyntaxError) as exc:
        return f"erro: {exc}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
