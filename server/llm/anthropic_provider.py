"""Anthropic Claude LLM provider — drop-in swap."""

import httpx
import logging
from typing import Optional, List
from server.llm.base import LLMProvider, LLMMessage, LLMResponse
from server.config import get_settings

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):

    BASE_URL = "https://api.anthropic.com/v1"

    @property
    def name(self) -> str:
        return "anthropic"

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        settings = get_settings()
        # Anthropic uses a different message format; system is a top-level param
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg += m.content + "\n"
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        if response_format == "json_object":
            system_msg += "\nRespond with valid JSON only."

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        if system_msg.strip():
            body["system"] = system_msg.strip()

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages", json=body, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        logger.info(f"Anthropic completion: model={data.get('model')} tokens={usage}")
        return LLMResponse(
            content=content,
            model=data.get("model", settings.anthropic_model),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        )
