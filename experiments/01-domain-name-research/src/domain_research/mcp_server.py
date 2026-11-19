"""MCP server exposing one provider's lookup as a tool.

Started over stdio by that provider's agent:
    python -m domain_research.mcp_server --provider porkbun
"""

import argparse

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from . import providers
from .config import PROVIDERS


def build(provider: str) -> MCPServer:
    server = MCPServer(name=f"{provider}-domains")

    @server.tool()
    async def check_domains(domains: list[str]) -> dict:
        """Check availability and price for a list of full domain names at this provider.

        Returns {"provider": str, "quotes": [...]} with one quote per domain. Each
        quote has a status of "available", "taken" or "unknown".
        """
        quotes = await providers.check(provider, domains)
        return {"provider": provider, "quotes": [q.model_dump() for q in quotes]}

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=list(PROVIDERS))
    args = parser.parse_args()
    load_dotenv()
    build(args.provider).run("stdio")


if __name__ == "__main__":
    main()
