import logging

import pytest

from fundamentals_agent.graph import graph

pytestmark = pytest.mark.anyio

logger = logging.getLogger(__name__)


async def test_graph_generates_markdown_report(
    patch_fake_mx_data_client,
    report_output_dir,
) -> None:
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    report_files = sorted(report_output_dir.glob("fundamentals_*.md"))
    logger.debug("Mock integration output: %s", output_text)
    logger.debug("Mock integration report files: %s", [str(path) for path in report_files])
    assert "600519.SH" in output_text
    assert "已调用东方财富妙想 mx-data skill 完成个股基本面查询。" in output_text
    assert "个股基本面信息收集完成。" in output_text
    assert "Markdown 报告" in output_text
    assert report_files
