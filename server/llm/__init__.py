"""LLM provider factory. Change provider via LLM_PROVIDER env var."""

from server.llm.base import LLMProvider
from server.config import get_settings


def get_llm() -> LLMProvider:
    """Return the configured LLM provider instance."""
    settings = get_settings()
    match settings.llm_provider:
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
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
