from fundamentals_agent.llm import get_llm_settings, resolve_llm_provider


def test_get_llm_settings_for_openai(monkeypatch) -> None:
    monkeypatch.delenv("STOCK_ANALYSIS_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    settings = get_llm_settings()

    assert settings.provider == "openai"
    assert settings.api_key == "openai-key"
    assert settings.api_base_url == "https://api.openai.com/v1"
    assert settings.model == "gpt-4.1-mini"


def test_get_llm_settings_for_zhipu(monkeypatch) -> None:
    monkeypatch.setenv("STOCK_ANALYSIS_LLM_PROVIDER", "zhipu")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("ZHIPU_API_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    monkeypatch.setenv("ZHIPU_MODEL", "glm-4.5-air")

    settings = get_llm_settings()

    assert settings.provider == "zhipu"
    assert settings.api_key == "zhipu-key"
    assert settings.api_base_url == "https://open.bigmodel.cn/api/paas/v4/"
    assert settings.model == "glm-4.5-air"


def test_resolve_llm_provider_rejects_unknown_provider() -> None:
    try:
        resolve_llm_provider("unknown")
    except ValueError as exc:
        assert "不支持的 LLM 提供方" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported provider")