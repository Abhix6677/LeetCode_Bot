import os
import logging
from generator.ai_providers.base import BaseAIProvider
from generator.ai_providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

def get_ai_provider() -> BaseAIProvider:
    provider_name = os.getenv("AI_PROVIDER", "deepseek").lower()
    
    # Generic OpenAI compatible config (OpenAI, DeepSeek, OpenRouter)
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    base_url = os.getenv("AI_BASE_URL", "")
    
    if provider_name == "deepseek":
        return OpenAICompatibleProvider(
            base_url=base_url or "https://api.deepseek.com/v1",
            api_key=api_key,
            model=model or "deepseek-chat",
            name="deepseek"
        )
    elif provider_name == "openrouter":
        return OpenAICompatibleProvider(
            base_url=base_url or "https://openrouter.ai/api/v1",
            api_key=api_key,
            model=model or "google/gemini-2.5-flash",
            name="openrouter"
        )
    elif provider_name == "openai":
        return OpenAICompatibleProvider(
            base_url=base_url or "https://api.openai.com/v1",
            api_key=api_key,
            model=model or "gpt-4o-mini",
            name="openai"
        )
    elif provider_name == "gemini":
        # Using OpenRouter for Gemini by default unless base_url is specified
        return OpenAICompatibleProvider(
            base_url=base_url or "https://openrouter.ai/api/v1",
            api_key=api_key,
            model=model or "google/gemini-2.5-flash",
            name="gemini"
        )
    else:
        logger.warning(f"Unknown AI_PROVIDER: {provider_name}. Falling back to default provider.")
        return OpenAICompatibleProvider(
            base_url=base_url or "http://localhost:20128/v1",
            api_key=api_key,
            model=model or "oc/deepseek-v4-flash-free",
            name="default"
        )
