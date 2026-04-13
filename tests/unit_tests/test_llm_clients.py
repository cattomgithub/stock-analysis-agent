from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from external_llm import (
    ChatMessage,
    create_openai_client,
    create_zhipu_client,
    load_llm_provider,
    load_llm_settings,
)


@dataclass
class DummyResponse:
    payload: dict[str, Any]
    status_code: int = 200
    text: str = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = type("ResponseLike", (), {"text": self.text})()
            raise requests.HTTPError(self.text or "request failed", response=response)

    def json(self) -> dict[str, Any]:
        return self.payload


class DummySession:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> DummyResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return DummyResponse(self.payload)


def test_load_llm_settings_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_llm_settings("openai", env={"OPENAI_MODEL": "gpt-5-mini"})

    with pytest.raises(ValueError, match="ZHIPU_MODEL"):
        load_llm_settings("zhipu", env={"ZHIPU_API_KEY": "secret"})


def test_load_llm_provider_supports_custom_env_key() -> None:
    assert (
        load_llm_provider(
            "FUNDAMENTALS_LLM_PROVIDER",
            env={"FUNDAMENTALS_LLM_PROVIDER": "OpenAI"},
        )
        == "openai"
    )

    with pytest.raises(ValueError, match="CUSTOM_LLM_PROVIDER"):
        load_llm_provider("CUSTOM_LLM_PROVIDER", env={})


@pytest.mark.parametrize(
    ("provider", "factory", "env", "expected_url"),
    [
        (
            "openai",
            create_openai_client,
            {
                "OPENAI_API_KEY": "openai-secret",
                "OPENAI_MODEL": "gpt-5-mini",
                "OPENAI_TIMEOUT_SECONDS": "15",
            },
            "https://api.openai.com/v1/chat/completions",
        ),
        (
            "zhipu",
            create_zhipu_client,
            {
                "ZHIPU_API_KEY": "zhipu-secret",
                "ZHIPU_MODEL": "glm-4.5-flash",
                "ZHIPU_TIMEOUT_SECONDS": "12",
            },
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        ),
    ],
)
def test_llm_client_builds_chat_completion_request(
    provider: str,
    factory,
    env: dict[str, str],
    expected_url: str,
) -> None:
    session = DummySession(
        {
            "model": env.get("OPENAI_MODEL") or env.get("ZHIPU_MODEL"),
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "测试响应",
                    }
                }
            ],
            "usage": {"total_tokens": 42},
        }
    )
    client = factory(session=session, env=env)

    response = client.prompt(
        "请解释 ROE",
        system_prompt="你是一名投研助手。",
        temperature=0.2,
        max_tokens=256,
    )

    assert response.provider == provider
    assert response.content == "测试响应"
    assert response.usage == {"total_tokens": 42}
    assert session.calls == [
        {
            "url": expected_url,
            "headers": {
                "Authorization": f"Bearer {env[f'{provider.upper()}_API_KEY']}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": env.get("OPENAI_MODEL") or env.get("ZHIPU_MODEL"),
                "messages": [
                    {"role": "system", "content": "你是一名投研助手。"},
                    {"role": "user", "content": "请解释 ROE"},
                ],
                "temperature": 0.2,
                "max_tokens": 256,
            },
            "timeout": float(env.get("OPENAI_TIMEOUT_SECONDS") or env.get("ZHIPU_TIMEOUT_SECONDS")),
        }
    ]


def test_llm_client_accepts_chat_message_instances() -> None:
    session = DummySession(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "第一段"}, {"type": "text", "text": "第二段"}],
                    }
                }
            ]
        }
    )
    client = create_openai_client(
        session=session,
        env={
            "OPENAI_API_KEY": "openai-secret",
            "OPENAI_MODEL": "gpt-5-mini",
        },
    )

    response = client.chat(
        [
            ChatMessage(role="system", content="你是一名投研助手。"),
            ChatMessage(role="user", content="总结一下自由现金流。"),
        ]
    )

    assert response.content == "第一段\n第二段"


def test_llm_client_raises_runtime_error_on_http_failure() -> None:
    class FailingSession:
        def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            json: dict[str, Any],
            timeout: float,
        ) -> DummyResponse:
            del url, headers, json, timeout
            return DummyResponse(payload={}, status_code=401, text="unauthorized")

    client = create_zhipu_client(
        session=FailingSession(),
        env={
            "ZHIPU_API_KEY": "zhipu-secret",
            "ZHIPU_MODEL": "glm-4.5-flash",
        },
    )

    with pytest.raises(RuntimeError, match="unauthorized"):
        client.prompt("你好")