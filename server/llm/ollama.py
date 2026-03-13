"""Ollama local LLM provider — offline fallback."""

import httpx
import logging
from typing import Optional, List
from server.llm.base import LLMProvider, LLMMessage, LLMResponse
from server.config import get_settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):

    @property
    def name(self) -> str:
        return "ollama"

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        settings = get_settings()
        body = {
            "model": settings.ollama_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format == "json_object":
            body["format"] = "json"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat", json=body
            )
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        logger.info(f"Ollama completion: model={data.get('model')}")
        return LLMResponse(
            content=content,
            model=data.get("model", settings.ollama_model),
        )
