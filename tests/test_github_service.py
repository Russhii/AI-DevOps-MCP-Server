import httpx
import pytest

from app.errors import AppError, ErrorCode
from app.services.github_service import GitHubService, parse_issue, parse_repo


def service(handler, retries=0):
    return GitHubService(transport=httpx.MockTransport(handler), retries=retries, backoff=0)


REPO = {"full_name": "a/b", "html_url": "u", "stargazers_count": 7, "license": None, "topics": ["x"]}


def test_parse_repo_handles_missing_fields():
    parsed = parse_repo(REPO)
    assert parsed["stars"] == 7 and parsed["license"] is None and parsed["forks"] == 0


def test_parse_invalid_shape():
    with pytest.raises(AppError) as exc:
        parse_repo(["not", "a", "dict"])
    assert exc.value.code == ErrorCode.EXTERNAL_API_ERROR


def test_parse_issue():
    issue = parse_issue({"number": 1, "title": "t", "labels": [{"name": "bug"}], "user": {"login": "me"}})
    assert issue["labels"] == ["bug"] and issue["author"] == "me"


async def test_get_repository_ok():
    svc = service(lambda r: httpx.Response(200, json=REPO))
    assert (await svc.get_repository("a", "b"))["full_name"] == "a/b"


async def test_issues_exclude_pull_requests():
    items = [{"number": 1, "title": "issue"}, {"number": 2, "title": "pr", "pull_request": {}}]
    svc = service(lambda r: httpx.Response(200, json=items))
    assert [i["number"] for i in await svc.get_issues("a", "b")] == [1]


async def test_rate_limit():
    svc = service(lambda r: httpx.Response(403, headers={"x-ratelimit-remaining": "0"}))
    with pytest.raises(AppError) as exc:
        await svc.get_repository("a", "b")
    assert exc.value.code == ErrorCode.RATE_LIMITED and exc.value.retryable


async def test_not_found_is_user_error():
    svc = service(lambda r: httpx.Response(404))
    with pytest.raises(AppError) as exc:
        await svc.get_repository("a", "b")
    assert exc.value.code == ErrorCode.INVALID_INPUT and not exc.value.retryable


async def test_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(AppError) as exc:
        await service(handler).get_repository("a", "b")
    assert exc.value.code == ErrorCode.TIMEOUT and exc.value.retryable


async def test_retries_server_errors_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=REPO)

    assert (await service(handler, retries=2).get_repository("a", "b"))["full_name"] == "a/b"
    assert len(calls) == 3


async def test_invalid_json():
    svc = service(lambda r: httpx.Response(200, content=b"<html>"))
    with pytest.raises(AppError) as exc:
        await svc.get_repository("a", "b")
    assert exc.value.code == ErrorCode.EXTERNAL_API_ERROR


async def test_path_injection_rejected():
    with pytest.raises(AppError) as exc:
        await service(lambda r: httpx.Response(200)).get_repository("../etc", "passwd")
    assert exc.value.code == ErrorCode.INVALID_INPUT
