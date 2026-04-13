import json
import logging

from fundamentals_agent.fundamentals import (
    StockTarget,
    build_fundamental_report,
    build_section_queries,
    detect_cn_stock_codes,
    extract_cn_stock_targets,
    generate_cn_stock_fundamental_report,
)
from fundamentals_agent.graph import graph
from tests.report_checks import (
    assert_generated_markdown_report,
    assert_report_contains_queries,
)

logger = logging.getLogger(__name__)


def _expected_queries(symbol: str) -> tuple[str, ...]:
    code, market = symbol.split(".")
    return tuple(
        query for _title, query in build_section_queries(StockTarget(code=code, market=market))
    )


def test_graph_compiles() -> None:
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_extract_cn_stock_targets_filters_non_stocks() -> None:
    targets = extract_cn_stock_targets("请分析 600519、000001、920047 和 159915")
    assert [target.symbol for target in targets] == [
        "600519.SH",
        "000001.SZ",
        "920047.BJ",
    ]


def test_detect_cn_stock_codes_tool() -> None:
    result = detect_cn_stock_codes.invoke({"text": "看看 600519 和 sz000001"})
    payload = json.loads(result)
    assert payload == {
        "contains_cn_stock_code": True,
        "codes": ["600519.SH", "000001.SZ"],
    }


def test_build_fundamental_report_writes_markdown(
    patch_fake_mx_data_client,
    fake_mx_data_client,
    report_output_dir,
) -> None:
    report_path, targets, markdown_text = build_fundamental_report(
        "请分析 600519 的基本面",
        output_dir=str(report_output_dir),
    )
    logger.debug("Generated report path in unit test: %s", report_path)
    expected_queries = _expected_queries("600519.SH")

    assert report_path.exists()
    assert [target.symbol for target in targets] == ["600519.SH"]
    assert fake_mx_data_client.query_log == list(expected_queries)
    validated_path, report_text = assert_generated_markdown_report(
        report_output_dir,
        expected_symbol="600519.SH",
        expected_name=fake_mx_data_client.company_name("600519.SH"),
        min_table_data_rows=4,
    )

    assert validated_path == report_path
    assert_report_contains_queries(report_text, expected_queries)
    assert fake_mx_data_client.company_name("600519.SH") in markdown_text
    assert "600519.SH 的主营业务测试样本" in report_text


def test_generate_cn_stock_fundamental_report_returns_completion_message(
    patch_fake_mx_data_client,
    fake_mx_data_client,
    report_output_dir,
) -> None:
    result = generate_cn_stock_fundamental_report.invoke(
        {
            "user_input": "请分析 600519 的基本面",
            "output_dir": str(report_output_dir),
        }
    )
    expected_queries = _expected_queries("600519.SH")

    report_path, report_text = assert_generated_markdown_report(
        report_output_dir,
        expected_symbol="600519.SH",
        expected_name=fake_mx_data_client.company_name("600519.SH"),
        min_table_data_rows=4,
    )

    assert fake_mx_data_client.query_log == list(expected_queries)
    assert_report_contains_queries(report_text, expected_queries)
    assert "600519.SH" in result
    assert "已调用东方财富妙想 mx-data skill 完成个股基本面查询。" in result
    assert str(report_path) in result
    assert "个股基本面信息收集完成。" in result


def test_graph_invokes_report_generation_with_fake_mx_client(
    patch_fake_mx_data_client,
    fake_mx_data_client,
    report_output_dir,
) -> None:
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    expected_queries = _expected_queries("600519.SH")
    report_path, report_text = assert_generated_markdown_report(
        report_output_dir,
        expected_symbol="600519.SH",
        expected_name=fake_mx_data_client.company_name("600519.SH"),
        min_table_data_rows=4,
    )

    assert fake_mx_data_client.query_log == list(expected_queries)
    assert_report_contains_queries(report_text, expected_queries)
    assert str(report_path) in output_text
    assert "个股基本面信息收集完成。" in output_text
