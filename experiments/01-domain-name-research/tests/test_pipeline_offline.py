"""End-to-end wiring test: real ADK orchestration, real A2A servers, real MCP
servers, with a scripted model and fake quotes. No network, no API key."""

import pytest

from domain_research.run import research, start_provider_agents


@pytest.mark.asyncio
async def test_pipeline_survives_a_provider_agent_that_is_down(tmp_path, monkeypatch):
    monkeypatch.setenv("DOMAIN_RESEARCH_OFFLINE", "1")
    processes = start_provider_agents(["porkbun", "registry"], tmp_path)  # godaddy is never started
    try:
        final = await research("coffee beans", ["godaddy", "porkbun", "registry"], ["com"], 6, tmp_path)
    finally:
        for process in processes:
            process.terminate()

    listed = final.ranked + final.dropped
    assert len(listed) == 6
    assert final.ranked, "the fake quotes leave at least one domain available"
    prices = [r.price for r in final.ranked]
    assert prices == sorted(prices)
    assert all(r.provider == "porkbun" for r in final.ranked)
