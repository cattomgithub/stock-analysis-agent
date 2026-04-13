import logging

import pytest

from fundamentals_agent.fundamentals import StockTarget, build_section_queries
from fundamentals_agent.graph import graph
from tests.report_checks import (
    assert_generated_markdown_report,
    assert_report_contains_queries,
)

pytestmark = pytest.mark.anyio

logger = logging.getLogger(__name__)


async def test_graph_generates_markdown_report_with_live_mx_skill(
    patch_live_mx_data_client,
    patch_fake_llm_summarizer,
    report_output_dir,
) -> None:
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    expected_queries = tuple(
        query
        for _title, query in build_section_queries(StockTarget(code="600519", market="SH"))
    )
    report_path, report_text = assert_generated_markdown_report(
        report_output_dir,
        expected_symbol="600519.SH",
        min_table_data_rows=4,
        forbidden_snippets=("查询失败：",),
    )
    logger.debug("Live integration output: %s", output_text)
    logger.debug("Live integration report path: %s", report_path)
    assert patch_live_mx_data_client.query_log == list(expected_queries)
    assert_report_contains_queries(report_text, expected_queries)
    assert "600519.SH" in output_text
    assert "已调用东方财富妙想 mx-data skill 完成个股基本面查询。" in output_text
    assert "已调用外部 LLM 完成结果整理。" in output_text
    assert "个股基本面信息收集完成。" in output_text
    assert "Markdown 报告" in output_text
    assert str(report_path) in output_text
