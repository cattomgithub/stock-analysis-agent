import pytest

from fundamentals_agent.graph import graph
from fundamentals_agent.llm import get_llm_settings

pytestmark = [pytest.mark.anyio, pytest.mark.external_llm]


async def test_graph_generates_markdown_report_with_live_llm(
    monkeypatch: pytest.MonkeyPatch,
    patch_fake_mx_data_client,
    tmp_path,
) -> None:
    try:
        settings = get_llm_settings()
    except ValueError as exc:
        pytest.skip(str(exc))

    monkeypatch.setenv("STOCK_ANALYSIS_REPORT_DIR", str(tmp_path))

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    assert "600519.SH" in output_text
    assert f"LLM 提供方：{settings.provider}" in output_text
    assert "LLM 总结生成失败" not in output_text
    assert "已生成 Markdown 报告" in output_text
    assert list(tmp_path.glob("fundamentals_*.md"))