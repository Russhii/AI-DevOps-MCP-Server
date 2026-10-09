"""Permissions: every tool is READ, WRITE or DESTRUCTIVE.

A tool can only run if the caller's API key carries that scope.
The check happens on the server, so the LLM cannot talk its way around it.
"""

from enum import StrEnum

from mcp.server.auth.middleware.auth_context import get_access_token

from app.config import get_settings
from app.errors import AppError, ErrorCode


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


def current_user() -> str:
    token = get_access_token()
    return token.client_id if token else "anonymous"


def authorize(permission: Permission) -> str:
    """Return the caller's name, or raise AUTHENTICATION/AUTHORIZATION_ERROR."""
    if not get_settings().require_auth:
        return "local-dev"  # auth switched off for local experiments / tests

    token = get_access_token()
    if token is None:
        raise AppError(ErrorCode.AUTHENTICATION_ERROR, "Authentication required", False)
    if permission.value not in token.scopes:
        raise AppError(
            ErrorCode.AUTHORIZATION_ERROR,
            f"API key '{token.client_id}' lacks the '{permission.value}' permission",
            False,
        )
    return token.client_id
