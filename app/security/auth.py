"""API-key authentication using the MCP SDK's TokenVerifier hook.

API_KEYS format:  name:key:scope+scope,name2:key2:scope
Example:          admin:s3cret:read+write+destructive,viewer:v1ew:read

The SDK's HTTP layer calls verify_token() on every request that carries
`Authorization: Bearer <key>`. A bad key never reaches a tool (HTTP 401).
"""

import hmac

from mcp.server.auth.provider import AccessToken

from app.security.permissions import Permission

_VALID_SCOPES = {p.value for p in Permission}


def parse_api_keys(raw: str) -> dict[str, tuple[str, list[str]]]:
    """Return {key: (name, scopes)}. Raises ValueError on malformed input."""
    keys: dict[str, tuple[str, list[str]]] = {}
    for entry in filter(None, (e.strip() for e in raw.split(","))):
        try:
            name, key, scopes_raw = entry.split(":")
        except ValueError:
            raise ValueError("API_KEYS entries must look like name:key:read+write") from None
        scopes = [s for s in scopes_raw.split("+") if s]
        unknown = set(scopes) - _VALID_SCOPES
        if not key or unknown:
            raise ValueError(f"Invalid API key entry for '{name}' (unknown scopes: {unknown})")
        keys[key] = (name, scopes)
    return keys


class ApiKeyVerifier:
    def __init__(self, keys: dict[str, tuple[str, list[str]]]):
        self._keys = keys

    async def verify_token(self, token: str) -> AccessToken | None:
        for key, (name, scopes) in self._keys.items():
            if hmac.compare_digest(key.encode(), token.encode()):  # constant-time compare
                return AccessToken(token=token, client_id=name, scopes=scopes)
        return None
