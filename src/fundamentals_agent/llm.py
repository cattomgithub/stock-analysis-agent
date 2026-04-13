"""Reusable OpenAI-compatible chat model configuration for agents."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

LLMProvider = Literal["openai", "zhipu"]

DEFAULT_PROVIDER: LLMProvider = "openai"
DEFAULT_BASE_URLS: dict[LLMProvider, str] = {
    "openai": "https://api.openai.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/",
}
DEFAULT_MODELS: dict[LLMProvider, str] = {
    "openai": "gpt-4.1-mini",
    "zhipu": "glm-4.5-air",
}
ENV_PREFIXES: dict[LLMProvider, str] = {
    "openai": "OPENAI",
    "zhipu": "ZHIPU",
}


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: LLMProvider
    api_base_url: str
    api_key: str
    model: str


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def resolve_llm_provider(provider: str | None = None) -> LLMProvider:
    selected = _clean_env(provider) or _clean_env(os.getenv("STOCK_ANALYSIS_LLM_PROVIDER"))
    if selected is None:
        return DEFAULT_PROVIDER

    normalized = selected.lower()
    if normalized not in ENV_PREFIXES:
        supported = ", ".join(sorted(ENV_PREFIXES))
        raise ValueError(
            f"不支持的 LLM 提供方: {selected}。请使用以下之一: {supported}。"
        )
    return cast(LLMProvider, normalized)


def get_llm_settings(provider: str | None = None) -> LLMSettings:
    resolved_provider = resolve_llm_provider(provider)
    prefix = ENV_PREFIXES[resolved_provider]

    api_key = _clean_env(os.getenv(f"{prefix}_API_KEY"))
    if api_key is None:
        raise ValueError(f"缺少环境变量 {prefix}_API_KEY。")

    return LLMSettings(
        provider=resolved_provider,
        api_base_url=_clean_env(os.getenv(f"{prefix}_API_BASE_URL"))
        or DEFAULT_BASE_URLS[resolved_provider],
        api_key=api_key,
        model=_clean_env(os.getenv(f"{prefix}_MODEL"))
        or DEFAULT_MODELS[resolved_provider],
    )


def is_llm_configured(provider: str | None = None) -> bool:
    try:
        get_llm_settings(provider)
    except ValueError:
        return False
    return True


def create_chat_model(
    provider: str | None = None,
    *,
    temperature: float = 0.1,
) -> ChatOpenAI:
    settings = get_llm_settings(provider)
    return ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.api_base_url,
        temperature=temperature,
    )


__all__ = [
    "DEFAULT_PROVIDER",
    "LLMSettings",
    "create_chat_model",
    "get_llm_settings",
    "is_llm_configured",
    "resolve_llm_provider",
]