import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.errors import AppError, ErrorCode
from app.registry import register_tool
from app.security.permissions import Permission
from app.services import task_service


async def create_task(title: str, description: str = "", priority: str = "medium") -> dict[str, Any]:
    """Create a task. priority must be low, medium or high. New tasks start as pending."""
    return await asyncio.to_thread(task_service.create_task, title, description, priority)


async def get_tasks(status: str | None = None, priority: str | None = None) -> dict[str, Any]:
    """List tasks, optionally filtered.

    status: pending, in_progress or completed. priority: low, medium or high.
    """
    return {"tasks": await asyncio.to_thread(task_service.list_tasks, status, priority)}


async def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Update fields of an existing task. Only the fields you pass are changed.

    priority: low, medium or high. status: pending, in_progress or completed.
    """
    return await asyncio.to_thread(
        task_service.update_task,
        task_id, title=title, description=description, priority=priority, status=status,
    )


async def delete_task(task_id: int, confirm: bool = False) -> dict[str, Any]:
    """Permanently delete a task. DESTRUCTIVE.

    Without confirm=true nothing is deleted and CONFIRMATION_REQUIRED is returned.
    Set confirm=true only after the human user has explicitly agreed to the deletion.
    """
    task = await asyncio.to_thread(task_service.get_task, task_id)  # also checks it exists
    if not confirm:
        raise AppError(
            ErrorCode.CONFIRMATION_REQUIRED,
            f"Deleting task {task_id} ('{task['title']}') is permanent. "
            "Ask the user to confirm, then call delete_task again with confirm=true.",
            False,
        )
    await asyncio.to_thread(task_service.delete_task, task_id)
    return {"deleted_task_id": task_id}


def register(mcp: MCPServer) -> None:
    register_tool(mcp, Permission.READ)(get_tasks)
    register_tool(mcp, Permission.WRITE)(create_task)
    register_tool(mcp, Permission.WRITE)(update_task)
    register_tool(mcp, Permission.DESTRUCTIVE)(delete_task)
