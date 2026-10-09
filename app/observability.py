"""Logging and metrics for every tool call. Secrets are never logged."""

import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger("devops_mcp")

_SECRET_KEY = re.compile(r"(key|token|secret|password|authorization|credential)", re.I)
_MAX_VALUE_LEN = 120

_metrics: dict[str, dict[str, float]] = defaultdict(
    lambda: {"calls": 0, "errors": 0, "total_latency_ms": 0.0}
)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def redact(args: dict[str, Any]) -> dict[str, Any]:
    """Mask secret-looking argument names and shorten long values."""
    safe: dict[str, Any] = {}
    for name, value in args.items():
        if _SECRET_KEY.search(name):
            safe[name] = "***"
        else:
            text = str(value)
            safe[name] = text if len(text) <= _MAX_VALUE_LEN else text[:_MAX_VALUE_LEN] + "..."
    return safe


def record_call(
    tool: str, user: str, args: dict[str, Any], error_code: str | None, latency_ms: float
) -> None:
    status = "ERROR" if error_code else "SUCCESS"
    m = _metrics[tool]
    m["calls"] += 1
    m["errors"] += 1 if error_code else 0
    m["total_latency_ms"] += latency_ms

    line = f"TOOL={tool} USER={user} STATUS={status} LATENCY={latency_ms:.0f}ms ARGS={redact(args)}"
    if error_code:
        line += f" ERROR={error_code}"
    logger.info(line)


def metrics_snapshot() -> dict[str, Any]:
    return {
        tool: {
            "calls": int(m["calls"]),
            "errors": int(m["errors"]),
            "avg_latency_ms": round(m["total_latency_ms"] / m["calls"], 1) if m["calls"] else 0,
        }
        for tool, m in _metrics.items()
    }
