"""Tool-selection evaluation. Run (server + GROQ_API_KEY needed):  python evaluation.py

Metrics are computed from real runs only; nothing here is pre-filled.

- Tool selection accuracy  = correct first tool choices / total queries
                             (expected null = the model should call NO tool)
- Invalid tool-call rate   = calls to unknown tools, bad JSON, or args failing the tool's schema
- Confirmation compliance  = destructive queries where the model did NOT pass confirm=true
- Execution success / latency: only READ tools are executed (safe); write tools are never run.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from groq import AsyncGroq
from jsonschema import ValidationError, validate

from agent import SYSTEM_PROMPT, Agent
from app.config import get_settings
from client import result_to_dict


def is_invalid_call(call: Any, schemas: dict[str, dict[str, Any]]) -> bool:
    name = call.function.name
    if name not in schemas:
        return True
    try:
        args = json.loads(call.function.arguments or "{}")
        validate(args, schemas[name])
    except (ValueError, ValidationError):
        return True
    return False


@asynccontextmanager
async def get_eval_client():
    from mcp import Client

    from app.server import create_server
    async with Client(create_server()) as client:
        yield client


async def evaluate() -> dict[str, Any]:
    import os
    os.environ["REQUIRE_AUTH"] = "false"
    settings = get_settings()
    if not settings.groq_api_key:
        raise SystemExit("Set GROQ_API_KEY in .env")
    cases = json.loads(Path("eval_dataset.json").read_text())

    async with get_eval_client() as client:
        agent = Agent(client, AsyncGroq(api_key=settings.groq_api_key), settings.groq_model)
        await agent.load_tools()
        mcp_tools = (await client.list_tools()).tools
        schemas = {t.name: t.input_schema for t in mcp_tools}
        read_only = {t.name for t in mcp_tools if t.annotations and t.annotations.read_only_hint}

        correct = invalid = calls_total = 0
        destructive_total = destructive_ok = 0
        executed = exec_ok = 0
        latencies: list[float] = []
        rows = []

        for case in cases:
            await asyncio.sleep(1.2)  # avoid Groq TPM/RPM rate limits
            message = await agent.decide(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": case["query"]}]
            )
            tool_calls = message.tool_calls or []
            chosen = tool_calls[0].function.name if tool_calls else None
            correct += chosen == case["expected"]
            calls_total += len(tool_calls)
            invalid += sum(is_invalid_call(c, schemas) for c in tool_calls)

            if case.get("destructive"):
                destructive_total += 1
                args = json.loads(tool_calls[0].function.arguments or "{}") if tool_calls else {}
                destructive_ok += args.get("confirm") is not True

            if chosen in read_only and not is_invalid_call(tool_calls[0], schemas):
                started = time.perf_counter()
                result = result_to_dict(await client.call_tool(chosen, json.loads(tool_calls[0].function.arguments or "{}")))
                latencies.append((time.perf_counter() - started) * 1000)
                executed += 1
                exec_ok += bool(result.get("success"))

            rows.append({"query": case["query"], "expected": case["expected"], "chosen": chosen})
            print(f"{'OK ' if chosen == case['expected'] else 'BAD'} {case['query']!r} -> {chosen} (expected {case['expected']})")

    def pct(a: int, b: int) -> str:
        return f"{100 * a / b:.1f}% ({a}/{b})" if b else "n/a"

    report = {
        "model": settings.groq_model,
        "tool_selection_accuracy": pct(correct, len(cases)),
        "invalid_tool_call_rate": pct(invalid, calls_total),
        "confirmation_compliance": pct(destructive_ok, destructive_total),
        "execution_success_rate (read tools)": pct(exec_ok, executed),
        "avg_tool_latency_ms (read tools)": round(sum(latencies) / len(latencies), 1) if latencies else "n/a",
        "cases": rows,
    }
    Path("eval_results.json").write_text(json.dumps(report, indent=2))
    print("\n" + json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    return report


if __name__ == "__main__":
    asyncio.run(evaluate())
