"""Shared settings: which providers exist, where their agents listen, which model runs them."""

import os

from google.adk.models.anthropic_llm import AnthropicGenerateContentConfig, AnthropicLlm
from google.adk.models.base_llm import BaseLlm
from google.genai import types

# provider name -> port of its A2A server
PROVIDERS: dict[str, int] = {
    "godaddy": 8101,
    "namecom": 8102,
    "porkbun": 8103,
    "registry": 8104,
}

DEFAULT_MODEL = "claude-opus-5-5"


def offline() -> bool:
    """Offline mode swaps the LLM and the provider lookups for scripted fakes."""
    return os.environ.get("DOMAIN_RESEARCH_OFFLINE") == "1"


def make_model() -> BaseLlm:
    if offline():
        from .fakes import FakeLlm

        return FakeLlm(model="fake")
    return AnthropicLlm(
        model=os.environ.get("DOMAIN_RESEARCH_MODEL", DEFAULT_MODEL),
        max_tokens=16000,
    )


def generation_config() -> types.GenerateContentConfig:
    # thinking_budget=-1 selects adaptive thinking. It is required here: without
    # it ADK forces a tool call to get structured output, which current Claude
    # models reject.
    return AnthropicGenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
        effort="medium",
    )


def agent_card_url(provider: str) -> str:
    return f"http://localhost:{PROVIDERS[provider]}/.well-known/agent-card.json"
