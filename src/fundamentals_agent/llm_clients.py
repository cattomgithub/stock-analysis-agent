"""Optional external LLM clients for OpenAI and Zhipu."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
import os
from typing import Any, Literal

from dotenv import load_dotenv
import requests

load_dotenv()

logger = logging.getLogger(__name__)

LLMProvider = Literal["openai", "zhipu"]

_ENV_PREFIXES: dict[LLMProvider, str] = {
    "openai": "OPENAI",
    "zhipu": "ZHIPU",
}

_DEFAULT_BASE_URLS: dict[LLMProvider, str] = {
    "openai": "https://api.openai.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str

    def to_payload(self) -> dict[str, str]:
        normalized_role = self.role.strip()
        normalized_content = self.content.strip()
        if not normalized_role:
            raise ValueError("消息 role 不能为空")
        if not normalized_content:
            raise ValueError("消息 content 不能为空")
        return {"role": normalized_role, "content": normalized_content}


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: LLMProvider
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 30.0

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True, slots=True)
class LLMResponse:
    provider: LLMProvider
    model: str
    content: str
    usage: dict[str, Any]
    raw_response: dict[str, Any]


def _get_env_prefix(provider: LLMProvider) -> str:
    try:
        return _ENV_PREFIXES[provider]
    except KeyError as exc:
        raise ValueError(f"不支持的 LLM provider: {provider}") from exc


def load_llm_settings(
    provider: LLMProvider,
    env: Mapping[str, str] | None = None,
) -> LLMSettings:
    env_map = os.environ if env is None else env
    prefix = _get_env_prefix(provider)

    api_key = str(env_map.get(f"{prefix}_API_KEY", "")).strip()
    model = str(env_map.get(f"{prefix}_MODEL", "")).strip()
    base_url = str(
        env_map.get(f"{prefix}_BASE_URL") or _DEFAULT_BASE_URLS[provider]
    ).strip()
    timeout_text = str(env_map.get(f"{prefix}_TIMEOUT_SECONDS") or "30").strip()

    missing_fields: list[str] = []
    if not api_key:
        missing_fields.append(f"{prefix}_API_KEY")
    if not model:
        missing_fields.append(f"{prefix}_MODEL")
    if missing_fields:
        raise ValueError(f"缺少 {provider} 配置: {', '.join(missing_fields)}")

    try:
        timeout_seconds = float(timeout_text)
    except ValueError as exc:
        raise ValueError(f"{prefix}_TIMEOUT_SECONDS 必须是数字") from exc
    if timeout_seconds <= 0:
        raise ValueError(f"{prefix}_TIMEOUT_SECONDS 必须大于 0")

    return LLMSettings(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _normalize_messages(
    messages: Sequence[ChatMessage | Mapping[str, Any]],
) -> list[dict[str, str]]:
    payload_messages: list[dict[str, str]] = []
    for message in messages:
        if isinstance(message, ChatMessage):
            payload_messages.append(message.to_payload())
            continue

        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        payload_messages.append(ChatMessage(role=role, content=content).to_payload())

    if not payload_messages:
        raise ValueError("messages 不能为空")
    return payload_messages


def _extract_response_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM 响应缺少 choices")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        normalized = content.strip()
        if normalized:
            return normalized
        raise RuntimeError("LLM 响应内容为空")

    if isinstance(content, list):
        text_parts = [
            str(item.get("text", "")).strip()
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        merged = "\n".join(part for part in text_parts if part)
        if merged:
            return merged

    raise RuntimeError("LLM 响应中缺少可解析的 message.content")


class ChatCompletionsClient:
    def __init__(
        self,
        settings: LLMSettings,
        session: requests.Session | Any | None = None,
    ) -> None:
        self.settings = settings
        self._session = session or requests.Session()

    def chat(
        self,
        messages: Sequence[ChatMessage | Mapping[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_payload: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": _normalize_messages(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_payload:
            payload.update(dict(extra_payload))

        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        logger.debug(
            "Calling %s chat completions model=%s url=%s",
            self.settings.provider,
            self.settings.model,
            self.settings.chat_completions_url,
        )

        try:
            response = self._session.post(
                self.settings.chat_completions_url,
                headers=headers,
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                detail = getattr(response_obj, "text", "") or ""
            raise RuntimeError(
                f"调用 {self.settings.provider} LLM 失败: {detail or exc}"
            ) from exc

        raw_payload = response.json()
        if not isinstance(raw_payload, dict):
            raise RuntimeError("LLM 响应格式错误，期望 JSON object")

        content = _extract_response_content(raw_payload)
        usage = raw_payload.get("usage")
        return LLMResponse(
            provider=self.settings.provider,
            model=str(raw_payload.get("model") or self.settings.model),
            content=content,
            usage=dict(usage) if isinstance(usage, dict) else {},
            raw_response=raw_payload,
        )

    def prompt(
        self,
        prompt_text: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_payload: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        normalized_prompt = prompt_text.strip()
        if not normalized_prompt:
            raise ValueError("prompt_text 不能为空")

        messages: list[ChatMessage] = []
        if system_prompt and system_prompt.strip():
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=normalized_prompt))
        return self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_payload=extra_payload,
        )


def create_llm_client(
    provider: LLMProvider,
    *,
    session: requests.Session | Any | None = None,
    env: Mapping[str, str] | None = None,
) -> ChatCompletionsClient:
    return ChatCompletionsClient(load_llm_settings(provider, env=env), session=session)


def create_openai_client(
    *,
    session: requests.Session | Any | None = None,
    env: Mapping[str, str] | None = None,
) -> ChatCompletionsClient:
    return create_llm_client("openai", session=session, env=env)


def create_zhipu_client(
    *,
    session: requests.Session | Any | None = None,
    env: Mapping[str, str] | None = None,
) -> ChatCompletionsClient:
    return create_llm_client("zhipu", session=session, env=env)


__all__ = [
    "ChatCompletionsClient",
    "ChatMessage",
    "LLMResponse",
    "LLMSettings",
    "create_llm_client",
    "create_openai_client",
    "create_zhipu_client",
    "load_llm_settings",
]