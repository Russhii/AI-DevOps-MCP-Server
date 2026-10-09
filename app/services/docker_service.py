"""Read-only Docker access through the docker CLI (no extra dependency)."""

import asyncio
import json
import re
from typing import Any

from app.errors import AppError, ErrorCode

_CONTAINER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MAX_OUTPUT = 5000


async def _docker(*args: str, timeout: float = 10.0) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
    except FileNotFoundError:
        raise AppError(ErrorCode.EXTERNAL_API_ERROR, "Docker CLI is not installed on the server", False) from None
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise AppError(ErrorCode.TIMEOUT, "Docker command timed out", True) from None
    text = out.decode(errors="replace")
    if proc.returncode != 0:
        raise AppError(ErrorCode.EXTERNAL_API_ERROR, f"Docker error: {text.strip()[:300]}", False)
    return text


async def list_containers(include_stopped: bool = False) -> list[dict[str, Any]]:
    args = ["ps", "--format", "{{json .}}"] + (["-a"] if include_stopped else [])
    rows = [json.loads(line) for line in (await _docker(*args)).splitlines() if line.strip()]
    return [
        {"id": r.get("ID"), "name": r.get("Names"), "image": r.get("Image"),
         "state": r.get("State"), "status": r.get("Status")}
        for r in rows
    ]


async def container_logs(name: str, tail: int = 50) -> str:
    if not _CONTAINER.match(name):
        raise AppError(ErrorCode.INVALID_INPUT, f"Invalid container name: {name!r}", False)
    if not 1 <= tail <= 500:
        raise AppError(ErrorCode.INVALID_INPUT, "tail must be between 1 and 500", False)
    return (await _docker("logs", "--tail", str(tail), name))[-_MAX_OUTPUT:]


async def inspect_container(name: str) -> dict[str, Any]:
    if not _CONTAINER.match(name):
        raise AppError(ErrorCode.INVALID_INPUT, f"Invalid container name: {name!r}", False)
    raw = await _docker("inspect", name)
    try:
        data = json.loads(raw)
        if not data:
            raise AppError(ErrorCode.INVALID_INPUT, f"Container {name!r} not found", False)
        info = data[0]
        state = info.get("State", {})
        return {
            "id": info.get("Id", "")[:12],
            "name": info.get("Name", "").lstrip("/"),
            "image": info.get("Config", {}).get("Image"),
            "created": info.get("Created"),
            "status": state.get("Status"),
            "running": state.get("Running"),
            "started_at": state.get("StartedAt"),
            "restart_count": info.get("RestartCount", 0),
            "ports": info.get("NetworkSettings", {}).get("Ports", {}),
            "health": state.get("Health", {}).get("Status") if "Health" in state else None,
        }
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        raise AppError(ErrorCode.EXTERNAL_API_ERROR, f"Failed to parse inspect output: {exc}", False)


async def container_stats(name: str | None = None) -> list[dict[str, Any]]:
    args = ["stats", "--no-stream", "--format", "{{json .}}"]
    if name:
        if not _CONTAINER.match(name):
            raise AppError(ErrorCode.INVALID_INPUT, f"Invalid container name: {name!r}", False)
        args.append(name)
    raw = await _docker(*args, timeout=15.0)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    return [
        {
            "id": r.get("ID"),
            "name": r.get("Name"),
            "cpu_perc": r.get("CPUPerc"),
            "mem_usage": r.get("MemUsage"),
            "mem_perc": r.get("MemPerc"),
            "net_io": r.get("NetIO"),
            "block_io": r.get("BlockIO"),
            "pids": r.get("PIDs"),
        }
        for r in rows
    ]
