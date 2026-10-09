"""MCP resources (read-only data a client can fetch) and prompts (reusable templates)."""

import asyncio
import json

from mcp.server.mcpserver import MCPServer

from app.observability import metrics_snapshot
from app.security.permissions import Permission, authorize
from app.services import task_service


def register(mcp: MCPServer) -> None:
    @mcp.resource("tasks://summary")
    async def tasks_summary() -> str:
        """Task counts grouped by status."""
        authorize(Permission.READ)
        return json.dumps(await asyncio.to_thread(task_service.summary))

    @mcp.resource("metrics://tools")
    async def tool_metrics() -> str:
        """Call counts, error counts and average latency per tool since the server started."""
        authorize(Permission.READ)
        return json.dumps(metrics_snapshot())

    @mcp.prompt()
    def triage_github_issues(owner: str, repo: str) -> str:
        """Ask the model to turn open GitHub issues into prioritised tasks."""
        return (
            f"Fetch the open issues of {owner}/{repo} with get_issues. Pick the ones that look "
            "high priority (bugs, security, regressions). For each, create a task with "
            "create_task using priority 'high' and the issue URL in the description. "
            "Finish with a short summary of what you created."
        )
