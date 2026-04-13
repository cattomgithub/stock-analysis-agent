import logging

import pytest

from fundamentals_agent.graph import graph
from fundamentals_agent.llm import get_llm_settings

pytestmark = [pytest.mark.anyio, pytest.mark.external_llm]

logger = logging.getLogger(__name__)


async def test_graph_generates_markdown_report_with_live_llm(
    patch_fake_mx_data_client,
    report_output_dir,
) -> None:
    try:
        settings = get_llm_settings()
    except ValueError as exc:
        pytest.skip(str(exc))

    logger.debug(
        "Running live LLM integration test with provider=%s model=%s output_dir=%s",
        settings.provider,
        settings.model,
        report_output_dir,
    )

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    report_files = sorted(report_output_dir.glob("fundamentals_*.md"))
    logger.debug("Live integration output: %s", output_text)
    logger.debug("Live integration report files: %s", [str(path) for path in report_files])
    assert "600519.SH" in output_text
    assert f"LLM 提供方：{settings.provider}" in output_text
    assert "LLM 总结生成失败" not in output_text
    assert "已生成 Markdown 报告" in output_text
    assert report_files