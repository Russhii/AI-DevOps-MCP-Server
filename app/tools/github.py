from typing import Any

from mcp.server.mcpserver import MCPServer

from app.config import get_settings
from app.registry import register_tool
from app.security.permissions import Permission
from app.services.github_service import GitHubService


def _service() -> GitHubService:
    return GitHubService(token=get_settings().github_token)


async def search_github(query: str, limit: int = 5) -> dict[str, Any]:
    """Search public GitHub repositories, most-starred first.

    query: GitHub search text, e.g. "fastapi language:python". limit: 1-30.
    """
    return {"repositories": await _service().search_repositories(query, limit)}


async def get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get details (stars, forks, language, license, open issues) of one GitHub repository."""
    return await _service().get_repository(owner, repo)


async def get_issues(
    owner: str, repo: str, state: str = "open", labels: str | None = None, limit: int = 10
) -> dict[str, Any]:
    """List issues of a GitHub repository (pull requests are excluded).

    state: open, closed or all. labels: comma-separated label names, e.g. "bug,high-priority".
    limit: 1-30.
    """
    return {"issues": await _service().get_issues(owner, repo, state, labels, limit)}


def register(mcp: MCPServer) -> None:
    for fn in (search_github, get_repository, get_issues):
        register_tool(mcp, Permission.READ)(fn)
