"""Security tests against a real Streamable HTTP server with API-key auth switched on."""

import socket
import threading
import time

import pytest
import uvicorn

from client import connect


@pytest.fixture(scope="module")
def server_url():
    mp = pytest.MonkeyPatch()
    mp.setenv("REQUIRE_AUTH", "true")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    mp.setenv("PORT", str(port))

    from app.server import create_server

    app = create_server().streamable_http_app()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)
    mp.undo()


async def call(url, key, tool, args):
    async with connect(url, key) as client:
        return (await client.call_tool(tool, args)).structured_content


async def test_missing_or_invalid_key_is_rejected(server_url):
    for key in (None, "wrong-key"):
        with pytest.raises(Exception):
            async with connect(server_url, key) as client:
                await client.list_tools()


async def test_read_key_can_read_but_not_write(server_url):
    assert (await call(server_url, "viewer-key", "system_info", {}))["success"] is True
    denied = await call(server_url, "viewer-key", "create_task", {"title": "x"})
    assert denied["error"]["code"] == "AUTHORIZATION_ERROR"


async def test_write_key_cannot_delete(server_url):
    created = await call(server_url, "writer-key", "create_task", {"title": "x"})
    denied = await call(server_url, "writer-key", "delete_task", {"task_id": created["data"]["id"], "confirm": True})
    assert denied["error"]["code"] == "AUTHORIZATION_ERROR"


async def test_delete_requires_confirmation(server_url):
    created = await call(server_url, "admin-key", "create_task", {"title": "keep me"})
    task_id = created["data"]["id"]

    unconfirmed = await call(server_url, "admin-key", "delete_task", {"task_id": task_id})
    assert unconfirmed["error"]["code"] == "CONFIRMATION_REQUIRED"
    still_there = await call(server_url, "admin-key", "get_tasks", {})
    assert task_id in [t["id"] for t in still_there["data"]["tasks"]]

    confirmed = await call(server_url, "admin-key", "delete_task", {"task_id": task_id, "confirm": True})
    assert confirmed["success"] is True
