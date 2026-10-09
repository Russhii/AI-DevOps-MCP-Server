import json

EXPECTED = {
    "calculate", "search_github", "get_repository", "get_issues", "get_tasks", "create_task",
    "update_task", "delete_task", "list_containers", "container_logs", "inspect_container",
    "container_stats", "system_info",
}


async def test_tool_discovery(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == EXPECTED
    assert tools["delete_task"].annotations.destructive_hint is True
    assert tools["get_tasks"].annotations.read_only_hint is True


async def test_tool_execution(client):
    result = await client.call_tool("calculate", {"operation": "add", "a": 2, "b": 3})
    assert result.structured_content == {
        "success": True, "data": {"operation": "add", "a": 2.0, "b": 3.0, "result": 5.0}
    }


async def test_structured_error(client):
    result = (await client.call_tool("calculate", {"operation": "divide", "a": 1, "b": 0})).structured_content
    assert result["success"] is False
    assert result["error"] == {"code": "INVALID_INPUT", "message": "Cannot divide by zero", "retryable": False}


async def test_invalid_tool(client):
    result = await client.call_tool("does_not_exist", {})
    assert result.is_error


async def test_invalid_arguments(client):
    result = await client.call_tool("calculate", {"operation": "add", "a": "abc", "b": 1})
    assert result.is_error


async def test_invalid_enum_value_is_structured(client):
    result = (await client.call_tool("create_task", {"title": "x", "priority": "urgent"})).structured_content
    assert result["error"]["code"] == "INVALID_INPUT"


async def test_system_info(client):
    data = (await client.call_tool("system_info", {})).structured_content["data"]
    assert {"operating_system", "python_version", "cpu_count", "platform"} <= set(data)


async def test_resource_and_prompt(client):
    await client.call_tool("create_task", {"title": "a"})
    summary = json.loads((await client.read_resource("tasks://summary")).contents[0].text)
    assert summary["total"] == 1
    prompts = {p.name for p in (await client.list_prompts()).prompts}
    assert "triage_github_issues" in prompts
