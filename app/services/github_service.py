"""GitHub REST API client. Handles timeouts, HTTP errors, rate limits and bad responses."""

import asyncio
import re
from typing import Any

import httpx

from app.errors import AppError, ErrorCode

API_URL = "https://api.github.com"
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_RETRY_INTERNALLY = {ErrorCode.TIMEOUT, ErrorCode.EXTERNAL_API_ERROR}  # transient only


def check_name(value: str, field: str) -> str:
    """Reject anything that could change the URL path (e.g. '../')."""
    if not _NAME.match(value):
        raise AppError(ErrorCode.INVALID_INPUT, f"Invalid {field}: {value!r}", False)
    return value


def check_limit(limit: int, maximum: int = 30) -> int:
    if not 1 <= limit <= maximum:
        raise AppError(ErrorCode.INVALID_INPUT, f"limit must be between 1 and {maximum}", False)
    return limit


def _as_dict(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AppError(ErrorCode.EXTERNAL_API_ERROR, "GitHub returned an unexpected response", False)
    return raw


def parse_repo(raw: Any) -> dict[str, Any]:
    r = _as_dict(raw)
    return {
        "full_name": r.get("full_name"),
        "description": r.get("description"),
        "url": r.get("html_url"),
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "open_issues": r.get("open_issues_count", 0),
        "language": r.get("language"),
        "license": (r.get("license") or {}).get("name"),
        "topics": r.get("topics", []),
        "default_branch": r.get("default_branch"),
        "updated_at": r.get("updated_at"),
    }


def parse_issue(raw: Any) -> dict[str, Any]:
    i = _as_dict(raw)
    return {
        "number": i.get("number"),
        "title": i.get("title"),
        "state": i.get("state"),
        "labels": [lbl.get("name") for lbl in i.get("labels", []) if isinstance(lbl, dict)],
        "author": (i.get("user") or {}).get("login"),
        "comments": i.get("comments", 0),
        "url": i.get("html_url"),
        "created_at": i.get("created_at"),
    }


class GitHubService:
    def __init__(
        self,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,  # tests inject a mock here
        retries: int = 2,
        backoff: float = 0.5,
        timeout: float = 10.0,
    ):
        self.token = token
        self.transport = transport
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout

    # ---- public API -------------------------------------------------------
    async def search_repositories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            raise AppError(ErrorCode.INVALID_INPUT, "query must not be empty", False)
        params = {"q": query, "sort": "stars", "per_page": check_limit(limit)}
        data = _as_dict(await self._get("/search/repositories", params))
        return [parse_repo(item) for item in data.get("items", [])]

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        path = f"/repos/{check_name(owner, 'owner')}/{check_name(repo, 'repo')}"
        return parse_repo(await self._get(path))

    async def get_issues(
        self, owner: str, repo: str, state: str = "open", labels: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        if state not in {"open", "closed", "all"}:
            raise AppError(ErrorCode.INVALID_INPUT, "state must be open, closed or all", False)
        path = f"/repos/{check_name(owner, 'owner')}/{check_name(repo, 'repo')}/issues"
        params: dict[str, Any] = {"state": state, "per_page": check_limit(limit)}
        if labels:
            params["labels"] = labels
        items = await self._get(path, params)
        if not isinstance(items, list):
            raise AppError(ErrorCode.EXTERNAL_API_ERROR, "GitHub returned an unexpected response", False)
        # GitHub's issues endpoint also returns pull requests; drop them.
        return [parse_issue(i) for i in items if "pull_request" not in i]

    # ---- HTTP plumbing ----------------------------------------------------
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(self.retries + 1):
            try:
                return await self._request(path, params)
            except AppError as exc:
                if exc.code not in _RETRY_INTERNALLY or not exc.retryable or attempt == self.retries:
                    raise
                await asyncio.sleep(self.backoff * 2**attempt)

    async def _request(self, path: str, params: dict[str, Any] | None) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-devops-mcp",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with httpx.AsyncClient(
                base_url=API_URL, headers=headers, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(path, params=params)
        except httpx.TimeoutException:
            raise AppError(ErrorCode.TIMEOUT, "GitHub API timed out", True) from None
        except httpx.HTTPError:
            raise AppError(ErrorCode.EXTERNAL_API_ERROR, "Could not reach GitHub", True) from None

        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError:
            raise AppError(ErrorCode.EXTERNAL_API_ERROR, "GitHub returned invalid JSON", False) from None

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        limited = response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers
        if code == 429 or (code == 403 and limited):
            reset = response.headers.get("x-ratelimit-reset")
            suffix = f" (resets at unix time {reset})" if reset else ""
            raise AppError(ErrorCode.RATE_LIMITED, f"GitHub API rate limit exceeded{suffix}", True)
        if code == 401:
            raise AppError(ErrorCode.AUTHENTICATION_ERROR, "GitHub rejected the configured token", False)
        if code == 403:
            raise AppError(ErrorCode.AUTHORIZATION_ERROR, "GitHub denied access to this resource", False)
        if code in (404, 422):
            raise AppError(ErrorCode.INVALID_INPUT, "GitHub could not find or process that request", False)
        raise AppError(ErrorCode.EXTERNAL_API_ERROR, f"GitHub API error (HTTP {code})", code >= 500)
