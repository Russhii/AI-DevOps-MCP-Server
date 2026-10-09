from typing import Any

from mcp.server.mcpserver import MCPServer

from app.registry import register_tool
from app.security.permissions import Permission
from app.services import docker_service


async def list_containers(include_stopped: bool = False) -> dict[str, Any]:
    """List Docker containers on the server. Set include_stopped=true to include stopped ones."""
    return {"containers": await docker_service.list_containers(include_stopped)}


async def container_logs(name: str, tail: int = 50) -> dict[str, Any]:
    """Get the last `tail` (1-500) log lines of a Docker container, by name or id."""
    return {"container": name, "logs": await docker_service.container_logs(name, tail)}


async def inspect_container(name: str) -> dict[str, Any]:
    """Inspect detailed configuration, status, ports, and health of a Docker container by name or id."""
    return {"container": await docker_service.inspect_container(name)}


async def container_stats(name: str | None = None) -> dict[str, Any]:
    """Get live CPU %, memory usage/limit, and network I/O statistics for containers."""
    return {"stats": await docker_service.container_stats(name)}


def register(mcp: MCPServer) -> None:
    register_tool(mcp, Permission.READ)(list_containers)
    register_tool(mcp, Permission.READ)(container_logs)
    register_tool(mcp, Permission.READ)(inspect_container)
    register_tool(mcp, Permission.READ)(container_stats)
