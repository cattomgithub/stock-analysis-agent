import json
import logging

from fundamentals_agent.fundamentals import (
    StockTarget,
    build_fundamental_report,
    build_section_queries,
    collect_reports_from_input,
    detect_cn_stock_codes,
    extract_cn_stock_name_candidates,
    extract_cn_stock_targets,
    generate_cn_stock_fundamental_report,
)
from fundamentals_agent.metrics import canonicalize_metric_label
from fundamentals_agent.report_formatting import build_fundamentals_formatting_prompt
from fundamentals_agent.graph import graph
from tests.report_checks import (
    assert_generated_markdown_report,
    assert_report_contains_queries,
)

logger = logging.getLogger(__name__)


def _expected_queries(symbol: str) -> tuple[str, ...]:
    code, market = symbol.split(".")
    return tuple(
        query
        for _title, queries in build_section_queries(StockTarget(code=code, market=market))
        for query in queries
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


def test_extract_cn_stock_name_candidates_from_request() -> None:
    candidates = extract_cn_stock_name_candidates("请分析贵州茅台、平安银行和 ETF 的基本面")
    assert candidates == ["贵州茅台", "平安银行"]


def test_detect_cn_stock_codes_tool() -> None:
    result = detect_cn_stock_codes.invoke({"text": "看看 600519 和 平安银行"})
    payload = json.loads(result)
    assert payload == {
        "contains_cn_stock_code": True,
        "contains_cn_stock_target": True,
        "codes": ["600519.SH"],
        "names": ["平安银行"],
    }


def test_build_fundamental_report_writes_markdown(
    patch_fake_mx_data_client,
    patch_fake_llm_summarizer,
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
    assert patch_fake_llm_summarizer.calls[0]["reports"] == [
        {"symbol": "600519.SH", "entity_label": fake_mx_data_client.company_name("600519.SH") + " (600519.SH)"}
    ]
    validated_path, report_text = assert_generated_markdown_report(
        report_output_dir,
        expected_symbol="600519.SH",
        expected_name=fake_mx_data_client.company_name("600519.SH"),
        min_table_data_rows=20,
    )

    assert validated_path == report_path
    assert_report_contains_queries(report_text, expected_queries)
    assert "## 外部 LLM 整理结果" in markdown_text
    assert "已基于东方财富 mx-data 汇总 600519.SH 的基本面数据。" in markdown_text
    assert "### 盈利指标" in report_text
    assert "### 估值指标" in report_text
    assert "### 现金流量指标" in report_text
    assert "### 财务风险指标" in report_text
    assert "### 公司概况" not in report_text
    assert "### 股东结构" not in report_text
    assert "营业现金流量" in report_text
    assert "自由现金流量" in report_text
    assert "经营活动现金流净额" not in report_text
    assert "净利润增长率" not in report_text
    assert "市销率" not in report_text
    assert "2024-09-30" not in report_text


def test_build_fundamental_report_accepts_stock_name_input(
    patch_fake_mx_data_client,
    patch_fake_llm_summarizer,
    fake_mx_data_client,
    report_output_dir,
) -> None:
    report_path, targets, report_text = build_fundamental_report(
        "请分析贵州茅台的基本面",
        output_dir=str(report_output_dir),
    )

    expected_queries = _expected_queries("600519.SH")
    assert report_path.exists()
    assert [target.symbol for target in targets] == ["600519.SH"]
    assert fake_mx_data_client.query_log[0] == "贵州茅台 公司简介 主营业务"
    assert fake_mx_data_client.query_log[1:] == list(expected_queries)
    assert "## 外部 LLM 整理结果" in report_text
    assert "已基于东方财富 mx-data 汇总 600519.SH 的基本面数据。" in report_text


def test_build_fundamentals_formatting_prompt_uses_metric_schema_only(
    patch_fake_mx_data_client,
) -> None:
    _targets, reports = collect_reports_from_input("请分析 600519 的基本面")
    prompt = build_fundamentals_formatting_prompt("请分析 600519 的基本面", reports)

    assert '"metric_schema": [' in prompt
    assert "盈利指标" in prompt
    assert "估值指标" in prompt
    assert "现金流量指标" in prompt
    assert "财务风险指标" in prompt
    assert "营业现金流量" in prompt
    assert "自由现金流量" in prompt
    assert "近五年 年报" in prompt
    assert "净利润+固定资产和投资性房地产折旧+使用权资产折旧+无形资产摊销+长期待摊费用摊销-投资活动现金流出" in prompt
    assert "公司概况" not in prompt
    assert "股东结构" not in prompt
    assert "净利润增长率" not in prompt
    assert "市销率" not in prompt


def test_build_section_queries_use_correct_metric_scope() -> None:
    expected_queries = dict(build_section_queries(StockTarget(code="600519", market="SH")))

    assert expected_queries == {
        "盈利指标": (
            "600519.SH 每股收益 近五年 年报",
            "600519.SH 净资产收益率 近五年 年报",
        ),
        "估值指标": (
            "600519.SH 市盈率 近五年 年报",
            "600519.SH 市净率 近五年 年报",
        ),
        "现金流量指标": (
            "600519.SH 经营活动产生的现金流量净额 近五年 年报",
            "600519.SH 净利润 近五年 年报",
            "600519.SH 固定资产和投资性房地产折旧 近五年 年报",
            "600519.SH 使用权资产折旧 近五年 年报",
            "600519.SH 无形资产摊销 近五年 年报",
            "600519.SH 长期待摊费用摊销 近五年 年报",
            "600519.SH 投资活动现金流出小计 近五年 年报",
        ),
        "财务风险指标": (
            "600519.SH 流动比率 近五年 年报",
            "600519.SH 资产负债率 近五年 年报",
        ),
    }
    for queries in expected_queries.values():
        assert queries
        for query in queries:
            assert "近五年 年报" in query


def test_canonicalize_metric_label_accepts_live_mx_field_aliases() -> None:
    assert canonicalize_metric_label("每股收益EPS(基本)") == "每股收益"
    assert canonicalize_metric_label("净资产收益率ROE(加权)") == "净资产收益率"
    assert canonicalize_metric_label("市盈率(TTM)") == "市盈率"


def test_collect_reports_compute_free_cash_flow_from_individual_queries(
    patch_fake_mx_data_client,
) -> None:
    _targets, reports = collect_reports_from_input("请分析 600519 的基本面")

    cashflow_section = next(section for section in reports[0].sections if section.title == "现金流量指标")
    rows = cashflow_section.tables[0]["rows"]

    assert rows[0]["date"] == "2024"
    assert rows[0]["营业现金流量"] == "139亿"
    assert rows[0]["自由现金流量"] == "73亿"


def test_generate_cn_stock_fundamental_report_returns_completion_message(
    patch_fake_mx_data_client,
    patch_fake_llm_summarizer,
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
        min_table_data_rows=20,
    )

    assert fake_mx_data_client.query_log == list(expected_queries)
    assert_report_contains_queries(report_text, expected_queries)
    assert "600519.SH" in result
    assert "已调用东方财富妙想 mx-data skill 完成个股基本面查询。" in result
    assert "已调用外部 LLM 完成结果整理。" in result
    assert str(report_path) in result
    assert "个股基本面信息收集完成。" in result


def test_graph_invokes_report_generation_with_fake_mx_client(
    patch_fake_mx_data_client,
    patch_fake_llm_summarizer,
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
        min_table_data_rows=20,
    )

    assert fake_mx_data_client.query_log == list(expected_queries)
    assert_report_contains_queries(report_text, expected_queries)
    assert str(report_path) in output_text
    assert "已调用外部 LLM 完成结果整理。" in output_text
    assert "个股基本面信息收集完成。" in output_text
