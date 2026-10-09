import os
import platform
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.registry import register_tool
from app.security.permissions import Permission


async def system_info() -> dict[str, Any]:
    """Return operating system, Python version, CPU count and platform of the server."""
    return {
        "operating_system": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "platform": platform.platform(),
    }


def register(mcp: MCPServer) -> None:
    register_tool(mcp, Permission.READ)(system_info)
