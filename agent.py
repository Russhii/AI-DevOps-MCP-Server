"""LLM agent: Groq decides which MCP tools to call; the MCP client executes them.

    User -> LLM -> tool call -> MCP client -> MCP server -> result -> LLM -> answer

Run (server must be running):  python agent.py
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from groq import APIError, AsyncGroq

from app.config import get_settings
from client import connect, result_to_dict

SYSTEM_PROMPT = """You are a DevOps assistant. You can use tools exposed by an MCP server.
Rules:
- Use tools for facts (GitHub, tasks, Docker, system, math). Never invent tool results.
- If a tool returns success=false, explain the error. Retry only if retryable=true.
- delete_task is destructive. Call it WITHOUT confirm first. If it returns CONFIRMATION_REQUIRED,
  tell the user what will be deleted and ask for confirmation. Only after the user clearly says
  yes in their latest message may you call it again with confirm=true.
- Be concise."""

MAX_STEPS = 8          # safety limit on the tool loop
MAX_RESULT_CHARS = 6000


def to_groq_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to the OpenAI/Groq function-calling format (nothing hardcoded)."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]


def cli_approve(tool: str, args: dict[str, Any]) -> bool:
    """Human-in-the-loop gate used by the terminal agent."""
    answer = input(f"\n[APPROVAL] The assistant wants to run {tool}({args}). Allow? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


class Agent:
    def __init__(
        self,
        mcp_client: Any,
        llm: Any,
        model: str,
        approve: Callable[[str, dict[str, Any]], bool] = cli_approve,
    ):
        self.mcp = mcp_client
        self.llm = llm
        self.model = model
        self.approve = approve
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tools: list[dict[str, Any]] = []
        self.destructive: set[str] = set()

    async def load_tools(self) -> None:
        """Tool discovery: ask the server what it offers."""
        mcp_tools = (await self.mcp.list_tools()).tools
        self.tools = to_groq_tools(mcp_tools)
        self.destructive = {
            t.name for t in mcp_tools if t.annotations and t.annotations.destructive_hint
        }

    async def decide(self, messages: list[dict[str, Any]]) -> Any:
        """One LLM call. Returns the assistant message (text and/or tool calls)."""
        response = await self.llm.chat.completions.create(
            model=self.model, messages=messages, tools=self.tools, tool_choice="auto", temperature=0
        )
        return response.choices[0].message

    async def run_tool(self, name: str, raw_args: str) -> dict[str, Any]:
        """Execute one tool call through MCP, with validation and the human approval gate."""
        known = {t["function"]["name"] for t in self.tools}
        if name not in known:
            return _error("TOOL_NOT_FOUND", f"Unknown tool {name!r}")
        try:
            args = json.loads(raw_args or "{}")
            if not isinstance(args, dict):
                raise ValueError
        except ValueError:
            return _error("INVALID_INPUT", "Tool arguments must be a JSON object")

        # Layer 2 of confirmation: a real human must approve, whatever the LLM claims.
        if name in self.destructive and args.get("confirm") is True:
            if not self.approve(name, args):
                return _error("CONFIRMATION_REQUIRED", "The user declined this action", False)

        result = await self.mcp.call_tool(name, args)
        return result_to_dict(result)

    async def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        for _ in range(MAX_STEPS):
            message = await self.decide(self.messages)
            if not message.tool_calls:
                answer = message.content or ""
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            self.messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments},
                        }
                        for c in message.tool_calls
                    ],
                }
            )
            for call in message.tool_calls:  # the LLM may request several tools at once
                result = await self.run_tool(call.function.name, call.function.arguments)
                print(f"  [tool] {call.function.name} -> success={result.get('success')}")
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result)[:MAX_RESULT_CHARS],
                    }
                )
        return "I stopped because the request needed too many tool steps."


def _error(code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "retryable": retryable}}


async def main() -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        raise SystemExit("Set GROQ_API_KEY in .env")
    llm = AsyncGroq(api_key=settings.groq_api_key)
    async with connect() as client:
        agent = Agent(client, llm, settings.groq_model)
        await agent.load_tools()
        print(f"Connected. {len(agent.tools)} tools loaded. Type 'exit' to quit.")
        while True:
            text = await asyncio.to_thread(input, "\nYou: ")
            if text.strip().lower() in {"exit", "quit"}:
                break
            try:
                print("Assistant:", await agent.chat(text))
            except APIError as exc:
                print(f"LLM error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
