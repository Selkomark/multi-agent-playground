"""Scripted stand-in for the LLM, used by offline mode and the tests.

It lets the whole pipeline run (ADK orchestration, A2A calls, MCP tool calls)
without an API key or any cost. It makes no decisions: it returns fixed names,
always calls the lookup tool once, and keeps every domain.
"""

import json
import re
from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

FAKE_NAMES = ["brewly", "kofi", "beanloop", "roastr", "cuppa", "mugly"]
DOMAIN = re.compile(r"\b[a-z0-9-]+\.[a-z]{2,}\b")


def _text(request: LlmRequest) -> str:
    return "\n".join(
        part.text for content in request.contents for part in content.parts or [] if part.text
    )


def _reply(part: types.Part) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[part]))


class FakeLlm(BaseLlm):
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        history = _text(llm_request)
        system = str(llm_request.config.system_instruction or "") if llm_request.config else ""
        has_tool_result = any(
            part.function_response for c in llm_request.contents for part in c.parts or []
        )

        if "check_domains" in llm_request.tools_dict:  # provider agent
            if has_tool_result:
                yield _reply(types.Part(text="Lookup finished."))
            else:
                domains = sorted(set(DOMAIN.findall(history)))
                call = types.FunctionCall(name="check_domains", args={"domains": domains})
                yield _reply(types.Part(function_call=call))
        elif "You are the naming agent" in system:
            candidates = [
                {"domain": f"{name}.com", "guideline": "easy to memorize", "reasoning": "offline fake"}
                for name in FAKE_NAMES
            ]
            yield _reply(types.Part(text=json.dumps({"candidates": candidates})))
        else:  # judge
            domains = sorted(set(DOMAIN.findall(system)))
            verdicts = [{"domain": d, "keep": True, "reason": "offline fake", "flags": []} for d in domains]
            yield _reply(types.Part(text=json.dumps({"verdicts": verdicts})))
