"""Cliente MCP persistente sobre stdio, com timeout por chamada."""

import asyncio
import json
import shlex
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)


class MCPToolbox:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> "MCPToolbox":
        s = get_settings()
        params = StdioServerParameters(
            command=s.mcp_command, args=shlex.split(s.mcp_args), env=None
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        listed = await self._session.list_tools()
        self._tools = {
            t.name: {"description": t.description, "schema": t.inputSchema}
            for t in listed.tools
        }
        log.info("mcp.ready", tools=sorted(self._tools))
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["schema"],
                },
            }
            for name, meta in self._tools.items()
        ]

    async def call(self, name: str, args: dict[str, Any],
                   timeout: float = 30.0) -> tuple[bool, str]:
        if self._session is None:
            return False, "sessão MCP não iniciada"
        if name not in self._tools:
            return False, f"ferramenta desconhecida: {name}"
        try:
            result = await asyncio.wait_for(self._session.call_tool(name, args), timeout)
        except TimeoutError:
            return False, f"timeout de {timeout}s em {name}"
        except Exception as exc:
            return False, f"falha em {name}: {exc}"

        parts = [getattr(block, "text", "") for block in result.content]
        text = "\n".join(p for p in parts if p)
        ok = not getattr(result, "isError", False)
        return ok, text or "(vazio)"


def summarize_observation(text: str, limit: int = 2500) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n…[{len(text) - limit} chars omitidos]"


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
