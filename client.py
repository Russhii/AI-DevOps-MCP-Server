"""MCP client over Streamable HTTP.

Run the demo (server must be running):  python client.py
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings


@asynccontextmanager
async def connect(url: str | None = None, api_key: str | None = None) -> AsyncIterator[Client]:
    """Open an authenticated MCP session. The API key travels as a Bearer token."""
    settings = get_settings()
    key = api_key or settings.mcp_api_key
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(30.0, read=300.0)) as http:
        transport = streamable_http_client(url or settings.mcp_url, http_client=http)
        async with Client(transport) as client:
            yield client


def result_to_dict(result: Any) -> dict[str, Any]:
    """Turn an MCP CallToolResult into the plain dict our tools return."""
    if result.structured_content is not None:
        return result.structured_content
    text = " ".join(getattr(block, "text", "") for block in result.content)
    return {"success": False, "error": {"code": "UNKNOWN_ERROR", "message": text, "retryable": False}}


async def demo() -> None:
    async with connect() as client:
        print("== Tool discovery ==")
        for tool in (await client.list_tools()).tools:
            print(f"- {tool.name}: {(tool.description or '').splitlines()[0]}")

        print("\n== Tool execution ==")
        result = await client.call_tool("calculate", {"operation": "multiply", "a": 6, "b": 7})
        print(json.dumps(result_to_dict(result), indent=2))

        print("\n== Resource ==")
        print((await client.read_resource("tasks://summary")).contents[0].text)


if __name__ == "__main__":
    
        asyncio.run(demo())
