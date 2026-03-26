"""LLM provider factory. Change provider via LLM_PROVIDER env var."""

from server.llm.base import LLMProvider
from server.config import get_settings
from typing import Optional

_llm_override: Optional[str] = None


def get_llm() -> LLMProvider:
    """Return the configured LLM provider instance."""
    settings = get_settings()
    provider = _llm_override or settings.llm_provider
    match provider:
        case "grok":
            from server.llm.grok import GrokProvider
            return GrokProvider()
        case "openai":
            from server.llm.openai_provider import OpenAIProvider
            return OpenAIProvider()
        case "anthropic":
            from server.llm.anthropic_provider import AnthropicProvider
            return AnthropicProvider()
        case "ollama":
            from server.llm.ollama import OllamaProvider
            return OllamaProvider()
        case "bedrock":
            from server.llm.bedrock import BedrockProvider
            return BedrockProvider()
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")


def switch_llm(provider: str) -> LLMProvider:
    """Hot-swap the active LLM provider at runtime."""
    global _llm_override
    if provider not in ("grok", "openai", "anthropic", "ollama", "bedrock"):
        raise ValueError(f"Unknown LLM provider: {provider}")
    _llm_override = provider
    return get_llm()


def get_active_llm_key() -> str:
    """Return the currently active LLM provider key."""
    return _llm_override or get_settings().llm_provider
