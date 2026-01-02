"""Factory for creating LLM providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.services.llm.base import LLMProvider

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

# Available providers
PROVIDERS = {
    "anthropic": "AnthropicProvider",
    "ollama": "OllamaProvider",
    "gemini": "GeminiProvider",
}


def get_available_providers() -> list[str]:
    """Return list of available provider names."""
    return list(PROVIDERS.keys())


def create_llm_provider(settings: Settings) -> LLMProvider:
    """
    Create an LLM provider based on settings.

    Args:
        settings: Application settings

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not supported or misconfigured
    """
    provider_name = settings.llm_provider.lower()

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when using 'anthropic' provider"
            )

        from src.services.llm.anthropic_provider import AnthropicProvider

        logger.info(f"Using Anthropic provider with model: {settings.anthropic_model}")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout=settings.claude_timeout_seconds,
        )

    elif provider_name == "ollama":
        from src.services.llm.ollama_provider import OllamaProvider

        logger.info(
            f"Using Ollama provider at {settings.ollama_base_url} "
            f"with model: {settings.ollama_model}"
        )
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout_seconds,
        )

    elif provider_name == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when using 'gemini' provider. "
                "Get your free API key from https://aistudio.google.com/app/apikey"
            )

        from src.services.llm.gemini_provider import GeminiProvider

        logger.info(f"Using Gemini provider with model: {settings.gemini_model}")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout=settings.gemini_timeout_seconds,
        )

    else:
        available = ", ".join(get_available_providers())
        raise ValueError(
            f"Unknown LLM provider: '{provider_name}'. "
            f"Available providers: {available}"
        )
