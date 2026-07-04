"""Single source of provider selection.

This is the ONLY place in the codebase that maps an `LLM_PROVIDER` string to a
concrete provider class. No other module is permitted to branch on provider
identity — that rule is what makes Bedrock/Azure deployment a one-line config
switch instead of a refactor.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config import Settings, get_settings
from app.providers.azure_stub import AzureStubProvider
from app.providers.base import LLMProvider
from app.providers.bedrock_stub import BedrockStubProvider
from app.providers.deepseek import DeepSeekProvider
from app.providers.gemini import GeminiProvider


def _build_deepseek(s: Settings) -> LLMProvider:
    return DeepSeekProvider(api_key=s.deepseek_api_key, model=s.deepseek_model)


def _build_gemini(s: Settings) -> LLMProvider:
    return GeminiProvider(api_key=s.gemini_api_key, model=s.gemini_model)


def _build_bedrock(s: Settings) -> LLMProvider:
    return BedrockStubProvider(model=s.bedrock_model, region=s.aws_region)


def _build_azure(s: Settings) -> LLMProvider:
    return AzureStubProvider(model=s.azure_model, endpoint=s.azure_endpoint)


_REGISTRY: dict[str, Callable[[Settings], LLMProvider]] = {
    "deepseek": _build_deepseek,
    "gemini": _build_gemini,
    "bedrock": _build_bedrock,
    "azure": _build_azure,
}


def get_provider(name: str | None = None, settings: Settings | None = None) -> LLMProvider:
    """Build the configured provider. `name` overrides `LLM_PROVIDER` — used e.g.
    to fetch the judge model (a different provider than generation)."""
    settings = settings or get_settings()
    key = (name or settings.llm_provider).strip().lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown LLM provider {key!r}. Valid options: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[key](settings)


def available_providers() -> list[str]:
    return sorted(_REGISTRY)
