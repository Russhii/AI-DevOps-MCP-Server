"""Agent tests with a scripted fake LLM (no network, no API key)."""

import json
from types import SimpleNamespace

from agent import Agent


def call(name, args, call_id="c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def reply(content=None, calls=None):
    return SimpleNamespace(content=content, tool_calls=calls or None)


class FakeLLM:
    """Returns pre-scripted assistant messages and records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.seen.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=self.script.pop(0))])


async def make_agent(client, script, approve=lambda *_: True):
    agent = Agent(client, FakeLLM(script), "fake-model", approve=approve)
    await agent.load_tools()
    return agent


async def test_tools_come_from_mcp_discovery(client):
    agent = await make_agent(client, [reply("hi")])
    names = {t["function"]["name"] for t in agent.tools}
    assert "create_task" in names and agent.destructive == {"delete_task"}


async def test_single_tool_call_then_answer(client):
    agent = await make_agent(client, [reply(calls=[call("calculate", {"operation": "add", "a": 1, "b": 2})]), reply("It is 3.")])
    assert await agent.chat("1+2?") == "It is 3."
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert json.loads(tool_msg["content"])["data"]["result"] == 3.0


async def test_multiple_sequential_tool_calls(client):
    script = [
        reply(calls=[call("create_task", {"title": "one"}, "a"), call("create_task", {"title": "two"}, "b")]),
        reply(calls=[call("get_tasks", {}, "c")]),
        reply("Created two tasks."),
    ]
    agent = await make_agent(client, script)
    assert await agent.chat("make two tasks") == "Created two tasks."
    assert len([m for m in agent.messages if m["role"] == "tool"]) == 3


async def test_tool_failure_is_reported_to_llm(client):
    script = [
        reply(calls=[call("calculate", {"operation": "divide", "a": 1, "b": 0})]),
        reply("Cannot divide by zero."),
    ]
    agent = await make_agent(client, script)
    await agent.chat("1/0")
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert json.loads(tool_msg["content"])["error"]["code"] == "INVALID_INPUT"


async def test_unknown_tool_and_bad_json(client):
    agent = await make_agent(client, [])
    assert (await agent.run_tool("hack_server", "{}"))["error"]["code"] == "TOOL_NOT_FOUND"
    assert (await agent.run_tool("calculate", "not json"))["error"]["code"] == "INVALID_INPUT"


async def test_delete_without_confirm_keeps_task(client):
    created = (await client.call_tool("create_task", {"title": "important"})).structured_content["data"]
    script = [reply(calls=[call("delete_task", {"task_id": created["id"]})]), reply("Please confirm deletion.")]
    agent = await make_agent(client, script)
    await agent.chat("delete it")
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert json.loads(tool_msg["content"])["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert (await client.call_tool("get_tasks", {})).structured_content["data"]["tasks"]


async def test_human_decline_blocks_confirmed_delete(client):
    created = (await client.call_tool("create_task", {"title": "important"})).structured_content["data"]
    script = [reply(calls=[call("delete_task", {"task_id": created["id"], "confirm": True})]), reply("Cancelled.")]
    agent = await make_agent(client, script, approve=lambda *_: False)
    await agent.chat("yes delete")
    assert (await client.call_tool("get_tasks", {})).structured_content["data"]["tasks"]


async def test_human_approval_allows_delete(client):
    created = (await client.call_tool("create_task", {"title": "bye"})).structured_content["data"]
    script = [reply(calls=[call("delete_task", {"task_id": created["id"], "confirm": True})]), reply("Deleted.")]
    agent = await make_agent(client, script, approve=lambda *_: True)
    await agent.chat("yes delete")
    assert (await client.call_tool("get_tasks", {})).structured_content["data"]["tasks"] == []


async def test_step_limit(client):
    looping = [reply(calls=[call("system_info", {}, str(i))]) for i in range(20)]
    agent = await make_agent(client, looping)
    assert "too many tool steps" in await agent.chat("loop")
