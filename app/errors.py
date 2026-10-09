"""Structured errors shared by every tool.

Tools never return raw exceptions. They raise AppError, and the registry
turns it into a predictable JSON envelope:

    {"success": false, "error": {"code": "...", "message": "...", "retryable": bool}}
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"                    # user error: fix the arguments
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"      # who are you?
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"        # you may not do this
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TIMEOUT = "TIMEOUT"                                # transient, retry
    RATE_LIMITED = "RATE_LIMITED"                      # transient, retry later
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"          # GitHub / Docker failed
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"    # human must approve first
    UNKNOWN_ERROR = "UNKNOWN_ERROR"                    # server bug


# Transient problems are worth retrying; everything else needs a different request.
_RETRYABLE_BY_DEFAULT = {ErrorCode.TIMEOUT, ErrorCode.RATE_LIMITED}


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str, retryable: bool | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = code in _RETRYABLE_BY_DEFAULT if retryable is None else retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "retryable": self.retryable}


def ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def fail(error: AppError) -> dict[str, Any]:
    return {"success": False, "error": error.to_dict()}
