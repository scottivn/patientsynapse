"""OpenAI LLM provider — drop-in swap."""

import httpx
import logging
from typing import Optional, List
from server.llm.base import LLMProvider, LLMMessage, LLMResponse
from server.config import get_settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):

    BASE_URL = "https://api.openai.com/v1"

    @property
    def name(self) -> str:
        return "openai"

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.openai_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json_object":
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions", json=body, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage")
        logger.info(f"OpenAI completion: model={data.get('model')} tokens={usage}")
        return LLMResponse(
            content=choice["content"],
            model=data.get("model", settings.openai_model),
            usage=usage,
        )
