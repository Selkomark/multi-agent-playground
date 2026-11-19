"""A provider agent, served as its own A2A service.

    python -m domain_research.provider_agent --provider porkbun

The agent receives a list of domains over A2A, calls its provider's MCP tool,
and answers with a ProviderReport as JSON. The model decides how to call the
tool; the numbers in the answer are copied from the tool result by code, so
the model cannot mistype a price.
"""

import argparse
import json
import os
import sys

import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

from .config import PROVIDERS, generation_config, make_model
from .schemas import ProviderReport

ENV_PREFIXES = ("DOMAIN_RESEARCH_", "GODADDY_", "NAMECOM_", "PORKBUN_")

INSTRUCTION = """You check domain names at one provider: {provider}.

The message you receive contains a list of domain names. Call the
check_domains tool once with every domain in that list. If the call fails,
try once more. Then reply with one short sentence saying the lookup finished.
Do not repeat the results: they are attached to your reply automatically.
Never state availability or a price from memory."""


def find_report(value) -> dict | None:
    """Find the {"provider", "quotes"} payload inside an MCP tool result, whatever its wrapping."""
    if isinstance(value, dict):
        if "quotes" in value and "provider" in value:
            return value
        return next((r for r in map(find_report, value.values()) if r), None)
    if isinstance(value, list):
        return next((r for r in map(find_report, value) if r), None)
    if isinstance(value, str) and "quotes" in value:
        try:
            return find_report(json.loads(value))
        except ValueError:
            return None
    return None


def build_agent(provider: str) -> LlmAgent:
    def keep_report(tool, args, tool_context, tool_response):
        report = find_report(tool_response)
        if report:
            tool_context.state["report"] = ProviderReport.model_validate(report).model_dump()
        return None

    def attach_report(callback_context: CallbackContext) -> types.Content:
        report = callback_context.state.get("report") or {"provider": provider, "quotes": []}
        return types.Content(role="model", parts=[types.Part(text=json.dumps(report))])

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "domain_research.mcp_server", "--provider", provider],
                # MCP gives a stdio server a minimal environment, so the settings
                # and credentials it needs are passed on explicitly.
                env={k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)},
            ),
            timeout=30,
        )
    )
    return LlmAgent(
        name=f"{provider}_provider_agent",
        description=f"Checks domain availability and price at {provider}.",
        model=make_model(),
        generate_content_config=generation_config(),
        instruction=INSTRUCTION.format(provider=provider),
        tools=[toolset],
        after_tool_callback=keep_report,
        after_agent_callback=attach_report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=list(PROVIDERS))
    args = parser.parse_args()
    load_dotenv()
    port = PROVIDERS[args.provider]
    app = to_a2a(build_agent(args.provider), port=port)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
