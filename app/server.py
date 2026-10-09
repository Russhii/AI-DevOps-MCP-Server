"""Entry point:  python -m app.server"""

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from app import resources
from app.config import get_settings
from app.database import init_db
from app.observability import configure_logging
from app.security.auth import ApiKeyVerifier, parse_api_keys
from app.tools import calculator, docker, github, system, tasks

INSTRUCTIONS = (
    "AI DevOps assistant tools: calculator, GitHub, tasks, Docker, system info. "
    "delete_task is destructive and needs explicit user confirmation."
)


def create_server() -> MCPServer:
    settings = get_settings()
    init_db()

    auth_kwargs = {}
    if settings.require_auth:
        keys = parse_api_keys(settings.api_keys)
        if not keys:
            raise RuntimeError("REQUIRE_AUTH is on but API_KEYS is empty. See .env.example.")
        base_url = f"http://{settings.host}:{settings.port}"
        auth_kwargs = {
            "token_verifier": ApiKeyVerifier(keys),
            "auth": AuthSettings(
                issuer_url=base_url,
                resource_server_url=f"{base_url}/mcp",
                validate_token_resource=False,  # API keys carry no audience claim
            ),
        }

    mcp = MCPServer("ai-devops-mcp", instructions=INSTRUCTIONS, **auth_kwargs)

    # The "tool registry": each module registers its own tools.
    for module in (calculator, github, tasks, docker, system):
        module.register(mcp)
    resources.register(mcp)
    return mcp


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    create_server().run("streamable-http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
