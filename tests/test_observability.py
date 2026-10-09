import logging

from app.observability import metrics_snapshot, redact


def test_redacts_secrets_and_truncates():
    safe = redact({"api_key": "abc", "GITHUB_TOKEN": "t", "query": "x" * 500, "n": 1})
    assert safe["api_key"] == "***" and safe["GITHUB_TOKEN"] == "***"
    assert len(safe["query"]) < 200 and safe["n"] == "1"


async def test_tool_calls_are_logged_and_counted(client, caplog):
    with caplog.at_level(logging.INFO, logger="devops_mcp"):
        await client.call_tool("calculate", {"operation": "add", "a": 1, "b": 1})
    line = next(r.message for r in caplog.records if "TOOL=calculate" in r.message)
    assert "STATUS=SUCCESS" in line and "LATENCY=" in line
    assert metrics_snapshot()["calculate"]["calls"] >= 1
