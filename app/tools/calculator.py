from typing import Any

from mcp.server.mcpserver import MCPServer

from app.errors import AppError, ErrorCode
from app.registry import register_tool
from app.security.permissions import Permission

OPERATIONS = ("add", "subtract", "multiply", "divide")


async def calculate(operation: str, a: float, b: float) -> dict[str, Any]:
    """Do basic math on two numbers.

    operation must be one of: add, subtract, multiply, divide.
    """
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise AppError(ErrorCode.INVALID_INPUT, "Cannot divide by zero", False)
        result = a / b
    else:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            f"Unknown operation {operation!r}. Use one of: {', '.join(OPERATIONS)}",
            False,
        )
    return {"operation": operation, "a": a, "b": b, "result": result}


def register(mcp: MCPServer) -> None:
    register_tool(mcp, Permission.READ)(calculate)
