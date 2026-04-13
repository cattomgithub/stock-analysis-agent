import pytest

from fundamentals_agent.graph import graph

pytestmark = pytest.mark.anyio


async def test_graph_generates_markdown_report(
    monkeypatch: pytest.MonkeyPatch,
    patch_fake_mx_data_client,
    patch_fake_chat_model,
    tmp_path,
) -> None:
    monkeypatch.setenv("STOCK_ANALYSIS_REPORT_DIR", str(tmp_path))

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    assert "600519.SH" in output_text
    assert "模型总结" in output_text
    assert "LLM 提供方：openai" in output_text
    assert "Markdown 报告" in output_text
    assert list(tmp_path.glob("fundamentals_*.md"))
