"""The tool registry.

register_tool() is the single door every tool goes through. It:
  1. checks authentication + permission (server-side, LLM cannot bypass)
  2. runs the tool
  3. converts any error into the structured error envelope
  4. logs and measures the call
  5. tells MCP clients whether the tool is read-only / destructive (annotations)
"""

import functools
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.errors import AppError, ErrorCode, fail, ok
from app.observability import record_call
from app.security.permissions import Permission, authorize, current_user

log = logging.getLogger("devops_mcp")

ANNOTATIONS = {
    Permission.READ: ToolAnnotations(read_only_hint=True),
    Permission.WRITE: ToolAnnotations(read_only_hint=False, destructive_hint=False),
    Permission.DESTRUCTIVE: ToolAnnotations(read_only_hint=False, destructive_hint=True),
}

ToolFn = Callable[..., Awaitable[Any]]


def guarded(permission: Permission) -> Callable[[ToolFn], ToolFn]:
    def decorator(fn: ToolFn) -> ToolFn:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            started = time.perf_counter()
            user, error_code = current_user(), None
            try:
                user = authorize(permission)
                result = ok(await fn(*args, **kwargs))
            except AppError as exc:
                error_code, result = exc.code.value, fail(exc)
            except Exception:
                log.exception("Unhandled error in tool %s", fn.__name__)
                error = AppError(ErrorCode.UNKNOWN_ERROR, "Unexpected server error", False)
                error_code, result = error.code.value, fail(error)
            record_call(fn.__name__, user, kwargs, error_code, (time.perf_counter() - started) * 1000)
            return result

        # The MCP schema comes from fn's parameters; the return is always the envelope dict.
        wrapper.__signature__ = inspect.signature(fn).replace(return_annotation=dict[str, Any])  # type: ignore[attr-defined]
        return wrapper

    return decorator


def register_tool(mcp: MCPServer, permission: Permission) -> Callable[[ToolFn], ToolFn]:
    def decorator(fn: ToolFn) -> ToolFn:
        wrapped = guarded(permission)(fn)
        mcp.tool(annotations=ANNOTATIONS[permission])(wrapped)
        return wrapped

    return decorator
